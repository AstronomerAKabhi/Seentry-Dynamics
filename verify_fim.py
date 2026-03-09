import os
import time
import subprocess
import sys

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DIR = os.path.join(BASE_DIR, "test_monitored")
LOG_FILE = os.path.join(BASE_DIR, "fim_events.log")
MAIN_SCRIPT = os.path.join(BASE_DIR, "main.py")

def run_verification():
    print(f"Starting FIM verification...")
    
    # Ensure test directory exists
    if not os.path.exists(TEST_DIR):
        os.makedirs(TEST_DIR)

    # Start the FIM in a background process
    fim_process = subprocess.Popen([sys.executable, MAIN_SCRIPT], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"FIM started with PID: {fim_process.pid}")
    
    # Give it a moment to initialize
    time.sleep(5)

    try:
        # 1. Create a file
        test_file = os.path.join(TEST_DIR, "test_file.txt")
        print(f"Creating file: {test_file}")
        with open(test_file, "w") as f:
            f.write("Initial content.")
            # Keep file open for a bit to allow psutil to catch it? 
            # Actually, for 'created' event, the file might be closed quickly.
            # Let's try to keep it open for modification test.
            time.sleep(2) 

        time.sleep(2)

        # 2. Modify the file (keep it open longer to ensure detection)
        print(f"Modifying file: {test_file}")
        with open(test_file, "a") as f:
            f.write("\nModified content.")
            time.sleep(3) # Hold the lock/handle

        time.sleep(2)

        # 3. Check logs
        if not os.path.exists(LOG_FILE):
            print("ERROR: Log file not found!")
            return

        print("Reading logs...")
        with open(LOG_FILE, "r") as f:
            logs = f.read()
            print(logs)

        # Verification logic
        if "test_file.txt" in logs:
            print("SUCCESS: File events detected.")
        else:
            print("FAILURE: File events NOT detected.")

        if "python" in logs or "main.py" in logs or str(os.getpid()) in logs: 
             # Note: The modifier is THIS script, so we expect python.exe or similar.
             # However, since we are running this script via python, the process name should be python/python.exe
            print("SUCCESS: Process attribution found (python/python.exe).")
        else:
            print("WARNING: Process attribution might have failed (expected python/python.exe).")

    finally:
        # Cleanup
        print("Stopping FIM...")
        fim_process.terminate()
        try:
            stdout, stderr = fim_process.communicate(timeout=10)
            print("FIM STDOUT:", stdout.decode())
            print("FIM STDERR:", stderr.decode())
        except Exception as e:
            print(f"Error reading FIM output: {e}")

if __name__ == "__main__":
    run_verification()
