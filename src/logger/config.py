import logging
import sys

from logging.config import dictConfig

from settings import config
from .formatters import JsonFormatter, PlainFormatter


def _parse_level(value: str | int | None) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        v = value.strip()
        if v.isdigit():
            return int(v)
        mapping = logging.getLevelNamesMapping()
        return mapping.get(v.upper(), logging.INFO)
    return logging.INFO


def setup_logging() -> None:
    level = _parse_level(getattr(config, "LOG_LEVEL", None))
    formatter = "plain" if (config.ENV == "dev" and config.LOG_FORMAT == "plain") else "json"

    uvicorn_access_logger = (
        {"level": level, "handlers": ["stdout"], "propagate": False}
        if config.UVICORN_ACCESS_LOG
        else {"level": "CRITICAL", "handlers": [], "propagate": False}
    )

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": True,
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

                "aiogram": {"level": level, "propagate": True},
                "aiogram.utils": {"level": "INFO", "propagate": False},
                "aiogram.utils.chat_action": {"level": "INFO", "propagate": False},
                "aiogram.event": {"level": "INFO", "handlers": ["stdout"], "propagate": False},

                "httpx": {"level": "WARNING", "propagate": False},
                "httpcore": {"level": "WARNING", "propagate": False},
                "hpack": {"level": "WARNING", "propagate": False},

                "sqlalchemy": {"level": "WARNING", "propagate": False},
                "alembic": {"level": "INFO", "propagate": False},

                "apps": {"level": level, "propagate": True},
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
