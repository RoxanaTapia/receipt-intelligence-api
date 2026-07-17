"""Load and flatten categorized receipt JSON from disk."""

from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from app.config import get_receipt_data_path
from app.models import CategorizedReceipt, LineItemRecord


@dataclass(frozen=True)
class LoadedReceipt:
    """One validated receipt file with its source path (needed for dedup)."""

    path: Path
    receipt: CategorizedReceipt


def load_receipts(data_path: Path | None = None) -> list[LoadedReceipt]:
    """Scan JSON files and return validated receipts with source paths.

    Skips files that are missing, unreadable, or fail categorization validation.
    """
    directory = data_path or get_receipt_data_path()
    if not directory.is_dir():
        return []

    loaded: list[LoadedReceipt] = []
    for json_file in sorted(directory.glob("*.json")):
        receipt = _parse_receipt_file(json_file)
        if receipt is not None:
            loaded.append(LoadedReceipt(path=json_file, receipt=receipt))
    return loaded


def load_line_items(data_path: Path | None = None) -> list[LineItemRecord]:
    """Scan JSON files and return flattened line-item records.

    Skips files that are missing, unreadable, or fail categorization validation.
    """
    records: list[LineItemRecord] = []
    for loaded in load_receipts(data_path):
        records.extend(_to_line_item_records(loaded.receipt))
    return records


def _parse_receipt_file(path: Path) -> CategorizedReceipt | None:
    try:
        return CategorizedReceipt.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError):
        return None


def _to_line_item_records(receipt: CategorizedReceipt) -> list[LineItemRecord]:
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
