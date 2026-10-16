"""Тесты сценарного мока LLM (инфраструктура e2e-тестов).

Проверяют, что ``MOCK_LLM_SCENARIO`` позволяет разным тестам получать разные
ответы провайдера, не меняя код приложения.
"""

from e2e_helpers import _QUICK_CHAT, mock_llm, run_cli_command
from ground_truth import get_global_facts, get_messages_by_name


class TestMockLlmScenarios:
    """Инфраструктурные тесты сценарного мока (UC-004/UC-012)."""

    def test_scripted_responses_used_in_order(self):
        """Сценарий отдаёт заранее заданные ответы по порядку."""
        scenario = mock_llm(
            responses=[
                {
                    "content": "ПЕРВЫЙ ОТВЕТ",
                    "reasoning": "размышление-1",
                    "prompt_tokens": 11,
                    "completion_tokens": 2,
                },
                {
                    "content": "ВТОРОЙ ОТВЕТ",
                    "reasoning": "размышление-2",
                    "prompt_tokens": 12,
                    "completion_tokens": 3,
                },
            ]
        )
        test_input = _QUICK_CHAT + "msg1\nmsg2\n/menu\n8\n"

        run_cli_command(test_input, mock=scenario)

        assistants = [
            m for m in get_messages_by_name("Чат 1") if m["role"] == "assistant"
        ]
        assert [m["content"] for m in assistants] == ["ПЕРВЫЙ ОТВЕТ", "ВТОРОЙ ОТВЕТ"]
        assert assistants[0]["reasoning"] == "размышление-1"

    def test_json_object_scenario_controls_global_facts(self):
        """Сценарий json_object задаёт факты, извлечённые в глобальную память."""
        scenario = mock_llm(json_object={"facts": ["Пользователь любит тесты"]})
        test_input = _QUICK_CHAT + "привет\n/menu\n8\n"

        run_cli_command(test_input, mock=scenario)

        assert get_global_facts() == ["Пользователь любит тесты"]

    def test_error_scenario_degrades_gracefully(self):
        """Ошибка провайдера не роняет приложение: выводится [ERROR]."""
        scenario = mock_llm(default={"error": "timeout"})
        test_input = _QUICK_CHAT + "привет\n/menu\n8\n"

        stdout, _, _ = run_cli_command(test_input, mock=scenario)

        assert "[ERROR]" in stdout
