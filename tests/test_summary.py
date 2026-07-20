"""Unit tests for structured spending summaries (#5)."""

from datetime import date
from pathlib import Path

from app.aggregation import aggregate_spending
from app.analytics_models import (
    AggregationResponse,
    AnalyticsQuery,
    AnalyticsTimeRange,
    CategorySpend,
    DeduplicationMeta,
    TimeRangePreset,
)
from app.models import Category
from app.summary import build_summary, category_percentage, format_period_label

AGG_FIXTURES = Path(__file__).parent / "fixtures" / "aggregation"


def test_category_percentage_normal() -> None:
    assert category_percentage(3.4, 10.0) == 34.0
    assert category_percentage(1.0, 3.0) == 33.3


def test_category_percentage_zero_total() -> None:
    assert category_percentage(0.0, 0.0) == 0.0
    assert category_percentage(5.0, 0.0) == 0.0


def test_format_period_label_presets() -> None:
    start, end = date(2026, 5, 10), date(2026, 5, 16)
    assert (
        format_period_label(start, end, AnalyticsTimeRange(preset=TimeRangePreset.LAST_WEEK))
        == "last 7 days"
    )
    assert (
        format_period_label(start, end, AnalyticsTimeRange(preset=TimeRangePreset.LAST_MONTH))
        == "last 30 days"
    )
    assert (
        format_period_label(
            start,
            end,
            AnalyticsTimeRange(preset=TimeRangePreset.LAST_N_DAYS, n_days=14),
        )
        == "last 14 days"
    )


def test_format_period_label_calendar_month() -> None:
    assert (
        format_period_label(date(2024, 3, 1), date(2024, 3, 31)) == "March 2024"
    )


def test_top_categories_ordered_by_spend() -> None:
    aggregation = AggregationResponse(
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 31),
        categories=None,
        total_spend=100.0,
        receipt_count=2,
        line_item_count=4,
        by_category=[
            CategorySpend(category=Category.SNACKS, total_spend=20.0, line_item_count=1),
            CategorySpend(category=Category.FOOD, total_spend=50.0, line_item_count=2),
            CategorySpend(category=Category.DRINKS, total_spend=30.0, line_item_count=1),
        ],
        deduplication=DeduplicationMeta(deduplicated_count=0),
    )
    summary = build_summary(aggregation, top_n=2)

    assert [row.category for row in summary.top_categories] == [
        Category.FOOD,
        Category.DRINKS,
    ]
    assert summary.by_category[0].percentage == 20.0  # snacks order preserved from input
    food = next(row for row in summary.by_category if row.category == Category.FOOD)
    assert food.percentage == 50.0

    top_fact = next(f for f in summary.summary_facts if f.fact == "top_category")
    assert top_fact.value == "food"
    assert "50.00 EUR" in top_fact.text
    assert "May 2026" in top_fact.text


def test_zero_total_yields_zero_percentages() -> None:
    aggregation = AggregationResponse(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        categories=None,
        total_spend=0.0,
        receipt_count=0,
        line_item_count=0,
        by_category=[
            CategorySpend(category=Category.SNACKS, total_spend=0.0, line_item_count=0),
        ],
        deduplication=DeduplicationMeta(deduplicated_count=0),
    )
    summary = build_summary(aggregation)

    assert summary.by_category[0].percentage == 0.0
    share = next(f for f in summary.summary_facts if f.fact == "category_share")
    assert share.value == 0.0
    assert share.unit == "%"
    assert "0%" in share.text


def test_summary_last_week_from_fixtures() -> None:
    time_range = AnalyticsTimeRange(preset=TimeRangePreset.LAST_WEEK)
    aggregation = aggregate_spending(
        AnalyticsQuery(time_range=time_range),
        data_path=AGG_FIXTURES,
        as_of=date(2026, 5, 16),
    )
    summary = build_summary(aggregation, time_range=time_range)

    assert summary.period_label == "last 7 days"
    assert summary.start_date == date(2026, 5, 10)
    assert summary.end_date == date(2026, 5, 16)
    assert summary.total_spend > 0
    assert any(f.fact == "category_share" for f in summary.summary_facts)
    assert any(f.fact == "top_category" for f in summary.summary_facts)


def test_summary_last_month_from_fixtures() -> None:
    time_range = AnalyticsTimeRange(preset=TimeRangePreset.LAST_MONTH)
    aggregation = aggregate_spending(
        AnalyticsQuery(time_range=time_range),
        data_path=AGG_FIXTURES,
        as_of=date(2026, 5, 19),
    )
    summary = build_summary(aggregation, time_range=time_range)

    assert summary.period_label == "last 30 days"
    assert summary.start_date == date(2026, 4, 20)
    assert summary.end_date == date(2026, 5, 19)
    assert summary.total_spend > 0
    assert len(summary.top_categories) >= 1


def test_optional_period_delta() -> None:
    current = AggregationResponse(
        start_date=date(2026, 5, 10),
        end_date=date(2026, 5, 16),
        categories=None,
        total_spend=120.0,
        receipt_count=1,
        line_item_count=1,
        by_category=[
            CategorySpend(category=Category.FOOD, total_spend=120.0, line_item_count=1),
        ],
        deduplication=DeduplicationMeta(deduplicated_count=0),
    )
    previous = AggregationResponse(
        start_date=date(2026, 5, 3),
        end_date=date(2026, 5, 9),
        categories=None,
        total_spend=100.0,
        receipt_count=1,
        line_item_count=1,
        by_category=[
            CategorySpend(category=Category.FOOD, total_spend=100.0, line_item_count=1),
        ],
        deduplication=DeduplicationMeta(deduplicated_count=0),
    )
    summary = build_summary(
        current,
        time_range=AnalyticsTimeRange(preset=TimeRangePreset.LAST_WEEK),
        previous=previous,
    )

    assert summary.period_delta is not None
    assert summary.period_delta.absolute_change == 20.0
    assert summary.period_delta.percent_change == 20.0
    assert any(f.fact == "period_delta_pct" for f in summary.summary_facts)


def test_period_delta_zero_previous_total() -> None:
    current = AggregationResponse(
        start_date=date(2026, 5, 10),
        end_date=date(2026, 5, 16),
        categories=None,
        total_spend=50.0,
        receipt_count=1,
        line_item_count=1,
        by_category=[
            CategorySpend(category=Category.FOOD, total_spend=50.0, line_item_count=1),
        ],
        deduplication=DeduplicationMeta(deduplicated_count=0),
    )
    previous = AggregationResponse(
        start_date=date(2026, 5, 3),
        end_date=date(2026, 5, 9),
        categories=None,
        total_spend=0.0,
        receipt_count=0,
        line_item_count=0,
        by_category=[],
        deduplication=DeduplicationMeta(deduplicated_count=0),
    )
    summary = build_summary(current, previous=previous)
    assert summary.period_delta is not None
    assert summary.period_delta.percent_change == 0.0
