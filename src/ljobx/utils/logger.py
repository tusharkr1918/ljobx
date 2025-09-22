# ljobx/utils/logger.py

import logging
import sys
from queue import Queue

class QueueLogHandler(logging.Handler):
    """A custom logging handler that puts logs into a queue."""
    def __init__(self, log_queue: Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))

def configure_logging(level: str = "INFO"):
    """
    Sets the log levels for the root logger and other noisy libraries.
    This function does NOT add handlers; it only sets levels.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger().setLevel(log_level)

    # Set levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

# Main setup function for non-UI scripts
def setup_logger(level: str = "INFO") -> None:
    """
    Sets up the logger with handlers for file and console output.
    """
    configure_logging(level)

    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        return

    log_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%m-%d %H:%M:%S"
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(log_format)
    root_logger.addHandler(stream_handler)

def get_logger(name: str) -> logging.Logger:
    """A helper to get a logger instance."""
    return logging.getLogger(name)