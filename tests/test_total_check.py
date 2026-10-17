"""Printed-total check: match, mismatch, missing, rounding, tax/fees."""

from pathlib import Path

from app.analytics_models import PrintedTotalStatus
from app.loader import LoadedReceipt
from app.models import CategorizedReceipt, Category, LineItem
from app.total_check import (
    DEFAULT_TOLERANCE,
    check_printed_total,
    computed_receipt_total,
    summarize_printed_totals,
)


def _item(price: float, description: str = "MILCH") -> LineItem:
    return LineItem(
        description=description,
        quantity=1,
        price=price,
        category=Category.FOOD,
    )


def _receipt(
    *,
    total: float | None,
    prices: list[float],
    tax: float | None = None,
    fees: float | None = None,
) -> CategorizedReceipt:
    return CategorizedReceipt(
        merchant="REWE",
        date="2026-05-19",
        total=total,
        tax=tax,
        fees=fees,
        line_items=[_item(price, description=f"ITEM-{index}") for index, price in enumerate(prices)],
    )


def test_match_when_printed_equals_line_items() -> None:
    receipt = _receipt(total=3.19, prices=[1.19, 2.00])
    result = check_printed_total(receipt, source_file="ok.json")

    assert result.status is PrintedTotalStatus.MATCH
    assert result.printed_total == 3.19
    assert result.computed_total == 3.19
    assert result.difference == 0.0
    assert result.tolerance == DEFAULT_TOLERANCE


def test_mismatch_when_printed_differs_beyond_tolerance() -> None:
    receipt = _receipt(total=5.66, prices=[1.78, 0.30, 1.99])
    result = check_printed_total(receipt, source_file="gap.json")

    assert result.computed_total == 4.07
    assert result.difference == -1.59
    assert result.status is PrintedTotalStatus.MISMATCH


def test_missing_when_printed_total_omitted() -> None:
    receipt = _receipt(total=None, prices=[1.19, 2.00])
    result = check_printed_total(receipt, source_file="no-total.json")

    assert result.status is PrintedTotalStatus.MISSING
    assert result.printed_total is None
    assert result.computed_total == 3.19
    assert result.difference is None


def test_rounding_within_tolerance_is_match() -> None:
    receipt = _receipt(total=3.31, prices=[1.10, 2.20])
    result = check_printed_total(receipt, source_file="round.json")

    assert result.computed_total == 3.30
    assert abs(result.difference or 0) <= DEFAULT_TOLERANCE
    assert result.status is PrintedTotalStatus.MATCH


def test_rounding_outside_tolerance_is_mismatch() -> None:
    receipt = _receipt(total=3.33, prices=[1.10, 2.20])
    result = check_printed_total(receipt, source_file="over.json")

    assert result.computed_total == 3.30
    assert abs(result.difference or 0) > DEFAULT_TOLERANCE
    assert result.status is PrintedTotalStatus.MISMATCH


def test_float_cents_round_to_printed_total() -> None:
    # 0.1 + 0.2 is 0.300...04 in binary float; cents rounding must still match.
    receipt = _receipt(total=0.30, prices=[0.1, 0.2])
    assert computed_receipt_total(receipt) == 0.30
    result = check_printed_total(receipt, source_file="cents.json")
    assert result.status is PrintedTotalStatus.MATCH


def test_tax_and_fees_are_added_when_present() -> None:
    receipt = _receipt(total=11.50, prices=[10.00], tax=1.00, fees=0.50)
    result = check_printed_total(receipt, source_file="tax.json")

    assert result.computed_total == 11.50
    assert result.status is PrintedTotalStatus.MATCH


def test_accepts_printed_total_alias() -> None:
    receipt = CategorizedReceipt.model_validate(
        {
            "merchant": "ALDI",
            "date": "2026-05-10",
            "printed_total": 8.50,
            "line_items": [
                {
                    "description": "BANANEN",
                    "quantity": 1,
                    "price": 8.50,
                    "category": "food",
                }
            ],
        }
    )
    assert receipt.total == 8.50
    result = check_printed_total(receipt, source_file="alias.json")
    assert result.status is PrintedTotalStatus.MATCH


def test_summary_counts_by_status(tmp_path: Path) -> None:
    match = LoadedReceipt(path=tmp_path / "match.json", receipt=_receipt(total=3.19, prices=[1.19, 2.00]))
    mismatch = LoadedReceipt(
        path=tmp_path / "mismatch.json",
        receipt=_receipt(total=9.00, prices=[1.00]),
    )
    missing = LoadedReceipt(
        path=tmp_path / "missing.json",
        receipt=_receipt(total=None, prices=[1.00]),
    )

    summary = summarize_printed_totals([match, mismatch, missing])

    assert summary.match_count == 1
    assert summary.mismatch_count == 1
    assert summary.missing_count == 1
    assert summary.tolerance == DEFAULT_TOLERANCE
    assert [row.status.value for row in summary.receipts] == [
        "match",
        "mismatch",
        "missing",
    ]
