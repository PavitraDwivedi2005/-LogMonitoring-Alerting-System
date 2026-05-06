"""
logger.py
---------
Structured JSON logging configuration for the application.
Uses python-json-logger for consistent, machine-readable log output.
"""

import logging
import sys
import os
from datetime import datetime, timezone
from pythonjsonlogger import json as json_logger


class CustomJsonFormatter(json_logger.JsonFormatter):
    """Adds extra fields to every log record."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = (
            datetime.now(timezone.utc).isoformat()
        )
        log_record["level"] = record.levelname
        log_record["module"] = record.module
        log_record["function"] = record.funcName
        # Remove the default 'levelname' to avoid duplication
        log_record.pop("levelname", None)


def setup_logger(
    name="log_monitor",
    log_file="app.log",
    level=logging.INFO,
):
    """
    Create and return a structured JSON logger.

    Outputs to both console (stdout) and a rotating log file.
    """
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(level)

    formatter = CustomJsonFormatter(
        fmt="%(timestamp)s %(level)s %(name)s %(module)s %(message)s"
    )

    # ── Console handler ──────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # ── File handler ─────────────────────────────────────────────
    try:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        logger.warning("Could not create log file: %s", log_file)

    return logger
