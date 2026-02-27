from config import DIRECTORIES_TO_WATCH
from monitor import FIMMonitor
from fim_logger import logger
import threading
from server import start_server

def run_monitor():
    try:
        logger.info("Initializing Behavioral File Integrity Monitor...")
        monitor = FIMMonitor(DIRECTORIES_TO_WATCH)
        monitor.start()
    except Exception as e:
        logger.critical(f"FIM Monitor CRASHED: {e}")
        import traceback
        logger.critical(traceback.format_exc())

if __name__ == "__main__":
    # Start FIM in a background thread
    monitor_thread = threading.Thread(target=run_monitor, daemon=True)
    monitor_thread.start()
    
    # Start Web Server (Main Thread)
    logger.info("Starting Dashboard Server on http://localhost:8000")
    start_server()
