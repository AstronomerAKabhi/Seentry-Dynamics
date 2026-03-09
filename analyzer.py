import psutil  # pyre-ignore[21]
import os
from fim_logger import logger

class Analyzer:
    @staticmethod
    def find_process(file_path):
        """
        Attempts to identify the process that has the given file open.
        Returns a string describing the process or None if not found.
        """
        try:
            # Normalize path for comparison
            target_path = os.path.abspath(file_path)
            
            # Iterate over all running processes
            for proc in psutil.process_iter(['pid', 'name', 'open_files']):
                try:
                    # We need to handle cases where open_files is None or access is denied
                    if not proc.info['open_files']:
                        continue
                        
                    for open_file in proc.info['open_files']:
                        if open_file.path == target_path:
                            return f"{proc.info['name']} (PID: {proc.info['pid']})"
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                    
        except Exception as e:
            logger.error(f"Error during process analysis: {e}")
            
        return None
