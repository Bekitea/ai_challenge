from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.domain.dtos.task_memory import TaskMemory
from core.domain.dtos.task_profile import TaskProfile

if TYPE_CHECKING:
    from core.domain.dtos.rag_context_chunk import RagContextChunk


@dataclass
class PromptSources:
    """Источники, подмешиваемые в системную часть контекста."""

    base_system_prompt: str | None = None
    global_facts: list[str] = field(default_factory=list)
    task_profile: TaskProfile | None = None
    phase_description: str | None = None
    rag_context: list[RagContextChunk] = field(default_factory=list)
    rag_enabled: bool = False
    task_memory: TaskMemory | None = None
