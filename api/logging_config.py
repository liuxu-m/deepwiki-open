import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler


class IgnoreLogChangeDetectedFilter(logging.Filter):
    def filter(self, record: logging.LogRecord):
        return "Detected file change in" not in record.getMessage()


def setup_logging(format: str = None):
    """
    Configure logging for the application with log rotation.

    Environment variables:
        LOG_LEVEL: Log level (default: INFO)
        LOG_FILE_PATH: Path to log file (default: logs/application.log)
        LOG_MAX_SIZE: Max size in MB before rotating (default: 10MB)
        LOG_BACKUP_COUNT: Number of backup files to keep (default: 5)

    Ensures log directory exists, prevents path traversal, and configures
    both rotating file and console handlers.
    """
    base_dir = Path(__file__).parent
    log_dir = base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    default_log_file = log_dir / "application.log"

    log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    is_development = os.environ.get("NODE_ENV") != "production"

    log_file_path = Path(os.environ.get("LOG_FILE_PATH", str(default_log_file)))

    log_dir_resolved = log_dir.resolve()
    resolved_path = log_file_path.resolve()
    if not str(resolved_path).startswith(str(log_dir_resolved) + os.sep):
        raise ValueError(f"LOG_FILE_PATH '{log_file_path}' is outside the trusted log directory '{log_dir_resolved}'")

    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        max_mb = int(os.environ.get("LOG_MAX_SIZE", 10))
        max_bytes = max_mb * 1024 * 1024
    except (TypeError, ValueError):
        max_bytes = 10 * 1024 * 1024

    try:
        backup_count = int(os.environ.get("LOG_BACKUP_COUNT", 5))
    except ValueError:
        backup_count = 5

    log_format = format or "%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(message)s"

    console_handler = logging.StreamHandler()
    formatter = logging.Formatter(log_format)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(IgnoreLogChangeDetectedFilter())

    handlers = [console_handler]
    if not is_development:
        file_handler = RotatingFileHandler(resolved_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(IgnoreLogChangeDetectedFilter())
        handlers.insert(0, file_handler)

    logging.basicConfig(level=log_level, handlers=handlers, force=True)

    logger = logging.getLogger(__name__)
    logger.debug(
        f"Logging configured: level={log_level_str}, "
        f"file={'disabled in development' if is_development else resolved_path}, max_size={max_bytes} bytes, "
        f"backup_count={backup_count}"
    )
