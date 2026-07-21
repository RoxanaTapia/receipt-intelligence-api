"""HTTP and pipeline tests for POST /questions (#8)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
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
    paths = client.get("/openapi.json").json()["paths"]
    assert "/questions" in paths
    assert "post" in paths["/questions"]
