"""Unit tests for budget and diet insight heuristics (#10)."""

from datetime import date
from pathlib import Path

from app.aggregation import aggregate_spending
from app.analytics_models import (
    AggregationResponse,
    AnalyticsQuery,
    AnalyticsTimeRange,
    CategorySpend,
    DeduplicationMeta,
    SummaryResponse,
)
from app.insight_models import Insight, InsightSeverity
from app.insight_service import (
    HIGH_DISCRETIONARY_WARN_PCT,
    SNACKS_SHARE_OF_GROCERY_WARN_PCT,
    generate_insights,
)
from app.models import Category
from app.summary import build_summary

AGG_FIXTURES = Path(__file__).parent / "fixtures" / "aggregation"


def _make_summary(by_category: list[tuple[Category, float]]) -> SummaryResponse:
    rows = [
        CategorySpend(category=category, total_spend=amount, line_item_count=1)
        for category, amount in by_category
    ]
    total = round(sum(amount for _, amount in by_category), 2)
    aggregation = AggregationResponse(
        start_date=date(2026, 5, 10),
        end_date=date(2026, 5, 16),
        categories=None,
        total_spend=total,
        receipt_count=1 if total else 0,
        line_item_count=len(rows),
        by_category=rows,
        deduplication=DeduplicationMeta(deduplicated_count=0),
    )
    return build_summary(aggregation)


def _by_type(insights: list[Insight], insight_type: str) -> Insight:
    return next(i for i in insights if i.insight_type == insight_type)


def test_snacks_share_warning_triggered() -> None:
    summary = _make_summary(
        [
            (Category.FOOD, 75.0),
            (Category.SNACKS, 25.0),
        ]
    )
    insight = _by_type(generate_insights(summary), "snacks_share_of_grocery")

    assert insight.triggered is True
    assert insight.severity == InsightSeverity.WARNING
    assert insight.value == 25.0
    assert insight.threshold == SNACKS_SHARE_OF_GROCERY_WARN_PCT
    assert "above the 20% guideline" in insight.text


def test_snacks_share_ok() -> None:
    summary = _make_summary(
        [
            (Category.FOOD, 90.0),
            (Category.SNACKS, 10.0),
        ]
    )
    insight = _by_type(generate_insights(summary), "snacks_share_of_grocery")

    assert insight.triggered is False
    assert insight.severity == InsightSeverity.OK
    assert insight.value == 10.0


def test_top_spend_category_info() -> None:
    summary = _make_summary(
        [
            (Category.FOOD, 70.0),
            (Category.SNACKS, 30.0),
        ]
    )
    insight = _by_type(generate_insights(summary), "top_spend_category")

    assert insight.severity == InsightSeverity.INFO
    assert insight.triggered is True
    assert insight.value == 70.0
    assert "food" in insight.text
    assert "70.0%" in insight.text


def test_discretionary_share_warning_triggered() -> None:
    summary = _make_summary(
        [
            (Category.FOOD, 50.0),
            (Category.SNACKS, 30.0),
            (Category.DRINKS, 20.0),
        ]
    )
    insight = _by_type(generate_insights(summary), "high_discretionary_share")

    assert insight.triggered is True
    assert insight.severity == InsightSeverity.WARNING
    assert insight.value == 50.0
    assert insight.threshold == HIGH_DISCRETIONARY_WARN_PCT


def test_discretionary_share_ok() -> None:
    summary = _make_summary(
        [
            (Category.FOOD, 75.0),
            (Category.SNACKS, 15.0),
            (Category.DRINKS, 10.0),
        ]
    )
    insight = _by_type(generate_insights(summary), "high_discretionary_share")

    assert insight.triggered is False
    assert insight.severity == InsightSeverity.OK
    assert insight.value == 25.0


def test_zero_total_no_warnings() -> None:
    summary = _make_summary([])
    insights = generate_insights(summary)

    assert len(insights) == 3
    assert all(i.severity != InsightSeverity.WARNING for i in insights)
    top = _by_type(insights, "top_spend_category")
    assert top.triggered is False
    assert "No spending" in top.text


def test_generate_insights_returns_all_three() -> None:
    summary = _make_summary(
        [
            (Category.FOOD, 60.0),
            (Category.SNACKS, 20.0),
            (Category.DRINKS, 20.0),
        ]
    )
    insights = generate_insights(summary)
    types = {i.insight_type for i in insights}

    assert len(insights) == 3
    assert types == {
        "snacks_share_of_grocery",
        "top_spend_category",
        "high_discretionary_share",
    }


def test_threshold_override() -> None:
    summary = _make_summary(
        [
            (Category.FOOD, 85.0),
            (Category.SNACKS, 15.0),
        ]
    )
    default = _by_type(generate_insights(summary), "snacks_share_of_grocery")
    overridden = _by_type(
        generate_insights(summary, snacks_share_warn_pct=10.0),
        "snacks_share_of_grocery",
    )

    assert default.triggered is False
    assert overridden.triggered is True
    assert overridden.threshold == 10.0


def test_insights_from_fixtures() -> None:
    aggregation = aggregate_spending(
        AnalyticsQuery(
            time_range=AnalyticsTimeRange(
                start_date=date(2026, 5, 1),
                end_date=date(2026, 5, 19),
            )
        ),
        data_path=AGG_FIXTURES,
        as_of=date(2026, 5, 19),
    )
    summary = build_summary(aggregation)
    insights = generate_insights(summary)

    assert len(insights) == 3
    assert all(isinstance(i.severity, InsightSeverity) for i in insights)
