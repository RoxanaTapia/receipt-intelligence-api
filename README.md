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
├── app/                   # FastAPI application
│   ├── main.py            # Entrypoint and routes
│   ├── config.py          # RECEIPT_DATA_PATH
│   ├── models.py          # Categorized receipt schemas
│   └── loader.py          # Read and flatten receipt JSON
├── requirements.txt       # Python dependencies
├── tests/                 # pytest (loader smoke tests)
└── docs/                  # Analytics and Q&A docs *(#3, #7, #9+)*
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

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional — default points at sibling n8n receipts
uvicorn app.main:app --reload
```

In another terminal:

```bash
curl http://localhost:8000/health   # {"status":"ok"}
```

Run tests:

```bash
pytest
```

## Agent workflow

One issue, one branch, one PR. Orchestrator runs `/verify` before opening a PR; you approve before merge.

**Start here:** [AGENTS.md](AGENTS.md)

## Roadmap (Module 4)

| Issue | Focus |
|-------|-------|
| #1 | Cursor bootstrap |
| #2 | FastAPI scaffold + receipt loader *(this issue)* |
| #3–#6 | Schemas, aggregation, summaries, REST API |
| #7 | Analytics documentation |
| #8–#11 | Q&A endpoint, routing, insights, test matrix |
