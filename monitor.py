import time
import os
from analyzer import Analyzer
from fim_logger import logger
from canary import CanaryManager

class FIMMonitor:
    def __init__(self, directories):
        self.directories = directories
        self.file_states = {} # path -> mtime
        self.running = False
        self.canary_manager = CanaryManager()

    def _scan(self):
        for directory in self.directories:
            if not os.path.exists(directory):
                continue

            current_files = set()
            try:
                for root, _, files in os.walk(directory):
                    for file in files:
                        file_path = os.path.normpath(os.path.join(root, file))
                        current_files.add(file_path)

                        try:
                            mtime = os.stat(file_path).st_mtime
                        except OSError:
                            continue

                        if file_path not in self.file_states:
                            self.file_states[file_path] = mtime
                            self._handle_event("CREATED", file_path)
                        elif mtime != self.file_states[file_path]:
                            self.file_states[file_path] = mtime
                            self._handle_event("MODIFIED", file_path)
            except Exception as e:
                logger.error(f"Error scanning {directory}: {e}")

            for file_path in list(self.file_states.keys()):
                if file_path.startswith(directory) and file_path not in current_files:
                    del self.file_states[file_path]
                    self._handle_event("DELETED", file_path)

    def _handle_event(self, event_type, file_path):
        try:
            if self.canary_manager.is_canary(file_path):
                # For canary triggers, attempt process attribution (attacker may still have file open)
                process_info = Analyzer.find_process(file_path)
                culprit = process_info if process_info else "Unknown (handle already closed)"
                logger.critical(f"!!! CANARY TRIGGERED !!! Event: {event_type} | File: {file_path}")
                logger.critical(f"POTENTIAL RANSOMWARE OR INTRUSION DETECTED! Culprit: {culprit}")
                return

            # For normal events, skip expensive process scan — in polling-based FIM the
            # file handle is already closed by the time we detect the change.
            logger.info(f"Event: {event_type} | File: {file_path}")
        except Exception as e:
            logger.error(f"Error handling event {event_type} for {file_path}: {e}")

    def start(self):
        self.running = True
        logger.info("Starting Manual FIM Monitor...")
        
        # Deploy Canaries
        for directory in self.directories:
            self.canary_manager.create_canaries(directory)
        
        # Initial scan to populate state without triggering events
        for directory in self.directories:
            for root, _, files in os.walk(directory):
                for file in files:
                    path = os.path.normpath(os.path.join(root, file))
                    try:
                        self.file_states[path] = os.stat(path).st_mtime
                    except OSError:
                        pass

        try:
            scan_count = 0
            while self.running:
                self._scan()
                scan_count += 1
                if scan_count % 20 == 0:
                    logger.info(f"HEARTBEAT: Monitor Active | Tracked Files: {len(self.file_states)}")
                time.sleep(0.25)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        logger.info("Stopping FIM Monitor...")
        self.running = False
        self.canary_manager.cleanup()
