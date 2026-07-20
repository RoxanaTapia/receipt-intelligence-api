"""Receipt coverage metadata for debug endpoints (#6).

Exposes how many files loaded, logical receipts after dedup, and the
transaction-date span — without computing spending totals.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from app.aggregation import deduplicate_receipts
from app.analytics_models import ReceiptCoverageResponse
from app.config import get_receipt_data_path
from app.loader import load_receipts


def receipt_coverage(data_path: Path | None = None) -> ReceiptCoverageResponse:
    """Summarize on-disk receipt files and dedup outcomes for observability."""
    directory = data_path or get_receipt_data_path()
    loaded = load_receipts(directory)
    winners, dedup_meta = deduplicate_receipts(loaded)

    dates = [date.fromisoformat(item.receipt.date) for item in winners]
    line_item_count = sum(len(item.receipt.line_items) for item in winners)

    return ReceiptCoverageResponse(
        data_path=str(directory),
        data_path_exists=directory.is_dir(),
        files_loaded=len(loaded),
        logical_receipt_count=len(winners),
        line_item_count=line_item_count,
        earliest_date=min(dates) if dates else None,
        latest_date=max(dates) if dates else None,
        loaded_files=[item.path.name for item in loaded],
        deduplication=dedup_meta,
    )
