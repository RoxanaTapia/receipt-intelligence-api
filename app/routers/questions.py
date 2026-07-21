"""Natural-language question answering endpoint (#8)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.claude_client import AnthropicClaudeClient, ClaudeCompleter
from app.config import get_anthropic_api_key, get_receipt_data_path
from app.qa_models import QuestionRequest, QuestionResponse
from app.qa_service import answer_question

router = APIRouter(tags=["questions"])


def get_data_path() -> Path:
    """Resolved receipt directory — overridden in tests."""
    return get_receipt_data_path()


def get_claude() -> ClaudeCompleter:
    """Live Claude client — overridden in tests with a stub."""
    if not get_anthropic_api_key():
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not configured (see .env.example)",
        )
    return AnthropicClaudeClient()


@router.post("/questions", response_model=QuestionResponse)
def post_question(
    body: QuestionRequest,
    data_path: Path = Depends(get_data_path),
    claude: ClaudeCompleter = Depends(get_claude),
) -> QuestionResponse:
    """Answer a spending question grounded in analytics facts."""
    return answer_question(body.question, data_path=data_path, claude=claude)
