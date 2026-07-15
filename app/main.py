"""FastAPI entrypoint for the Receipt Intelligence API."""

from fastapi import FastAPI

app = FastAPI(title="Receipt Intelligence API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
