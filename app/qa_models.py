"""Q&A request/response and routing validation models (#8).

RoutedQuery mirrors docs/question-answering.md so Claude JSON validates against
the same AnalyticsQuery rules used by aggregation.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.analytics_models import (
    AggregationResponse,
    AnalyticsQuery,
    AnalyticsTimeRange,
    SummaryResponse,
)
from app.models import Category


class Intent(str, Enum):
    """Exactly one intent per question (see docs/question-answering.md)."""

    SPENDING_BY_CATEGORY = "spending_by_category"
    AVERAGE_DAILY_SPEND = "average_daily_spend"
    CATEGORY_SHARE = "category_share"
    PERIOD_COMPARISON = "period_comparison"
    GENERAL_INSIGHT = "general_insight"


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, description="Natural-language spending question")


class RoutedQuery(BaseModel):
    """Parsed routing output before AnalyticsQuery validation."""

    intent: Intent | None = None
    time_range: AnalyticsTimeRange | None = None
    categories: list[Category] | None = None
    compare_to: AnalyticsTimeRange | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class QuestionQuery(BaseModel):
    """Echo of the validated analytics query used for this answer."""

    intent: Intent
    analytics: AnalyticsQuery
    compare_to: AnalyticsTimeRange | None = None
    warnings: list[str] = Field(default_factory=list)


class QuestionFacts(BaseModel):
    """Structured grounding payload — Claude may only narrate these numbers."""

    aggregation: AggregationResponse
    summary: SummaryResponse | None = None
    average_daily_spend: float | None = None
    day_count: int | None = None
    previous_aggregation: AggregationResponse | None = None


class QuestionResponse(BaseModel):
    answer: str
    facts: QuestionFacts | None = None
    query: QuestionQuery | None = None
    meta: dict[str, Any] | None = Field(
        default=None,
        description="Optional refusal codes / debug (e.g. no_receipt_data)",
    )
