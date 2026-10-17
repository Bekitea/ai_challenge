"""Эндпоинты профилей задач и их инвариантов."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from core.presentation.api.deps import UseCasesDep
from core.presentation.api.schemas import (
    ActionResult,
    AddInvariantRequest,
    CreateTaskProfileRequest,
    DeleteProfileResult,
    Invariant,
    TaskProfile,
    TaskProfileDetail,
)

router = APIRouter(tags=["task-profiles"])


@router.get("/task-profiles", response_model=list[TaskProfile])
def list_task_profiles(uc: UseCasesDep):
    """Список профилей задач."""
    return uc.list_task_profiles.execute()


@router.post("/task-profiles", response_model=TaskProfile, status_code=201)
def create_task_profile(
    request: CreateTaskProfileRequest, uc: UseCasesDep
):
    """Создаёт профиль задачи."""
    return uc.create_task_profile.execute(
        request.name,
        request.description,
        request.preferences,
        request.invariants,
    )


@router.get("/task-profiles/{profile_id}", response_model=TaskProfileDetail)
def get_task_profile(profile_id: str, uc: UseCasesDep):
    """Профиль задачи с памятью."""
    profile = uc.get_task_profile_memory.execute(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Профиль {profile_id} не найден")
    return profile


@router.delete("/task-profiles/{profile_id}", response_model=DeleteProfileResult)
def delete_task_profile(profile_id: str, uc: UseCasesDep):
    """Удаляет профиль задачи (если он не привязан к чатам)."""
    return uc.delete_task_profile.execute(profile_id)


@router.get("/task-profiles/{profile_id}/invariants", response_model=list[Invariant])
def list_invariants(profile_id: str, uc: UseCasesDep):
    """Инварианты профиля задачи."""
    return uc.list_invariants.execute(profile_id)


@router.post(
    "/task-profiles/{profile_id}/invariants",
    response_model=Invariant,
    status_code=status.HTTP_201_CREATED,
)
def add_invariant(
    profile_id: str,
    request: AddInvariantRequest,
    uc: UseCasesDep,
):
    """Добавляет инвариант в профиль задачи."""
    return uc.add_invariant.execute(profile_id, request.text)


@router.delete("/invariants/{invariant_id}", response_model=ActionResult)
def remove_invariant(
    invariant_id: int, uc: UseCasesDep
):
    """Удаляет инвариант по ID."""
    removed = uc.remove_invariant.execute(invariant_id)
    return ActionResult(success=removed)
