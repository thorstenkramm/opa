import os
import subprocess
import shutil
from dataclasses import dataclass

from config import Config
from mysql_info import MySQLInfo
from store_manager import StoreManager
from logger import OpaLogger
from utils import format_bytes, calc_parallelism


class NotEnoughDiskSpaceError(Exception):
    """Exception raised when backup wouldn't fit in disk space"

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


@dataclass
class BackupResult:
    successful: int = 0
    failed: int = 0
    total: int = 1
    all_skipped_successfully: bool = False
    all_skipped_faulty: bool = False


class XtraBackup:
    def __init__(self, config: Config, store_manager: StoreManager, logger: OpaLogger):
        self.logger = logger
        self.config = config
        self.store_manager = store_manager
        self.mysql_info = MySQLInfo(mysql_bin=config.mysql_bin)

    def execute(self) -> BackupResult:
        """
        Execute the XtraBackup command according to the configured strategy
        :return: BackupResult
        """
        self.logger.debug(f"MySQL data directory: {self.mysql_info.data_dir}")
        self.logger.info(f"Starting XtraBackup with strategy: streamcompress={self.config.streamcompress}, "
                         f"prepare={self.config.prepare}, tgz={self.config.tgz}")

        # Exit if we don't have enough free space
        if not self._check_free_space():
            return BackupResult(failed=1)

        # Determine backup strategy and execute
        try:
            if self.config.streamcompress:
                success = self._execute_streamcompress()
            else:
                success = self._execute_regular()
                if success and self.config.prepare:
                    success = self._execute_prepare()
                if success and self.config.tgz:
                    success = self._compress_to_tgz()

            if success:
                self.logger.info("XtraBackup completed successfully")
                self.store_manager.store_backup_info(self.mysql_info.data_dir.bytes_used)
                self.store_manager.link_to_last_dir()
                return BackupResult(successful=1, total=1)
            else:
                self.logger.error("XtraBackup failed")
                return BackupResult(failed=1, total=1)

        except Exception as e:
            self.logger.error(f"XtraBackup failed with error: {e}")
            return BackupResult(failed=1, total=1)

    def _check_free_space(self) -> bool:
        """Check if there's enough free space for the backup"""
        # For XtraBackup, we need more space than mysqldump due to the nature of physical backups
        # Regular backup needs approximately the same space as the data directory
        # Streamcompress reduces this significantly
        if self.config.streamcompress:
            required_free_bytes = self.mysql_info.data_dir.bytes_used * 0.3  # Estimate 30% for compressed
        else:
            required_free_bytes = self.mysql_info.data_dir.bytes_used * 1.2  # Add 20% buffer for regular
            if self.config.tgz:
                # Need additional space for compression
                required_free_bytes = self.mysql_info.data_dir.bytes_used * 1.5

        self.logger.info(
            f"Backup will require approximately {format_bytes(required_free_bytes)} bytes. "
            f"Having {format_bytes(self.store_manager.current_dir.bytes_free)} free."
        )

        if required_free_bytes > self.store_manager.current_dir.bytes_free:
            raise NotEnoughDiskSpaceError("Not enough free space in target directory.")
        return True

    def _execute_regular(self) -> bool:
        """Execute regular XtraBackup (uncompressed copy)"""
        backup_dir = os.path.join(self.store_manager.current_dir.path, "backup")

        # Build XtraBackup command
        cmd = [
            self.config.xtrabackup_bin,
            "--backup",
            f"--target-dir={backup_dir}",
            f"--parallel={calc_parallelism(self.config.parallelism)}"
        ]

        # Add any additional XtraBackup options
        cmd.extend(self.config.xtrabackup_options)

        self.logger.info(f"Executing XtraBackup command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode != 0:
                self.logger.error(f"XtraBackup failed with return code {result.returncode}")
                self.logger.error(f"Error output: {result.stderr}")
                return False

            # Check for completion message in output
            if "completed OK!" in result.stdout or "completed OK!" in result.stderr:
                self.logger.info("XtraBackup regular backup completed successfully")
                return True
            else:
                self.logger.error("XtraBackup did not complete successfully")
                return False

        except Exception as e:
            self.logger.error(f"Error executing XtraBackup: {e}")
            return False

    def _execute_prepare(self) -> bool:
        """Execute the prepare step on the backup"""
        backup_dir = os.path.join(self.store_manager.current_dir.path, "backup")

        if not os.path.exists(backup_dir):
            self.logger.error(f"Backup directory does not exist: {backup_dir}")
            return False

        # Build prepare command
        cmd = [
            self.config.xtrabackup_bin,
            "--prepare",
            f"--target-dir={backup_dir}"
        ]

        self.logger.info(f"Executing XtraBackup prepare command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode != 0:
                self.logger.error(f"XtraBackup prepare failed with return code {result.returncode}")
                self.logger.error(f"Error output: {result.stderr}")
                return False

            if "completed OK!" in result.stdout or "completed OK!" in result.stderr:
                self.logger.info("XtraBackup prepare completed successfully")
                return True
            else:
                self.logger.error("XtraBackup prepare did not complete successfully")
                return False

        except Exception as e:
            self.logger.error(f"Error executing XtraBackup prepare: {e}")
            return False

    def _execute_streamcompress(self) -> bool:
        """Execute XtraBackup with stream compression"""
        output_file = os.path.join(self.store_manager.current_dir.path, "backup.xbstream")

        # Build XtraBackup command with streaming and compression
        cmd = [
            self.config.xtrabackup_bin,
            "--backup",
            "--stream=xbstream",
            "--compress",
            f"--compress-threads={calc_parallelism(self.config.parallelism)}",
            f"--parallel={calc_parallelism(self.config.parallelism)}"
        ]

        # Add any additional XtraBackup options
        cmd.extend(self.config.xtrabackup_options)

        self.logger.info(f"Executing XtraBackup streamcompress to {output_file}")
        self.logger.debug(f"Command: {' '.join(cmd)}")

        try:
            with open(output_file, 'wb') as outfile:
                result = subprocess.run(
                    cmd,
                    stdout=outfile,
                    stderr=subprocess.PIPE,
                    text=False,
                    check=False
                )

            if result.returncode != 0:
                self.logger.error(f"XtraBackup streamcompress failed with return code {result.returncode}")
                stderr_text = result.stderr.decode('utf-8', errors='replace') if result.stderr else ""
                self.logger.error(f"Error output: {stderr_text}")
                return False

            # Check if output file was created and has content
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                self.logger.info(f"XtraBackup streamcompress completed successfully: {output_file}")
                return True
            else:
                self.logger.error("XtraBackup streamcompress failed - output file is empty or missing")
                return False

        except Exception as e:
            self.logger.error(f"Error executing XtraBackup streamcompress: {e}")
            return False

    def _compress_to_tgz(self) -> bool:
        """Compress the backup directory to a tar.gz file"""
        backup_dir = os.path.join(self.store_manager.current_dir.path, "backup")
        output_file = os.path.join(self.store_manager.current_dir.path, "backup.tar.gz")

        if not os.path.exists(backup_dir):
            self.logger.error(f"Backup directory does not exist: {backup_dir}")
            return False

        # Check if pigz is available for parallel compression
        pigz_available = shutil.which("pigz") is not None

        if pigz_available:
            # Use pigz for parallel compression
            threads = calc_parallelism(self.config.parallelism)
            cmd = f"tar -cf - -C {self.store_manager.current_dir.path} backup | pigz -p {threads} > {output_file}"
            self.logger.info(f"Compressing backup with pigz using {threads} threads")
        else:
            # Fall back to regular gzip
            cmd = f"tar -czf {output_file} -C {self.store_manager.current_dir.path} backup"
            self.logger.info("Compressing backup with gzip (pigz not available)")

        self.logger.debug(f"Compression command: {cmd}")

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode != 0:
                self.logger.error(f"Compression failed with return code {result.returncode}")
                self.logger.error(f"Error output: {result.stderr}")
                return False

            # Verify the compressed file exists and has content
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                # Remove the uncompressed backup directory to save space
                shutil.rmtree(backup_dir)
                self.logger.info(f"Backup compressed successfully to {output_file}")
                return True
            else:
                self.logger.error("Compression failed - output file is empty or missing")
                return False

        except Exception as e:
            self.logger.error(f"Error compressing backup: {e}")
            return False
