"""HTTP and pipeline tests for POST /questions (#8)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.qa_facts import (
    DEFAULTED_TO_CORPUS_SPAN,
    DEFAULTED_TO_REQUEST_WINDOW,
    question_mentions_time,
)
from app.qa_service import answer_question
from app.routers import questions as questions_router

AGG_FIXTURES = Path(__file__).parent / "fixtures" / "aggregation"


class ScriptedClaude:
    """Deterministic Claude stub: first call routes, second narrates."""

    def __init__(self, route_json: dict, answer: str = "Grounded answer.") -> None:
        self.route_json = route_json
        self.answer = answer
        self.calls: list[tuple[str, str]] = []

    def complete(self, *, system: str, user: str) -> str:
        self.calls.append((system, user))
        if len(self.calls) == 1:
            return json.dumps(self.route_json)
        return self.answer


def _client(data_path: Path, claude: ScriptedClaude) -> TestClient:
    app.dependency_overrides[questions_router.get_data_path] = lambda: data_path
    app.dependency_overrides[questions_router.get_claude] = lambda: claude
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_questions_endpoint_returns_answer_and_facts() -> None:
    claude = ScriptedClaude(
        {
            "intent": "spending_by_category",
            "time_range": {"start_date": "2026-05-01", "end_date": "2026-05-19"},
            "categories": ["food"],
            "compare_to": None,
            "warnings": [],
            "error": None,
        },
        answer="You spent money on food in that period.",
    )
    client = _client(AGG_FIXTURES, claude)
    response = client.post(
        "/questions",
        json={"question": "How much did I spend on healthy food last week?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "You spent money on food in that period."
    assert body["facts"] is not None
    assert "aggregation" in body["facts"]
    assert body["facts"]["aggregation"]["total_spend"] >= 0
    assert body["query"]["intent"] == "spending_by_category"
    assert body["query"]["analytics"]["categories"] == ["food"]
    assert len(claude.calls) == 2
    narrate_user = claude.calls[1][1]
    total = body["facts"]["aggregation"]["total_spend"]
    assert str(total) in narrate_user or f"{total:.2f}" in narrate_user


def test_average_daily_spend_includes_derived_fact() -> None:
    claude = ScriptedClaude(
        {
            "intent": "average_daily_spend",
            "time_range": {"start_date": "2026-05-01", "end_date": "2026-05-19"},
            "categories": ["drinks"],
            "compare_to": None,
            "warnings": ["defaulted_time_range_to_last_week"],
            "error": None,
        }
    )
    result = answer_question(
        "What's my average daily spending on drinks?",
        data_path=AGG_FIXTURES,
        claude=claude,
    )
    assert result.facts is not None
    assert result.facts.day_count == 19
    assert result.facts.average_daily_spend is not None
    assert result.query is not None
    assert result.query.intent.value == "average_daily_spend"


def test_no_receipt_data_refuses_without_claude(tmp_path: Path) -> None:
    claude = ScriptedClaude({"intent": None, "error": "should_not_be_called"})
    result = answer_question(
        "How much on food?",
        data_path=tmp_path,
        claude=claude,
    )
    assert result.facts is None
    assert result.query is None
    assert result.meta is not None
    assert result.meta["refusal"] == "no_receipt_data"
    assert claude.calls == []


def test_routing_failure_refuses() -> None:
    claude = ScriptedClaude(
        {
            "intent": None,
            "time_range": None,
            "categories": None,
            "compare_to": None,
            "warnings": [],
            "error": "unsupported_question",
        }
    )
    result = answer_question(
        "What is the meaning of life?",
        data_path=AGG_FIXTURES,
        claude=claude,
    )
    assert result.facts is None
    assert result.meta is not None
    assert result.meta["refusal"] == "routing_failed"
    assert len(claude.calls) == 1


def test_missing_api_key_returns_503() -> None:
    app.dependency_overrides.clear()
    with patch("app.routers.questions.get_anthropic_api_key", return_value=None):
        client = TestClient(app)
        response = client.post("/questions", json={"question": "How much on food?"})
    assert response.status_code == 503


def test_openapi_includes_questions() -> None:
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    assert "/questions" in paths
    assert "post" in paths["/questions"]
    body_schema = spec["components"]["schemas"]["QuestionRequest"]
    assert "start_date" in body_schema["properties"]
    assert "end_date" in body_schema["properties"]
    assert "question" in body_schema["required"]
    assert "start_date" not in body_schema.get("required", [])


_PER_CATEGORY_ROUTE = {
    "intent": "spending_by_category",
    "time_range": {"preset": "last_week"},
    "categories": None,
    "compare_to": None,
    "warnings": ["defaulted_time_range_to_last_week"],
    "error": None,
}


def test_undated_per_category_uses_request_window() -> None:
    """Demo bug: undated 'per category' must not resolve last_week vs today."""
    claude = ScriptedClaude(_PER_CATEGORY_ROUTE, answer="Here is spend by category.")
    client = _client(AGG_FIXTURES, claude)
    response = client.post(
        "/questions",
        json={
            "question": "How much did I spend per category?",
            "start_date": "2026-05-01",
            "end_date": "2026-05-19",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["facts"] is not None
    aggregation = body["facts"]["aggregation"]
    assert aggregation["start_date"] == "2026-05-01"
    assert aggregation["end_date"] == "2026-05-19"
    assert aggregation["total_spend"] == 13.76
    by_category = {row["category"]: row["total_spend"] for row in aggregation["by_category"]}
    assert by_category == {
        "food": 4.68,
        "snacks": 2.0,
        "drinks": 6.78,
        "other": 0.3,
    }
    assert body["query"]["intent"] == "spending_by_category"
    assert body["query"]["analytics"]["categories"] is None
    assert body["query"]["warnings"] == [DEFAULTED_TO_REQUEST_WINDOW]


def test_undated_question_defaults_to_corpus_span() -> None:
    claude = ScriptedClaude(_PER_CATEGORY_ROUTE)
    result = answer_question(
        "How much did I spend per category?",
        data_path=AGG_FIXTURES,
        claude=claude,
    )
    assert result.facts is not None
    assert result.facts.aggregation.start_date == date(2026, 5, 10)
    assert result.facts.aggregation.end_date == date(2026, 5, 19)
    assert result.facts.aggregation.total_spend == 13.76
    assert result.query is not None
    assert result.query.warnings == [DEFAULTED_TO_CORPUS_SPAN]


def test_last_week_question_keeps_preset_despite_request_window() -> None:
    claude = ScriptedClaude(
        {
            "intent": "spending_by_category",
            "time_range": {"preset": "last_week"},
            "categories": ["food"],
            "compare_to": None,
            "warnings": [],
            "error": None,
        }
    )
    result = answer_question(
        "How much did I spend on healthy food last week?",
        data_path=AGG_FIXTURES,
        claude=claude,
        as_of=date(2026, 5, 16),
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 31),
    )
    assert result.facts is not None
    assert result.facts.aggregation.start_date == date(2026, 5, 10)
    assert result.facts.aggregation.end_date == date(2026, 5, 16)
    assert result.query is not None
    assert result.query.analytics.time_range.preset is not None


def test_named_month_range_is_not_replaced_by_request_window() -> None:
    claude = ScriptedClaude(
        {
            "intent": "spending_by_category",
            "time_range": {"start_date": "2026-05-01", "end_date": "2026-05-31"},
            "categories": ["drinks"],
            "compare_to": None,
            "warnings": ["resolved_month_year_from_receipt_coverage"],
            "error": None,
        }
    )
    result = answer_question(
        "How much did I spend on drinks in May?",
        data_path=AGG_FIXTURES,
        claude=claude,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 31),
    )
    assert result.facts is not None
    assert result.facts.aggregation.start_date == date(2026, 5, 1)
    assert result.facts.aggregation.end_date == date(2026, 5, 31)
    assert result.facts.aggregation.total_spend == 6.78


def test_one_sided_date_returns_422() -> None:
    claude = ScriptedClaude(_PER_CATEGORY_ROUTE)
    client = _client(AGG_FIXTURES, claude)
    response = client.post(
        "/questions",
        json={"question": "How much did I spend per category?", "start_date": "2026-05-01"},
    )
    assert response.status_code == 422
    assert claude.calls == []


def test_reversed_dates_return_422() -> None:
    claude = ScriptedClaude(_PER_CATEGORY_ROUTE)
    client = _client(AGG_FIXTURES, claude)
    response = client.post(
        "/questions",
        json={
            "question": "How much did I spend per category?",
            "start_date": "2026-08-31",
            "end_date": "2026-07-01",
        },
    )
    assert response.status_code == 422


def test_unknown_body_field_is_ignored() -> None:
    claude = ScriptedClaude(_PER_CATEGORY_ROUTE, answer="Totals from the corpus.")
    client = _client(AGG_FIXTURES, claude)
    response = client.post(
        "/questions",
        json={
            "question": "How much did I spend per category?",
            "unexpected_field": "ok",
        },
    )
    assert response.status_code == 200
    assert response.json()["facts"]["aggregation"]["total_spend"] == 13.76


def test_question_mentions_time_detects_periods() -> None:
    assert question_mentions_time("How much did I spend per category?") is False
    assert question_mentions_time("What's my average daily spending on drinks?") is False
    assert question_mentions_time("How much did I spend on healthy food last week?") is True
    assert question_mentions_time("How much did I spend on drinks in July?") is True
    assert question_mentions_time("How much between 2026-05-01 and 2026-05-19?") is True
