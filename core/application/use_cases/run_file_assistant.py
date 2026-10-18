from __future__ import annotations

from core.application.dtos.file_assistant_result_dto import FileAssistantResultDTO
from core.application.use_cases.prepare_assistant_context import (
    PrepareAssistantContextUseCase,
)
from core.application.use_cases.send_message import SendMessageUseCase

# Goal-level инструкция: ассистент сам решает, какие файлы читать и менять,
# показывает diff до применения и подводит итог по изменениям. Задача
# пользователя подставляется в шаблон ("""{goal}""").
FILE_ASSISTANT_INSTRUCTION = """\
Ты — ассистент по работе с файлами проекта. Работай автономно и доводи задачу \
до результата, сам определяя, какие файлы нужно изучить и изменить. Не проси \
пользователя открывать конкретные файлы — находи их сам доступными инструментами.

Правила работы:
1. Сначала изучи проект: ищи информацию по нескольким файлам (search_in_files), \
читай нужные файлы (read_file), при необходимости смотри git-контекст \
(list_changed_files, get_diff).
2. Для изменений используй write_file/replace_in_file. По умолчанию они возвращают \
preview-diff и НЕ меняют файл: сначала покажи diff, затем вызови инструмент повторно \
с apply=True, чтобы применить изменение.
   - Для СУЩЕСТВУЮЩИХ файлов применяй replace_in_file и заменяй только нужный \
фрагмент. НИКОГДА не переписывай существующий файл целиком через write_file.
   - write_file используй только для НОВЫХ файлов.
   - Держи аргументы инструментов компактными: не вставляй в один вызов содержимое \
большого файла целиком (иначе ответ обрывается по лимиту токенов). Вызывай \
инструменты по одному.
3. При необходимости работай минимум с 2–3 файлами.
4. В конце ответа кратко перечисли, какие файлы прочитал и какие изменил, и приведи \
итоговый diff/список изменений.
5. Не трогай файлы с секретами (`.env*`), не выходи за пределы корня проекта и \
сохраняй формат/стиль существующих файлов.

Задача пользователя: {goal}
"""


class RunFileAssistantUseCase:
    """Выполняет задачу пользователя по работе с файлами проекта.

    Готовит контекст чата (проектная БЗ + MCP-серверы ``files``/``git``), затем
    оборачивает цель пользователя в goal-level инструкцию и передаёт её агенту
    через обычный ``send_message``. Presentation остаётся DTO-only.
    """

    def __init__(
        self,
        *,
        prepare_context: PrepareAssistantContextUseCase,
        send_message: SendMessageUseCase,
        instruction_template: str = FILE_ASSISTANT_INSTRUCTION,
    ):
        self._prepare_context = prepare_context
        self._send_message = send_message
        self._instruction = instruction_template

    def execute(self, agent_id: int, goal: str) -> FileAssistantResultDTO:
        """Готовит контекст и отправляет задачу агенту.

        Args:
            agent_id: ID чата, в котором выполняется задача.
            goal: Формулировка задачи на уровне цели.

        Returns:
            FileAssistantResultDTO: сообщения о подготовке контекста и ответ
            агента (None, если цель пуста).
        """
        messages = self._prepare_context.execute(agent_id)
        goal = goal.strip()
        if not goal:
            return FileAssistantResultDTO(messages=messages, response=None)

        prompt = self._instruction.format(goal=goal)
        response = self._send_message.execute(agent_id, prompt)
        return FileAssistantResultDTO(messages=messages, response=response)
