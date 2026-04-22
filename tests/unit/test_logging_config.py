import logging
from pathlib import Path

from api.logging_config import setup_logging


def test_setup_logging_is_idempotent(monkeypatch):
    log_file = Path('D:/my_code/python_code/deepwiki-open/api/logs/test-application.log')
    monkeypatch.setenv('LOG_FILE_PATH', str(log_file))
    monkeypatch.setenv('NODE_ENV', 'production')

    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    try:
        root_logger.handlers = []
        setup_logging()
        first_handlers = list(root_logger.handlers)

        setup_logging()
        second_handlers = list(root_logger.handlers)

        assert len(first_handlers) == len(second_handlers)
        assert len(second_handlers) == 2
    finally:
        for handler in root_logger.handlers:
            handler.close()
        root_logger.handlers = original_handlers


def test_setup_logging_uses_console_only_in_development(monkeypatch):
    monkeypatch.setenv('NODE_ENV', 'development')
    monkeypatch.delenv('LOG_FILE_PATH', raising=False)

    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    try:
        root_logger.handlers = []
        setup_logging()
        handlers = list(root_logger.handlers)

        assert len(handlers) == 1
        assert isinstance(handlers[0], logging.StreamHandler)
    finally:
        for handler in root_logger.handlers:
            handler.close()
        root_logger.handlers = original_handlers
