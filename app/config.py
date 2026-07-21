"""Application configuration from environment variables."""

from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_RECEIPT_DATA_PATH = Path("../receipt-intelligence-n8n/data/receipts")
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"


def get_receipt_data_path() -> Path:
    """Return the directory containing categorized receipt JSON files."""
    raw = os.environ.get("RECEIPT_DATA_PATH")
    if raw:
        return Path(raw)
    return DEFAULT_RECEIPT_DATA_PATH


def get_anthropic_api_key() -> str | None:
    """Anthropic API key for Q&A routing and narration (#8)."""
    raw = os.environ.get("ANTHROPIC_API_KEY")
    return raw.strip() if raw and raw.strip() else None


def get_anthropic_model() -> str:
    """Claude model id — override with ANTHROPIC_MODEL when needed."""
    return os.environ.get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL).strip()
