"""Logging configuration for better-tg-upload."""

from logging import DEBUG, INFO, WARNING, Formatter, StreamHandler, getLogger
from sys import stderr


_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_DATE = "%H:%M:%S"


def setup_logging(verbose: bool = False) -> None:
    """Configure the root ``better_tg_upload`` logger.

    Parameters
    ----------
    verbose:
        When *True*, set level to ``DEBUG``; otherwise ``INFO``.
    """
    level = DEBUG if verbose else INFO
    handler = StreamHandler(stderr)
    handler.setFormatter(Formatter(_LOG_FORMAT, datefmt=_LOG_DATE))

    root = getLogger("better_tg_upload")
    root.setLevel(level)

    # Avoid duplicate handlers on repeated calls.
    if not root.handlers:
        root.addHandler(handler)

    # Silence noisy pyrogram internals unless debugging.
    pyrogram_logger = getLogger("pyrogram")
    pyrogram_logger.setLevel(DEBUG if verbose else WARNING)
