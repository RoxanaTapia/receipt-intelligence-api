"""Unit checks for Q&A prompt builders."""

from datetime import date

from app.qa_prompts import build_routing_user_message


def test_routing_message_includes_receipt_span() -> None:
    message = build_routing_user_message(
        "How much did I spend on drinks in July?",
        earliest_date=date(2026, 7, 1),
        latest_date=date(2026, 8, 31),
    )
    assert "2026-07-01 … 2026-08-31" in message
    assert "How much did I spend on drinks in July?" in message
    assert "resolved_month_year_from_receipt_coverage" in message


def test_routing_message_without_span() -> None:
    message = build_routing_user_message("How much last week?")
    assert "unknown (no receipt dates loaded)" in message
