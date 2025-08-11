import unittest
import tempfile
import os
import sys
import importlib.util
from config import Config, ZbxConfig, ConditionsConfig

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the main module properly
spec = importlib.util.spec_from_file_location("main_module", "__main__.py")
main_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_module)

create_installer_script = main_module.create_installer_script
validate_setup = main_module.validate_setup


class TestInstallerGeneration(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        self.test_config = Config(
            backup_dir="/tmp/opa",
            parallelism=1,
            versions=1,
            delete_before=False,
            xtrabackup_bin="xtrabackup",
            mysql_bin="mysql",
            xtrabackup_options=[],
            streamcompress=False,
            prepare=False,
            tgz=False,
            log_level="info",
            check_xtrabackup_version=True,
            zbx=ZbxConfig(item_key="", sender_bin="", agent_conf=""),
            conditions=ConditionsConfig(
                skip_conditions=[], skip_conditions_timeout=0,
                run_conditions=[], run_conditions_timeout=0,
                terminate_conditions=[], terminate_conditions_timeout=0
            )
        )

    def test_create_installer_script(self):
        """Test creating an installer script."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            test_file = f.name

        try:
            # Create installer script
            download_url = "https://example.com/xtrabackup.deb"
            version = "8.0"

            result = create_installer_script(test_file, download_url, version)

            # Check that script was created
            self.assertTrue(result)
            self.assertTrue(os.path.exists(test_file))

            # Check script content
            with open(test_file, 'r') as f:
                content = f.read()

            self.assertIn("#!/bin/sh", content)
            self.assertIn(download_url, content)
            self.assertIn(version, content)
            self.assertIn("percona xtrabackup", content)
            self.assertIn("curl --fail", content)
            self.assertIn("apt-get install", content)

            # Check that script is executable
            file_stats = os.stat(test_file)
            self.assertTrue(file_stats.st_mode & 0o111)  # Check execute permission

        finally:
            # Clean up
            if os.path.exists(test_file):
                os.unlink(test_file)

    def test_create_installer_script_failure(self):
        """Test handling of script creation failure."""
        # Try to create script in non-existent directory
        result = create_installer_script(
            "/nonexistent/dir/script.sh",
            "https://example.com/xtrabackup.deb",
            "8.0"
        )

        self.assertFalse(result)

    # Simplified tests without complex mocking
    def test_installer_generation_logic(self):
        """Test that installer script is generated with correct content."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            test_file = f.name

        try:
            # Test data
            download_url = "https://downloads.percona.com/downloads/Percona-XtraBackup-8.0/xtrabackup.deb"
            version = "8.0"

            # Create installer
            result = create_installer_script(test_file, download_url, version)

            # Verify creation
            self.assertTrue(result)
            self.assertTrue(os.path.exists(test_file))

            # Check content includes all necessary components
            with open(test_file, 'r') as f:
                content = f.read()

            # Verify shell script header
            self.assertTrue(content.startswith("#!/bin/sh"))

            # Verify it mentions the version
            self.assertIn(f"version {version}", content)

            # Verify download URL is included
            self.assertIn(download_url, content)

            # Verify it uses curl with fail flag
            self.assertIn("curl --fail -ls", content)

            # Verify apt-get install command
            self.assertIn("apt-get install -y --no-install-recommends", content)

            # Verify cleanup
            self.assertIn('rm -f "$TMP_FILE"', content)

            # Verify error handling
            self.assertIn("if [ $? -ne 0 ]", content)

        finally:
            if os.path.exists(test_file):
                os.unlink(test_file)

    def test_installer_script_content(self):
        """Test the content of generated installer script."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            test_file = f.name

        try:
            download_url = "https://downloads.percona.com/xtrabackup-8.0.deb"
            version = "8.0"

            create_installer_script(test_file, download_url, version)

            with open(test_file, 'r') as f:
                content = f.read()

            # Check for required elements
            self.assertIn('TMP_FILE="/tmp/percona-xtrabackup.deb"', content)
            self.assertIn('test -e "$TMP_FILE"', content)
            self.assertIn('rm -f "$TMP_FILE"', content)
            self.assertIn('DEBIAN_FRONTEND=noninteractive', content)
            self.assertIn('--no-install-recommends', content)
            self.assertIn('if [ $? -ne 0 ]', content)  # Error checking
            self.assertIn('exit 1', content)  # Error exit
            self.assertIn(f'XtraBackup {version} installed successfully', content)

        finally:
            if os.path.exists(test_file):
                os.unlink(test_file)


if __name__ == '__main__':
    unittest.main()
