from monitor import FIMMonitor
from config import DIRECTORIES_TO_WATCH
import time
import logging

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

print("Starting Debug Monitor...")
monitor = FIMMonitor(DIRECTORIES_TO_WATCH)
monitor.start()

try:
    while True:
        monitor._scan()
        time.sleep(1)
except KeyboardInterrupt:
    monitor.stop()
