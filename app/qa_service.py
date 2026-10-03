"""Natural-language Q&A pipeline (#8).

Route question → validate → analytics facts → Claude narration grounded in facts.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from app.claude_client import AnthropicClaudeClient, ClaudeCompleter
from app.coverage import receipt_coverage
from app.qa_facts import _gather_facts, _to_question_query
from app.qa_models import QuestionFacts, QuestionResponse
from app.qa_prompts import NARRATION_SYSTEM, build_narration_user_message
from app.qa_routing import _route_question


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
        routed = _route_question(cleaned, client, coverage=coverage)
        query = _to_question_query(routed)
    except (ValidationError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        return _refusal(
            "I couldn't match that to a spending question I can answer. "
            "Try asking about spend by category, a daily average, or a share "
            "over a clear time range — for example, drinks in July.",
            code="routing_failed",
            detail=str(exc),
        )

    facts = _gather_facts(query, data_path=data_path, as_of=reference)
    answer = _narrate(cleaned, facts, client)
    return QuestionResponse(answer=answer, facts=facts, query=query)


def _narrate(question: str, facts: QuestionFacts, claude: ClaudeCompleter) -> str:
    payload = facts.model_dump(mode="json")
    return claude.complete(
        system=NARRATION_SYSTEM,
        user=build_narration_user_message(question, payload),
    )


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
