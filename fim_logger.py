import logging
import sys
import queue
from config import LOG_FILE

# Global queue for log broadcasting
log_queue = queue.Queue()

class QueueHandler(logging.Handler):
    """Custom handler to push logs to a queue."""
    def emit(self, record):
        try:
            msg = self.format(record)
            log_queue.put(msg)
        except Exception:
            self.handleError(record)

def setup_logger():
    """Configures and returns the logger."""
    logger = logging.getLogger("BehavioralFIM")
    logger.setLevel(logging.INFO)

    # File Handler
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)

    # Queue Handler for WebSockets
    queue_handler = QueueHandler()
    queue_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(queue_handler)

    return logger

logger = setup_logger()
