"""Validation tests for the analytics query/response contract."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.analytics_models import (
    AggregationResponse,
    AnalyticsQuery,
    AnalyticsTimeRange,
    CategorySpend,
    DeduplicationMeta,
    TimeRangePreset,
)
from app.models import Category


def test_last_week_preset() -> None:
    tr = AnalyticsTimeRange(preset=TimeRangePreset.LAST_WEEK)
    assert tr.preset == TimeRangePreset.LAST_WEEK
    assert tr.n_days is None


def test_last_n_days_requires_n() -> None:
    with pytest.raises(ValidationError):
        AnalyticsTimeRange(preset=TimeRangePreset.LAST_N_DAYS)


def test_last_n_days_with_n() -> None:
    tr = AnalyticsTimeRange(preset=TimeRangePreset.LAST_N_DAYS, n_days=14)
    assert tr.n_days == 14


def test_explicit_range() -> None:
    tr = AnalyticsTimeRange(start_date=date(2026, 5, 1), end_date=date(2026, 5, 19))
    assert tr.start_date == date(2026, 5, 1)


def test_rejects_preset_and_explicit() -> None:
    with pytest.raises(ValidationError):
        AnalyticsTimeRange(
            preset=TimeRangePreset.LAST_WEEK,
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 7),
        )


def test_rejects_inverted_explicit_range() -> None:
    with pytest.raises(ValidationError):
        AnalyticsTimeRange(start_date=date(2026, 5, 10), end_date=date(2026, 5, 1))


def test_query_and_response_shapes() -> None:
    query = AnalyticsQuery(
        time_range=AnalyticsTimeRange(preset=TimeRangePreset.LAST_MONTH),
        categories=[Category.FOOD, Category.DRINKS],
    )
    response = AggregationResponse(
        start_date=date(2026, 4, 17),
        end_date=date(2026, 5, 16),
        categories=query.categories,
        total_spend=12.5,
        receipt_count=1,
        line_item_count=3,
        by_category=[
            CategorySpend(category=Category.FOOD, total_spend=10.0, line_item_count=2),
            CategorySpend(category=Category.DRINKS, total_spend=2.5, line_item_count=1),
        ],
        deduplication=DeduplicationMeta(deduplicated_count=1, superseded_files=["old.json"]),
    )
    assert response.deduplication.deduplicated_count == 1
    assert response.total_spend == 12.5
