"""Application configuration from environment variables."""

from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_RECEIPT_DATA_PATH = Path("../receipt-intelligence-n8n/data/receipts")


def get_receipt_data_path() -> Path:
    """Return the directory containing categorized receipt JSON files."""
    raw = os.environ.get("RECEIPT_DATA_PATH")
    if raw:
        return Path(raw)
    return DEFAULT_RECEIPT_DATA_PATH
