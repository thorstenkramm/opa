import os.path
import subprocess
from datetime import datetime
import re

from dir_info import get_dir_last_change, get_dir_info, get_dir_size


class MySQLInfo:
    def __init__(self, mysql_bin='mysql'):
        self.mysql_bin = mysql_bin
        self.data_dir = get_dir_info(self.get_data_dir())
        self.databases = self.get_databases()

    def get_data_dir(self) -> str:
        """
        Get the MySQL data directory path by querying the MySQL server.

        Returns:
            str: Path to the MySQL data directory
        """
        # Execute SQL query to get the data directory
        cmd = [self.mysql_bin, "-N", "-e", "SELECT @@datadir"]

        result = subprocess.run(cmd, check=True, capture_output=True, text=True)

        # Return the output to get the data directory path
        # Typically, the output will be a single line with the path
        return result.stdout.strip()

    def get_databases(self) -> list:
        """
        Get list of all databases.
        Executes "mysql -e "show databases" -N"
        :return: list
        """

        # Execute the MySQL command to show databases
        cmd = [self.mysql_bin, "-e", "show databases", "-N"]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)

        # Split the output by newlines and filter out empty strings
        databases = [db.strip() for db in result.stdout.split('\n') if db.strip()]
        # Filter out system databases
        system_dbs = ['information_schema', 'sys', 'performance_schema']
        databases = [db for db in databases if db not in system_dbs]

        return databases

    def get_database_last_change(self, database) -> datetime:
        database_dir = os.path.join(self.data_dir.path, database)
        return get_dir_last_change(database_dir)

    def get_mysql_version(self) -> str:
        """
        Get the MySQL server version.

        Returns:
            str: MySQL version in format "major.minor" (e.g., "8.0", "5.7")
        """
        # Execute SQL query to get the MySQL version
        cmd = [self.mysql_bin, "-N", "-e", "SELECT VERSION()"]

        result = subprocess.run(cmd, check=True, capture_output=True, text=True)

        # Parse the version string (e.g., "8.0.35-0ubuntu0.22.04.1" -> "8.0")
        version_string = result.stdout.strip()

        # Extract major.minor version using regex
        match = re.match(r'^(\d+\.\d+)', version_string)
        if match:
            return match.group(1)
        else:
            raise ValueError(f"Unable to parse MySQL version from: {version_string}")

    def get_databases_size(self) -> int:
        """
        Get the sum of disk space consumed by all databases.

        Returns:
            int: Total size in bytes of all non-system databases
        """
        total_size = 0

        for database in self.databases:
            database_dir = os.path.join(self.data_dir.path, database)
            try:
                # Get size of this database directory
                db_size = get_dir_size(database_dir)
                total_size += db_size
            except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
                # Skip databases that can't be accessed (might not have directories)
                continue

        return total_size
