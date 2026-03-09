# Compatibility shim: re-exports from fim_logger
from fim_logger import logger, log_queue, QueueHandler, setup_logger

__all__ = ['logger', 'log_queue', 'QueueHandler', 'setup_logger']
