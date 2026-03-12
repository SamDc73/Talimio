import logging.config


def setup_logging() -> None:
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
