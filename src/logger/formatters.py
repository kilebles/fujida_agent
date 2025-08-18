import time
import logging
from settings import config
from .context import request_id_var, chat_id_var, user_id_var


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        import json
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "app": config.APP_NAME,
        }
        rid = request_id_var.get()
        cid = chat_id_var.get()
        uid = user_id_var.get()
        if rid:
            payload["request_id"] = rid
        if cid is not None:
            payload["chat_id"] = cid
        if uid is not None:
            payload["user_id"] = uid
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class PlainFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[37m",
        "INFO": "\033[36m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[41m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET
        rid = request_id_var.get()
        cid = chat_id_var.get()
        uid = user_id_var.get()
        parts = [
            f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(record.created))}",
            f"{color}{record.levelname:<8}{reset}",
            record.name,
            f"msg={record.getMessage()}",
        ]
        if rid:
            parts.append(f"request_id={rid}")
        if cid is not None:
            parts.append(f"chat_id={cid}")
        if uid is not None:
            parts.append(f"user_id={uid}")
        if record.exc_info:
            parts.append(self.formatException(record.exc_info))
        return " | ".join(parts)
