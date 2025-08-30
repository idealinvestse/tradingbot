"""A script to download the precompiled TA-Lib wheel for Windows."""

import logging
import platform
import sys
from pathlib import Path

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

# --- Configuration ---
# URL for the unofficial Windows binaries.
# This source is widely used but rely on it at your own risk.
BASE_URL = "https://sourceforge.net/projects/talib-whl/files/ta_lib_0.4.28"

# Define the specific wheel file for Python 3.10 on 64-bit Windows
PYTHON_VERSION = "cp310"
ARCHITECTURE = "win_amd64"
TA_LIB_VERSION = "0.4.28"

WHEEL_FILENAME = f"TA_Lib-{TA_LIB_VERSION}-{PYTHON_VERSION}-{PYTHON_VERSION}-{ARCHITECTURE}.whl"
DOWNLOAD_URL = f"{BASE_URL}/{WHEEL_FILENAME}/download"

# --- Main Execution ---


def download_file(url: str, target_path: Path) -> bool:
    """Downloads a file from a URL to a target path."""
    if target_path.exists():
        logging.info(f"'{target_path.name}' already exists. Skipping download.")
        return True

    logging.info(f"Downloading '{WHEEL_FILENAME}' from {url}...")
    try:
        response = requests.get(url, timeout=60, stream=True)
        response.raise_for_status()  # Raise an exception for bad status codes

        with open(target_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        logging.info(f"Successfully downloaded to '{target_path}'.")
        return True

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to download file: {e}")
        logging.error(
            "Please download the file manually from a reliable source "
            "(e.g., Christoph Gohlke's website) and place it in the project root."
        )
        return False


def main():
    """Main function to run the download script."""
    # Ensure the script is run on Windows
    if platform.system() != "Windows":
        logging.warning("This script is intended for Windows only. Exiting.")
        sys.exit(0)

    # The target directory is the project root (one level up from 'scripts')
    project_root = Path(__file__).parent.parent
    target_file_path = project_root / WHEEL_FILENAME

    if download_file(DOWNLOAD_URL, target_file_path):
        logging.info("\nNext steps:")
        logging.info(f"1. Run: pip install {WHEEL_FILENAME}")
        logging.info("2. Run: pip install -e .[dev,test]")


if __name__ == "__main__":
    main()
