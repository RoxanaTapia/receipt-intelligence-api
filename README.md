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
├── Dockerfile             # Production image (uvicorn on :8000)
├── .dockerignore          # Lean build context for Docker
├── .env.example           # Local config template (incl. ANTHROPIC_API_KEY)
├── app/                   # FastAPI application
│   ├── main.py            # Entrypoint
│   ├── routers/           # REST routes (analytics + questions)
│   ├── config.py          # RECEIPT_DATA_PATH, Anthropic settings
│   ├── models.py          # Categorized receipt schemas
│   ├── analytics_models.py # Analytics query/response contract
│   ├── aggregation.py     # Spending aggregation + dedup
│   ├── summary.py         # Structured summaries
│   ├── coverage.py        # Receipt coverage metadata
│   ├── total_check.py     # Printed total vs line-item sum
│   ├── insight_service.py # Budget/diet insight heuristics
│   ├── qa_service.py      # Q&A pipeline
│   └── loader.py          # Read and flatten receipt JSON
├── requirements.txt       # Python dependencies
├── pytest.ini             # pytest config
├── tests/                 # pytest
└── docs/                  # Analytics and Q&A docs
    ├── analytics-schema.md              # Time ranges, filters, dedup
    ├── analytics.md                     # End-to-end analytics guide
    ├── question-answering.md            # Q&A pipeline, prompts, setup
    └── question-answering-test-matrix.md # Q&A scenarios + key facts
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
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional — default points at sibling n8n receipts
uvicorn app.main:app --reload
```

In another terminal:

```bash
curl http://localhost:8000/health   # {"status":"ok"}
curl "http://localhost:8000/analytics/receipts"
# OpenAPI UI: http://localhost:8000/docs
```

More analytics `curl` examples: [docs/analytics.md](docs/analytics.md).  
Q&A setup and `POST /questions` examples: [docs/question-answering.md](docs/question-answering.md).

Run tests:

```bash
pytest
```

### Docker image

Production-oriented image for Compose / VPS (no `--reload`). Default `RECEIPT_DATA_PATH` inside the container is `/data/receipts` — mount categorized JSON there (or override the env var).

```bash
docker build -t receipt-intelligence-api .
docker run --rm -p 8000:8000 \
  -e RECEIPT_DATA_PATH=/data/receipts \
  -v /absolute/path/to/receipts:/data/receipts \
  receipt-intelligence-api
curl http://localhost:8000/health   # {"status":"ok"}
```

**Demo Compose:** the umbrella repo [`receipt-intelligence-demo`](https://github.com/RoxanaTapia/receipt-intelligence-demo) should build from this repository root (`context` = this repo, `dockerfile` = `Dockerfile`) and mount a shared receipts volume at `/data/receipts` with `RECEIPT_DATA_PATH=/data/receipts`.

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/analytics.md](docs/analytics.md) | End-to-end analytics guide: architecture, setup, API, dedup |
| [docs/analytics-schema.md](docs/analytics-schema.md) | Analytics contract: time ranges, filters, response shapes, dedup |
| [docs/question-answering.md](docs/question-answering.md) | Q&A pipeline: routing, narration, insights, setup, curl |
| [docs/question-answering-test-matrix.md](docs/question-answering-test-matrix.md) | Q&A test matrix: sample questions, expected routing, key facts |
| [AGENTS.md](AGENTS.md) | Cursor agent workflow |

## Agent workflow

One issue, one branch, one PR. Orchestrator runs `/verify` before opening a PR; you approve before merge.

**Start here:** [AGENTS.md](AGENTS.md)

## Shipped (Module 4)

Module 4 is complete. Historical scope:

| Area | Focus |
|------|-------|
| Bootstrap + loader | Cursor workflow, FastAPI scaffold, receipt loader |
| Analytics | Query schemas, aggregation, summaries, REST, docs |
| Q&A | Endpoint, routing, insights, test matrix + docs |
