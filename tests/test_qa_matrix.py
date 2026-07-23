"""Lightweight checks for Q&A test-matrix routing JSON (#11).

Keep ROUTING_CASES in sync with docs/question-answering-test-matrix.md.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Category
from app.qa_models import Intent, RoutedQuery
from app.qa_service import answer_question
from app.routers import questions as questions_router
from tests.test_qa_api import ScriptedClaude

AGG_FIXTURES = Path(__file__).parent / "fixtures" / "aggregation"

# Expected routing objects from docs/question-answering-test-matrix.md
ROUTING_CASES: list[tuple[str, dict]] = [
    (
        "L1",
        {
            "intent": "spending_by_category",
            "time_range": {"preset": "last_week"},
            "categories": ["food"],
            "compare_to": None,
            "warnings": [],
            "error": None,
        },
    ),
    (
        "L2",
        {
            "intent": "average_daily_spend",
            "time_range": {"preset": "last_week"},
            "categories": ["drinks"],
            "compare_to": None,
            "warnings": ["defaulted_time_range_to_last_week"],
            "error": None,
        },
    ),
    (
        "L3",
        {
            "intent": "category_share",
            "time_range": {"preset": "last_month"},
            "categories": ["snacks"],
            "compare_to": None,
            "warnings": [],
            "error": None,
        },
    ),
    (
        "L4",
        {
            "intent": "period_comparison",
            "time_range": {"preset": "last_week"},
            "categories": ["food"],
            "compare_to": None,
            "warnings": ["compare_to_defaults_to_previous_equal_window"],
            "error": None,
        },
    ),
    (
        "L5",
        {
            "intent": "general_insight",
            "time_range": {"preset": "last_week"},
            "categories": None,
            "compare_to": None,
            "warnings": ["defaulted_time_range_to_last_week"],
            "error": None,
        },
    ),
    (
        "L6",
        {
            "intent": "spending_by_category",
            "time_range": {"start_date": "2026-05-01", "end_date": "2026-05-19"},
            "categories": ["drinks"],
            "compare_to": None,
            "warnings": [],
            "error": None,
        },
    ),
    (
        "E2",
        {
            "intent": None,
            "time_range": None,
            "categories": None,
            "compare_to": None,
            "warnings": [],
            "error": "ambiguous_time",
        },
    ),
    (
        "E3",
        {
            "intent": None,
            "time_range": None,
            "categories": None,
            "compare_to": None,
            "warnings": [],
            "error": "unknown_category",
        },
    ),
    (
        "E4",
        {
            "intent": None,
            "time_range": None,
            "categories": None,
            "compare_to": None,
            "warnings": [],
            "error": "unsupported_question",
        },
    ),
    (
        "E5",
        {
            "intent": "spending_by_category",
            "time_range": {"start_date": "2026-05-01", "end_date": "2026-05-19"},
            "categories": ["food", "snacks"],
            "compare_to": None,
            "warnings": [],
            "error": None,
        },
    ),
    (
        "I1",
        {
            "intent": "general_insight",
            "time_range": {"start_date": "2026-05-01", "end_date": "2026-05-19"},
            "categories": None,
            "compare_to": None,
            "warnings": [],
            "error": None,
        },
    ),
]


@pytest.mark.parametrize("case_id,payload", ROUTING_CASES, ids=[c[0] for c in ROUTING_CASES])
def test_matrix_routing_json_validates(case_id: str, payload: dict) -> None:
    routed = RoutedQuery.model_validate(payload)
    if payload["error"]:
        assert routed.error == payload["error"]
        assert routed.intent is None
    else:
        assert routed.error is None
        assert routed.intent is not None
        assert routed.time_range is not None


def test_matrix_l6_drinks_key_fact() -> None:
    """L6: soda synonym + explicit dates → drinks total from fixtures."""
    route = dict(ROUTING_CASES[5][1])  # L6
    claude = ScriptedClaude(route, answer="You spent 6.78 on drinks.")
    result = answer_question(
        "How much on soda between 2026-05-01 and 2026-05-19?",
        data_path=AGG_FIXTURES,
        claude=claude,
    )
    assert result.facts is not None
    assert result.facts.aggregation.total_spend == pytest.approx(6.78)
    assert result.query is not None
    assert result.query.intent == Intent.SPENDING_BY_CATEGORY
    assert result.query.analytics.categories == [Category.DRINKS]


def test_matrix_e5_multi_category_key_fact() -> None:
    route = dict(ROUTING_CASES[9][1])  # E5
    claude = ScriptedClaude(route)
    result = answer_question(
        "How much did I spend on food and snacks between 2026-05-01 and 2026-05-19?",
        data_path=AGG_FIXTURES,
        claude=claude,
    )
    assert result.facts is not None
    assert result.facts.aggregation.total_spend == pytest.approx(6.68)


def test_matrix_i1_insight_key_facts() -> None:
    route = dict(ROUTING_CASES[10][1])  # I1
    claude = ScriptedClaude(route, answer="Here are your budget and diet signals.")
    result = answer_question(
        "How am I doing on budget and diet for 2026-05-01 to 2026-05-19?",
        data_path=AGG_FIXTURES,
        claude=claude,
    )
    assert result.facts is not None
    assert result.facts.insights is not None
    by_type = {i.insight_type: i for i in result.facts.insights}
    assert by_type["snacks_share_of_grocery"].triggered is True
    assert by_type["snacks_share_of_grocery"].value == pytest.approx(29.9, abs=0.1)
    assert by_type["high_discretionary_share"].triggered is True
    assert by_type["high_discretionary_share"].value == pytest.approx(63.8, abs=0.1)
    assert by_type["top_spend_category"].triggered is True


def test_matrix_e4_routing_error_refuses() -> None:
    route = dict(ROUTING_CASES[8][1])  # E4
    claude = ScriptedClaude(route)
    result = answer_question(
        "What is the meaning of life?",
        data_path=AGG_FIXTURES,
        claude=claude,
    )
    assert result.facts is None
    assert result.meta is not None
    assert result.meta["refusal"] == "routing_failed"


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_matrix_l6_via_http() -> None:
    route = dict(ROUTING_CASES[5][1])
    claude = ScriptedClaude(route, answer="Drinks total from fixtures.")
    app.dependency_overrides[questions_router.get_data_path] = lambda: AGG_FIXTURES
    app.dependency_overrides[questions_router.get_claude] = lambda: claude
    client = TestClient(app)
    response = client.post(
        "/questions",
        json={"question": "How much on soda between 2026-05-01 and 2026-05-19?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["facts"]["aggregation"]["total_spend"] == pytest.approx(6.78)
    # Ensure response JSON is serializable (Claude facts path)
    json.dumps(body)

