import os
import sys
import ctypes
from fim_logger import logger

# Windows file attribute constants
_FILE_ATTRIBUTE_NORMAL = 0x80
_FILE_ATTRIBUTE_HIDDEN = 0x02

def _reset_attributes(path: str):
    """Clears hidden/read-only/system attributes so the file can be written or deleted."""
    if sys.platform == "win32" and hasattr(ctypes, "windll"):
        try:
            ctypes.windll.kernel32.SetFileAttributesW(path, _FILE_ATTRIBUTE_NORMAL)  # type: ignore
        except Exception:
            pass

def _hide_file(path: str):
    """Sets the hidden attribute on Windows."""
    if sys.platform == "win32" and hasattr(ctypes, "windll"):
        try:
            ctypes.windll.kernel32.SetFileAttributesW(path, _FILE_ATTRIBUTE_HIDDEN)  # type: ignore
        except Exception as e:
            logger.warning(f"Could not hide canary {path}: {e}")


class CanaryManager:
    def __init__(self):
        self.canaries: dict[str, str] = {}  # normalized_path -> content
        self.canary_names = [
            "passwords.txt", "config.bak", "admin_creds.xml", "wallet.dat",
            "salaryexpend.xls", "employee_records.xlsx", "financial_report_2024.pdf",
            "tax_returns.docx", "customer_data.csv", "private_keys.pem", "backup_db.sql"
        ]

    def create_canaries(self, directory):
        """Creates (or re-deploys) canary files in the specified directory."""
        if not os.path.exists(directory):
            return

        for name in self.canary_names:
            # Use normpath so keys always match what os.walk returns
            canary_path = os.path.normpath(os.path.join(directory, name))
            try:
                # Clear any restrictive attributes from a previous run before writing
                if os.path.exists(canary_path):
                    _reset_attributes(canary_path)

                content = f"This is a honeypot file. Do not touch. {name}"
                with open(canary_path, "w") as f:
                    f.write(content)

                _hide_file(canary_path)
                self.canaries[canary_path] = content
                logger.info(f"Deployed canary: {canary_path}")
            except Exception as e:
                logger.error(f"Failed to create canary {canary_path}: {e}")

    def is_canary(self, file_path: str) -> bool:
        """Checks if a file path belongs to a tracked canary (path-normalized)."""
        return os.path.normpath(file_path) in self.canaries

    def cleanup(self):
        """Removes all deployed canaries."""
        logger.info("Cleaning up canaries...")
        for path in list(self.canaries.keys()):
            if os.path.exists(path):
                try:
                    _reset_attributes(path)  # ensure it's deletable
                    os.remove(path)
                    logger.info(f"Removed canary: {path}")
                except Exception as e:
                    logger.error(f"Failed to remove canary {path}: {e}")
        self.canaries.clear()
