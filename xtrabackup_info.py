import os
import subprocess
import re
from typing import Optional, Tuple, Dict


# XtraBackup version mapping converted from xtrabackup-version-map.yml
# This mapping defines which XtraBackup version to use for each MySQL version
# on different Linux distributions

# Base URLs for different XtraBackup versions
_BASE_24 = "https://downloads.percona.com/downloads/Percona-XtraBackup-2.4/Percona-XtraBackup-2.4.29/binary/debian"
_BASE_80 = "https://downloads.percona.com/downloads/Percona-XtraBackup-8.0/Percona-XtraBackup-8.0.35-33/binary/debian"
_BASE_82 = ("https://downloads.percona.com/downloads/Percona-XtraBackup-innovative-release/"
            "Percona-XtraBackup-8.2.0-1/binary/debian")
_BASE_84 = "https://downloads.percona.com/downloads/Percona-XtraBackup-8.4/Percona-XtraBackup-8.4.0-3/binary/debian"

XTRABACKUP_VERSION_MAP = {
    "debian": {
        "11": {  # bullseye
            "mysql": {
                "5.6": f"{_BASE_24}/bullseye/x86_64/percona-xtrabackup-24_2.4.29-1.bullseye_amd64.deb",
                "5.7": f"{_BASE_24}/bullseye/x86_64/percona-xtrabackup-24_2.4.29-1.bullseye_amd64.deb",
                "8.0": f"{_BASE_80}/bullseye/x86_64/percona-xtrabackup-80_8.0.35-33-1.bullseye_amd64.deb",
                "8.2": f"{_BASE_82}/bullseye/x86_64/percona-xtrabackup-82_8.2.0-1-1.bullseye_amd64.deb",
                "8.4": f"{_BASE_84}/bullseye/x86_64/percona-xtrabackup-84_8.4.0-3-1.bullseye_amd64.deb"
            }
        },
        "12": {  # bookworm
            "mysql": {
                "5.6": f"{_BASE_24}/bookworm/x86_64/percona-xtrabackup-24_2.4.29-1.bookworm_amd64.deb",
                "5.7": f"{_BASE_24}/bookworm/x86_64/percona-xtrabackup-24_2.4.29-1.bookworm_amd64.deb",
                "8.0": f"{_BASE_80}/bookworm/x86_64/percona-xtrabackup-80_8.0.35-33-1.bookworm_amd64.deb",
                "8.2": f"{_BASE_82}/bookworm/x86_64/percona-xtrabackup-82_8.2.0-1-1.bookworm_amd64.deb",
                "8.4": f"{_BASE_84}/bookworm/x86_64/percona-xtrabackup-84_8.4.0-3-1.bookworm_amd64.deb"
            }
        }
    },
    "ubuntu": {
        "20.04": {  # focal
            "mysql": {
                "5.6": f"{_BASE_24}/focal/x86_64/percona-xtrabackup-24_2.4.29-1.focal_amd64.deb",
                "5.7": f"{_BASE_24}/focal/x86_64/percona-xtrabackup-24_2.4.29-1.focal_amd64.deb",
                "8.0": f"{_BASE_80}/focal/x86_64/percona-xtrabackup-80_8.0.35-33-1.focal_amd64.deb",
                "8.2": f"{_BASE_82}/focal/x86_64/percona-xtrabackup-82_8.2.0-1-1.focal_amd64.deb",
                "8.4": f"{_BASE_84}/focal/x86_64/percona-xtrabackup-84_8.4.0-3-1.focal_amd64.deb"
            }
        },
        "22.04": {  # jammy
            "mysql": {
                "5.6": f"{_BASE_24}/jammy/x86_64/percona-xtrabackup-24_2.4.29-1.jammy_amd64.deb",
                "5.7": f"{_BASE_24}/jammy/x86_64/percona-xtrabackup-24_2.4.29-1.jammy_amd64.deb",
                "8.0": f"{_BASE_80}/jammy/x86_64/percona-xtrabackup-80_8.0.35-33-1.jammy_amd64.deb",
                "8.2": f"{_BASE_82}/jammy/x86_64/percona-xtrabackup-82_8.2.0-1-1.jammy_amd64.deb",
                "8.4": f"{_BASE_84}/jammy/x86_64/percona-xtrabackup-84_8.4.0-3-1.jammy_amd64.deb"
            }
        },
        "24.04": {  # noble
            "mysql": {
                # MySQL 5.6.x and 5.7.x use XtraBackup 2.4 (using jammy package as noble doesn't have 2.4)
                "5.6": f"{_BASE_24}/jammy/x86_64/percona-xtrabackup-24_2.4.29-1.jammy_amd64.deb",
                "5.7": f"{_BASE_24}/jammy/x86_64/percona-xtrabackup-24_2.4.29-1.jammy_amd64.deb",
                "8.0": f"{_BASE_80}/noble/x86_64/percona-xtrabackup-80_8.0.35-33-1.noble_amd64.deb",
                # MySQL 8.2.x uses XtraBackup 8.2 (using jammy package as noble doesn't have 8.2 yet)
                "8.2": f"{_BASE_82}/jammy/x86_64/percona-xtrabackup-82_8.2.0-1-1.jammy_amd64.deb",
                "8.4": f"{_BASE_84}/noble/x86_64/percona-xtrabackup-84_8.4.0-3-1.noble_amd64.deb"
            }
        }
    }
}


