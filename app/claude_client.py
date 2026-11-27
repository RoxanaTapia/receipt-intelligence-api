"""Thin Anthropic Messages API wrapper for Q&A (#8)."""

from __future__ import annotations

from typing import Protocol

from app.config import get_anthropic_api_key, get_anthropic_model


class ClaudeCompleter(Protocol):
    def complete(self, *, system: str, user: str) -> str:
        """Return assistant text for a system + user message pair."""


class AnthropicClaudeClient:
    """Live Claude client — requires ANTHROPIC_API_KEY."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else get_anthropic_api_key()
        self._model = model or get_anthropic_model()

    def complete(self, *, system: str, user: str) -> str:
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set — add it to .env (see .env.example)")

        import anthropic

        client = anthropic.Anthropic(api_key=self._api_key)
        message = client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts = [block.text for block in message.content if hasattr(block, "text")]
        text = "".join(parts).strip()
        if not text:
            raise RuntimeError("Claude returned an empty response")
        return text
