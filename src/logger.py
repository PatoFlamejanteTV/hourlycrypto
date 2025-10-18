# src/logger.py
import logging
import sys
from .config import get_config

def setup_logging():
    """Sets up logging for the bot."""
    log_level_str = get_config("logging", "level", "LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    log_file = get_config("logging", "file", "LOG_FILE", "bot.log")

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file)
        ]
    )
