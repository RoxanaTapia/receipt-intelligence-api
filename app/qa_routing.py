"""Read the JSON Claude returns when it decides what kind of spending question this is."""

from __future__ import annotations

import json
import re

from app.analytics_models import ReceiptCoverageResponse
from app.claude_client import ClaudeCompleter
from app.qa_models import RoutedQuery
from app.qa_prompts import ROUTING_SYSTEM, build_routing_user_message

_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _route_question(
    question: str,
    claude: ClaudeCompleter,
    *,
    coverage: ReceiptCoverageResponse,
) -> RoutedQuery:
    raw = claude.complete(
        system=ROUTING_SYSTEM,
        user=build_routing_user_message(
            question,
            earliest_date=coverage.earliest_date,
            latest_date=coverage.latest_date,
        ),
    )
    payload = _parse_json_object(raw)
    routed = RoutedQuery.model_validate(payload)
    if routed.error:
        raise ValueError(routed.error)
    if routed.intent is None or routed.time_range is None:
        raise ValueError("routing response missing intent or time_range")
    return routed


def _parse_json_object(raw: str) -> dict:
    text = raw.strip()
    text = _JSON_FENCE.sub("", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0 or end < start:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    return json.loads(text[start : end + 1])
