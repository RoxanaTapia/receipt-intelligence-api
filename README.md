# Receipt Intelligence API

You point this API at categorized receipt JSON and ask it about your spending. It totals what you spent by category and by time, and it answers everyday questions in plain language — for example, how much you spent on groceries last week.

Those files are written by [receipt-intelligence-n8n](https://github.com/RoxanaTapia/receipt-intelligence-n8n), which turns receipt PDFs into categorized JSON under `data/receipts/`. This API reads that folder. When you want both pieces running together, the [receipt demo](https://github.com/RoxanaTapia/receipt-intelligence-demo) builds this repo and mounts the shared receipts volume.

## Related repositories

| Repo | Role |
|------|------|
| [`receipt-intelligence-n8n`](https://github.com/RoxanaTapia/receipt-intelligence-n8n) | PDF ingest, categorization, `data/receipts/` output |
| [`receipt-intelligence-demo`](https://github.com/RoxanaTapia/receipt-intelligence-demo) | Compose demo that builds this API and shares a receipts volume |
| **This repo** | Analytics, REST API, natural-language questions |

## Repository structure

```
receipt-intelligence-api/
├── AGENTS.md              # How a change happens, and where things are
├── .cursor/rules/         # Short rules for agents
├── .editorconfig          # Editor defaults
├── .github/               # Issue template, pull request template, tests
├── Dockerfile             # Production image (uvicorn on :8000)
├── .dockerignore          # Lean build context for Docker
├── .env.example           # Local config template (incl. ANTHROPIC_API_KEY)
├── LICENSE                # MIT license
├── pyproject.toml         # Ruff settings
├── app/                   # FastAPI application
│   ├── main.py            # Entrypoint
│   ├── routers/           # REST routes (analytics + questions)
│   ├── config.py          # RECEIPT_DATA_PATH, Anthropic settings
│   ├── models.py          # Categorized receipt schemas
│   ├── analytics_models.py # Analytics query/response contract
│   ├── aggregation.py     # Spending aggregation + dedup
│   ├── summary.py         # Structured summaries
│   ├── coverage.py        # Receipt coverage metadata
│   ├── insight_service.py # Scoped spending insights by category
│   ├── qa_service.py      # Q&A pipeline
│   └── loader.py          # Read and flatten receipt JSON
├── requirements.txt       # Python dependencies
├── pytest.ini             # pytest config
├── tests/                 # pytest
└── docs/                  # Analytics, Q&A, and contributor docs
    ├── analytics-schema.md              # Time ranges, filters, dedup
    ├── analytics.md                     # End-to-end analytics guide
    ├── contributing.md                  # Notes for people changing the API
    ├── question-answering.md            # Q&A pipeline, prompts, setup
    └── question-answering-test-matrix.md # Q&A scenarios + key facts
```

## Prerequisites

- Python 3.11+
- Sibling clone: `receipt-intelligence-n8n` with categorized JSON in `data/receipts/`

## Getting started

1. **Clone both repos** side by side:
   ```
   receipt-intelligence-system/
   ├── receipt-intelligence-n8n/
   └── receipt-intelligence-api/
   ```
2. **Copy env:** `cp .env.example .env`
3. **Set receipt data path** in `.env` (default points at sibling n8n `data/receipts/`)

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

GitHub runs these tests, and Ruff, on every pull request and on every push to main. The commands are in [AGENTS.md](AGENTS.md).

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
| [docs/contributing.md](docs/contributing.md) | Notes for people changing the API |
