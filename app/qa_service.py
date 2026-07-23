"""Natural-language Q&A pipeline (#8).

Route question → validate → analytics facts → Claude narration grounded in facts.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

from pydantic import ValidationError

from app.aggregation import aggregate_spending, resolve_time_range
from app.analytics_models import AggregationResponse, AnalyticsQuery, AnalyticsTimeRange
from app.claude_client import AnthropicClaudeClient, ClaudeCompleter
from app.coverage import receipt_coverage
from app.insight_service import generate_insights
from app.qa_models import (
    Intent,
    QuestionFacts,
    QuestionQuery,
    QuestionResponse,
    RoutedQuery,
)
from app.qa_prompts import (
    NARRATION_SYSTEM,
    ROUTING_SYSTEM,
    build_narration_user_message,
    build_routing_user_message,
)
from app.summary import build_summary

_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def answer_question(
    question: str,
    *,
    data_path: Path | None = None,
    claude: ClaudeCompleter | None = None,
    as_of: date | None = None,
) -> QuestionResponse:
    """Run the full Q&A pipeline and return answer + facts + query."""
    cleaned = question.strip()
    if not cleaned:
        return _refusal("Please ask a spending question.", code="empty_question")

    coverage = receipt_coverage(data_path)
    if coverage.files_loaded == 0 or coverage.logical_receipt_count == 0:
        return _refusal(
            "I don't have any receipt data loaded yet, so I can't answer spending questions.",
            code="no_receipt_data",
        )

    client = claude or AnthropicClaudeClient()
    reference = as_of or date.today()

    try:
        routed = _route_question(cleaned, client)
        query = _to_question_query(routed)
    except (ValidationError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        return _refusal(
            "I couldn't map that to a spending question I support. "
            "Try asking about spend by category, daily averages, or shares over a time range.",
            code="routing_failed",
            detail=str(exc),
        )

    facts = _gather_facts(query, data_path=data_path, as_of=reference)
    answer = _narrate(cleaned, facts, client)
    return QuestionResponse(answer=answer, facts=facts, query=query)


def _route_question(question: str, claude: ClaudeCompleter) -> RoutedQuery:
    raw = claude.complete(
        system=ROUTING_SYSTEM,
        user=build_routing_user_message(question),
    )
    payload = _parse_json_object(raw)
    routed = RoutedQuery.model_validate(payload)
    if routed.error:
        raise ValueError(routed.error)
    if routed.intent is None or routed.time_range is None:
        raise ValueError("routing response missing intent or time_range")
    return routed


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


def _narrate(question: str, facts: QuestionFacts, claude: ClaudeCompleter) -> str:
    payload = facts.model_dump(mode="json")
    return claude.complete(
        system=NARRATION_SYSTEM,
        user=build_narration_user_message(question, payload),
    )


def _parse_json_object(raw: str) -> dict:
    text = raw.strip()
    text = _JSON_FENCE.sub("", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0 or end < start:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    return json.loads(text[start : end + 1])


def _refusal(
    answer: str,
    *,
    code: str,
    detail: str | None = None,
) -> QuestionResponse:
    meta: dict = {"refusal": code}
    if detail:
        meta["detail"] = detail
    return QuestionResponse(answer=answer, facts=None, query=None, meta=meta)
