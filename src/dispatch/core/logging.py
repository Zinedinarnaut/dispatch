"""Logging helpers for Dispatch."""
from __future__ import annotations

from logging.config import dictConfig


DEFAULT_LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
}


def setup_logging(level: str = "INFO") -> None:
    """Configure application logging using dictConfig."""

    config = DEFAULT_LOGGING_CONFIG.copy()
    config = {**config, "root": {**config["root"], "level": level.upper()}}
    dictConfig(config)
