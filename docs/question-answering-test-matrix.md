# Q&A test matrix

Repeatable verification for Module 4 natural-language Q&A (#11).

**Contract:** [question-answering.md](question-answering.md)  
**Upstream pattern:** [n8n categorization-test-matrix.md](https://github.com/RoxanaTapia/receipt-intelligence-n8n/blob/main/docs/categorization-test-matrix.md)

Questions are **strategic** — one row per intent, edge, or insight signal — not one row per sample PDF. The API reads categorized JSON, not PDFs.

## Purpose

Prove the pipeline behaves on **routing + grounded facts**, not only a green-path curl:

| Focus | What we check |
|-------|----------------|
| **Learning-objective intents** | All five intents from the routing contract |
| **Synonyms / multi-category** | Colloquial words map to taxonomy; filters combine cleanly |
| **Edges** | No data, ambiguous time, unknown category, unsupported question |
| **Budget/diet insights (#10)** | `general_insight` surfaces heuristic signals |

Prompt or routing changes happen **only** where this matrix shows consistent drift across runs.

## Grounding corpus

| Corpus | Path | Use |
|--------|------|-----|
| **API aggregation fixtures** | [`tests/fixtures/aggregation/`](../tests/fixtures/aggregation/) | Pin **key facts** (totals, shares, insights) with `as_of` = `2026-05-20` |
| **Live n8n receipts** | `RECEIPT_DATA_PATH` (sibling `data/receipts/`) | Manual curl smoke; amounts vary by what’s on disk |

⚠️ Key-fact columns below assume the aggregation fixture set and explicit
`2026-05-01`–`2026-05-19` (or noted window). Rolling presets need a fixed
`as_of` for apples-to-apples checks.

**Fixture totals** (after dedup, `2026-05-01`–`2026-05-19`):

| Category | Spend |
|----------|------:|
| food | 4.68 |
| snacks | 2.00 |
| drinks | 6.78 |
| other | 0.30 |
| **total** | **13.76** |

Insight signals on that window (see [#10](question-answering.md#budget-and-diet-insights-10)): snacks share of grocery ≈ **29.9%** (warning), top category **drinks** ≈ **49.3%**, discretionary (snacks+drinks) ≈ **63.8%** (warning).

## How to run the matrix

### 1. Automated routing checks (no Anthropic key)

```bash
source .venv/bin/activate
pytest tests/test_qa_matrix.py -q
```

These assert expected routing JSON validates as `RoutedQuery` and that scripted
pipeline cases hit the key facts above.

### 2. Manual end-to-end (live Claude)

1. `cp .env.example .env` and set `ANTHROPIC_API_KEY`
2. Point `RECEIPT_DATA_PATH` at fixtures or sibling receipts
3. `uvicorn app.main:app --reload`
4. For each scenario, `POST /questions` (see [Setup and curl](question-answering.md#setup-and-curl))
5. Record **Run 1** / **Run 2** routing intent + whether key facts appear in `facts` / answer
6. Set **Status**: ✅ match · ⚠️ drift · ❌ fail / refuse unexpectedly

---

## Learning-objective scenarios

Few-shot style questions from the routing contract.

| ID | Question | Expected intent | Expected routing highlights | Key facts (fixture corpus) |
|----|----------|-----------------|----------------------------|----------------------------|
| L1 | How much did I spend on healthy food last week? | `spending_by_category` | `categories: ["food"]`, `time_range.preset: last_week` | food spend in resolved window |
| L2 | What's my average daily spending on drinks? | `average_daily_spend` | `categories: ["drinks"]`, default `last_week` + warning `defaulted_time_range_to_last_week` | `average_daily_spend`, `day_count` |
| L3 | What percent of my spending was snacks last month? | `category_share` | `categories: ["snacks"]`, `preset: last_month` | snacks `%` from summary |
| L4 | How does my food spend last week compare to the week before? | `period_comparison` | `categories: ["food"]`, `compare_to: null` (previous equal window) | current + `previous_aggregation` |
| L5 | Give me a simple budget and diet insight. | `general_insight` | `categories: null`, default `last_week` + default-time warning | `facts.insights` (3 signals) |
| L6 | How much on soda between 2026-05-01 and 2026-05-19? | `spending_by_category` | `categories: ["drinks"]`, explicit dates | drinks **6.78** |

---

## Edge-case scenarios

| ID | Question / setup | Expected outcome | Notes |
|----|------------------|------------------|-------|
| E1 | Any spend question with **empty** `RECEIPT_DATA_PATH` | Refuse `no_receipt_data`; **no** Claude calls | Covered in `tests/test_qa_api.py` |
| E2 | How much did I spend on food in mid-spring? | Routing `error: ambiguous_time` → refuse `routing_failed` | Do not invent a year/window |
| E3 | How much did I spend on electronics last week? | `error: unknown_category` **or** refuse via validation | Never invent a taxonomy value |
| E4 | What is the meaning of life? | `error: unsupported_question` → refuse | Not a spending question |
| E5 | How much did I spend on food and snacks between 2026-05-01 and 2026-05-19? | `spending_by_category`, `categories: ["food", "snacks"]` | Multi-category filter; fixture total **6.68** |

---

## Budget / diet insight scenarios (#10)

Use `general_insight` (or `GET /analytics/insights`) on the fixture window
`2026-05-01`–`2026-05-19`.

| ID | Question | Expected signals in `facts.insights` |
|----|----------|--------------------------------------|
| I1 | How am I doing on budget and diet for 2026-05-01 to 2026-05-19? | `snacks_share_of_grocery` **warning** (~29.9% > 20%); `high_discretionary_share` **warning** (~63.8% > 40%); `top_spend_category` **info** (drinks) |
| I2 | Give me a spending overview for 2026-05-01 to 2026-05-19. | Same three insight types; narration must not invent health/nutrition claims |

For REST-only checks (no Claude):

```bash
curl "http://localhost:8000/analytics/insights?start_date=2026-05-01&end_date=2026-05-19"
```

(Point the server at `tests/fixtures/aggregation` or copy those files into the data path.)

---

## Expected routing JSON (machine-checkable)

Success rows used by `tests/test_qa_matrix.py` — keep in sync when editing the tables above.

| ID | Expected `RoutedQuery` JSON |
|----|-----------------------------|
| L1 | `{"intent":"spending_by_category","time_range":{"preset":"last_week"},"categories":["food"],"compare_to":null,"warnings":[],"error":null}` |
| L2 | `{"intent":"average_daily_spend","time_range":{"preset":"last_week"},"categories":["drinks"],"compare_to":null,"warnings":["defaulted_time_range_to_last_week"],"error":null}` |
| L3 | `{"intent":"category_share","time_range":{"preset":"last_month"},"categories":["snacks"],"compare_to":null,"warnings":[],"error":null}` |
| L4 | `{"intent":"period_comparison","time_range":{"preset":"last_week"},"categories":["food"],"compare_to":null,"warnings":["compare_to_defaults_to_previous_equal_window"],"error":null}` |
| L5 | `{"intent":"general_insight","time_range":{"preset":"last_week"},"categories":null,"compare_to":null,"warnings":["defaulted_time_range_to_last_week"],"error":null}` |
| L6 | `{"intent":"spending_by_category","time_range":{"start_date":"2026-05-01","end_date":"2026-05-19"},"categories":["drinks"],"compare_to":null,"warnings":[],"error":null}` |
| E2 | `{"intent":null,"time_range":null,"categories":null,"compare_to":null,"warnings":[],"error":"ambiguous_time"}` |
| E3 | `{"intent":null,"time_range":null,"categories":null,"compare_to":null,"warnings":[],"error":"unknown_category"}` |
| E4 | `{"intent":null,"time_range":null,"categories":null,"compare_to":null,"warnings":[],"error":"unsupported_question"}` |
| E5 | `{"intent":"spending_by_category","time_range":{"start_date":"2026-05-01","end_date":"2026-05-19"},"categories":["food","snacks"],"compare_to":null,"warnings":[],"error":null}` |
| I1 | `{"intent":"general_insight","time_range":{"start_date":"2026-05-01","end_date":"2026-05-19"},"categories":null,"compare_to":null,"warnings":[],"error":null}` |

**Count:** 11 routing rows + E1 (empty data) = **12** scenarios (≥10 required).

---

## Results summary

Fill after a live two-run pass (optional for PR; useful before Module 5):

| ID | Run 1 intent / outcome | Run 2 | Status | Notes |
|----|------------------------|-------|--------|-------|
| L1–L6 | | | | |
| E1–E5 | | | | |
| I1–I2 | | | | |

**Drift notes** (⚠️ on both runs → candidate prompt fix in [question-answering.md](question-answering.md)):

```
(none yet)
```

---

## Known limitations

| Limitation | Notes |
|------------|-------|
| **Narration wording** | Claude prose varies; assert **facts JSON**, not exact answer text |
| **Rolling windows** | Presets depend on `as_of` / “today” — pin dates for key-fact checks |
| **Live vs fixtures** | Sibling `data/receipts/` amounts differ from aggregation fixtures |
| **Sample PDFs** | Anonymized PDFs live in n8n `samples/`; Q&A matrix uses **categorized JSON**, not PDF re-ingest |

---

## Related docs

| Doc | Role |
|-----|------|
| [question-answering.md](question-answering.md) | Pipeline, prompts, setup, curl |
| [analytics.md](analytics.md) | Aggregation / REST |
| [analytics-schema.md](analytics-schema.md) | Time ranges, response shapes |
| [n8n samples README](https://github.com/RoxanaTapia/receipt-intelligence-n8n/blob/main/samples/README.md) | Anonymized PDF catalog (upstream) |
