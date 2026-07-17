"""Smoke tests for the receipt loader."""

from pathlib import Path

from app.loader import load_line_items, load_receipts
from app.models import Category

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_load_categorized_fixture() -> None:
    records = load_line_items(FIXTURES_DIR)

    assert len(records) == 3
    assert all(record.date == "2026-05-19" for record in records)
    assert all(record.merchant == "REWE" for record in records)

    categories = {record.category for record in records}
    assert categories == {Category.DRINKS, Category.OTHER, Category.FOOD}

    apple_juice = next(r for r in records if r.description == "APFELSAFT")
    assert apple_juice.category == Category.DRINKS
    assert apple_juice.price == 1.78
    assert apple_juice.quantity == 2


def test_load_receipts_includes_source_path() -> None:
    loaded = load_receipts(FIXTURES_DIR)

    assert len(loaded) == 1
    assert loaded[0].path.name == "categorized_receipt.json"
    assert loaded[0].receipt.merchant == "REWE"
    assert loaded[0].receipt.categorized_at is not None


def test_skips_invalid_json(tmp_path: Path) -> None:
    (tmp_path / "bad.json").write_text('{"merchant": "REWE"}', encoding="utf-8")
    assert load_line_items(tmp_path) == []
    assert load_receipts(tmp_path) == []
