from dataclasses import dataclass
import os
import multiprocessing

# Try to import tomllib (Python 3.11+), fall back to tomli if not available
try:
    import tomllib

    toml_lib = tomllib
except ModuleNotFoundError:
    try:
        import tomli

        toml_lib = tomli
    except ModuleNotFoundError:
        try:
            import toml

            toml_lib = toml  # Use toml with the same interface
        except ModuleNotFoundError:
            raise ImportError("TOML parsing library not found. Please install python3-toml from Debian repositories.")


@dataclass
class ZbxConfig:
    item_key: str
    sender_bin: str
    agent_conf: str


@dataclass
class ConditionsConfig:
    skip_conditions: list[str]
    skip_conditions_timeout: int
    run_conditions: list[str]
    run_conditions_timeout: int
    terminate_conditions: list[str]
    terminate_conditions_timeout: int


@dataclass
class Config:
    backup_dir: str
    parallelism: int
    versions: int
    delete_before: bool
    xtrabackup_bin: str
    mysql_bin: str
    xtrabackup_options: list[str]
    streamcompress: bool
    prepare: bool
    tgz: bool
    log_level: str
    check_xtrabackup_version: bool
    zbx: ZbxConfig
    conditions: ConditionsConfig


def get_config(config_file: str) -> Config:
    """
    Read the config toml file and return a Config object

    Args:
        config_file: Path to the TOML configuration file

    Returns:
        Config object with settings from the TOML file

    Raises:
        FileNotFoundError: If the config file doesn't exist
        ValueError: If required settings are missing
    """
    if not os.path.isfile(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")

    # Read the TOML file
    try:
        # Try text mode first (for Debian 11)
        with open(config_file, "r") as f:
            config_data = toml_lib.load(f)
    except TypeError:
        # Fall back to binary mode (for other versions)
        try:
            with open(config_file, "rb") as f:
                config_data = toml_lib.load(f)
        except Exception as e:
            raise ValueError(f"Error parsing TOML file: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error parsing TOML file: {str(e)}")

    # Extract main section
    if "main" not in config_data:
        raise ValueError("Missing 'main' section in configuration file")

    main_config = config_data["main"]

    if "zabbix" in config_data:
        zbx_config = config_data["zabbix"]
    else:
        zbx_config = {}

    if "conditions" in config_data:
        conditions_config = config_data["conditions"]
    else:
        conditions_config = {}

    # Check for required backup_dir
    if "backup_dir" not in main_config:
        raise ValueError("Required setting 'backup_dir' is missing")

    # Check link_type
    link_type = str(main_config.get("link_type", "hard"))
    if link_type not in ["hard", "symbolic"]:
        raise ValueError(f"Invalid link type: {link_type}")

    backup_dir = main_config["backup_dir"]
    # Verify backup_dir exists
    if not os.path.isdir(backup_dir):
        raise ValueError(f"Backup directory does not exist: {backup_dir}")

    # Check for mutually exclusive backup strategies
    streamcompress = main_config.get("streamcompress", False)
    prepare = main_config.get("prepare", False)
    tgz = main_config.get("tgz", False)

    if streamcompress and (prepare or tgz):
        raise ValueError("streamcompress is mutually exclusive with prepare and tgz options")

    # Set defaults and override with values from config file
    config = Config(
        backup_dir=backup_dir,
        # Default: number of CPUs
        parallelism=main_config.get("parallelism", multiprocessing.cpu_count()),
        # Default: 1
        versions=main_config.get("versions", 1),
        # Default: False
        delete_before=main_config.get("delete_before", False),
        # Default: "xtrabackup" (in PATH)
        xtrabackup_bin=main_config.get("xtrabackup_bin", "xtrabackup"),
        # Default: "mysql" (in PATH)
        mysql_bin=main_config.get("mysql_bin", "mysql"),
        # Default: empty list
        xtrabackup_options=main_config.get("xtrabackup_options", []),
        # Default: False
        streamcompress=streamcompress,
        # Default: False
        prepare=prepare,
        # Default: False
        tgz=tgz,
        # Default: "info"
        log_level=main_config.get("log_level", "info"),
        # Default: True (check xtrabackup version by default)
        check_xtrabackup_version=main_config.get("check_xtrabackup_version", True),
        zbx=ZbxConfig(
            item_key=zbx_config.get("item_key", ""),
            sender_bin=zbx_config.get("sender_bin", "zabbix_sender"),
            agent_conf=zbx_config.get("agent_conf", "/etc/zabbix/zabbix_agentd.conf"),
        ),
        conditions=ConditionsConfig(
            skip_conditions=conditions_config.get("skip_conditions", []),
            skip_conditions_timeout=conditions_config.get("skip_conditions_timeout", 0),
            run_conditions=conditions_config.get("run_conditions", []),
            run_conditions_timeout=conditions_config.get("run_conditions_timeout", 0),
            terminate_conditions=conditions_config.get("terminate_conditions", []),
            terminate_conditions_timeout=conditions_config.get("terminate_conditions_timeout", 0),
        )
    )

    # Reject pointless configs
    if config.parallelism == 0:
        raise ValueError("Parallelism cannot be zero")

    return config
