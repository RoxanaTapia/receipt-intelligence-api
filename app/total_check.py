"""Compare computed receipt totals to the amount printed on the receipt.

Spending analytics still sum line-item prices. This check is a separate
data-quality signal: whether extraction captured the printed total.
"""

from __future__ import annotations

from app.analytics_models import (
    PrintedTotalCheck,
    PrintedTotalCheckSummary,
    PrintedTotalStatus,
)
from app.loader import LoadedReceipt
from app.models import CategorizedReceipt

DEFAULT_TOLERANCE = 0.02


def computed_receipt_total(receipt: CategorizedReceipt) -> float:
    """Sum line-item prices plus optional tax and fees, rounded to cents.

    Each ``price`` is already the line total (quantity is not multiplied).
    """
    items = sum(item.price for item in receipt.line_items)
    extras = (receipt.tax or 0) + (receipt.fees or 0)
    return round(items + extras, 2)


def check_printed_total(
    receipt: CategorizedReceipt,
    *,
    source_file: str,
    tolerance: float = DEFAULT_TOLERANCE,
) -> PrintedTotalCheck:
    """Return match / mismatch / missing for one receipt."""
    computed = computed_receipt_total(receipt)
    printed = receipt.total
    if printed is None:
        return PrintedTotalCheck(
            source_file=source_file,
            merchant=receipt.merchant,
            date=receipt.date,
            printed_total=None,
            computed_total=computed,
            difference=None,
            status=PrintedTotalStatus.MISSING,
            tolerance=tolerance,
        )

    difference = round(computed - printed, 2)
    status = (
        PrintedTotalStatus.MATCH
        if abs(difference) <= tolerance
        else PrintedTotalStatus.MISMATCH
    )
    return PrintedTotalCheck(
        source_file=source_file,
        merchant=receipt.merchant,
        date=receipt.date,
        printed_total=printed,
        computed_total=computed,
        difference=difference,
        status=status,
        tolerance=tolerance,
    )


def summarize_printed_totals(
    loaded: list[LoadedReceipt],
    *,
    tolerance: float = DEFAULT_TOLERANCE,
) -> PrintedTotalCheckSummary:
    """Run the printed-total check on each loaded receipt (usually dedup winners)."""
    receipts = [
        check_printed_total(
            item.receipt,
            source_file=item.path.name,
            tolerance=tolerance,
        )
        for item in loaded
    ]
    return PrintedTotalCheckSummary(
        match_count=sum(1 for row in receipts if row.status is PrintedTotalStatus.MATCH),
        mismatch_count=sum(
            1 for row in receipts if row.status is PrintedTotalStatus.MISMATCH
        ),
        missing_count=sum(
            1 for row in receipts if row.status is PrintedTotalStatus.MISSING
        ),
        tolerance=tolerance,
        receipts=receipts,
    )
