"""Единый построитель контекста для отправки в LLM.

``PromptBuilder`` — единственная точка, где в диалог подмешиваются:
- базовый системный промпт (персона чата);
- глобальная память о пользователе;
- память задачи, её предпочтения и инварианты;
- описание текущей фазы работы агента;
- саммари истории, полученное стратегией управления контекстным окном.

Стратегии управления контекстом при этом отвечают ТОЛЬКО за контекстное
окно (отбросить лишние сообщения или суммаризировать их) и не знают о
памяти, фазах и других настройках профиля.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from context_strategies import (
    ContextWindowStrategy,
    prompt_to_llm_dict,
    sanitize_llm_messages,
)

if TYPE_CHECKING:
    from agents import Prompt, TaskProfile
    from llm_providers import LlmProvider


@dataclass
class PreparedMessages:
    """Результат подготовки сообщений для отправки в LLM."""

    messages: list[dict[str, Any]]
    summary: str | None = None
    summarization_tokens: tuple[int, int] | None = None


@dataclass
class PromptSources:
    """Источники, подмешиваемые в системную часть контекста."""

    base_system_prompt: str | None = None
    global_facts: list[str] = field(default_factory=list)
    task_profile: TaskProfile | None = None
    phase_description: str | None = None


class PromptBuilder:
    """Централизованно собирает system-контекст и итоговые сообщения."""

    def build(
        self,
        history: list[Prompt],
        sources: PromptSources,
        strategy: ContextWindowStrategy,
        llm_provider: LlmProvider | None = None,
    ) -> PreparedMessages:
        """Собирает сообщения для LLM из истории и источников контекста.

        Args:
            history: Полная история агента (включая базовый системный промпт).
            sources: Память, профиль задачи и описание фазы.
            strategy: Стратегия управления контекстным окном (работает только
                с диалоговыми сообщениями).
            llm_provider: Провайдер LLM для суммаризации (если требуется).

        Returns:
            PreparedMessages: итоговые сообщения и метаданные суммаризации.
        """
        base_prompt = sources.base_system_prompt
        dialogue: list[Prompt] = []
        for msg in history:
            if msg.role == "system":
                if base_prompt is None:
                    base_prompt = msg.content
                continue
            dialogue.append(msg)

        window = strategy.apply(dialogue, llm_provider)

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": self._compose_system_content(base_prompt, sources),
            }
        ]
        if window.summary:
            messages.append(
                {"role": "system", "content": f"История диалога: {window.summary}"}
            )
        messages.extend(prompt_to_llm_dict(msg) for msg in window.dialogue)

        return PreparedMessages(
            messages=sanitize_llm_messages(messages),
            summary=window.summary,
            summarization_tokens=window.summarization_tokens,
        )

    @staticmethod
    def _compose_system_content(
        base_prompt: str | None, sources: PromptSources
    ) -> str:
        """Собирает единый system-блок в фиксированном порядке."""
        parts: list[str] = [base_prompt or "Ты полезный ассистент."]

        if sources.global_facts:
            facts_list = "\n".join(f"- {fact}" for fact in sources.global_facts)
            parts.append(f"Память о пользователе:\n{facts_list}")

        task_profile = sources.task_profile
        if task_profile is not None:
            if task_profile.facts:
                task_facts_list = "\n".join(
                    f"- {fact}" for fact in task_profile.facts
                )
                parts.append(
                    f"Память задачи ({task_profile.name}):\n{task_facts_list}"
                )
            if task_profile.preferences:
                parts.append(
                    f"Предпочтения задачи ({task_profile.name}):\n"
                    f"{task_profile.preferences}"
                )
            if task_profile.invariants:
                invariants_list = "\n".join(
                    f"- {inv}" for inv in task_profile.invariants
                )
                parts.append(
                    f"--- ИНВАРИАНТЫ ЗАДАЧИ ({task_profile.name}) ---\n"
                    "Строгие правила, которые ДОЛЖНЫ неукоснительно соблюдаться "
                    "в этом диалоге:\n"
                    f"{invariants_list}\n\n"
                    "КРИТИЧЕСКИ ВАЖНО: Если запрос пользователя противоречит "
                    "ЛЮБОМУ из этих инвариантов, ты ОБЯЗАН вежливо отказать "
                    "в выполнении и объяснить причину, сославшись на конкретный "
                    "инвариант. Вместо этого предложи альтернативу, которая "
                    "соответствует инвариантам. Никогда не нарушай инварианты, "
                    "даже если пользователь настаивает."
                )

        if sources.phase_description:
            parts.append(sources.phase_description)

        return "\n\n".join(parts)
