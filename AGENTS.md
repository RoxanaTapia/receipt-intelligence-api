# AGENTS.md — Receipt Intelligence API

How we use Cursor agents, rules, and commands in this repository.

## Project Vision

Supporting **FastAPI** backend for the Receipt Intelligence System: load categorized receipt JSON, compute spending analytics, and answer natural-language budget questions — grounded in real data.

**Stack:** FastAPI · Pydantic · pytest · Claude (Q&A narration only)

**Sibling repo:** [receipt-intelligence-n8n](https://github.com/RoxanaTapia/receipt-intelligence-n8n) writes categorized receipts to `data/receipts/`. This repo **reads** them via `RECEIPT_DATA_PATH`.

## Project references

Agents use generic language; this table maps terms to **this repo**. Cross-repo docs link to n8n.

| Term | Path |
|------|------|
| Categorization schema (upstream contract) | [n8n: categorization-schema.md](https://github.com/RoxanaTapia/receipt-intelligence-n8n/blob/main/docs/categorization-schema.md) |
| Receipt data on disk | [n8n: data/README.md](https://github.com/RoxanaTapia/receipt-intelligence-n8n/blob/main/data/README.md) |
| Sample receipt JSON | [n8n: data/receipts/example.json](https://github.com/RoxanaTapia/receipt-intelligence-n8n/blob/main/data/receipts/example.json) |
| Claude prompt standards (Q&A) | [n8n: n8n-claude-standards.md](https://github.com/RoxanaTapia/receipt-intelligence-n8n/blob/main/docs/n8n-claude-standards.md) |
| Analytics schemas | `docs/analytics-schema.md` *(#3)* |
| Analytics guide | `docs/analytics.md` *(#7)* |
| Q&A guide | `docs/question-answering.md` *(#8, #9, #10, #11)* |

## Current Focus

- **Active issue:** #10 — budget and diet insight generation
- **Module 4 roadmap:** Q&A (#8–#11); routing (#9) and Q&A endpoint (#8) complete
- **Analytics (#3–#7):** complete (schemas, aggregation, summaries, REST, docs)
- **Loader (#2):** complete via PR #13
- **Bootstrap (#1):** complete via PR #12

## Core Principles

- Keep things simple, readable, and maintainable
- Small, focused functions and changes
- One issue → one branch → one PR
- Prioritize clarity and long-term quality

## Agent Roster

| Role | Responsibility | Notes |
|------|----------------|-------|
| `milestone-orchestrator` | Coordinates shipping, branches, commits | Only agent allowed to commit |
| `fastapi-engineer` | FastAPI routes, services, Pydantic models, loader | Primary implement specialist |
| `claude-prompt-engineer` | Q&A and routing prompts (API-side Claude calls) | Consult for #9, #8, #10 |
| `docs-writer` | Documentation draft and review | `/document` |
| `verifier` | Quality checks before PR | `/verify` |
| `software-engineering-professor` | Teaches issues and concepts | `/lecture-on-issue` |

## Workflow

1. Pick a GitHub issue on the [Project board](https://github.com/users/RoxanaTapia/projects/3).
2. *(Optional)* `/lecture-on-issue #NN`
3. `/ship-issue #NN`
4. `/document` if docs deliverables → `/verify` → PR → human approves merge
5. `/ship-complete #NN` after merge

## Slash Commands

| Command | Purpose |
|---------|---------|
| `/ship-issue` | Ship one GitHub issue end-to-end |
| `/document` | Docs-writer review |
| `/verify` | Acceptance criteria coverage before PR |
| `/ship-complete` | Tick issue checkboxes after merge |
| `/lecture-on-issue` | Learn before building |

## Rules

| Rule | Scope |
|------|-------|
| `.cursor/rules/documentation.mdc` | Markdown docs |
| `.cursor/rules/elegant-minimal-python.mdc` | Python code |

## Commit & PR Policy

- Granular commits (ideally 1–4 per issue)
- Only `milestone-orchestrator` creates commits
- PR starts with a **Main contribution** paragraph
- Human must approve before push or merge

## Notes for Cursor

Read this file at the start of a new agent chat. Open **this repo** as the workspace root for Module 4 `/ship-issue`.
