# Receipt Intelligence API

FastAPI backend for spending analytics and natural-language Q&A over categorized receipt JSON.

Receipts are **written** by [receipt-intelligence-n8n](https://github.com/RoxanaTapia/receipt-intelligence-n8n) (n8n workflows). This repo **reads** `data/receipts/*.json` from the sibling project.

## Related repositories

| Repo | Role |
|------|------|
| [`receipt-intelligence-n8n`](https://github.com/RoxanaTapia/receipt-intelligence-n8n) | PDF ingest, categorization, `data/receipts/` output |
| **This repo** | Analytics, REST API, Q&A |

## Repository structure

```
receipt-intelligence-api/
├── AGENTS.md              # Cursor agent workflow — start here
├── .cursor/               # Agents, commands, rules
├── .env.example           # Local config template
├── docs/                  # Analytics and Q&A docs (Module 4)
└── app/                   # FastAPI application (#2+)
```

## Prerequisites

- Python 3.11+
- [GitHub CLI](https://cli.github.com/) (`gh`)
- [Cursor](https://cursor.com/)
- Sibling clone: `receipt-intelligence-n8n` with categorized JSON in `data/receipts/`

## Getting started

1. **Clone both repos** side by side:
   ```
   receipt-intelligence-system/
   ├── receipt-intelligence-n8n/
   └── receipt-intelligence-api/   ← open this in Cursor
   ```
2. **Copy env:** `cp .env.example .env`
3. **Set receipt data path** in `.env` (default points at sibling n8n `data/receipts/`)
4. **Pick an issue** on the [Project board](https://github.com/users/RoxanaTapia/projects/3) → `/ship-issue #NN` (see [AGENTS.md](AGENTS.md))

### Local run

*Coming in #2 — FastAPI scaffold.*

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
curl http://localhost:8000/health
```

## Agent workflow

One issue, one branch, one PR. Orchestrator runs `/verify` before opening a PR; you approve before merge.

**Start here:** [AGENTS.md](AGENTS.md)

## Roadmap (Module 4)

| Issue | Focus |
|-------|-------|
| #1 | Cursor bootstrap *(this issue)* |
| #2 | FastAPI scaffold + receipt loader |
| #3–#6 | Schemas, aggregation, summaries, REST API |
| #7 | Analytics documentation |
| #8–#11 | Q&A endpoint, routing, insights, test matrix |
