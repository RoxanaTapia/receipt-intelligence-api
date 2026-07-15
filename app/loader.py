"""Load and flatten categorized receipt JSON from disk."""

from pathlib import Path

from pydantic import ValidationError

from app.config import get_receipt_data_path
from app.models import CategorizedReceipt, LineItemRecord


def load_line_items(data_path: Path | None = None) -> list[LineItemRecord]:
    """Scan JSON files and return flattened line-item records.

    Skips files that are missing, unreadable, or fail categorization validation.
    """
    directory = data_path or get_receipt_data_path()
    if not directory.is_dir():
        return []

    records: list[LineItemRecord] = []
    for json_file in sorted(directory.glob("*.json")):
        records.extend(_load_receipt_file(json_file))
    return records


def _load_receipt_file(path: Path) -> list[LineItemRecord]:
    try:
        receipt = CategorizedReceipt.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError):
        return []

    return [
        LineItemRecord(
            date=receipt.date,
            merchant=receipt.merchant,
            category=item.category,
            price=item.price,
            quantity=item.quantity,
            description=item.description,
        )
        for item in receipt.line_items
    ]
