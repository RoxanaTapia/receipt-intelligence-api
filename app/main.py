"""FastAPI entrypoint for the Receipt Intelligence API."""

from fastapi import FastAPI

from app.routers import analytics, questions

app = FastAPI(
    title="Receipt Intelligence API",
    description=(
        "Spending analytics and grounded natural-language Q&A over categorized "
        "receipt JSON. Schemas: docs/analytics-schema.md; Q&A: docs/question-answering.md."
    ),
)

app.include_router(analytics.router)
app.include_router(questions.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
