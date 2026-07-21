"""Claude prompts for Q&A routing (#9) and answer narration (#8).

Routing text is the production prompt from docs/question-answering.md.
Narration must use only structured facts — never invent amounts.
"""

from __future__ import annotations

import json
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
- no time mentioned → {"preset":"last_week"} and add warning "defaulted_time_range_to_last_week"

Categories (taxonomy only): food, snacks, drinks, household, other.
Synonyms: healthy food/groceries/produce → food; treats/chips/candy → snacks;
soda/juice/coffee/water → drinks; cleaning/toiletries → household; pfand/deposit → other.
No category / overall → null. Never invent new category strings.

Period comparison: leave compare_to null unless the user names an explicit previous range; the API resolves the immediately previous equal-length window.

## Few-shot examples
Q: How much did I spend on healthy food last week?
→ {"intent":"spending_by_category","time_range":{"preset":"last_week"},"categories":["food"],"compare_to":null,"warnings":[],"error":null}

Q: What's my average daily spending on drinks?
→ {"intent":"average_daily_spend","time_range":{"preset":"last_week"},"categories":["drinks"],"compare_to":null,"warnings":["defaulted_time_range_to_last_week"],"error":null}

Q: What percent of my spending was snacks last month?
→ {"intent":"category_share","time_range":{"preset":"last_month"},"categories":["snacks"],"compare_to":null,"warnings":[],"error":null}

Q: How does my food spend last week compare to the week before?
→ {"intent":"period_comparison","time_range":{"preset":"last_week"},"categories":["food"],"compare_to":null,"warnings":["compare_to_defaults_to_previous_equal_window"],"error":null}

Q: Give me a simple budget and diet insight.
→ {"intent":"general_insight","time_range":{"preset":"last_week"},"categories":null,"compare_to":null,"warnings":["defaulted_time_range_to_last_week"],"error":null}

Q: How much on soda between 2026-05-01 and 2026-05-19?
→ {"intent":"spending_by_category","time_range":{"start_date":"2026-05-01","end_date":"2026-05-19"},"categories":["drinks"],"compare_to":null,"warnings":[],"error":null}

## Output format
{
  "intent": "<intent or null>",
  "time_range": { ... } | null,
  "categories": ["food"] | null,
  "compare_to": { ... } | null,
  "warnings": [],
  "error": null
}

User question:
"""

NARRATION_SYSTEM = """\
You are a spending coach for the Receipt Intelligence System.
Answer in clear, concise prose using ONLY the structured facts provided.
Do not invent amounts, merchants, categories, or percentages that are not in the facts JSON.
If the facts show zero spend or an empty period, say so honestly — do not guess.
Do not mention JSON, prompts, or that you are an AI unless asked.
"""


def build_routing_user_message(question: str) -> str:
    return f"{ROUTING_TASK}{question.strip()}"


def build_narration_user_message(question: str, facts: dict[str, Any]) -> str:
    facts_json = json.dumps(facts, default=str, indent=2)
    return (
        "## Task\n"
        "Write a short answer to the user question grounded only in the facts below.\n\n"
        f"## User question\n{question.strip()}\n\n"
        f"## Facts (JSON)\n{facts_json}\n\n"
        "## Output\n"
        "Plain-text answer only — no markdown fences, no extra JSON wrapper.\n"
    )
