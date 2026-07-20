# Analytics guide

Spending analytics over categorized receipt JSON loaded via `RECEIPT_DATA_PATH`.

📌 **Schema contract** (time ranges, filters, aggregation, dedup, summaries, REST):
[analytics-schema.md](analytics-schema.md).

| Today (#6) | Later (**#7**) |
|------------|----------------|
| REST endpoints + curl examples below | End-to-end guide: services, ops, how to run queries |

## REST endpoints (interim)

With the API running (`uvicorn app.main:app --reload`):

```bash
# Category totals — explicit range
curl "http://localhost:8000/analytics/spending?start_date=2026-05-01&end_date=2026-05-19"

# Drinks only — rolling window
curl "http://localhost:8000/analytics/spending?preset=last_N_days&n_days=14&categories=drinks"

# Structured summary facts
curl "http://localhost:8000/analytics/summary?preset=last_month"

# Coverage + dedup debug
curl "http://localhost:8000/analytics/receipts"
```

Interactive OpenAPI: [http://localhost:8000/docs](http://localhost:8000/docs).

Until #7 lands, treat [analytics-schema.md](analytics-schema.md) as the source of
truth for analytics data shapes.
