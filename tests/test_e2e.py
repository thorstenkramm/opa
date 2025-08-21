import time
import unittest
import subprocess
import os


class TestEndToEnd(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        # Build the app
        subprocess.run(".github/scripts/build.sh")
        self.databases = ['demo1', 'demo2']
        self.backup_dir = "/tmp/opa"
        self.installer_file = "/tmp/xtrabackup-installer.txt"
        # Prepare the backup dir
        subprocess.run(f"rm -rf {self.backup_dir} || true", shell=True)
        os.mkdir(self.backup_dir)
        # Prepare the databases
        for database in self.databases:
            print(f"Creating database {database} ...")
            subprocess.run(
                f"mysql -e 'DROP DATABASE IF EXISTS {database}; CREATE DATABASE {database}'",
                shell=True,
                check=True
            )
            print(f"Filling database {database} with demo data ...")
            subprocess.run(f"mysql {database}< ./test_data/world.sql", shell=True, check=True)
        # Wait for all mysql background write processes to be completed
        time.sleep(4)
        # Remove Xtrabackup to test installation via OPA
        get_pkg = subprocess.run(
            "sudo dpkg -l|grep xtrabackup|awk '{print $2}'",
            shell=True,
            check=True,
            capture_output=True
        )
        pkg = get_pkg.stdout.decode("utf-8").strip().replace("\n", "")
        if pkg != "":
            subprocess.run(f"sudo apt purge -y {pkg}", shell=True, check=True)
        if os.path.exists(self.installer_file):
            os.remove(self.installer_file)

    @classmethod
    def tearDownClass(self):
        # Remove the created database
        for database in self.databases:
            subprocess.run(f"mysql -e 'DROP DATABASE {database}'", shell=True, check=True)

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_00_validation(self):
        response = subprocess.run(
            f"./opa -c ./test_data/regular.conf --validate --create-installer {self.installer_file}",
            shell=True,
            check=False,
            capture_output=True
        )
        self.assertEqual(response.returncode, 1)
        self.assertIn("ERROR: XtraBackup not found", response.stdout.decode("utf-8"), 'Error not found')
        self.assertTrue(os.path.exists(self.installer_file))
        subprocess.run(f"sh {self.installer_file}", shell=True, check=True)

    def test_01_regular(self):
        self.__run_backup('regular')

        log_content = self.__read_log()

        # Assert no errors found in the log
        self.assertNotIn("Error", log_content, "Errors found in the log file")
        self.assertIn(
            "Starting XtraBackup with strategy: streamcompress=False, prepare=False, tgz=False",
            log_content,
            "Backup strategy not found in the log file"
        )
        subfolders = count_subfolders(os.path.join(self.backup_dir, 'last/backup'))
        self.assertGreaterEqual(subfolders, 4, "Subfolders not found in the backup")

    def test_02_prepare(self):
        self.__run_backup('prepare')
        log_content = self.__read_log()

        # Assert no errors found in the log
        self.assertNotIn("Error", log_content, "Errors found in the log file")
        self.assertIn(
            "Starting XtraBackup with strategy: streamcompress=False, prepare=True, tgz=False",
            log_content,
            "Backup strategy not found in the log file"
        )
        subfolders = count_subfolders(os.path.join(self.backup_dir, 'last/backup'))

        self.assertGreaterEqual(subfolders, 4, "Subfolders not found in the backup")

    def test_03_streamcompress(self):
        self.__run_backup('streamcompress')
        log_content = self.__read_log()
        # Assert no errors found in the log
        self.assertNotIn("Error", log_content, "Errors found in the log file")
        self.assertIn(
            "Starting XtraBackup with strategy: streamcompress=True, prepare=False, tgz=False",
            log_content,
            "Backup strategy not found in the log file"
        )
        subfolders = count_subfolders(os.path.join(self.backup_dir, 'last'))

        self.assertEqual(subfolders, 0, "Subfolders not found in the backup")

    def test_04_restore(self):
        # Restore from backup
        subprocess.run("sudo ./test_data/restore_from_streamcompress.sh", shell=True, check=True)

    def __run_backup(self, config: str, expected_exit_code: int = 0):
        response = subprocess.run(
            f"./opa -c test_data/{config}.conf",
            shell=True,
            check=False,
            capture_output=True
        )
        self.assertEqual(response.returncode, expected_exit_code)
        print(response.stdout.decode())
        print(response.stderr.decode())
        self.__read_zabbix_sender_log()

    def __read_log(self) -> str:
        # Open and read the log file
        log_file = '/tmp/opa/last.log'
        print("Reading log file: " + log_file)
        with open(log_file, "r") as f:
            log_content = f.read()

        print("=" * 120)
        print(log_content)
        print("=" * 120)

        return log_content

    def __read_zabbix_sender_log(self):
        log_file = '/tmp/zabbix_sender.log'
        with open(log_file, "r") as f:
            log_content = f.read()
        self.assertIn("Summary", log_content, f"Summary not found in {log_file}")


def count_subfolders(directory_path):
    """
    Count the number of real subfolders in the specified directory,
    excluding symbolic links to folders.

    Args:
        directory_path (str): Path to the directory

    Returns:
        int: Number of real subfolders (excluding symlinks)
    """
    # Check if the directory exists
    if not os.path.isdir(directory_path):
        raise ValueError(f"The path {directory_path} is not a valid directory")

    # Get all items in the directory
    items = os.listdir(directory_path)

    # Count only real directories (not symbolic links)
    real_subfolders = 0
    for item in items:
        full_path = os.path.join(directory_path, item)
        # Check if it's a directory AND not a symbolic link
        if os.path.isdir(full_path) and not os.path.islink(full_path):
            real_subfolders += 1

    print(f"subfolders in {directory_path}: {real_subfolders}")
    return real_subfolders


if __name__ == "__main__":
    unittest.main()
