import os
import time
import subprocess
import sys

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DIR = os.path.join(BASE_DIR, "test_monitored")
LOG_FILE = os.path.join(BASE_DIR, "fim_events.log")
MAIN_SCRIPT = os.path.join(BASE_DIR, "main.py")

def run_canary_verification():
    print(f"Starting Canary verification...")
    
    if not os.path.exists(TEST_DIR):
        os.makedirs(TEST_DIR)

    # Start FIM
    fim_process = subprocess.Popen([sys.executable, MAIN_SCRIPT], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"FIM started with PID: {fim_process.pid}")
    
    time.sleep(5) # Wait for startup and canary deployment

    try:
        # Check if canaries were created
        canary_path = os.path.join(TEST_DIR, "passwords.txt")
        if os.path.exists(canary_path):
            print(f"SUCCESS: Canary file found at {canary_path}")
        else:
            print(f"FAILURE: Canary file NOT found at {canary_path}")
            return

        # Trigger the trap!
        print(f"Touching the canary: {canary_path}")
        with open(canary_path, "a") as f:
            f.write("\nI am an intruder!")
            time.sleep(2)

        time.sleep(10)

        # Check logs for CRITICAL alert
        print("Reading logs...")
        with open(LOG_FILE, "r") as f:
            logs = f.read()
            print(logs)

        if "!!! CANARY TRIGGERED !!!" in logs:
            print("SUCCESS: Canary Alert Detected!")
        else:
            print("FAILURE: Canary Alert NOT Detected.")

    finally:
        print("Stopping FIM...")
        fim_process.terminate()
        fim_process.wait()
        
        # Check cleanup
        if not os.path.exists(canary_path):
             print("SUCCESS: Canary cleanup verified.")
        else:
             print("WARNING: Canary file still exists after cleanup (might take a moment or failed).")

if __name__ == "__main__":
    run_canary_verification()
