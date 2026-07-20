"""Analytics REST endpoints (#6).

Thin HTTP adapter: query-string params → AnalyticsQuery → aggregation/summary/
coverage services. Response models match docs/analytics-schema.md.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError

from app.aggregation import aggregate_spending
from app.analytics_models import (
    AggregationResponse,
    AnalyticsQuery,
    AnalyticsTimeRange,
    ReceiptCoverageResponse,
    SummaryResponse,
    TimeRangePreset,
)
from app.config import get_receipt_data_path
from app.coverage import receipt_coverage
from app.models import Category
from app.summary import build_summary

router = APIRouter(prefix="/analytics", tags=["analytics"])


def get_data_path() -> Path:
    """Resolved receipt directory — overridden in tests."""
    return get_receipt_data_path()


def build_analytics_query(
    preset: TimeRangePreset | None = None,
    n_days: int | None = Query(default=None, ge=1),
    start_date: date | None = None,
    end_date: date | None = None,
    categories: list[Category] | None = Query(default=None),
) -> AnalyticsQuery:
    """Map flat query params to the #3 AnalyticsQuery contract."""
    try:
        return AnalyticsQuery(
            time_range=AnalyticsTimeRange(
                preset=preset,
                n_days=n_days,
                start_date=start_date,
                end_date=end_date,
            ),
            categories=categories,
        )
    except ValidationError as exc:
        # Drop raw input/ctx — they may contain date/enum objects that break JSON.
        detail = [
            {"type": err["type"], "loc": list(err.get("loc", ())), "msg": err["msg"]}
            for err in exc.errors()
        ]
        raise HTTPException(status_code=422, detail=detail) from exc


@router.get("/spending", response_model=AggregationResponse)
def get_spending(
    query: AnalyticsQuery = Depends(build_analytics_query),
    data_path: Path = Depends(get_data_path),
) -> AggregationResponse:
    """Category totals for a time range (after receipt deduplication)."""
    return aggregate_spending(query, data_path=data_path)


@router.get("/summary", response_model=SummaryResponse)
def get_summary(
    query: AnalyticsQuery = Depends(build_analytics_query),
    data_path: Path = Depends(get_data_path),
) -> SummaryResponse:
    """Structured summary facts derived from spending aggregation."""
    aggregation = aggregate_spending(query, data_path=data_path)
    return build_summary(aggregation, time_range=query.time_range)


@router.get("/receipts", response_model=ReceiptCoverageResponse)
def get_receipts(
    data_path: Path = Depends(get_data_path),
) -> ReceiptCoverageResponse:
    """Coverage and dedup metadata for debugging duplicate hash files."""
    return receipt_coverage(data_path)
