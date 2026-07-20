"""Analytics query and response schemas — the Module 4 data contract (#3).

Aggregation (#4), summaries (#5), REST (#6), and Q&A layers reuse these shapes
so time ranges, filters, and dedup metadata stay consistent.
See docs/analytics-schema.md.
"""

from datetime import date
from enum import Enum
from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.models import Category


class TimeRangePreset(str, Enum):
    """Named windows resolved relative to a reference date (usually today)."""

    LAST_WEEK = "last_week"
    LAST_MONTH = "last_month"
    LAST_N_DAYS = "last_N_days"


class AnalyticsTimeRange(BaseModel):
    """Select receipts by transaction ``date`` (YYYY-MM-DD), never ``categorized_at``.

    Exactly one mode is allowed:

    - ``preset`` of ``last_week`` or ``last_month``
    - ``preset`` of ``last_N_days`` plus ``n_days``
    - explicit ``start_date`` and ``end_date`` (inclusive)
    """

    preset: TimeRangePreset | None = None
    n_days: int | None = Field(default=None, ge=1)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_exactly_one_mode(self) -> Self:
        has_preset = self.preset is not None
        has_explicit = self.start_date is not None or self.end_date is not None

        if has_preset == has_explicit:
            raise ValueError(
                "Provide either a preset (last_week / last_month / last_N_days) "
                "or both start_date and end_date — not both, not neither"
            )

        if has_explicit:
            if self.start_date is None or self.end_date is None:
                raise ValueError("Both start_date and end_date are required for an explicit range")
            if self.start_date > self.end_date:
                raise ValueError("start_date must be on or before end_date")
            if self.n_days is not None:
                raise ValueError("n_days is only valid with preset last_N_days")
            return self

        if self.preset == TimeRangePreset.LAST_N_DAYS:
            if self.n_days is None:
                raise ValueError("n_days is required when preset is last_N_days")
        elif self.n_days is not None:
            raise ValueError("n_days is only valid with preset last_N_days")

        return self


class AnalyticsQuery(BaseModel):
    """Inputs shared by aggregation, REST endpoints, and Q&A routing."""

    time_range: AnalyticsTimeRange
    categories: list[Category] | None = Field(
        default=None,
        description="None or empty means all categories from the taxonomy",
    )


class CategorySpend(BaseModel):
    category: Category
    total_spend: float
    line_item_count: int = Field(ge=0)


class DeduplicationMeta(BaseModel):
    """How many hash-file duplicates were ignored when computing totals."""

    deduplicated_count: int = Field(
        ge=0,
        description="Count of superseded receipt files excluded from aggregation",
    )
    superseded_files: list[str] | None = Field(
        default=None,
        description="Optional debug list of ignored filenames",
    )


class AggregationResponse(BaseModel):
    """Canonical aggregation payload for summaries, REST, and Q&A grounding."""

    start_date: date = Field(description="Resolved inclusive range start (transaction dates)")
    end_date: date = Field(description="Resolved inclusive range end (transaction dates)")
    categories: list[Category] | None = Field(
        default=None,
        description="Categories included; None or empty means all",
    )
    total_spend: float
    receipt_count: int = Field(ge=0)
    line_item_count: int = Field(ge=0)
    by_category: list[CategorySpend]
    deduplication: DeduplicationMeta


class CategoryShare(BaseModel):
    """Category spend plus share of the period total (0–100)."""

    category: Category
    total_spend: float
    percentage: float = Field(ge=0, description="Share of total_spend; 0 when total is 0")
    line_item_count: int = Field(ge=0)


class SummaryFact(BaseModel):
    """One structured, testable claim — facts before Claude narration (#5)."""

    fact: str = Field(description="Stable key, e.g. category_share, top_category")
    value: float | str
    unit: str | None = Field(default=None, description="%, EUR, or null for labels")
    text: str = Field(description="Template-filled human-readable string")


class PeriodDelta(BaseModel):
    """Optional compare of this period's total against a previous aggregation."""

    previous_total_spend: float
    absolute_change: float
    percent_change: float = Field(
        description="Relative change vs previous total; 0 when previous total is 0",
    )


class SummaryResponse(BaseModel):
    """Human-readable summary facts derived from an AggregationResponse."""

    start_date: date
    end_date: date
    period_label: str
    total_spend: float
    by_category: list[CategoryShare]
    top_categories: list[CategoryShare]
    summary_facts: list[SummaryFact]
    period_delta: PeriodDelta | None = None


class ReceiptCoverageResponse(BaseModel):
    """Debug view of loaded files, dedup winners, and covered transaction dates."""

    data_path: str = Field(description="Resolved RECEIPT_DATA_PATH directory")
    data_path_exists: bool
    files_loaded: int = Field(ge=0, description="Valid JSON receipt files read from disk")
    logical_receipt_count: int = Field(
        ge=0,
        description="Receipts remaining after deduplication",
    )
    line_item_count: int = Field(ge=0, description="Line items on logical (deduped) receipts")
    earliest_date: date | None = Field(
        default=None,
        description="Earliest transaction date among logical receipts; null if none",
    )
    latest_date: date | None = Field(
        default=None,
        description="Latest transaction date among logical receipts; null if none",
    )
    loaded_files: list[str] = Field(
        default_factory=list,
        description="Filenames successfully loaded before dedup",
    )
    deduplication: DeduplicationMeta
