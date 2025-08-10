import logging
import os


class OpaLogger(logging.Logger):
    """Custom logger class that extends logging.Logger with additional functionality"""

    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)
        self.log_file = None

    def read_log(self):
        """Read and return the content of the log file"""
        if self.log_file and os.path.exists(self.log_file):
            with open(self.log_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""


def new_logger(log_file: str = "", log_level: str = "info") -> OpaLogger:
    """
    Create a new logger. If log_file is not given, logs are printed to stdout.
    If log_file exists, it will be overwritten. Logs are NOT appended to existing files.
    :param log_file: Path to log file, if empty logs go to stdout only
    :param log_level: Log level (debug, info, warning, error)
    :return: Configured logging instance
    """
    # Create custom logger
    logging.setLoggerClass(OpaLogger)
    logger = logging.getLogger('opa')
    # Ensure we have the right type
    assert isinstance(logger, OpaLogger)

    # Store the log file path
    logger.log_file = log_file

    # Set log level based on parameter
    log_level_map = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR
    }
    level = log_level_map.get(log_level.lower(), logging.INFO)
    logger.setLevel(level)

    # Clear any existing handlers
    if logger.handlers:
        logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

    # Create file handler if log_file is specified
    if log_file:
        file_handler = logging.FileHandler(log_file, mode='w')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    else:
        # add a console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    logger.info(f"Logger initialized with level: {log_level}")

    return logger
