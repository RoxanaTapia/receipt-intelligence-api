# Contributing and operating

This page keeps the shipping workflow for people changing the API. If you
are running it, start with the [README](../README.md). Endpoint detail lives
in [analytics.md](analytics.md) and [question-answering.md](question-answering.md).

## Tools

- [GitHub CLI](https://cli.github.com/) (`gh`)
- [Cursor](https://cursor.com/)
- Python 3.11+ and a sibling `receipt-intelligence-n8n` clone when you need
  categorized JSON (setup steps are in the [README](../README.md))

Open this repo as the workspace root, beside the sibling project:

```
receipt-intelligence-system/
├── receipt-intelligence-n8n/
└── receipt-intelligence-api/   ← open this in Cursor
```

## Agent workflow

One issue, one branch, one PR. Orchestrator runs `/verify` before opening a
PR; you approve before merge.

📌 **Start here:** [AGENTS.md](../AGENTS.md) — Cursor agent workflow.

1. Pick an issue on the [Project board](https://github.com/users/RoxanaTapia/projects/3).
2. Ship it with `/ship-issue #NN` (commands and roles are in [AGENTS.md](../AGENTS.md)).
3. `/verify` checks acceptance criteria before the PR opens.

## Shipped (Module 4)

Module 4 is complete. Historical scope:

| Area | Focus |
|------|-------|
| Bootstrap + loader | Cursor workflow, FastAPI scaffold, receipt loader |
| Analytics | Query schemas, aggregation, summaries, REST, docs |
| Q&A | Endpoint, routing, insights, test matrix + docs |
