import os
import time
import subprocess
import sys
import requests

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DIR = os.path.join(BASE_DIR, "test_monitored")
MAIN_SCRIPT = os.path.join(BASE_DIR, "main.py")

def run_ui_verification():
    print(f"Starting UI verification...")
    
    if not os.path.exists(TEST_DIR):
        os.makedirs(TEST_DIR)

    # Start FIM + Server
    fim_process = subprocess.Popen([sys.executable, MAIN_SCRIPT], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"FIM Server started with PID: {fim_process.pid}")
    
    time.sleep(10) # Wait for server startup

    try:
        # 1. Check if Dashboard is reachable
        try:
            response = requests.get("http://localhost:8000/")
            if response.status_code == 200:
                print("SUCCESS: Dashboard is accessible at http://localhost:8000/")
            else:
                print(f"FAILURE: Dashboard returned status {response.status_code}")
                return
        except requests.exceptions.ConnectionError:
            print("FAILURE: Could not connect to Dashboard server.")
            return

        # 2. Trigger Events (to ensure they are logged and hopefully broadcasted)
        # We can't easily verify WebSocket receipt in this script without a WS client, 
        # but if the server is up and FIM is running, it's a good sign.
        
        print("Triggering events...")
        test_file = os.path.join(TEST_DIR, "dashboard_test.txt")
        with open(test_file, "w") as f:
            f.write("Hello Dashboard")
        time.sleep(2)
        
        canary_path = os.path.join(TEST_DIR, "passwords.txt")
        if os.path.exists(canary_path):
             with open(canary_path, "a") as f:
                f.write("\nIntruder!")
        
        print("Events triggered. Please check the browser dashboard manually if possible.")

    finally:
        print("Stopping FIM Server...")
        fim_process.terminate()
        try:
            stdout, stderr = fim_process.communicate(timeout=5)
            print("\n--- SERVER LOGS ---")
            print(stdout.decode())
            print("\n--- SERVER ERRORS ---")
            print(stderr.decode())
        except Exception as e:
            print(f"Error reading logs: {e}")

if __name__ == "__main__":
    run_ui_verification()
