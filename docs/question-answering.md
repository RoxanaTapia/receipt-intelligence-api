# Question answering

End-to-end guide: natural-language budget questions → routing → analytics →
Claude narration, plus budget/diet insight heuristics.

📌 **Test matrix (scenarios + key facts):** [question-answering-test-matrix.md](question-answering-test-matrix.md)  
📌 **Analytics contract:** [analytics-schema.md](analytics-schema.md) · [analytics.md](analytics.md)  
📌 **Upstream taxonomy:** [n8n categorization-schema.md](https://github.com/RoxanaTapia/receipt-intelligence-n8n/blob/main/docs/categorization-schema.md)  
📌 **Prompt style:** [n8n-claude-standards.md](https://github.com/RoxanaTapia/receipt-intelligence-n8n/blob/main/docs/n8n-claude-standards.md)

## Role of this document

| Consumer | How it uses this doc |
|----------|----------------------|
| **Operators** | Setup, env vars, example `curl` |
| **`app/qa_prompts.py`** | Distilled routing + narration prompts at runtime |
| **`app/qa_service.py`** | Validate routed JSON → analytics → narrate |
| **Test matrix** | Expected routing JSON and key facts for sample questions |

Claude receives a **distilled prompt** at runtime — not this markdown file.

## Pipeline

```mermaid
flowchart LR
  Q["User question"] --> R["Routing prompt"]
  R --> J["Routed query JSON"]
  J --> V["Validate → AnalyticsQuery + intent"]
  V --> A["Aggregation / summary"]
  A --> I["Insight heuristics"]
  I --> N["Narration prompt"]
  N --> Ans["Grounded answer"]
```

`POST /questions` runs this flow in [`app/qa_service.py`](../app/qa_service.py).
Insights run only for `general_insight` (same heuristics as `GET /analytics/insights`).

## Setup and curl

Prerequisites: Python 3.11+, categorized receipt JSON on disk (sibling n8n
`data/receipts/` or [`tests/fixtures/aggregation/`](../tests/fixtures/aggregation/)),
and an Anthropic API key for live Q&A.

| Variable | Required | Purpose |
|----------|----------|---------|
| `RECEIPT_DATA_PATH` | No (has default) | Directory of categorized `*.json` — see [`.env.example`](../.env.example) |
| `ANTHROPIC_API_KEY` | Yes for `POST /questions` | Routing + narration Claude calls |
| `ANTHROPIC_MODEL` | No | Override default Haiku model id |

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set ANTHROPIC_API_KEY; adjust RECEIPT_DATA_PATH if needed
uvicorn app.main:app --reload
```

```bash
# Health
curl http://localhost:8000/health

# Natural-language Q&A (requires ANTHROPIC_API_KEY)
curl -s http://localhost:8000/questions \
  -H "Content-Type: application/json" \
  -d '{"question":"How much did I spend on healthy food last week?"}'

# Undated question pinned to an analytics window (same ISO dates as /analytics/summary)
curl -s http://localhost:8000/questions \
  -H "Content-Type: application/json" \
  -d '{"question":"How much did I spend per category?","start_date":"2026-07-01","end_date":"2026-08-31"}'

# Insights without Claude (analytics only)
curl "http://localhost:8000/analytics/insights?preset=last_week"
```

Response shape: `{ "answer", "facts", "query", "meta?" }`. On refusal
(e.g. empty data), `facts` and `query` are null and `meta.refusal` holds a code.

OpenAPI UI: `http://localhost:8000/docs`. Scenario checklist:
[question-answering-test-matrix.md](question-answering-test-matrix.md).

Analytics-only setup (no Anthropic key): [analytics.md — Local setup](analytics.md#local-setup-and-run).

| Stage | Owner | Rule |
|-------|-------|------|
| Interpret NL → structured query | Claude (routing) | Fuzzy synonyms, intent, time phrases |
| Validate JSON | Python / Pydantic | Fail closed on unknown categories or bad time modes |
| Compute totals / shares | Analytics layer | Deterministic — never invent amounts |
| Build budget/diet insights | Insight service | Rule-based; only for `general_insight` (and `GET /analytics/insights`) |
| Narrate answer | Claude | Use only facts from analytics / insights |

⚠️ **Do not** use Claude to invent spend amounts. Routing may guess *intent and filters*; money comes only from aggregation/summary.

## Intent types

Exactly **one** intent per question.

| Intent | When to use | Analytics path |
|--------|-------------|----------------|
| `spending_by_category` | How much spent (optionally in categories / period) | Aggregation: `total_spend`, `by_category` |
| `average_daily_spend` | Per-day average over the resolved window | Aggregation total ÷ inclusive day count |
| `category_share` | Share / percent of spend by category | Summary: `by_category[].percentage`, share facts |
| `period_comparison` | This period vs a previous period | Two aggregations + `period_delta` (see #5) |
| `general_insight` | Broad “how am I doing?” / budget-diet style | Summary + structured insights (see [Budget and diet insights](#budget-and-diet-insights)) |

### Routing rules (priority)

1. Prefer the **most specific** intent that matches the wording.
2. Words like *average*, *per day*, *daily* → `average_daily_spend` (even if a category is named).
3. Words like *percent*, *share*, *portion*, *how much of my spending* → `category_share`.
4. Words like *compared to*, *vs*, *more than last*, *week over week* → `period_comparison`.
5. Words like *insight*, *overview*, *how am I doing*, *budget and diet* → `general_insight`.
6. Otherwise → `spending_by_category` (default spend question).

If the question is empty or not about spending, set `"intent": null` and
`"error": "unsupported_question"` (validator rejects; the endpoint returns a refusal).

## Time-expression mapping

Map phrases to [time ranges](analytics-schema.md#time-ranges). Named rolling
windows (`last_week`, `last_month`, `last_N_days`) are relative to `as_of`
(usually today), not calendar week/month boundaries. Undated questions do
**not** use those presets — see the last row below. Python also rewrites a
rolling preset when the question named no period (`apply_undated_window` in
[`app/qa_facts.py`](../app/qa_facts.py)), so a router that still emits
`last_week` is corrected before aggregation.

| Phrase (examples) | Routed `time_range` |
|-------------------|---------------------|
| “last week”, “past week”, “the last 7 days” | `{ "preset": "last_week" }` |
| “last month”, “past month”, “the last 30 days” | `{ "preset": "last_month" }` |
| “yesterday” | `{ "preset": "last_N_days", "n_days": 1 }` |
| “last N days”, “past N days”, “over the last N days” | `{ "preset": "last_N_days", "n_days": N }` (`N ≥ 1`) |
| “from DATE to DATE”, “between DATE and DATE”, “in May 2026” (if bounds clear) | `{ "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD" }` |
| No time mentioned | Explicit dates from the request `start_date`/`end_date` when present; otherwise the loaded receipt span (`earliest_date`…`latest_date`). **Not** rolling `last_week` vs today. |

| Ambiguity | Rule |
|-----------|------|
| “this week” / “this month” | Treat as rolling `last_week` / `last_month` unless the user gives explicit dates |
| Unparseable date | `"time_range": null` + `"error": "ambiguous_time"` — do not guess a year |

## Category mapping

Allowed taxonomy values (lowercase): `food`, `snacks`, `drinks`, `household`,
`other`. Unknown tokens must **not** be invented — omit from `categories` or
set `"error": "unknown_category"`.

| Colloquial / synonym | Taxonomy |
|----------------------|----------|
| healthy food, groceries, ingredients, produce, meal, meals | `food` |
| snacks, treats, chips, candy, chocolate, sweets | `snacks` |
| drinks, beverages, soda, juice, coffee, water, soft drinks | `drinks` |
| household, cleaning, toiletries, personal care, detergent | `household` |
| other, miscellaneous, deposit, pfand | `other` |

| Filter rule | Routed `categories` |
|-------------|---------------------|
| One mapped category | `["food"]` (etc.) |
| Several mentioned | `["food", "drinks"]` (dedupe, taxonomy order optional) |
| No category / “everything” / “overall” / “per category” / “by category” | `null` (all categories; breakdown is `aggregation.by_category`) |
| Synonym not in table and not a taxonomy term | Prefer `null` + note in `warnings`, or `error` if the whole question hinges on that word |

## Routed query JSON (output contract)

Routing Claude returns **one JSON object** (no markdown fences). Fields
`time_range` and `categories` must match [`AnalyticsQuery`](../app/analytics_models.py)
so the Q&A service can validate with the same Pydantic models.

```json
{
  "intent": "average_daily_spend",
  "time_range": { "preset": "last_week" },
  "categories": ["drinks"],
  "compare_to": null,
  "warnings": [],
  "error": null
}
```

| Field | Type | Notes |
|-------|------|-------|
| `intent` | string \| null | One of the five intents, or null on hard failure |
| `time_range` | object \| null | Same modes as [AnalyticsTimeRange](analytics-schema.md#time-ranges) |
| `categories` | string[] \| null | Taxonomy values only; null = all |
| `compare_to` | object \| null | For `period_comparison` only: previous window (`preset` or explicit dates). Default when null: immediately preceding window of the same length as `time_range` |
| `warnings` | string[] | Soft issues (e.g. defaulted time range) |
| `error` | string \| null | Hard failure code: `unsupported_question`, `ambiguous_time`, `unknown_category` |

### Example objects

**Spend on snacks last month**

```json
{
  "intent": "spending_by_category",
  "time_range": { "preset": "last_month" },
  "categories": ["snacks"],
  "compare_to": null,
  "warnings": [],
  "error": null
}
```

**Average daily drinks (no time in the question → corpus span)**

```json
{
  "intent": "average_daily_spend",
  "time_range": { "start_date": "2026-05-10", "end_date": "2026-05-19" },
  "categories": ["drinks"],
  "compare_to": null,
  "warnings": ["defaulted_time_range_to_corpus_span"],
  "error": null
}
```

**Per-category breakdown over a client window**

```json
{
  "intent": "spending_by_category",
  "time_range": { "start_date": "2026-07-01", "end_date": "2026-08-31" },
  "categories": null,
  "compare_to": null,
  "warnings": ["defaulted_time_range_to_request_window"],
  "error": null
}
```

**Share of food last week**

```json
{
  "intent": "category_share",
  "time_range": { "preset": "last_week" },
  "categories": ["food"],
  "compare_to": null,
  "warnings": [],
  "error": null
}
```

## Routing prompt (three layers)

Follows the project three-layer pattern (system / task / output). Few-shots
below are part of the task layer for ambiguous questions.

### Production prompt

Copy into the routing Claude call (substitute the user question):

```text
## System
You are a spending-query router for the Receipt Intelligence System.
Return one JSON object only — no markdown fences, no explanation.
Do not invent spend amounts, merchants, or receipt data. You only extract intent and filters.

## Task
Map the user question to a routed analytics query.

Intents (exactly one, or null with error):
- spending_by_category — how much spent (default)
- average_daily_spend — average / per day / daily
- category_share — percent / share / portion of spending
- period_comparison — compared to / vs / week over week / month over month
- general_insight — overview / insight / how am I doing / budget and diet

Time range (exactly one mode; rolling windows vs today):
- last_week → {"preset":"last_week"}
- last_month → {"preset":"last_month"}
- yesterday → {"preset":"last_N_days","n_days":1}
- last N days → {"preset":"last_N_days","n_days":N}
- explicit → {"start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD"}
- no time mentioned → never use rolling last_week vs today. If a client window
  is listed below, {"start_date":"...","end_date":"..."} and warning
  "defaulted_time_range_to_request_window". Otherwise use the receipt data span
  as explicit dates and warning "defaulted_time_range_to_corpus_span"
- named month/season without a year → pick a year inside the receipt data span
  (prefer the year of latest_date); never invent a year outside that span

Categories (taxonomy only): food, snacks, drinks, household, other.
Synonyms: healthy food/groceries/produce → food; treats/chips/candy → snacks;
soda/juice/coffee/water → drinks; cleaning/toiletries → household; pfand/deposit → other.
No category / overall / per category / by category → null (breakdown is by_category).
Never invent new category strings.

Period comparison: leave compare_to null unless the user names an explicit previous range; the API resolves the immediately previous equal-length window.

## Few-shot examples
Q: How much did I spend on healthy food last week?
→ {"intent":"spending_by_category","time_range":{"preset":"last_week"},"categories":["food"],"compare_to":null,"warnings":[],"error":null}

Q: What's my average daily spending on drinks?
(with receipt data spanning 2026-05-10…2026-05-19, no client window)
→ {"intent":"average_daily_spend","time_range":{"start_date":"2026-05-10","end_date":"2026-05-19"},"categories":["drinks"],"compare_to":null,"warnings":["defaulted_time_range_to_corpus_span"],"error":null}

Q: What percent of my spending was snacks last month?
→ {"intent":"category_share","time_range":{"preset":"last_month"},"categories":["snacks"],"compare_to":null,"warnings":[],"error":null}

Q: How does my food spend last week compare to the week before?
→ {"intent":"period_comparison","time_range":{"preset":"last_week"},"categories":["food"],"compare_to":null,"warnings":["compare_to_defaults_to_previous_equal_window"],"error":null}

Q: Give me a simple budget and diet insight.
(with receipt data spanning 2026-05-10…2026-05-19, no client window)
→ {"intent":"general_insight","time_range":{"start_date":"2026-05-10","end_date":"2026-05-19"},"categories":null,"compare_to":null,"warnings":["defaulted_time_range_to_corpus_span"],"error":null}

Q: How much on soda between 2026-05-01 and 2026-05-19?
→ {"intent":"spending_by_category","time_range":{"start_date":"2026-05-01","end_date":"2026-05-19"},"categories":["drinks"],"compare_to":null,"warnings":[],"error":null}

Q: How much did I spend on drinks in July?
(with receipt data spanning 2026-07-01…2026-08-31)
→ {"intent":"spending_by_category","time_range":{"start_date":"2026-07-01","end_date":"2026-07-31"},"categories":["drinks"],"compare_to":null,"warnings":["resolved_month_year_from_receipt_coverage"],"error":null}

Q: How much did I spend per category?
(with client window 2026-07-01…2026-08-31)
→ {"intent":"spending_by_category","time_range":{"start_date":"2026-07-01","end_date":"2026-08-31"},"categories":null,"compare_to":null,"warnings":["defaulted_time_range_to_request_window"],"error":null}

## Output format
{
  "intent": "<intent or null>",
  "time_range": { ... } | null,
  "categories": ["food"] | null,
  "compare_to": { ... } | null,
  "warnings": [],
  "error": null
}

## Receipt data span
{{EARLIEST}} … {{LATEST}}

## Client window
{{CLIENT_WINDOW_OR_NONE}}

## User question
{{QUESTION}}
```

### Few-shot pattern index

| # | Pattern | Intent | Notable mapping |
|---|---------|--------|-----------------|
| 1 | Category + “last week” | `spending_by_category` | “healthy food” → `food` |
| 2 | “Average daily” + category | `average_daily_spend` | No time → corpus span + warning |
| 3 | “Percent / share” | `category_share` | Snacks + `last_month` |
| 4 | “Compare to” prior period | `period_comparison` | `compare_to: null` → previous equal window |
| 5 | Budget / diet insight | `general_insight` | `categories: null`; no time → corpus span |
| 6 | Synonym + explicit dates | `spending_by_category` | “soda” → `drinks` |
| 7 | Bare month + coverage year | `spending_by_category` | “July” → July inside receipt span |
| 8 | “Per category” + client window | `spending_by_category` | `categories: null`; request dates |

## Parse → validate

After the routing call (`app/qa_service.py`):

| Step | Check |
|------|-------|
| Parse | Non-empty response; valid JSON object |
| Validate | `intent` in allowed set (or error path); `time_range` / `categories` via `AnalyticsQuery` rules |
| Undated window | If the question named no period and routing still returned a rolling preset, replace it with request `start_date`/`end_date` or the receipt span |
| Fail closed | On `error` or validation failure → refuse; do not call aggregation with guessed filters |
| No receipts | If coverage shows zero files/logical receipts → refuse without calling Claude |

## Narration prompt

After analytics facts are computed, a second Claude call turns them into prose.
Amounts must come only from the facts JSON.

### Production prompt

Implemented in [`app/qa_prompts.py`](../app/qa_prompts.py) (`NARRATION_SYSTEM` +
`build_narration_user_message`). Distilled form:

```text
## System
You are a spending coach for the Receipt Intelligence System.
Answer in clear, concise prose using ONLY the structured facts provided.
Do not invent amounts, merchants, categories, or percentages that are not in the facts JSON.
If the facts show zero spend or an empty period, say so honestly — do not guess.
When facts include insights, treat them as spending-pattern observations only —
do not make health or nutritional claims.
Do not mention JSON, prompts, or that you are an AI unless asked.

## Task
Write a short answer to the user question grounded only in the facts below.
If the facts include an insights list, lead with those signals
(use each insight's text; do not invent extra metrics).

## User question
{{QUESTION}}

## Facts (JSON)
{{FACTS_JSON}}

## Output
Plain-text answer only — no markdown fences, no extra JSON wrapper.
```

### Endpoint shape

`POST /questions` with `{ "question": "...", "start_date"?: "...", "end_date"?: "..." }`
returns `{ "answer", "facts", "query", "meta?" }` — see [Setup and curl](#setup-and-curl).
Optional `start_date` / `end_date` are inclusive ISO dates, same contract as
`GET /analytics/summary`. Both are required when either is sent; unknown extra
fields are ignored. When the question names no period, those bounds (or the
loaded receipt span if omitted) replace a rolling preset so undated demo
questions are not resolved against clock-today.

For `general_insight`, `facts.insights` holds the structured insight list from
[`generate_insights()`](../app/insight_service.py).

## Budget and diet insights

Composite signals built from [`SummaryResponse`](analytics-schema.md#structured-summaries)
shares — not Claude guesses. Lifestyle spending patterns only; **not** medical
or nutritional advice.

| Path | How insights are produced |
|------|---------------------------|
| `POST /questions` with `general_insight` | `_gather_facts` → `generate_insights(summary)` → `facts.insights` → narration |
| `GET /analytics/insights` | Same heuristics; returns `InsightResponse` without Claude |

Implementation: [`app/insight_service.py`](../app/insight_service.py),
[`app/insight_models.py`](../app/insight_models.py).

### Insight types

| `insight_type` | Formula | Default threshold | Severity |
|----------------|---------|-------------------|----------|
| `snacks_share_of_grocery` | `snacks / (food + snacks) × 100` | **20%** — warning when above | `warning` / `ok` |
| `top_spend_category` | Top category by `total_spend` (share of total) | none (informational) | `info` |
| `high_discretionary_share` | `(snacks + drinks) / total × 100` | **40%** — warning when above | `warning` / `ok` |

Constants: `SNACKS_SHARE_OF_GROCERY_WARN_PCT`, `HIGH_DISCRETIONARY_WARN_PCT`
in [`app/insight_service.py`](../app/insight_service.py) (overridable as
keyword args for tests).

Zero totals: shares are `0`; no warning severities; `top_spend_category` reports
no spending for the period.

### Insight object shape

```json
{
  "insight_type": "snacks_share_of_grocery",
  "severity": "warning",
  "triggered": true,
  "value": 25.0,
  "threshold": 20.0,
  "unit": "%",
  "text": "Snacks were 25.0% of your grocery spend (food + snacks) last 7 days. That's above the 20% guideline."
}
```

## Related work

| Issue | Delivers |
|-------|----------|
| ✅ #3–#7 | `AnalyticsQuery`, aggregation, summaries, REST, analytics docs |
| ✅ #9 | Routing contract, mappings, routing prompt |
| ✅ #8 | `POST /questions`, narration prompt, Anthropic env |
| ✅ #10 | Insight heuristics, `GET /analytics/insights`, thresholds |
| ✅ #11 | Test matrix, setup/`curl` guide, README links |

## Related docs

| Doc | Role |
|-----|------|
| [question-answering-test-matrix.md](question-answering-test-matrix.md) | Sample questions, expected routing, key facts |
| [analytics-schema.md](analytics-schema.md) | Time ranges, categories, response shapes |
| [analytics.md](analytics.md) | How aggregation/REST work today |
| [n8n-claude-standards.md](https://github.com/RoxanaTapia/receipt-intelligence-n8n/blob/main/docs/n8n-claude-standards.md) | Cross-repo Claude conventions (includes Q&A routing section) |
