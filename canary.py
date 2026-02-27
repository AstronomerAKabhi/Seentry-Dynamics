import os
import logging
from fim_logger import logger

class CanaryManager:
    def __init__(self):
        self.canaries = {} # path -> original_content
        self.canary_names = [
            "passwords.txt", "config.bak", "admin_creds.xml", "wallet.dat",
            "salaryexpend.xls", "employee_records.xlsx", "financial_report_2024.pdf",
            "tax_returns.docx", "customer_data.csv", "private_keys.pem", "backup_db.sql"
        ]

    def create_canaries(self, directory):
        """Creates canary files in the specified directory."""
        if not os.path.exists(directory):
            return

        for name in self.canary_names:
            canary_path = os.path.join(directory, name)
            
            if os.path.exists(canary_path):
                logger.warning(f"Skipping canary creation: {canary_path} already exists.")
                # Do not track existing user files to prevent false alarms
                continue

            try:
                content = f"This is a honeypot file. Do not touch. {name}"
                with open(canary_path, "w") as f:
                    f.write(content)
                
                # Hide the file on Windows
                try:
                    import ctypes
                    import sys
                    if sys.platform == "win32" and hasattr(ctypes, "windll"):
                        FILE_ATTRIBUTE_HIDDEN = 0x02
                        ctypes.windll.kernel32.SetFileAttributesW(canary_path, FILE_ATTRIBUTE_HIDDEN) # type: ignore
                except Exception as e:
                    logger.warning(f"Could not hide canary {canary_path}: {e}")

                self.canaries[canary_path] = content
                logger.info(f"Deployed canary: {canary_path}")
            except Exception as e:
                logger.error(f"Failed to create canary {canary_path}: {e}")

    def is_canary(self, file_path):
        """Checks if the file path corresponds to a known canary."""
        return file_path in self.canaries

    def cleanup(self):
        """Removes all deployed canaries."""
        logger.info("Cleaning up canaries...")
        for path, original_content in list(self.canaries.items()):
            if original_content == "EXISTING":
                continue # Safety check against accidentally tracking/deleting real user files
            if os.path.exists(path):
                try:
                    os.remove(path)
                    logger.info(f"Removed canary: {path}")
                except Exception as e:
                    logger.error(f"Failed to remove canary {path}: {e}")
        self.canaries.clear()
