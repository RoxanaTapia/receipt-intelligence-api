"""Structured spending summaries on top of aggregation (#5).

Turns AggregationResponse rows into percentages, top-N categories, period
labels, and template-filled summary facts. See docs/analytics-schema.md.
"""

from __future__ import annotations

import calendar
from datetime import date

from app.analytics_models import (
    AggregationResponse,
    AnalyticsTimeRange,
    CategoryShare,
    PeriodDelta,
    SummaryFact,
    SummaryResponse,
    TimeRangePreset,
)


def category_percentage(category_spend: float, total_spend: float) -> float:
    """Share of total as 0–100. Zero total → 0 (never divide-by-zero)."""
    if total_spend == 0:
        return 0.0
    return round((category_spend / total_spend) * 100, 1)


def format_period_label(
    start: date,
    end: date,
    time_range: AnalyticsTimeRange | None = None,
) -> str:
    """Human-readable window for templates and API responses."""
    if time_range is not None and time_range.preset is not None:
        if time_range.preset == TimeRangePreset.LAST_WEEK:
            return "last 7 days"
        if time_range.preset == TimeRangePreset.LAST_MONTH:
            return "last 30 days"
        if time_range.preset == TimeRangePreset.LAST_N_DAYS:
            assert time_range.n_days is not None
            return f"last {time_range.n_days} days"

    if start == end:
        return _format_day(start)

    last_day = calendar.monthrange(start.year, start.month)[1]
    if (
        start.year == end.year
        and start.month == end.month
        and start.day == 1
        and end.day == last_day
    ):
        return start.strftime("%B %Y")

    return f"{_format_day(start)} to {_format_day(end)}"


def build_summary(
    aggregation: AggregationResponse,
    *,
    time_range: AnalyticsTimeRange | None = None,
    top_n: int = 3,
    previous: AggregationResponse | None = None,
) -> SummaryResponse:
    """Derive percentages, top categories, and summary facts from aggregation."""
    period_label = format_period_label(
        aggregation.start_date,
        aggregation.end_date,
        time_range,
    )
    by_category = [
        CategoryShare(
            category=row.category,
            total_spend=row.total_spend,
            percentage=category_percentage(row.total_spend, aggregation.total_spend),
            line_item_count=row.line_item_count,
        )
        for row in aggregation.by_category
    ]
    ranked = sorted(by_category, key=lambda row: row.total_spend, reverse=True)
    top_categories = ranked[: max(top_n, 0)]

    summary_facts = _build_facts(by_category, top_categories, period_label)
    period_delta = _period_delta(aggregation.total_spend, previous) if previous else None
    if period_delta is not None:
        summary_facts.append(_delta_fact(period_delta, period_label))

    return SummaryResponse(
        start_date=aggregation.start_date,
        end_date=aggregation.end_date,
        period_label=period_label,
        total_spend=aggregation.total_spend,
        by_category=by_category,
        top_categories=top_categories,
        summary_facts=summary_facts,
        period_delta=period_delta,
    )


def _build_facts(
    by_category: list[CategoryShare],
    top_categories: list[CategoryShare],
    period_label: str,
) -> list[SummaryFact]:
    facts: list[SummaryFact] = []
    for row in by_category:
        pct = row.percentage
        facts.append(
            SummaryFact(
                fact="category_share",
                value=pct,
                unit="%",
                text=(
                    f"You spent {pct}% on {row.category.value} {period_label}."
                ),
            )
        )
    if top_categories:
        top = top_categories[0]
        amount = _format_amount(top.total_spend)
        facts.append(
            SummaryFact(
                fact="top_category",
                value=top.category.value,
                unit=None,
                text=(
                    f"Your top category {period_label} was {top.category.value} "
                    f"({amount} EUR)."
                ),
            )
        )
    return facts


def _period_delta(
    current_total: float,
    previous: AggregationResponse,
) -> PeriodDelta:
    previous_total = previous.total_spend
    absolute = round(current_total - previous_total, 2)
    if previous_total == 0:
        percent = 0.0
    else:
        percent = round((absolute / previous_total) * 100, 1)
    return PeriodDelta(
        previous_total_spend=previous_total,
        absolute_change=absolute,
        percent_change=percent,
    )


def _delta_fact(delta: PeriodDelta, period_label: str) -> SummaryFact:
    return SummaryFact(
        fact="period_delta_pct",
        value=delta.percent_change,
        unit="%",
        text=(
            f"Total spend {period_label} changed by {delta.percent_change}% "
            f"vs the previous period."
        ),
    )


def _format_amount(value: float) -> str:
    return f"{value:.2f}"


def _format_day(value: date) -> str:
    return value.strftime("%d %B %Y").lstrip("0")
