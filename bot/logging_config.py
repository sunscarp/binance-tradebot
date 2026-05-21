"""Logging configuration for the trading bot."""
import logging
import os
from logging.handlers import RotatingFileHandler

DEFAULT_LOG_FILE = "logs/trading_bot.log"
DEFAULT_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(
    log_file: str = DEFAULT_LOG_FILE,
    level: int = logging.INFO,
    console_level: int = logging.INFO,
) -> None:
    """
    Set up root logger with:
      • Rotating file handler  → logs/trading_bot.log  (5 MB × 3 backups)
      • Stream handler         → stdout
    """
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # capture everything; handlers filter

    fmt = logging.Formatter(DEFAULT_FORMAT, datefmt=DATE_FORMAT)

    # ── File handler ──────────────────────────────────────────────────
    fh = RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # ── Console handler ───────────────────────────────────────────────
    ch = logging.StreamHandler()
    ch.setLevel(console_level)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # Silence noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
