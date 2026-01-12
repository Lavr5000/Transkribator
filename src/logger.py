"""Logging configuration for WhisperTyping."""
import logging
import sys
from pathlib import Path

from .config import Config


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Setup application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("whisper-typing")

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console handler (stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)  # Only warnings+ to console
    console_format = logging.Formatter(
        "%(levelname)s: %(message)s"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler (optional, in config dir)
    try:
        log_file = Config.get_config_dir() / "app.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=1_000_000,  # 1MB
            backupCount=2,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    except Exception:
        # File logging is optional
        pass

    return logger


# Import RotatingFileHandler
import logging.handlers

# Global logger instance
logger = setup_logging()
