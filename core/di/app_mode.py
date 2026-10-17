from dataclasses import dataclass
from enum import Enum, auto
from typing import Final

import config


class AppMode(Enum):
    """Режимы работы приложения."""

    PRODUCTION = auto()  # Реальный LLM провайдер
    TEST = auto()  # Mock провайдер
    LOCAL = auto()  # Локальный запуск (Ollama и т.п.) без обязательных ключей


@dataclass(frozen=True)
class ModeConfig:
    """Конфигурация режима работы."""

    mode: AppMode
    use_mock_provider: bool
    require_env_vars: bool


# Константы режимов
PRODUCTION_MODE: Final = ModeConfig(
    mode=AppMode.PRODUCTION,
    use_mock_provider=False,
    require_env_vars=True,
)

TEST_MODE: Final = ModeConfig(
    mode=AppMode.TEST,
    use_mock_provider=True,
    require_env_vars=False,
)

# Локальный режим: реальные провайдеры (например, Ollama), но без
# обязательных ключей Yandex Cloud.
LOCAL_MODE: Final = ModeConfig(
    mode=AppMode.LOCAL,
    use_mock_provider=False,
    require_env_vars=False,
)


def get_mode_config() -> ModeConfig:
    """Возвращает конфигурацию на основе APPLICATION_MODE из config.py.

    Returns:
        ModeConfig: Конфигурация режима.
    """
    mode = config.APPLICATION_MODE
    if mode == "TEST":
        return TEST_MODE
    if mode == "LOCAL":
        return LOCAL_MODE
    return PRODUCTION_MODE


def validate_production_env(
    yandex_api_key: str | None, yandex_folder_id: str | None
) -> None:
    """Проверяет наличие необходимых переменных окружения для продакшен режима.

    Args:
        yandex_api_key: API ключ Yandex Cloud.
        yandex_folder_id: ID папки Yandex Cloud.

    Raises:
        EnvironmentError: Если отсутствуют необходимые переменные окружения.
    """
    missing_vars = []
    if not yandex_api_key:
        missing_vars.append("YANDEX_CLOUD_API_KEY")
    if not yandex_folder_id:
        missing_vars.append("YANDEX_CLOUD_FOLDER")

    if missing_vars:
        raise OSError(
            f"Для работы в продакшен режиме необходимы переменные окружения: {', '.join(missing_vars)}. "
        )
