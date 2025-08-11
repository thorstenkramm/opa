import unittest
from unittest.mock import patch, MagicMock, mock_open
import subprocess

from xtrabackup_info import (
    get_xtrabackup_version,
    get_distro_info,
    load_version_map,
    get_xtrabackup_download_url,
    get_required_xtrabackup_version,
    validate_xtrabackup_version
)


class TestXtraBackupInfo(unittest.TestCase):

    @patch('subprocess.run')
    def test_get_xtrabackup_version_2_4(self, mock_subprocess_run):
        """Test getting XtraBackup 2.4 version."""
        mock_result = MagicMock()
        mock_result.stdout = "xtrabackup version 2.4.29 based on MySQL server 5.7.40 Linux (x86_64)"
        mock_result.stderr = ""
        mock_subprocess_run.return_value = mock_result

        version = get_xtrabackup_version()

        self.assertEqual(version, "2.4")
        mock_subprocess_run.assert_called_once_with(
            ['xtrabackup', '--version'],
            check=True,
            capture_output=True,
            text=True
        )

    @patch('subprocess.run')
    def test_get_xtrabackup_version_8_0(self, mock_subprocess_run):
        """Test getting XtraBackup 8.0 version."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = "xtrabackup version 8.0.35-33 based on MySQL server 8.0.35 Linux (x86_64)"
        mock_subprocess_run.return_value = mock_result

        version = get_xtrabackup_version('/usr/bin/xtrabackup')

        self.assertEqual(version, "8.0")
        mock_subprocess_run.assert_called_once_with(
            ['/usr/bin/xtrabackup', '--version'],
            check=True,
            capture_output=True,
            text=True
        )

    @patch('subprocess.run')
    def test_get_xtrabackup_version_8_4(self, mock_subprocess_run):
        """Test getting XtraBackup 8.4 version."""
        mock_result = MagicMock()
        mock_result.stdout = "xtrabackup version 8.4.0-3 based on MySQL server 8.4.0"
        mock_result.stderr = ""
        mock_subprocess_run.return_value = mock_result

        version = get_xtrabackup_version()

        self.assertEqual(version, "8.4")

    @patch('subprocess.run')
    def test_get_xtrabackup_version_not_found(self, mock_subprocess_run):
        """Test when xtrabackup is not found."""
        mock_subprocess_run.side_effect = FileNotFoundError()

        version = get_xtrabackup_version()

        self.assertIsNone(version)

    @patch('subprocess.run')
    def test_get_xtrabackup_version_error(self, mock_subprocess_run):
        """Test when xtrabackup returns an error."""
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, 'xtrabackup')

        version = get_xtrabackup_version()

        self.assertIsNone(version)

    @patch('subprocess.run')
    def test_get_xtrabackup_version_invalid_output(self, mock_subprocess_run):
        """Test when xtrabackup output cannot be parsed."""
        mock_result = MagicMock()
        mock_result.stdout = "Invalid output"
        mock_result.stderr = ""
        mock_subprocess_run.return_value = mock_result

        with self.assertRaises(ValueError) as context:
            get_xtrabackup_version()

        self.assertIn("Unable to parse XtraBackup version", str(context.exception))

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open,
           read_data='NAME="Ubuntu"\nVERSION="22.04.3 LTS (Jammy Jellyfish)"\n'
                     'ID=ubuntu\nID_LIKE=debian\nVERSION_ID="22.04"\n')
    def test_get_distro_info_from_os_release(self, mock_file, mock_exists):
        """Test getting distro info from /etc/os-release."""
        mock_exists.return_value = True

        distro, version = get_distro_info()

        self.assertEqual(distro, "ubuntu")
        self.assertEqual(version, "22.04")
        mock_exists.assert_called_once_with('/etc/os-release')

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open,
           read_data='PRETTY_NAME="Debian GNU/Linux 11 (bullseye)"\nNAME="Debian GNU/Linux"\n'
                     'VERSION_ID="11"\nVERSION="11 (bullseye)"\nID=debian\n')
    def test_get_distro_info_debian(self, mock_file, mock_exists):
        """Test getting Debian distro info."""
        mock_exists.return_value = True

        distro, version = get_distro_info()

        self.assertEqual(distro, "debian")
        self.assertEqual(version, "11")

    @patch('subprocess.run')
    @patch('os.path.exists')
    def test_get_distro_info_fallback_lsb_release(self, mock_exists, mock_subprocess_run):
        """Test fallback to lsb_release when /etc/os-release doesn't exist."""
        mock_exists.return_value = False

        # Mock lsb_release responses
        def subprocess_side_effect(*args, **kwargs):
            if args[0] == ['lsb_release', '-si']:
                result = MagicMock()
                result.returncode = 0
                result.stdout = "Ubuntu\n"
                return result
            elif args[0] == ['lsb_release', '-sr']:
                result = MagicMock()
                result.returncode = 0
                result.stdout = "20.04\n"
                return result
            return MagicMock(returncode=1)

        mock_subprocess_run.side_effect = subprocess_side_effect

        distro, version = get_distro_info()

        self.assertEqual(distro, "ubuntu")
        self.assertEqual(version, "20.04")

    @patch('subprocess.run')
    @patch('os.path.exists')
    def test_get_distro_info_unknown(self, mock_exists, mock_subprocess_run):
        """Test when distro cannot be determined."""
        mock_exists.return_value = False
        mock_subprocess_run.side_effect = FileNotFoundError()

        distro, version = get_distro_info()

        self.assertEqual(distro, "unknown")
        self.assertEqual(version, "unknown")

    def test_load_version_map(self):
        """Test loading the version map."""
        version_map = load_version_map()

        # Check structure
        self.assertIn("debian", version_map)
        self.assertIn("ubuntu", version_map)

        # Check Debian versions
        self.assertIn("11", version_map["debian"])
        self.assertIn("12", version_map["debian"])

        # Check Ubuntu versions
        self.assertIn("20.04", version_map["ubuntu"])
        self.assertIn("22.04", version_map["ubuntu"])
        self.assertIn("24.04", version_map["ubuntu"])

        # Check MySQL versions for a specific distro
        self.assertIn("mysql", version_map["ubuntu"]["22.04"])
        self.assertIn("5.7", version_map["ubuntu"]["22.04"]["mysql"])
        self.assertIn("8.0", version_map["ubuntu"]["22.04"]["mysql"])
        self.assertIn("8.4", version_map["ubuntu"]["22.04"]["mysql"])

    @patch('xtrabackup_info.load_version_map')
    def test_get_xtrabackup_download_url(self, mock_load_map):
        """Test getting download URL for XtraBackup."""
        mock_load_map.return_value = {
            "ubuntu": {
                "22.04": {
                    "mysql": {
                        "8.0": "https://downloads.percona.com/xtrabackup-8.0.deb",
                        "5.7": "https://downloads.percona.com/xtrabackup-2.4.deb"
                    }
                }
            },
            "debian": {
                "11": {
                    "mysql": {
                        "8.0": "https://downloads.percona.com/debian-xtrabackup-8.0.deb"
                    }
                }
            }
        }

        # Test valid URL retrieval
        url = get_xtrabackup_download_url("8.0", "ubuntu", "22.04")
        self.assertEqual(url, "https://downloads.percona.com/xtrabackup-8.0.deb")

        # Test unsupported distro
        url = get_xtrabackup_download_url("8.0", "centos", "7")
        self.assertIsNone(url)

        # Test unsupported distro version
        url = get_xtrabackup_download_url("8.0", "ubuntu", "24.04")
        self.assertIsNone(url)

        # Test unsupported MySQL version
        url = get_xtrabackup_download_url("8.4", "ubuntu", "22.04")
        self.assertIsNone(url)

    def test_get_required_xtrabackup_version(self):
        """Test determining required XtraBackup version for MySQL versions."""
        # MySQL 5.6 and 5.7 require XtraBackup 2.4
        self.assertEqual(get_required_xtrabackup_version("5.6"), "2.4")
        self.assertEqual(get_required_xtrabackup_version("5.7"), "2.4")

        # MySQL 8.0 and 8.2 require XtraBackup 8.0
        self.assertEqual(get_required_xtrabackup_version("8.0"), "8.0")
        self.assertEqual(get_required_xtrabackup_version("8.2"), "8.0")

        # MySQL 8.4 requires XtraBackup 8.4
        self.assertEqual(get_required_xtrabackup_version("8.4"), "8.4")

        # Unknown version
        self.assertIsNone(get_required_xtrabackup_version("10.6"))  # MariaDB
        self.assertIsNone(get_required_xtrabackup_version("9.0"))  # Future version

    @patch('xtrabackup_info.get_distro_info')
    @patch('xtrabackup_info.get_xtrabackup_download_url')
    @patch('xtrabackup_info.get_xtrabackup_version')
    def test_validate_xtrabackup_version_compatible(self, mock_get_version, mock_get_url, mock_get_distro):
        """Test validation when versions are compatible."""
        mock_get_version.return_value = "8.0"

        is_valid, message, url = validate_xtrabackup_version("8.0")

        self.assertTrue(is_valid)
        self.assertIn("compatible", message)
        self.assertIsNone(url)
        mock_get_version.assert_called_once_with('xtrabackup')

    @patch('xtrabackup_info.get_distro_info')
    @patch('xtrabackup_info.get_xtrabackup_download_url')
    @patch('xtrabackup_info.get_xtrabackup_version')
    def test_validate_xtrabackup_version_not_found_with_url(self, mock_get_version, mock_get_url, mock_get_distro):
        """Test validation when XtraBackup is not found but URL is available."""
        mock_get_version.return_value = None
        mock_get_distro.return_value = ("ubuntu", "22.04")
        mock_get_url.return_value = "https://downloads.percona.com/xtrabackup-8.0.deb"

        is_valid, message, url = validate_xtrabackup_version("8.0", "/custom/path/xtrabackup")

        self.assertFalse(is_valid)
        self.assertIn("not found", message)
        self.assertIn("/custom/path/xtrabackup", message)
        self.assertIn("Download XtraBackup 8.0", message)
        self.assertIn("https://downloads.percona.com/xtrabackup-8.0.deb", message)
        self.assertEqual(url, "https://downloads.percona.com/xtrabackup-8.0.deb")

    @patch('xtrabackup_info.get_distro_info')
    @patch('xtrabackup_info.get_xtrabackup_download_url')
    @patch('xtrabackup_info.get_xtrabackup_version')
    def test_validate_xtrabackup_version_not_found_no_url(self, mock_get_version, mock_get_url, mock_get_distro):
        """Test validation when XtraBackup is not found and no URL available."""
        mock_get_version.return_value = None
        mock_get_distro.return_value = ("unknown", "unknown")
        mock_get_url.return_value = None

        is_valid, message, url = validate_xtrabackup_version("8.0", "/custom/path/xtrabackup")

        self.assertFalse(is_valid)
        self.assertIn("not found", message)
        self.assertIn("/custom/path/xtrabackup", message)
        self.assertNotIn("Download", message)  # No download suggestion
        self.assertIsNone(url)

    @patch('xtrabackup_info.get_distro_info')
    @patch('xtrabackup_info.get_xtrabackup_download_url')
    @patch('xtrabackup_info.get_xtrabackup_version')
    def test_validate_xtrabackup_version_mismatch_with_url(self, mock_get_version, mock_get_url, mock_get_distro):
        """Test validation when versions don't match and URL is available."""
        mock_get_version.return_value = "2.4"
        mock_get_distro.return_value = ("ubuntu", "22.04")
        mock_get_url.return_value = "https://downloads.percona.com/xtrabackup-8.0.deb"

        is_valid, message, url = validate_xtrabackup_version("8.0")

        self.assertFalse(is_valid)
        self.assertIn("not compatible", message)
        self.assertIn("Required version: 8.0", message)
        self.assertIn("https://downloads.percona.com/xtrabackup-8.0.deb", message)
        self.assertEqual(url, "https://downloads.percona.com/xtrabackup-8.0.deb")

    @patch('xtrabackup_info.get_distro_info')
    @patch('xtrabackup_info.get_xtrabackup_version')
    def test_validate_xtrabackup_version_unknown_mysql(self, mock_get_version, mock_get_distro):
        """Test validation with unknown MySQL version."""
        mock_get_version.return_value = "8.0"
        mock_get_distro.return_value = ("ubuntu", "22.04")

        is_valid, message, url = validate_xtrabackup_version("10.6")  # MariaDB version

        self.assertFalse(is_valid)
        self.assertIn("MySQL version 10.6 unknown", message)
        self.assertIn("extend XTRABACKUP_VERSION_MAP", message)
        self.assertIsNone(url)

    @patch('xtrabackup_info.get_distro_info')
    @patch('xtrabackup_info.get_xtrabackup_version')
    def test_validate_xtrabackup_version_unknown_distro(self, mock_get_version, mock_get_distro):
        """Test validation with unknown distro."""
        mock_get_version.return_value = "2.4"
        mock_get_distro.return_value = ("unknown", "unknown")

        is_valid, message, url = validate_xtrabackup_version("8.0")

        self.assertFalse(is_valid)
        self.assertIn("not compatible", message)
        self.assertIn("Linux distribution unknown", message)
        self.assertIsNone(url)

    @patch('xtrabackup_info.get_distro_info')
    @patch('xtrabackup_info.get_xtrabackup_download_url')
    @patch('xtrabackup_info.get_xtrabackup_version')
    def test_validate_xtrabackup_version_unsupported_distro(self, mock_get_version, mock_get_url, mock_get_distro):
        """Test validation with unsupported distro/version combination."""
        mock_get_version.return_value = "2.4"
        mock_get_distro.return_value = ("centos", "9")
        mock_get_url.return_value = None

        is_valid, message, url = validate_xtrabackup_version("8.0")

        self.assertFalse(is_valid)
        self.assertIn("not compatible", message)
        self.assertIn("Distribution centos 9", message)
        self.assertIn("not found in XTRABACKUP_VERSION_MAP", message)
        self.assertIsNone(url)


if __name__ == '__main__':
    unittest.main()
