import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pythonjsonlogger import jsonlogger

def setup_logger(name: str, log_dir: str = "logs") -> logging.Logger:
    """
    Configure a unified logger with both console and JSON rotating file handlers.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers if setup_logger is called multiple times
    if logger.handlers:
        return logger

    # Ensure log directory exists
    os.makedirs(log_dir, exist_ok=True)
    
    # 1. Console Handler (Standard Formatting)
    console_handler = logging.StreamHandler()
    console_format = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
    console_handler.setFormatter(console_format)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # 2. JSON Rotating File Handler (For external aggregators like Vector/FluentBit)
    log_file = os.path.join(log_dir, f"{name}.json")
    file_handler = TimedRotatingFileHandler(log_file, when="midnight", interval=1, backupCount=7)
    
    # JSON formatter
    json_formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s',
        rename_fields={"asctime": "timestamp", "levelname": "level"}
    )
    file_handler.setFormatter(json_formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    # Note: If Vector or FluentBit is running as a sidecar, it can tail the .json files in the logs directory.

    return logger
