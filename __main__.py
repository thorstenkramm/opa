#!/usr/bin/env python3
import argparse
import os
import sys

from xtrabackup import XtraBackup, BackupResult, NotEnoughDiskSpaceError
from config import get_config
from logger import new_logger
from store_manager import StoreManager
from zabbix_sender import ZabbixSender
from version import get_version
from conditions_manager import ConditionsManager
from mysql_info import MySQLInfo
from xtrabackup_info import get_xtrabackup_version, validate_xtrabackup_version, get_distro_info


def parse_arguments():
    """
    Parse command line arguments
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Optimized Percona-Xtrabackup Archiver - A smart wrapper around xtrabackup')
    parser.add_argument('-c', '--config',
                        default='/etc/opa/opa.conf',
                        help='Path to the configuration file (default: /etc/opa/opa.conf)')
    parser.add_argument('-d', '--debug',
                        action='store_true',
                        help='Set log level to debug and override log level from config file')
    parser.add_argument('-v', '--version',
                        action='store_true',
                        help='Print version information and exit')
    parser.add_argument('--validate',
                        action='store_true',
                        help='Validate configuration and xtrabackup version without running backup')
    parser.add_argument('--create-installer',
                        metavar='PATH',
                        help='Create XtraBackup installer script at specified path (requires --validate)')

    return parser.parse_args()


def create_installer_script(filepath, download_url, version):
    """
    Create a shell script to install XtraBackup.
    Args:
        filepath: Path where to create the installer script
        download_url: URL to download XtraBackup from
        version: Required XtraBackup version

    Returns:
        bool: True if script was created successfully
    """
    installer_template = '''#!/bin/sh
# This installer has been automatically created by opa.
# Your system is missing the percona xtrabackup utility version {version}.
# Use the below instructions or execute with /bin/sh
TMP_FILE="/tmp/percona-xtrabackup.deb"
test -e "$TMP_FILE" && rm -f "$TMP_FILE"
curl --fail -ls -o "$TMP_FILE" {download_url}
if [ $? -ne 0 ]; then
    echo "Failed to download XtraBackup from {download_url}"
    exit 1
fi
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$TMP_FILE"
if [ $? -ne 0 ]; then
    echo "Failed to install XtraBackup package"
    rm -f "$TMP_FILE"
    exit 1
fi
rm -f "$TMP_FILE"
echo "XtraBackup {version} installed successfully"
'''

    try:
        script_content = installer_template.format(
            version=version,
            download_url=download_url
        )

        with open(filepath, 'w') as f:
            f.write(script_content)

        # Make the script executable
        import os
        os.chmod(filepath, 0o755)

        return True
    except Exception as e:
        print(f"ERROR: Failed to create installer script: {e}")
        return False


def validate_setup(config):
    """
    Validate the OPA setup including MySQL and XtraBackup versions.

    Args:
        config: Configuration object

    Returns:
        tuple: (is_valid, messages, validation_data) where:
            - is_valid is boolean
            - messages is list of strings
            - validation_data is dict with validation details
    """
    messages = []
    is_valid = True
    has_warnings = False
    validation_data = {
        'xtrabackup_missing': False,
        'download_url': None,
        'required_version': None,
        'mysql_version': None
    }

    # Print configuration info
    messages.append("Configuration file: Valid")
    messages.append(f"Backup directory: {config.backup_dir}")

    # Get distro info
    distro_name, distro_version = get_distro_info()
    messages.append(f"Linux distribution: {distro_name} {distro_version}")

    # Check MySQL connection and version
    try:
        mysql_info = MySQLInfo(mysql_bin=config.mysql_bin)
        mysql_version = mysql_info.get_mysql_version()
        validation_data['mysql_version'] = mysql_version
        messages.append(f"MySQL version: {mysql_version}")
    except Exception as e:
        messages.append(f"ERROR: Unable to connect to MySQL: {e}")
        return False, messages, validation_data

    # Check XtraBackup version
    xtrabackup_version = get_xtrabackup_version(config.xtrabackup_bin)
    if xtrabackup_version:
        messages.append(f"XtraBackup version: {xtrabackup_version}")
    else:
        validation_data['xtrabackup_missing'] = True

    # Validate version compatibility (this also handles not found case)
    version_valid, version_message, download_url = validate_xtrabackup_version(
        mysql_version, config.xtrabackup_bin
    )

    # Store validation data for installer generation
    if download_url:
        validation_data['download_url'] = download_url
    if not version_valid and xtrabackup_version is None:
        # XtraBackup is missing, get required version
        from xtrabackup_info import get_required_xtrabackup_version
        validation_data['required_version'] = get_required_xtrabackup_version(mysql_version)

    if not version_valid:
        if config.check_xtrabackup_version:
            messages.append(f"ERROR: {version_message}")
            is_valid = False
        else:
            messages.append(f"WARNING: {version_message}")
            has_warnings = True
    else:
        messages.append(f"Version compatibility: {version_message}")

    # Return appropriate exit status with validation data
    if not is_valid:
        return False, messages, validation_data
    elif has_warnings:
        return True, messages, validation_data  # Warnings don't fail validation
    else:
        return True, messages, validation_data


def main():
    # Parse command line options
    args = parse_arguments()

    # Print version and exit
    if args.version:
        print(get_version())
        sys.exit(0)

    # Check if --create-installer is used without --validate
    if args.create_installer and not args.validate:
        sys.stderr.write("ERROR: --create-installer requires --validate\n")
        sys.exit(1)

    # Read configuration file
    try:
        config = get_config(args.config)
    except ValueError as e:
        sys.stderr.write("Invalid configuration: %s\n" % e)
        sys.exit(1)

    # Handle validation mode
    if args.validate:
        is_valid, messages, validation_data = validate_setup(config)
        for message in messages:
            print(message)

        # Handle installer creation if requested
        if args.create_installer:
            if validation_data['xtrabackup_missing'] and validation_data['download_url']:
                print()
                print(f"Creating installer script at: {args.create_installer}")
                if create_installer_script(
                        args.create_installer,
                        validation_data['download_url'],
                        validation_data['required_version'] or "unknown"
                ):
                    print(f"Installer script created successfully: {args.create_installer}")
                    print("Execute it with: sh " + args.create_installer)
                else:
                    print("Failed to create installer script")
                    sys.exit(1)
            elif not validation_data['xtrabackup_missing']:
                print()
                print("XtraBackup is already installed - no installer needed")
            else:
                print()
                print("Cannot create installer: No download URL available for your system")
                sys.exit(1)

        sys.exit(0 if is_valid else 1)

    # Initialize logger with appropriate log level
    log_level = "debug" if args.debug else config.log_level

    # Initialize the store manage that handles all backup directories
    store_manager = StoreManager(config.backup_dir)

    # Initialize the logger
    log_file = os.path.join(store_manager.current_dir.path, "opa.log")
    logger = new_logger(log_file, log_level)
    logger.debug(f"Using configuration file: {args.config}")
    if args.debug:
        logger.debug("Debug mode enabled via command line argument")

    # Check MySQL and XtraBackup versions
    try:
        mysql_info = MySQLInfo(mysql_bin=config.mysql_bin)
        mysql_version = mysql_info.get_mysql_version()
        xtrabackup_version = get_xtrabackup_version(config.xtrabackup_bin)

        # Log versions in debug mode
        if args.debug:
            logger.debug(f"MySQL version: {mysql_version}")
            logger.debug(f"XtraBackup version: {xtrabackup_version}")

        # Validate version compatibility if enabled
        if config.check_xtrabackup_version:
            version_valid, version_message, download_url = validate_xtrabackup_version(
                mysql_version, config.xtrabackup_bin
            )

            if not version_valid:
                logger.error(version_message)
                sys.exit(1)
            else:
                logger.debug(f"Version check passed: {version_message}")
        else:
            # Still check versions but only warn if mismatch
            if xtrabackup_version:
                version_valid, version_message, download_url = validate_xtrabackup_version(
                    mysql_version, config.xtrabackup_bin
                )
                if not version_valid:
                    logger.warning(version_message)
    except Exception as e:
        logger.error(f"Error checking versions: {e}")
        sys.exit(1)

    # Initialize a backup result
    backup_result = BackupResult()

    # Initialize zabbix sender
    zabbix_sender = ZabbixSender(config.zbx, logger)

    # Initialize conditions manager
    conditions_manager = ConditionsManager(config.conditions, logger)

    # Check skip conditions
    if conditions_manager.check_skip_conditions():
        logger.info("Backup skipped due to skip conditions (but considered successful)")
        backup_result.all_skipped_successfully = True
        zabbix_sender.send_log_file(backup_result)
        store_manager.remove_skipped()
        sys.exit(0)

    # Check run conditions
    if not conditions_manager.check_run_conditions():
        logger.error("Backup aborted due to failed run conditions")
        backup_result.all_skipped_faulty = True
        zabbix_sender.send_log_file(backup_result)
        store_manager.remove_skipped()
        sys.exit(1)

    # Clean up before doing the backup, if desired
    store_manager.cleanup_before(config.versions) if config.delete_before else None
    # Do the backup
    try:
        xtrabackup = XtraBackup(config, store_manager, logger)
        backup_result = xtrabackup.execute()
    except NotEnoughDiskSpaceError as e:
        logger.error(e)
        backup_result.all_skipped_faulty = True
        zabbix_sender.send_log_file(backup_result)
        store_manager.remove_skipped()
        sys.exit(1)
    except Exception as e:
        logger.error(e)

    # Clean up after doing the backup, if desired
    if not config.delete_before:
        removed = store_manager.cleanup_after(config.versions)
        logger.info(f"Removed old backup directories: {removed}")

    # Execute terminate conditions
    if not conditions_manager.execute_terminate_conditions(store_manager.current_dir.path):
        logger.error("One or more terminate conditions failed")
        # Note: We don't exit with error here as the backup itself was successful

    # Send log to zabbix, if desired
    zabbix_sender.send_log_file(backup_result)


if __name__ == "__main__":
    main()
