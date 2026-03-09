import os

# Directories to monitor
# For testing, we will monitor a 'test_monitored' directory in the current folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_MONITORED_DIR = os.path.join(BASE_DIR, "test_monitored")

# Ensure the directory exists
if not os.path.exists(TEST_MONITORED_DIR):
    os.makedirs(TEST_MONITORED_DIR)

DIRECTORIES_TO_WATCH = [
    TEST_MONITORED_DIR
]

LOG_FILE = os.path.join(BASE_DIR, "fim_events.log")
