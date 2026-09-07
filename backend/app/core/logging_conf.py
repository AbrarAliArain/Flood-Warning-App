"""Logging setup.

A single configured root handler keeps uvicorn, the risk engine and the
WhatsApp transport writing to the same place with request-relevant context.
"""
import logging
import sys

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"
_configured = False


def setup(level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]
    # Third-party HTTP chatter is noise next to emergency-dispatch events.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    setup()
    return logging.getLogger(name)
