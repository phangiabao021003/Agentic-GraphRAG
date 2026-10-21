"""Process-wide logging setup. Call configure_logging() before importing app modules.

Stdout only (12-factor; `docker compose logs` is the log viewer). Idempotent so that
uvicorn --reload re-imports do not stack handlers.
"""
import logging
import os
import sys

HANDLER_NAME = "nutrition-va"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_NOISY_LOGGERS = ("httpx", "httpcore")


def _level_from_env() -> int:
    raw = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = logging.getLevelName(raw)
    return level if isinstance(level, int) else logging.INFO


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(_level_from_env())

    if not any(h.name == HANDLER_NAME for h in root.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.name = HANDLER_NAME
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(handler)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
