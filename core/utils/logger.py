"""Centralized logging configuration for the patching project."""

import logging
import sys
from pathlib import Path


def setup_logger(
    name: str, log_file: str = None, level: str = "INFO"
) -> logging.Logger:
    """Setup a logger with console and optional file output.

    Examples:
        # Console only
        logger = setup_logger(__name__)

        # Console + file
        logger = setup_logger(__name__, "app.log")

        # Infrastructure module
        logger = setup_logger("infrastructure.ec2_client", "aws.log")
    """
    # Make log_file optional for console-only logging
    logger = logging.getLogger(name)
    try:
        logger.setLevel(getattr(logging, level.upper()))
    except AttributeError:
        logger.setLevel(logging.INFO)  # fallback to INFO

    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        if log_file:
            Path("logs").mkdir(exist_ok=True)
            file_handler = logging.FileHandler(f"logs/{log_file}")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    return logger


def get_infrastructure_logger(module_name: str) -> logging.Logger:
    """Get logger for infrastructure modules."""
    return setup_logger(f"infrastructure.{module_name}")
