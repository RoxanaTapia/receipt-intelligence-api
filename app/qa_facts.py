"""Build the spending totals the routed question needs."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from app.aggregation import aggregate_spending, resolve_time_range
from app.analytics_models import (
    AggregationResponse,
    AnalyticsQuery,
    AnalyticsTimeRange,
)
from app.insight_service import generate_insights
from app.qa_models import Intent, QuestionFacts, QuestionQuery, RoutedQuery
from app.summary import build_summary


def _to_question_query(routed: RoutedQuery) -> QuestionQuery:
    assert routed.intent is not None
    assert routed.time_range is not None
    analytics = AnalyticsQuery(
        time_range=routed.time_range,
        categories=routed.categories,
    )
    return QuestionQuery(
        intent=routed.intent,
        analytics=analytics,
        compare_to=routed.compare_to,
        warnings=list(routed.warnings),
    )


def _gather_facts(
    query: QuestionQuery,
    *,
    data_path: Path | None,
    as_of: date,
) -> QuestionFacts:
    aggregation = aggregate_spending(
        query.analytics,
        data_path=data_path,
        as_of=as_of,
    )

    previous: AggregationResponse | None = None
    summary = None
    average_daily = None
    day_count = None
    insights = None

    if query.intent == Intent.PERIOD_COMPARISON:
        previous = _previous_aggregation(
            query,
            data_path=data_path,
            as_of=as_of,
            current=aggregation,
        )

    if query.intent in {
        Intent.CATEGORY_SHARE,
        Intent.GENERAL_INSIGHT,
        Intent.PERIOD_COMPARISON,
    }:
        summary = build_summary(
            aggregation,
            time_range=query.analytics.time_range,
            previous=previous,
        )

    if query.intent == Intent.GENERAL_INSIGHT and summary is not None:
        insights = generate_insights(summary)

    if query.intent == Intent.AVERAGE_DAILY_SPEND:
        day_count = (aggregation.end_date - aggregation.start_date).days + 1
        average_daily = round(aggregation.total_spend / day_count, 2) if day_count else 0.0

    return QuestionFacts(
        aggregation=aggregation,
        summary=summary,
        average_daily_spend=average_daily,
        day_count=day_count,
        previous_aggregation=previous,
        insights=insights,
    )


def _previous_aggregation(
    query: QuestionQuery,
    *,
    data_path: Path | None,
    as_of: date,
    current: AggregationResponse,
) -> AggregationResponse:
    compare_range = query.compare_to
    if compare_range is None:
        span_days = (current.end_date - current.start_date).days + 1
        previous_end = current.start_date - timedelta(days=1)
        previous_start = previous_end - timedelta(days=span_days - 1)
        compare_range = AnalyticsTimeRange(
            start_date=previous_start,
            end_date=previous_end,
        )
    else:
        resolve_time_range(compare_range, as_of)

    previous_query = AnalyticsQuery(
        time_range=compare_range,
        categories=query.analytics.categories,
    )
    return aggregate_spending(previous_query, data_path=data_path, as_of=as_of)
