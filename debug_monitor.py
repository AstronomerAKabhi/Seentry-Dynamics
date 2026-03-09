from monitor import FIMMonitor
from config import DIRECTORIES_TO_WATCH
import os
import time

monitor = FIMMonitor(DIRECTORIES_TO_WATCH)

# Deploy canaries
for directory in DIRECTORIES_TO_WATCH:
    monitor.canary_manager.create_canaries(directory)

# Populate initial file state without triggering events
for directory in DIRECTORIES_TO_WATCH:
    for root, _, files in os.walk(directory):
        for file in files:
            path = os.path.join(root, file)
            try:
                monitor.file_states[path] = os.stat(path).st_mtime
            except OSError:
                pass

print("Debug monitor running. Press Ctrl+C to stop.")
try:
    while True:
        monitor._scan()
        time.sleep(1)
except KeyboardInterrupt:
    monitor.stop()
