# Project guide

## What we're building

This is the backend for the Receipt Intelligence demo
([receipt-intelligence-demo](https://github.com/RoxanaTapia/receipt-intelligence-demo)).
It reads categorized receipt JSON, totals spending, and answers plain-language
questions about that spending.

[receipt-intelligence-n8n](https://github.com/RoxanaTapia/receipt-intelligence-n8n)
writes the categorized JSON. This API reads it from `RECEIPT_DATA_PATH`.
The demo builds this API and shares that receipt folder.

## How a change happens

1. **One issue.** One request, one piece of work. Use `.github/ISSUE_TEMPLATE.md`.
   The title starts with one emoji code, such as 🛠️ or 📄.
2. **One branch.** A separate copy of the project, with a plain descriptive name.
3. **One pull request.** The title is a plain sentence. The description follows
   `.github/pull_request_template.md`.
4. **Automated tests.** GitHub runs the tests and Ruff on every pull request and
   on every push to main.
5. **Roxana reviews and merges.**

## Where things are

| Path | What it is |
|---|---|
| [README.md](README.md) | What this API is, and how to run it |
| [app/](app/) | The FastAPI application |
| [app/main.py](app/main.py) | Entrypoint and health check |
| [app/routers/](app/routers/) | Analytics and question routes |
| [app/loader.py](app/loader.py) | Reads categorized receipt JSON |
| [app/aggregation.py](app/aggregation.py) | Spending totals |
| [app/qa_service.py](app/qa_service.py) | Answers a question from those totals |
| [docs/analytics.md](docs/analytics.md) | Analytics guide |
| [docs/analytics-schema.md](docs/analytics-schema.md) | Analytics request and response shapes |
| [docs/question-answering.md](docs/question-answering.md) | How a question is answered |
| [docs/question-answering-test-matrix.md](docs/question-answering-test-matrix.md) | Sample questions and expected routing |
| [docs/contributing.md](docs/contributing.md) | Notes for people changing the API |
| [tests/](tests/) | Automated tests and receipt fixtures |
| [.github/workflows/tests.yml](.github/workflows/tests.yml) | Runs the tests and Ruff on GitHub |
| [.cursor/rules/](.cursor/rules/) | Rules for agents working in this repo |
| [pyproject.toml](pyproject.toml) | Ruff settings |
| [requirements.txt](requirements.txt) | Python dependencies |
| [LICENSE](LICENSE) | MIT license |

## Tests

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install ruff==0.17.6
ruff check .
ruff format --check .
pytest
```

The tests use fixtures and stand-ins. They do not call a live API and do not
need an API key.

## For the agents

Do:

- Read this guide and `.cursor/rules/` before you edit.
- Stay inside the current issue. One issue, one branch, one pull request.
- Keep the change small. Leave app behaviour as it is unless the issue asks you to change it.
- Run the tests and Ruff before the pull request is ready for Roxana.

Don't:

- Don't put secrets in a file, a log, or a pull request.
- Don't add a real API key. The tests must pass without one.
- Don't weaken a test to make it pass.
- Don't put agent roles, shipping routines, or deploy steps back into this guide.
