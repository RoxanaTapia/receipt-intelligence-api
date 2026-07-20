"""FastAPI entrypoint for the Receipt Intelligence API."""

from fastapi import FastAPI

from app.routers import analytics

app = FastAPI(
    title="Receipt Intelligence API",
    description=(
        "Spending analytics over categorized receipt JSON. "
        "Response shapes: docs/analytics-schema.md."
    ),
)

app.include_router(analytics.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
