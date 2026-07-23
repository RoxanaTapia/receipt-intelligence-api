"""Structured budget and diet insight objects (#10).

Heuristics produce these shapes; Claude may only narrate them — never invent
amounts. Thresholds live in ``insight_service`` and are documented in
``docs/question-answering.md``.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class InsightSeverity(str, Enum):
    """How strongly the insight should be emphasized in narration."""

    INFO = "info"
    WARNING = "warning"
    OK = "ok"


class Insight(BaseModel):
    """One rule-based insight grounded in analytics shares and totals."""

    insight_type: str
    severity: InsightSeverity
    triggered: bool
    value: float
    threshold: float | None = None
    unit: str
    text: str


class InsightResponse(BaseModel):
    """REST payload for ``GET /analytics/insights``."""

    period_label: str
    total_spend: float
    insights: list[Insight]
