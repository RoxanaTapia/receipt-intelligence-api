# Analytics schema

Module 4 **data contract** for spending analytics: time ranges, category filters,
aggregation response shapes, and receipt deduplication.

📌 **Source of truth** for shapes shared by aggregation (#4), summaries (#5),
REST (#6), and Q&A (#8–#11). Pydantic mirrors live in
[`app/analytics_models.py`](../app/analytics_models.py).

Upstream category taxonomy:
[n8n categorization-schema.md](https://github.com/RoxanaTapia/receipt-intelligence-n8n/blob/main/docs/categorization-schema.md).

How duplicate hash files appear on disk:
[n8n data/README.md](https://github.com/RoxanaTapia/receipt-intelligence-n8n/blob/main/data/README.md).

⚠️ This document defines the contract. **#4 implements** aggregation and dedup;
this issue does not compute totals.

## Date semantics

| Field | Role in analytics |
|-------|-------------------|
| Receipt **`date`** | Transaction date (`YYYY-MM-DD`). **All time-range filters use this field.** |
| **`categorized_at`** | When categorization was written. Used only to pick a dedup **winner**, never as the spend date. |
| Filename date segment | Same transaction date as JSON `date` (see n8n data README). |

## Time ranges

Exactly **one** mode per query. Inclusive bounds on transaction `date`.

| Mode | Fields | Resolved window (reference day = `as_of`, usually today) |
|------|--------|----------------------------------------------------------|
| `last_week` | `preset: last_week` | `as_of - 6 days` … `as_of` (7 calendar days) |
| `last_month` | `preset: last_month` | `as_of - 29 days` … `as_of` (30 calendar days) |
| `last_N_days` | `preset: last_N_days`, `n_days: N` (`N ≥ 1`) | `as_of - (N - 1) days` … `as_of` |
| Explicit | `start_date`, `end_date` | Those dates, inclusive (`start_date ≤ end_date`) |

Rolling windows (not calendar week/month boundaries) keep “last week” stable across locales.

### Example query objects

```json
{ "time_range": { "preset": "last_week" }, "categories": null }
```

```json
{ "time_range": { "preset": "last_N_days", "n_days": 14 }, "categories": ["food", "drinks"] }
```

```json
{
  "time_range": { "start_date": "2026-05-01", "end_date": "2026-05-19" },
  "categories": ["household"]
}
```

## Category filters

| Filter | Meaning |
|--------|---------|
| `categories: null` or `[]` | All taxonomy values: `food`, `snacks`, `drinks`, `household`, `other` |
| One or more values | Only line items in those categories (after dedup) |

Categories come from the upstream taxonomy; unknown strings fail validation.

## Aggregation units

Every aggregation response exposes:

| Unit | Field | Meaning |
|------|-------|---------|
| Total spend | `total_spend` | Sum of included line-item `price` values (each `price` is the line total, matching upstream extraction) |
| Spend by category | `by_category[]` | Per-category `total_spend` and `line_item_count` |
| Line-item count | `line_item_count` | Number of line items included |
| Receipt count | `receipt_count` | Number of **deduplicated** logical receipts included |

Resolved `start_date` / `end_date` on the response always reflect the effective window
(after preset resolution).

### Response shape

```json
{
  "start_date": "2026-05-10",
  "end_date": "2026-05-16",
  "categories": null,
  "total_spend": 24.5,
  "receipt_count": 1,
  "line_item_count": 4,
  "by_category": [
    { "category": "food", "total_spend": 18.0, "line_item_count": 3 },
    { "category": "drinks", "total_spend": 6.5, "line_item_count": 1 }
  ],
  "deduplication": {
    "deduplicated_count": 1,
    "superseded_files": ["2026-05-15_rewe_aaaaaaaa.json"]
  }
}
```

## Receipt deduplication policy

n8n may keep **multiple hash-named files** for one shopping trip when extraction or
categories drift across re-runs (see
[n8n data/README.md — Re-runs and multiple files](https://github.com/RoxanaTapia/receipt-intelligence-n8n/blob/main/data/README.md)).
The loader (#2) reads every valid file; analytics must collapse duplicates or totals
**double-count**.

| Concept | Rule |
|---------|------|
| **Logical receipt key** | `(date, merchant, canonical line items)` — each line item compared by `description`, `quantity`, `price`. **Category is excluded** from identity so a re-categorized trip still matches. |
| **Winner** | File with the latest `categorized_at`. Fallback: file mtime if the timestamp is missing. |
| **Effect** | Aggregation uses one version per logical receipt; older hash files are ignored for totals. |
| **Transparency** | Response `deduplication.deduplicated_count` is required; `superseded_files[]` is optional debug detail. |

### Merchant variance

If Claude emits different merchant strings (`"REWE"` vs `"REWE Markt"`), logical keys
**do not** match — both files can contribute to totals. That matches the n8n note that
merchant variance creates separate files; cleanup is operational, not silent merge by slug.

### Worked example

Two files, same shopping trip, categories changed on re-run:

| File | `date` | `merchant` | Line items (desc / qty / price) | Categories | `categorized_at` |
|------|--------|------------|----------------------------------|------------|------------------|
| `2026-05-15_rewe_aaaaaaaa.json` | `2026-05-15` | `REWE` | Milk / 1 / 1.19 | `other` | `2026-05-15T10:00:00Z` |
| `2026-05-15_rewe_bbbbbbbb.json` | `2026-05-15` | `REWE` | Milk / 1 / 1.19 | `food` | `2026-05-16T09:00:00Z` |

- **Logical key** matches (category ignored).
- **Winner:** `…bbbbbbbb.json` (later `categorized_at`).
- **Totals:** Milk counts once under `food` (€1.19).
- **Metadata:** `deduplicated_count: 1`, optional
  `superseded_files: ["2026-05-15_rewe_aaaaaaaa.json"]`.

## Pydantic mapping

| Concept | Model (`app/analytics_models.py`) |
|---------|-----------------------------------|
| Time range | `AnalyticsTimeRange`, `TimeRangePreset` |
| Query | `AnalyticsQuery` |
| Per-category row | `CategorySpend` |
| Dedup metadata | `DeduplicationMeta` |
| Aggregation result | `AggregationResponse` |

Receipt / line-item persistence shapes remain in [`app/models.py`](../app/models.py).

## Related docs

| Doc | Owner |
|-----|--------|
| [analytics.md](analytics.md) | Stub now; fuller guide in **#7** |
| This schema | **#3** (this issue) |
