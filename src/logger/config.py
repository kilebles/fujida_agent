import logging
import sys
from logging.config import dictConfig

from settings import config
from .formatters import JsonFormatter, PlainFormatter


def setup_logging() -> None:
    level = getattr(logging, config.LOG_LEVEL, logging.INFO)
    formatter = "plain" if (config.ENV == "dev" and config.LOG_FORMAT == "plain") else "json"

    uvicorn_access_logger = {
        "level": "CRITICAL",
        "handlers": [],
        "propagate": False,
    }
    if config.UVICORN_ACCESS_LOG:
        uvicorn_access_logger = {
            "level": level,
            "handlers": ["stdout"],
            "propagate": False,
        }

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {"()": JsonFormatter},
                "plain": {"()": PlainFormatter},
            },
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stdout,
                    "level": level,
                    "formatter": formatter,
                }
            },
            "root": {"level": level, "handlers": ["stdout"]},
            "loggers": {
                "uvicorn": {"level": level, "handlers": ["stdout"], "propagate": False},
                "uvicorn.error": {"level": level, "handlers": ["stdout"], "propagate": False},
                "uvicorn.access": uvicorn_access_logger,
                "aiogram": {"level": level, "handlers": ["stdout"], "propagate": False},
                "httpx": {"level": "WARNING", "handlers": ["stdout"], "propagate": False},
                "sqlalchemy": {"level": "WARNING", "handlers": ["stdout"], "propagate": False},
                "alembic": {"level": "INFO", "handlers": ["stdout"], "propagate": False},
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
