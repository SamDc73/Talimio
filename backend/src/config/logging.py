import logging
import logging.config
from typing import Any


def setup_logging() -> dict[str, Any]:
    """Configure logging for the application."""
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "level": "INFO",
            },
        },
        "root": {"level": "INFO", "handlers": ["console"]},
    }

    logging.config.dictConfig(config)
    return config
