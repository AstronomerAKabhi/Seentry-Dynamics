import time
import os
from analyzer import Analyzer
from logger import logger

from canary import CanaryManager

class FIMMonitor:
    def __init__(self, directories):
        self.directories = directories
        self.file_states = {} # path -> mtime
        self.running = False
        self.canary_manager = CanaryManager()

    def _scan(self):
        for directory in self.directories:
            # Ensure canaries exist (in case they were deleted)
            # self.canary_manager.create_canaries(directory) # Re-deploy if missing? Maybe too aggressive.
            # Let's just create them once at start.
            
            if not os.path.exists(directory):
                continue
                
            current_files = set()
            try:
                # Simple recursive scan or flat scan? 
                # Let's do flat for now as per previous debug, but we can do recursive easily.
                # Let's stick to the config. If directories are passed, we scan them.
                # For recursive, we'd need os.walk. Let's do os.walk.
                for root, _, files in os.walk(directory):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # print(f"DEBUG: Saw file {file_path}") # Too verbose
                        if "test" in file.lower() or "new" in file.lower():
                             # logger.info(f"DEBUG: Scanned {file}") 
                             pass
                        current_files.add(file_path)
                        
                        try:
                            mtime = os.stat(file_path).st_mtime
                        except OSError:
                            continue # File might be gone

                        if file_path not in self.file_states:
                            # Created
                            self.file_states[file_path] = mtime
                            self._handle_event("CREATED", file_path)
                        elif mtime != self.file_states[file_path]:
                            # Modified
                            self.file_states[file_path] = mtime
                            self._handle_event("MODIFIED", file_path)
            except Exception as e:
                logger.error(f"Error scanning {directory}: {e}")

            # Check for deleted files
            # We need to track which files belong to this directory to detect deletions efficiently.
            # For simplicity in this fallback, we'll just check all known files that start with this directory.
            # (This is inefficient for large numbers of files but fine for this task).
            # A better way: maintain state per directory.
            
            # Let's just iterate a copy of keys
            for file_path in list(self.file_states.keys()):
                if file_path.startswith(directory):
                    if file_path not in current_files:
                        # Deleted
                        del self.file_states[file_path]
                        self._handle_event("DELETED", file_path)

    def _handle_event(self, event_type, file_path):
        print(f"DEBUG: Handling event {event_type} for {file_path}") # Direct console output
        process_str = "Unknown Process"
        
        try:
            is_canary = self.canary_manager.is_canary(file_path)
            
            if is_canary:
                logger.critical(f"!!! CANARY TRIGGERED !!! Event: {event_type} | File: {file_path}")
                logger.critical("POTENTIAL RANSOMWARE OR INTRUSION DETECTED!")
                
                # process_info = Analyzer.find_process(file_path)
                # if process_info:
                #     logger.critical(f"Culprit Process: {process_info}")
                # else:
                #     logger.critical("Culprit Process: Unknown (could not identify open handle)")
                    
                return # Skip normal logging

            if event_type in ["CREATED", "MODIFIED"]:
                # process_info = Analyzer.find_process(file_path)
                # if process_info:
                #     process_str = process_info
                pass
            
            log_msg = f"Event: {event_type} | File: {file_path} | Process: {process_str}"
            print(f"DEBUG: Logging message: {log_msg}")
            logger.info(log_msg)
        except Exception as e:
            print(f"ERROR in _handle_event: {e}")
            logger.error(f"Error handling event: {e}")

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
                    path = os.path.join(root, file)
                    try:
                        self.file_states[path] = os.stat(path).st_mtime
                    except OSError:
                        pass

        try:
            scan_count = 0
            while self.running:
                self._scan()
                scan_count += 1
                if scan_count % 5 == 0:
                    # Log heartbeat to UI to prove it's alive
                    logger.info(f"HEARTBEAT: Monitor Active | Tracked Files: {len(self.file_states)}")
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        logger.info("Stopping FIM Monitor...")
        self.running = False
        self.canary_manager.cleanup()
