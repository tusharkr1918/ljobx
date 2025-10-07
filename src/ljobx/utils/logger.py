# ljobx/utils/logger.py

import logging
from logging import StreamHandler, FileHandler
from logging.handlers import RotatingFileHandler
from typing import List, Optional
from queue import Queue

# Import the config object to get the LOG_FILE path
from ljobx.core.config import config

class QueueLogHandler(logging.Handler):
    """A custom logging handler that puts logs into a queue."""
    def __init__(self, log_queue: Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))

def setup_root_logger(level: int = logging.INFO) -> logging.Logger:
    """
    Set up a root logger with the specified level.

    Note:
    - If `force` is not set to True and any logging methods
    (e.g., `logging.info()`, `logging.debug()`) have been called
    before this function, the root logger may already be configured
    with default settings instead of the ones specified here.
    """
    logging.basicConfig(
        level=level,
        format='[%(asctime)s] - %(levelname)s [%(threadName)s] - %(message)s (%(filename)s:%(lineno)d - %(name)s)',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            StreamHandler(),
            RotatingFileHandler(config.LOG_FILE, maxBytes=5*1024*1024, backupCount=5),
            FileHandler('app_recent.log', mode='w')
        ],
        force=True
    )
    return logging.getLogger()

def setup_module_logger(name: str, level: Optional[int] = None, propagate: bool = False, handlers: Optional[List] = None) -> logging.Logger:
    """
    Set up a module-specific logger with the given name and optional level.

    Notes:
    - A module logger inherits the root logger's level, filters only.
    - In case if the module logger has no handlers, messages are propagated to the root logger.
    - Root logger applies its handlers, level filtering, and formatters to the propagated messages. (If module logger have
      log level set to DEBUG, and root logger have level set to INFO, then DEBUG messages from module logger will be filtered out by root logger).
    - If you want to disable propagation, set `propagate` to False.

    - Setting any configuration (handlers, formatters, etc.) will override the root logger's configuration.
    """

    logger = logging.getLogger(name)

    if level is not None:
        logger.setLevel(level)

    if handlers:
        for handler in handlers:
            if not isinstance(handler, logging.Handler):
                raise TypeError("All items in handlers must be instances of logging.Handler")
            logger.addHandler(handler)

    logger.propagate = propagate
    if not propagate and not logger.hasHandlers():
        logging.warning(
            f"Module logger '{name}' has no handlers and propagation is disabled. "
            "It will not be able to output log messages."
        )

    return logger