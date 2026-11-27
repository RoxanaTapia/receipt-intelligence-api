"""Spending aggregation over categorized receipts (#4).

Resolves time ranges, deduplicates logical receipts per the #3 policy, then
sums line-item prices by category. See docs/analytics-schema.md.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.analytics_models import (
    AggregationResponse,
    AnalyticsQuery,
    AnalyticsTimeRange,
    CategorySpend,
    DeduplicationMeta,
    TimeRangePreset,
)
from app.loader import LoadedReceipt, load_receipts
from app.models import CategorizedReceipt, Category


def resolve_time_range(time_range: AnalyticsTimeRange, as_of: date) -> tuple[date, date]:
    """Turn a preset or explicit range into inclusive transaction-date bounds."""
    if time_range.start_date is not None and time_range.end_date is not None:
        return time_range.start_date, time_range.end_date

    if time_range.preset == TimeRangePreset.LAST_WEEK:
        days = 7
    elif time_range.preset == TimeRangePreset.LAST_MONTH:
        days = 30
    elif time_range.preset == TimeRangePreset.LAST_N_DAYS:
        assert time_range.n_days is not None  # validated by AnalyticsTimeRange
        days = time_range.n_days
    else:
        raise ValueError("time_range must have a preset or explicit dates")

    start = as_of - timedelta(days=days - 1)
    return start, as_of


def logical_receipt_key(receipt: CategorizedReceipt) -> tuple:
    """Identity of one shopping trip — category excluded so re-labels still match."""
    items = tuple(
        sorted((item.description, item.quantity, item.price) for item in receipt.line_items)
    )
    return (receipt.date, receipt.merchant, items)


def deduplicate_receipts(
    loaded: list[LoadedReceipt],
) -> tuple[list[LoadedReceipt], DeduplicationMeta]:
    """Keep the latest categorized_at per logical key; drop superseded hash files."""
    winners: dict[tuple, LoadedReceipt] = {}
    superseded: list[str] = []

    for candidate in loaded:
        key = logical_receipt_key(candidate.receipt)
        existing = winners.get(key)
        if existing is None:
            winners[key] = candidate
            continue

        if _is_newer(candidate, existing):
            superseded.append(existing.path.name)
            winners[key] = candidate
        else:
            superseded.append(candidate.path.name)

    meta = DeduplicationMeta(
        deduplicated_count=len(superseded),
        superseded_files=superseded or None,
    )
    return list(winners.values()), meta


def aggregate_spending(
    query: AnalyticsQuery,
    *,
    data_path: Path | None = None,
    as_of: date | None = None,
) -> AggregationResponse:
    """Load receipts, dedup, filter by range/categories, and return category totals."""
    reference = as_of or date.today()
    start_date, end_date = resolve_time_range(query.time_range, reference)

    winners, dedup_meta = deduplicate_receipts(load_receipts(data_path))
    in_range = [
        loaded
        for loaded in winners
        if start_date <= _parse_receipt_date(loaded.receipt.date) <= end_date
    ]

    allowed = _allowed_categories(query.categories)
    spend_by_category: dict[Category, float] = defaultdict(float)
    count_by_category: dict[Category, int] = defaultdict(int)
    line_item_count = 0
    receipt_count = 0

    for loaded in in_range:
        matched = [item for item in loaded.receipt.line_items if item.category in allowed]
        if not matched:
            continue
        receipt_count += 1
        for item in matched:
            spend_by_category[item.category] += item.price
            count_by_category[item.category] += 1
            line_item_count += 1

    by_category = [
        CategorySpend(
            category=category,
            total_spend=spend_by_category[category],
            line_item_count=count_by_category[category],
        )
        for category in Category
        if count_by_category[category] > 0
    ]

    return AggregationResponse(
        start_date=start_date,
        end_date=end_date,
        categories=query.categories,
        total_spend=sum(row.total_spend for row in by_category),
        receipt_count=receipt_count,
        line_item_count=line_item_count,
        by_category=by_category,
        deduplication=dedup_meta,
    )


def _allowed_categories(categories: list[Category] | None) -> set[Category]:
    if not categories:
        return set(Category)
    return set(categories)


def _parse_receipt_date(value: str) -> date:
    return date.fromisoformat(value)


def _is_newer(candidate: LoadedReceipt, incumbent: LoadedReceipt) -> bool:
    return _version_timestamp(candidate) > _version_timestamp(incumbent)


def _version_timestamp(loaded: LoadedReceipt) -> datetime:
    """Prefer categorized_at; fall back to file mtime when the timestamp is missing."""
    raw = loaded.receipt.categorized_at
    if raw:
        return _parse_categorized_at(raw)
    mtime = loaded.path.stat().st_mtime
    return datetime.fromtimestamp(mtime, tz=timezone.utc)


def _parse_categorized_at(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
