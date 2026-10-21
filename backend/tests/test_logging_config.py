import logging

import pytest

from app.logging_config import HANDLER_NAME, LOG_FORMAT, configure_logging


def _our_handlers():
    return [h for h in logging.getLogger().handlers if h.name == HANDLER_NAME]


@pytest.fixture(autouse=True)
def _restore_root_logger():
    root = logging.getLogger()
    before_level = root.level
    yield
    for h in _our_handlers():
        root.removeHandler(h)
    root.setLevel(before_level)


def test_configure_installs_exactly_one_handler_even_when_called_twice(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    configure_logging()
    configure_logging()
    assert len(_our_handlers()) == 1


def test_default_level_is_info(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    configure_logging()
    assert logging.getLogger().level == logging.INFO


def test_log_level_env_is_respected(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    configure_logging()
    assert logging.getLogger().level == logging.DEBUG


def test_invalid_log_level_falls_back_to_info(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "LOUD")
    configure_logging()
    assert logging.getLogger().level == logging.INFO


def test_format_has_level_and_logger_name(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    configure_logging()
    handler = _our_handlers()[0]
    record = logging.LogRecord("app.agent.loop", logging.ERROR, __file__, 1, "boom", None, None)
    line = handler.format(record)
    assert "| ERROR    | app.agent.loop | boom" in line
    assert handler.formatter._fmt == LOG_FORMAT


def test_httpx_loggers_are_quieted(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    configure_logging()
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
