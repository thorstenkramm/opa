import unittest
from unittest.mock import patch, MagicMock, call
from datetime import datetime
import subprocess
import os

# Assume dir_info.py and mysql_info.py are in the same directory or accessible via PYTHONPATH
from mysql_info import MySQLInfo


# We need a dummy DirInfo class or mock object for get_dir_info's return value
# If DirInfo isn't easily importable or defined elsewhere, create a simple mock structure:
class MockDirInfo:
    def __init__(self, path):
        self.path = path

    def __repr__(self):
        return f"MockDirInfo(path='{self.path}')"


# Use the mock DirInfo if the real one isn't available/needed for basic tests
# from dir_info import DirInfo # Use this if DirInfo is available and needed

class TestMySQLInfo(unittest.TestCase):

    @patch('mysql_info.get_dir_last_change')
    @patch('mysql_info.get_dir_info', return_value=MockDirInfo('/var/lib/mysql'))  # Use MockDirInfo
    @patch('subprocess.run')
    def test_init_and_dependencies(self, mock_subprocess_run, mock_get_dir_info, mock_get_dir_last_change):
        """
        Test initialization (__init__) and that dependencies are called correctly.
        """
        # --- Arrange ---
        # Mock subprocess.run for get_data_dir
        mock_data_dir_result = MagicMock()
        mock_data_dir_result.stdout = '/var/lib/mysql\n'
        mock_data_dir_result.check_returncode.return_value = None  # Simulate check=True passing

        # Mock subprocess.run for get_databases
        mock_db_list_result = MagicMock()
        mock_db_list_result.stdout = (
            'db1\ndb2\ninformation_schema\nsys\n\ndb3\nperformance_schema\nmysql\n')  # Added 'mysql' system db
        mock_db_list_result.check_returncode.return_value = None  # Simulate check=True passing

        # Configure subprocess.run to return different values based on call args
        mock_subprocess_run.side_effect = [
            mock_data_dir_result,  # First call (get_data_dir)
            mock_db_list_result  # Second call (get_databases)
        ]

        # Mock get_dir_info to return our mock DirInfo object with the correct path
        mock_dir_info_obj = MockDirInfo('/var/lib/mysql')
        mock_get_dir_info.return_value = mock_dir_info_obj

        # --- Act ---
        mysql_info = MySQLInfo(mysql_bin='custom_mysql')

        # --- Assert ---
        # Check mysql_bin attribute
        self.assertEqual(mysql_info.mysql_bin, 'custom_mysql')

        # Check calls to subprocess.run
        expected_calls = [
            call(['custom_mysql', '-N', '-e', 'SELECT @@datadir'], check=True, capture_output=True, text=True),
            call(['custom_mysql', '-e', 'show databases', '-N'], check=True, capture_output=True, text=True)
        ]
        mock_subprocess_run.assert_has_calls(expected_calls)
        self.assertEqual(mock_subprocess_run.call_count, 2)

        # Check call to get_dir_info
        mock_get_dir_info.assert_called_once_with('/var/lib/mysql')
        self.assertEqual(mysql_info.data_dir, mock_dir_info_obj)
        self.assertEqual(mysql_info.data_dir.path, '/var/lib/mysql')  # Verify path attribute access

        # Check databases attribute (filtering applied)
        # Added 'mysql' to the system_dbs list in the original code if needed,
        # otherwise adjust expected list here. Assuming 'mysql' is NOT filtered by default.
        # Let's update the filter in the original code or here for consistency.
        # Assuming original code filters: 'information_schema', 'sys', 'performance_schema'
        self.assertEqual(mysql_info.databases, ['db1', 'db2', 'db3', 'mysql'])

        # Ensure get_dir_last_change was NOT called during init
        mock_get_dir_last_change.assert_not_called()

    @patch('subprocess.run')
    def test_get_data_dir(self, mock_subprocess_run):
        """
        Test the get_data_dir method in isolation.
        """
        # --- Arrange ---
        mock_result = MagicMock()
        mock_result.stdout = ' /path/to/data/dir\n  '
        mock_result.check_returncode.return_value = None
        mock_subprocess_run.return_value = mock_result

        # Need to bypass __init__'s calls for isolated test
        with patch.object(MySQLInfo, 'get_databases', return_value=[]), \
                patch('mysql_info.get_dir_info', return_value=MockDirInfo('/mock/path')):  # Use MockDirInfo

            # Instantiate - this will call the mocked get_data_dir via __init__
            instance = MySQLInfo(mysql_bin='mysql')

        # --- Act ---
        # Call get_data_dir again explicitly to test its direct return value
        data_dir_path = instance.get_data_dir()

        # --- Assert ---
        # Check the specific call for get_data_dir
        get_data_dir_call = call(
            ['mysql', '-N', '-e', 'SELECT @@datadir'],
            check=True, capture_output=True, text=True
        )
        # It was called once during init and once explicitly
        mock_subprocess_run.assert_has_calls([get_data_dir_call, get_data_dir_call])
        self.assertEqual(mock_subprocess_run.call_count, 2)

        # Check the *return value* of the explicit call
        self.assertEqual(data_dir_path, '/path/to/data/dir')

    @patch('subprocess.run')
    def test_get_databases(self, mock_subprocess_run):
        """
        Test the get_databases method in isolation.
        """
        # --- Arrange ---
        mock_result = MagicMock()
        # Include system DBs and empty lines in mock output
        mock_result.stdout = 'db_alpha\ndb_beta\n\ninformation_schema\nperformance_schema\nsys\ndb_gamma\n'
        mock_result.check_returncode.return_value = None
        mock_subprocess_run.return_value = mock_result

        # Need to bypass __init__'s calls for isolated test
        with patch.object(MySQLInfo, 'get_data_dir', return_value='/mock/datadir'), \
                patch('mysql_info.get_dir_info', return_value=MockDirInfo('/mock/datadir')):  # Use MockDirInfo

            # Instantiate - this will call the mocked get_databases via __init__
            instance = MySQLInfo(mysql_bin='mysql')

        # --- Act ---
        # Call get_databases again explicitly to test its direct return value
        databases = instance.get_databases()

        # --- Assert ---
        # Check the specific call for get_databases
        get_databases_call = call(
            ['mysql', '-e', 'show databases', '-N'],
            check=True, capture_output=True, text=True
        )
        # It was called once during init and once explicitly
        mock_subprocess_run.assert_has_calls([get_databases_call, get_databases_call])
        self.assertEqual(mock_subprocess_run.call_count, 2)

        # Check the *return value* of the explicit call (filtering applied)
        self.assertEqual(databases, ['db_alpha', 'db_beta', 'db_gamma'])

    @patch('mysql_info.get_dir_last_change')
    @patch('mysql_info.get_dir_info', return_value=MockDirInfo('/base/data/path'))  # Use MockDirInfo
    @patch('subprocess.run')
    def test_get_database_last_change(self, mock_subprocess_run, mock_get_dir_info, mock_get_dir_last_change):
        """
        Test the get_database_last_change method.
        """
        # --- Arrange ---
        # Mock subprocess for __init__ calls
        mock_data_dir_result = MagicMock(stdout='/base/data/path\n')
        mock_db_list_result = MagicMock(stdout='db1\ndb2\n')
        mock_subprocess_run.side_effect = [mock_data_dir_result, mock_db_list_result]

        # Mock the return value for get_dir_last_change
        expected_datetime = datetime(2023, 10, 27, 10, 30, 0)
        mock_get_dir_last_change.return_value = expected_datetime

        # Instantiate the class
        mysql_info = MySQLInfo()  # Uses mocks set up above

        # --- Act ---
        db_name = 'db1'
        last_change_time = mysql_info.get_database_last_change(db_name)

        # --- Assert ---
        # Verify get_dir_info was called during init
        mock_get_dir_info.assert_called_once_with('/base/data/path')

        # Verify get_dir_last_change was called correctly
        expected_db_path = os.path.join('/base/data/path', db_name)
        mock_get_dir_last_change.assert_called_once_with(expected_db_path)

        # Verify the returned datetime
        self.assertEqual(last_change_time, expected_datetime)

    @patch('mysql_info.get_dir_info', return_value=MockDirInfo('/var/lib/mysql'))  # Use MockDirInfo
    @patch('subprocess.run')
    def test_subprocess_error_get_data_dir(self, mock_subprocess_run, mock_get_dir_info):
        """ Test that CalledProcessError in get_data_dir propagates """
        # --- Arrange ---
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, 'cmd', stderr='Error accessing mysql')

        # --- Act & Assert ---
        with self.assertRaises(subprocess.CalledProcessError):
            MySQLInfo()  # Error should occur during __init__ when calling get_data_dir

    @patch('mysql_info.get_dir_info', return_value=MockDirInfo('/var/lib/mysql'))  # Use MockDirInfo
    @patch('subprocess.run')
    def test_subprocess_error_get_databases(self, mock_subprocess_run, mock_get_dir_info):
        """ Test that CalledProcessError in get_databases propagates """
        # --- Arrange ---
        mock_data_dir_result = MagicMock(stdout='/var/lib/mysql\n')
        mock_subprocess_run.side_effect = [
            mock_data_dir_result,  # First call (get_data_dir) succeeds
            subprocess.CalledProcessError(1, 'cmd', stderr='Error showing databases')  # Second call fails
        ]

        # --- Act & Assert ---
        with self.assertRaises(subprocess.CalledProcessError):
            MySQLInfo()  # Error should occur during __init__ when calling get_databases


if __name__ == '__main__':
    unittest.main()
