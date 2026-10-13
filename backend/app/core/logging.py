"""Structured logging with workflow-aware context, request correlation, and secret redaction."""

import json
import logging
import re
import sys
from datetime import datetime, timezone

from app.core.request_context import request_id_ctx

REDACTED_KEYS = {"password", "passwd", "api_key", "apikey", "secret", "token", "authorization", "set-cookie"}
REDACT_PATTERN = re.compile(r"(password\s*=\s*|api[_-]?key\s*[=:]\s*|secret\s*[=:]\s*|bearer\s+)([^\s&;'\"]+)", re.IGNORECASE)


def redact(value):
    if isinstance(value, dict):
        return {k: ("***" if str(k).lower() in REDACTED_KEYS else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return REDACT_PATTERN.sub(r"\1***", value)
    return value


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_ctx.get(),
            "message": redact(record.getMessage()),
        }
        for key in ("project_id", "workflow", "agent", "task", "event", "status", "duration", "error"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = redact(value)
        if record.exc_info:
            payload["error"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
