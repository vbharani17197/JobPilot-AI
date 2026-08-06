"""Structured logging via loguru."""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def setup_logging(log_file: Path, level: str = "INFO",
                  rotation: str = "10 MB", retention: str = "30 days") -> None:
    """Configure console + rotating file logging.

    Console gets a clean human-readable line; the file keeps full detail.
    """
    logger.remove()  # drop the default handler

    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
               "<cyan>{name}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_file,
        level="DEBUG",
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        enqueue=True,
    )


__all__ = ["logger", "setup_logging"]
