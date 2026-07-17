"""Unit tests for spending aggregation and receipt deduplication."""

from datetime import date
from pathlib import Path

from app.aggregation import (
    aggregate_spending,
    deduplicate_receipts,
    logical_receipt_key,
    resolve_time_range,
)
from app.analytics_models import AnalyticsQuery, AnalyticsTimeRange, TimeRangePreset
from app.loader import load_receipts
from app.models import Category

AGG_FIXTURES = Path(__file__).parent / "fixtures" / "aggregation"


def test_resolve_last_week() -> None:
    start, end = resolve_time_range(
        AnalyticsTimeRange(preset=TimeRangePreset.LAST_WEEK),
        as_of=date(2026, 5, 16),
    )
    assert start == date(2026, 5, 10)
    assert end == date(2026, 5, 16)


def test_resolve_last_n_days() -> None:
    start, end = resolve_time_range(
        AnalyticsTimeRange(preset=TimeRangePreset.LAST_N_DAYS, n_days=3),
        as_of=date(2026, 5, 19),
    )
    assert start == date(2026, 5, 17)
    assert end == date(2026, 5, 19)


def test_resolve_explicit_range() -> None:
    start, end = resolve_time_range(
        AnalyticsTimeRange(start_date=date(2026, 5, 1), end_date=date(2026, 5, 19)),
        as_of=date(2026, 12, 1),
    )
    assert start == date(2026, 5, 1)
    assert end == date(2026, 5, 19)


def test_logical_key_ignores_category() -> None:
    loaded = load_receipts(AGG_FIXTURES)
    older = next(r for r in loaded if r.path.name.endswith("aaaaaaaa.json") and "rewe" in r.path.name)
    newer = next(r for r in loaded if r.path.name.endswith("bbbbbbbb.json"))
    assert logical_receipt_key(older.receipt) == logical_receipt_key(newer.receipt)


def test_dedup_keeps_latest_categorized_at() -> None:
    winners, meta = deduplicate_receipts(load_receipts(AGG_FIXTURES))
    winner_names = {w.path.name for w in winners}

    assert "2026-05-15_rewe_bbbbbbbb.json" in winner_names
    assert "2026-05-15_rewe_aaaaaaaa.json" not in winner_names
    assert meta.deduplicated_count == 1
    assert meta.superseded_files == ["2026-05-15_rewe_aaaaaaaa.json"]


def test_aggregate_all_categories_in_range() -> None:
    response = aggregate_spending(
        AnalyticsQuery(
            time_range=AnalyticsTimeRange(start_date=date(2026, 5, 1), end_date=date(2026, 5, 19)),
            categories=None,
        ),
        data_path=AGG_FIXTURES,
        as_of=date(2026, 5, 19),
    )

    by_category = {row.category: row for row in response.by_category}
    assert response.receipt_count == 3  # ALDI + winning REWE May 15 + REWE May 19
    assert response.line_item_count == 7
    assert by_category[Category.FOOD].total_spend == 1.5 + 1.19 + 1.99
    assert by_category[Category.SNACKS].total_spend == 2.0
    assert by_category[Category.DRINKS].total_spend == 5.0 + 1.78
    assert by_category[Category.OTHER].total_spend == 0.3
    assert Category.OTHER in by_category  # from May 19; May 15 milk is food on winner
    assert response.total_spend == sum(row.total_spend for row in response.by_category)
    assert response.deduplication.deduplicated_count == 1


def test_aggregate_single_category_filter() -> None:
    response = aggregate_spending(
        AnalyticsQuery(
            time_range=AnalyticsTimeRange(preset=TimeRangePreset.LAST_N_DAYS, n_days=14),
            categories=[Category.DRINKS],
        ),
        data_path=AGG_FIXTURES,
        as_of=date(2026, 5, 19),
    )

    assert response.categories == [Category.DRINKS]
    assert response.start_date == date(2026, 5, 6)
    assert response.end_date == date(2026, 5, 19)
    assert len(response.by_category) == 1
    assert response.by_category[0].category == Category.DRINKS
    assert response.by_category[0].total_spend == 5.0 + 1.78
    assert response.total_spend == 6.78
    assert response.receipt_count == 2  # ALDI + REWE May 19


def test_aggregate_multiple_category_filter() -> None:
    response = aggregate_spending(
        AnalyticsQuery(
            time_range=AnalyticsTimeRange(start_date=date(2026, 5, 10), end_date=date(2026, 5, 10)),
            categories=[Category.FOOD, Category.SNACKS],
        ),
        data_path=AGG_FIXTURES,
        as_of=date(2026, 5, 19),
    )

    assert {row.category for row in response.by_category} == {Category.FOOD, Category.SNACKS}
    assert response.total_spend == 3.5
    assert response.receipt_count == 1


def test_aggregate_empty_directory(tmp_path: Path) -> None:
    response = aggregate_spending(
        AnalyticsQuery(time_range=AnalyticsTimeRange(preset=TimeRangePreset.LAST_WEEK)),
        data_path=tmp_path,
        as_of=date(2026, 5, 19),
    )

    assert response.total_spend == 0
    assert response.receipt_count == 0
    assert response.line_item_count == 0
    assert response.by_category == []
    assert response.deduplication.deduplicated_count == 0


def test_aggregate_no_receipts_in_range() -> None:
    response = aggregate_spending(
        AnalyticsQuery(
            time_range=AnalyticsTimeRange(start_date=date(2026, 1, 1), end_date=date(2026, 1, 31)),
        ),
        data_path=AGG_FIXTURES,
        as_of=date(2026, 5, 19),
    )

    assert response.total_spend == 0
    assert response.receipt_count == 0
    assert response.by_category == []
    # Dedup still runs across the loaded corpus
    assert response.deduplication.deduplicated_count == 1