def get_xtrabackup_version(xtrabackup_bin: str = 'xtrabackup') -> Optional[str]:
    """
    Get the installed XtraBackup version.

    Args:
        xtrabackup_bin: Path to xtrabackup binary

    Returns:
        str: XtraBackup version in format "major.minor" (e.g., "8.0", "2.4")
        None: If xtrabackup is not found
    """
    try:
        cmd = [xtrabackup_bin, '--version']
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)

        # Parse version from output
        # XtraBackup 2.4: "xtrabackup version 2.4.29 based on MySQL server 5.7.40"
        # XtraBackup 8.0: "xtrabackup version 8.0.35-33 based on MySQL server 8.0.35"
        # XtraBackup 8.4: "xtrabackup version 8.4.0-3 based on MySQL server 8.4.0"
        version_output = result.stdout + result.stderr  # Some versions output to stderr

        # Look for version pattern
        match = re.search(r'version\s+(\d+\.\d+)', version_output)
        if match:
            return match.group(1)
        else:
            raise ValueError(f"Unable to parse XtraBackup version from: {version_output}")

    except FileNotFoundError:
        return None
    except subprocess.CalledProcessError:
        return None


def get_distro_info() -> Tuple[str, str]:
    """
    Get the Linux distribution name and version.

    Returns:
        Tuple[str, str]: (distro_name, distro_version)
        For example: ("ubuntu", "22.04") or ("debian", "11")
    """
    # Try /etc/os-release first (most modern systems)
    if os.path.exists('/etc/os-release'):
        distro_id = None
        version_id = None

        with open('/etc/os-release', 'r') as f:
            for line in f:
                if line.startswith('ID='):
                    distro_id = line.split('=')[1].strip().strip('"').lower()
                elif line.startswith('VERSION_ID='):
                    version_id = line.split('=')[1].strip().strip('"')

        if distro_id and version_id:
            return distro_id, version_id

    # Fallback to lsb_release command
    try:
        # Get distribution ID
        cmd_id = ['lsb_release', '-si']
        result_id = subprocess.run(cmd_id, capture_output=True, text=True)
        distro_id = result_id.stdout.strip().lower() if result_id.returncode == 0 else None

        # Get release version
        cmd_release = ['lsb_release', '-sr']
        result_release = subprocess.run(cmd_release, capture_output=True, text=True)
        version_id = result_release.stdout.strip() if result_release.returncode == 0 else None

        if distro_id and version_id:
            return distro_id, version_id
    except FileNotFoundError:
        pass

    # If we can't determine, return unknown
    return "unknown", "unknown"


def load_version_map() -> Dict:
    """
    Load the XtraBackup version mapping.

    Returns:
        Dict: The version mapping dictionary
    """
    return XTRABACKUP_VERSION_MAP


