"""E2E tests: TestUC025_ApiKeysMenu (UC-025).

Выпуск и отзыв API-ключей через главное меню (пункт 6).
"""

from e2e_helpers import run_cli_command
from ground_truth import get_api_keys


def _secret_from_stdout(stdout: str) -> str:
    """Извлекает показанный один раз секрет ключа из вывода CLI."""
    for line in stdout.splitlines():
        if "Ключ: " in line:
            return line.split("Ключ: ", 1)[1].strip()
    return ""


class TestUC025_ApiKeysMenu:
    """TC-149..TC-153: управление API-ключами из главного меню."""

    def test_tc_149_create_api_key_shows_secret_once(self):
        """TC-149: Создание ключа показывает секрет один раз."""
        test_input = "6\n1\nMy Key\n0\n8\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "--- API-КЛЮЧИ ---" in stdout
        assert "[OK] API-ключ 'My Key' создан." in stdout
        assert "Ключ: aic_" in stdout
        assert "больше он не будет показан" in stdout

        secret = _secret_from_stdout(stdout)
        keys = get_api_keys()
        assert len(keys) == 1
        assert keys[0]["name"] == "My Key"
        assert keys[0]["prefix"] == secret[: len(keys[0]["prefix"])]
        assert len(keys[0]["key_hash"]) == 64
        # Открытый секрет в БД не хранится — только хеш
        assert keys[0]["key_hash"] != secret

    def test_tc_150_empty_name_reprompts(self):
        """TC-150: Пустое имя -> ошибка и повторный запрос."""
        test_input = "6\n1\n\nKey B\n0\n8\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "Название API-ключа не может быть пустым." in stdout
        assert "[OK] API-ключ 'Key B' создан." in stdout
        keys = get_api_keys()
        assert [k["name"] for k in keys] == ["Key B"]

    def test_tc_151_list_keys_hides_secret(self):
        """TC-151: Список ключей не показывает секрет (только префикс)."""
        test_input = "6\n1\nKey List\n2\n0\n8\n"

        stdout, _, _ = run_cli_command(test_input)

        full_key = _secret_from_stdout(stdout)
        assert full_key.startswith("aic_")

        assert "--- СПИСОК API-КЛЮЧЕЙ ---" in stdout
        assert "Key List" in stdout
        list_section = stdout.split("--- СПИСОК API-КЛЮЧЕЙ ---", 1)[1]
        # Полный секрет в списке не выводится — только усечённый префикс.
        assert full_key not in list_section
        assert "aic_" in list_section
        assert "…" in list_section

        keys = get_api_keys()
        assert len(keys) == 1
        assert keys[0]["name"] == "Key List"
        assert full_key not in keys[0]["key_hash"]
        assert keys[0]["key_hash"] != full_key

    def test_tc_152_delete_key(self):
        """TC-152: Отзыв ключа удаляет его из списка."""
        test_input = "6\n1\nKeyDel\n3\n1\ny\n2\n0\n8\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "[OK] API-ключ 'KeyDel' отозван." in stdout
        assert "API-ключи отсутствуют." in stdout
        assert get_api_keys() == []

    def test_tc_153_invalid_menu_choice(self):
        """TC-153: Неверный выбор в меню ключей -> предупреждение."""
        test_input = "6\n9\n0\n8\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "Неверный выбор, попробуйте снова." in stdout
        assert get_api_keys() == []
