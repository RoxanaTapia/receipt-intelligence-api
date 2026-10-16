"""Build the spending totals the routed question needs."""

from __future__ import annotations

import re
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

DEFAULTED_TO_LAST_WEEK = "defaulted_time_range_to_last_week"
DEFAULTED_TO_REQUEST_WINDOW = "defaulted_time_range_to_request_window"
DEFAULTED_TO_CORPUS_SPAN = "defaulted_time_range_to_corpus_span"

_MONTH_NAMES = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
_RELATIVE_PHRASES = (
    "yesterday",
    "today",
    "last week",
    "past week",
    "this week",
    "last month",
    "past month",
    "this month",
    "last year",
    "this year",
)
_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_YEAR = re.compile(r"\b20\d{2}\b")
_LAST_N_DAYS = re.compile(r"\b(?:last|past|over the last)\s+\d+\s+days?\b")


def question_mentions_time(question: str) -> bool:
    """True when the wording names a period — month, ISO date, or rolling phrase."""
    lowered = question.lower()
    if any(phrase in lowered for phrase in _RELATIVE_PHRASES):
        return True
    if any(re.search(rf"\b{month}\b", lowered) for month in _MONTH_NAMES):
        return True
    return bool(
        _ISO_DATE.search(lowered)
        or _YEAR.search(lowered)
        or _LAST_N_DAYS.search(lowered)
    )


def apply_undated_window(
    query: QuestionQuery,
    *,
    question: str,
    request_start: date | None,
    request_end: date | None,
    corpus_start: date | None,
    corpus_end: date | None,
) -> QuestionQuery:
    """Replace a rolling preset when the question named no dates.

    Prefer the client window (same ISO pair as /analytics/summary). Without
    one, replace a rolling preset with the loaded receipt span so undated
    questions are not resolved against today. Explicit ranges from routing
    stay as-is when the client sent no window.
    """
    if question_mentions_time(question):
        return query

    if request_start is not None and request_end is not None:
        start, end = request_start, request_end
        warning = DEFAULTED_TO_REQUEST_WINDOW
    elif query.analytics.time_range.preset is not None and corpus_start is not None and corpus_end is not None:
        start, end = corpus_start, corpus_end
        warning = DEFAULTED_TO_CORPUS_SPAN
    else:
        return query

    analytics = query.analytics.model_copy(
        update={"time_range": AnalyticsTimeRange(start_date=start, end_date=end)}
    )
    warnings = [item for item in query.warnings if item != DEFAULTED_TO_LAST_WEEK]
    warnings.append(warning)
    return query.model_copy(update={"analytics": analytics, "warnings": warnings})


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
