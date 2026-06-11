"""Structured logging configuration using structlog over the stdlib logging.

Produces human-friendly colourised logs in development and JSON logs in
production so they can be ingested by log aggregators (Loki, ELK, CloudWatch).
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.config.settings import settings


def configure_logging() -> None:
    """Configure stdlib logging + structlog processors once at startup."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.is_production:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging (aiogram, sqlalchemy, apscheduler) through structlog.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=log_level,
    )

    # Tame noisy third-party loggers.
    for noisy in ("aiogram.event", "aiosqlite", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.db_echo else logging.WARNING
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger.

    The logger name is bound into the event dict as ``logger`` rather than via
    ``structlog.stdlib.add_logger_name`` (which requires a stdlib logger with a
    ``.name`` attribute and is incompatible with ``PrintLoggerFactory``).
    """
    logger = structlog.get_logger()
    return logger.bind(logger=name) if name else logger
