"""Эндпоинт AI-ревью pull request (UC-032).

Лёгкий раннер GitHub Actions собирает diff и метаданные PR, отправляет их сюда
одним POST-запросом; бэкенд делает RAG-поиск по базе знаний «Ревью кода»,
вызывает LLM и возвращает готовый Markdown. Presentation остаётся DTO-only.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

import config
from core.application.dtos.code_review_dto import CodeReviewRequestDTO
from core.presentation.api.deps import UseCasesDep
from core.presentation.api.schemas import CodeReviewRequest, CodeReviewResponse

router = APIRouter(tags=["reviews"])


@router.post("/review-pr", response_model=CodeReviewResponse)
def review_pull_request(request: CodeReviewRequest, uc: UseCasesDep):
    """Выполняет AI-ревью pull request по переданному diff."""
    if not config.REVIEW_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI-ревью PR отключено (REVIEW_ENABLED=false).",
        )

    result = uc.review_pull_request.execute(
        CodeReviewRequestDTO(
            repo=request.repo,
            pr_number=request.pr_number,
            pr_title=request.pr_title,
            author=request.author,
            base_branch=request.base_branch,
            head_branch=request.head_branch,
            changed_files=list(request.changed_files),
            diff=request.diff,
        )
    )
    return CodeReviewResponse.model_validate(result)