def get_xtrabackup_download_url(mysql_version: str, distro_name: str, distro_version: str) -> Optional[str]:
    """
    Get the download URL for the correct XtraBackup version.

    Args:
        mysql_version: MySQL version (e.g., "8.0", "5.7")
        distro_name: Linux distribution name (e.g., "ubuntu", "debian")
        distro_version: Distribution version (e.g., "22.04", "11")

    Returns:
        str: Download URL for the appropriate XtraBackup package
        None: If no matching version found
    """
    version_map = load_version_map()

    # Check if distro is supported
    if distro_name not in version_map:
        return None

    # Check if distro version is supported
    if distro_version not in version_map[distro_name]:
        return None

    # Check if MySQL version is supported
    mysql_versions = version_map[distro_name][distro_version].get('mysql', {})
    if mysql_version not in mysql_versions:
        return None

    return mysql_versions[mysql_version]


def get_required_xtrabackup_version(mysql_version: str) -> str:
    """
    Determine the required XtraBackup version for a given MySQL version.

    Args:
        mysql_version: MySQL version (e.g., "8.0", "5.7", "8.4")

    Returns:
        str: Required XtraBackup version (e.g., "8.0", "2.4", "8.4")
    """
    # Based on the compatibility rules from the YAML file
    if mysql_version in ["5.6", "5.7"]:
        return "2.4"
    elif mysql_version in ["8.0"]:
        return "8.0"
    elif mysql_version in ["8.2"]:
        return "8.2"
    elif mysql_version == "8.4":
        return "8.4"
    else:
        # For unknown versions, we can't determine the required version
        return None


def validate_xtrabackup_version(mysql_version: str,
                                xtrabackup_bin: str = 'xtrabackup') -> Tuple[bool, str, Optional[str]]:
    """
    Validate that the installed XtraBackup version is compatible with MySQL version.

    Args:
        mysql_version: MySQL version (e.g., "8.0", "5.7")
        xtrabackup_bin: Path to xtrabackup binary

    Returns:
        Tuple[bool, str, Optional[str]]:
            - bool: True if versions are compatible
            - str: Status message
            - Optional[str]: Download URL if version mismatch
    """
    # Get installed XtraBackup version
    xtrabackup_version = get_xtrabackup_version(xtrabackup_bin)

    if xtrabackup_version is None:
        # XtraBackup not found - try to provide download URL
        required_version = get_required_xtrabackup_version(mysql_version)
        if required_version:
            distro_name, distro_version = get_distro_info()
            download_url = get_xtrabackup_download_url(mysql_version, distro_name, distro_version)
            if download_url:
                return False, (f"XtraBackup not found at '{xtrabackup_bin}'. "
                               f"Download XtraBackup {required_version} for MySQL {mysql_version} from: "
                               f"{download_url}"), download_url
        return False, f"XtraBackup not found at '{xtrabackup_bin}'", None

    # Get required XtraBackup version
    required_version = get_required_xtrabackup_version(mysql_version)

    if required_version is None:
        distro_name, distro_version = get_distro_info()
        return False, (f"MySQL version {mysql_version} unknown, extend XTRABACKUP_VERSION_MAP in xtrabackup_info.py "
                       f"or disable check_xtrabackup_version in the opa.conf"), None

    # Check if versions match
    if xtrabackup_version == required_version:
        return True, f"XtraBackup {xtrabackup_version} is compatible with MySQL {mysql_version}", None

    # Version mismatch - get download URL
    distro_name, distro_version = get_distro_info()

    if distro_name == "unknown" or distro_version == "unknown":
        return False, (f"XtraBackup {xtrabackup_version} is not compatible with MySQL {mysql_version}. "
                       f"Required version: {required_version}. "
                       f"Linux distribution unknown, extend XTRABACKUP_VERSION_MAP in xtrabackup_info.py "
                       f"or disable check_xtrabackup_version in the opa.conf"), None

    download_url = get_xtrabackup_download_url(mysql_version, distro_name, distro_version)

    if download_url is None:
        return False, (f"XtraBackup {xtrabackup_version} is not compatible with MySQL {mysql_version}. "
                       f"Required version: {required_version}. "
                       f"Distribution {distro_name} {distro_version} or MySQL {mysql_version} not found in "
                       f"XTRABACKUP_VERSION_MAP, extend it or disable check_xtrabackup_version in the opa.conf"), None

    return False, (f"XtraBackup {xtrabackup_version} is not compatible with MySQL {mysql_version}. "
                   f"Required version: {required_version}. "
                   f"Download the correct version from: {download_url}"), download_url
