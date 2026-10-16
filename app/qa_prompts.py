"""Claude prompts for Q&A routing (#9) and answer narration (#8 / #10).

Routing text is the production prompt from docs/question-answering.md.
Narration must use only structured facts — never invent amounts.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

# Distilled from docs/question-answering.md — keep in sync when the contract changes.
ROUTING_SYSTEM = """\
You are a spending-query router for the Receipt Intelligence System.
Return one JSON object only — no markdown fences, no explanation.
Do not invent spend amounts, merchants, or receipt data. You only extract intent and filters.
"""

ROUTING_TASK = """\
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
"""

NARRATION_SYSTEM = """\
You are a spending coach for the Receipt Intelligence System.
Answer in clear, concise prose using ONLY the structured facts provided.
Do not invent amounts, merchants, categories, or percentages that are not in the facts JSON.
If the facts show zero spend or an empty period, say so honestly — do not guess.
When stating money amounts, write plain numbers with two decimals and no currency
symbol (e.g. 5.10). Do not use $ or €.
When facts include insights, treat them as spending-pattern observations only —
do not make health or nutritional claims.
Do not mention JSON, prompts, or that you are an AI unless asked.
"""


def build_routing_user_message(
    question: str,
    *,
    earliest_date: date | None = None,
    latest_date: date | None = None,
    client_start: date | None = None,
    client_end: date | None = None,
) -> str:
    """Build the router user message, optionally grounded in receipt coverage dates."""
    span = "unknown (no receipt dates loaded)"
    if earliest_date is not None and latest_date is not None:
        span = f"{earliest_date.isoformat()} … {latest_date.isoformat()}"
    if client_start is not None and client_end is not None:
        client_window = (
            f"{client_start.isoformat()} … {client_end.isoformat()} "
            "(use these dates when the question names no time)"
        )
    else:
        client_window = "none — default undated questions to the receipt data span"
    return (
        f"{ROUTING_TASK}"
        f"## Receipt data span\n{span}\n\n"
        f"## Client window\n{client_window}\n\n"
        f"## User question\n{question.strip()}\n"
    )


def build_narration_user_message(question: str, facts: dict[str, Any]) -> str:
    facts_json = json.dumps(facts, default=str, indent=2)
    return (
        "## Task\n"
        "Write a short answer to the user question grounded only in the facts below.\n"
        "If the facts include an insights list, lead with those signals "
        "(use each insight's text; do not invent extra metrics).\n\n"
        f"## User question\n{question.strip()}\n\n"
        f"## Facts (JSON)\n{facts_json}\n\n"
        "## Output\n"
        "Plain-text answer only — no markdown fences, no extra JSON wrapper.\n"
    )
