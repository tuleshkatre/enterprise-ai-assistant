"""Application logging setup."""

import logging
import sys

from app.config import settings


def configure_logging() -> None:
    """Configure structured console logging once per process."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level.upper())
