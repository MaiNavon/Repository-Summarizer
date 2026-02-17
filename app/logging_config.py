"""Logging configuration for the GitHub Repository Summarizer."""

import logging
import sys
import os
from typing import Optional


def setup_logging(level: Optional[str] = None) -> None:
    """
    Configures application logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). 
               Defaults to LOG_LEVEL env var or INFO.
    """
    log_level_str = level or os.environ.get("LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Gets a logger for a module."""
    return logging.getLogger(name)
