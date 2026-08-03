"""
Centralised logging configuration.

WHY NOT JUST USE `print()`?
----------------------------
`print()` statements have no severity level, no timestamp, and can't be
turned off in production without editing code. The standard library's
`logging` module solves all three:

* Levels (DEBUG/INFO/WARNING/ERROR) let us silence noisy debug logs in
  production while keeping errors visible.
* Every log line is automatically timestamped and tagged with the module
  that emitted it, which is invaluable when debugging a request that
  touched five different services.
* Log output can be redirected (to a file, to stdout for Docker/Render to
  collect, to a log aggregator) without touching application code.

Every module in the app calls `get_logger(__name__)` so log lines are
prefixed with their originating module (e.g. `app.services.pdf_service`),
making it obvious where a message came from.
"""

import logging
import sys

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure_root_logger() -> None:
    """Configure the root logger exactly once per process."""
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, ensuring the root logger is configured first."""
    _configure_root_logger()
    return logging.getLogger(name)
