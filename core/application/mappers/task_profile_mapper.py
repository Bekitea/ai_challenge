from __future__ import annotations

from core.application.dtos.task_profile_detail_dto import TaskProfileDetailDTO
from core.application.dtos.task_profile_info import TaskProfileInfo
from core.domain.dtos.task_profile import TaskProfile


def _task_profile_to_info(profile: TaskProfile) -> TaskProfileInfo:
    """Преобразует ``TaskProfile`` в краткий DTO для списка."""
    return TaskProfileInfo(
        id=profile.id,
        name=profile.name,
        description=profile.description,
        created_at=profile.created_at,
        facts_count=len(profile.facts),
        preferences=profile.preferences or "",
        invariants_count=len(profile.invariants),
        mcp_servers=list(profile.mcp_servers),
    )


def _task_profile_to_detail(profile: TaskProfile) -> TaskProfileDetailDTO:
    """Преобразует ``TaskProfile`` в детальный DTO с памятью."""
    return TaskProfileDetailDTO(
        id=profile.id,
        name=profile.name,
        description=profile.description,
        created_at=profile.created_at,
        facts=list(profile.facts),
        preferences=profile.preferences or "",
        invariants=list(profile.invariants),
        mcp_servers=list(profile.mcp_servers),
    )
