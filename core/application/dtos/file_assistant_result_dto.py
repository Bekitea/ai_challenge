from __future__ import annotations

from dataclasses import dataclass, field

from core.application.dtos.message_response_dto import MessageResponseDTO


@dataclass
class FileAssistantResultDTO:
    """Результат команды файлового ассистента (``/files``).

    ``messages`` — информационные/предупредительные сообщения о подготовке
    контекста (подключение проектной БЗ и MCP-серверов). ``response`` —
    ответ агента, если задача была передана; ``None`` для пустой задачи
    (тогда presentation выводит подсказку).
    """

    messages: list[str] = field(default_factory=list)
    response: MessageResponseDTO | None = None
