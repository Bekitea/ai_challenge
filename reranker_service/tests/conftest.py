"""Общая настройка тестов reranker_service.

Сервис намеренно изолирован в отдельном окружении (Python 3.12 + torch), но
его HTTP-контракт хочется проверять в основном наборе. Поэтому до импорта
``server.py`` в ``sys.modules`` подставляются облегчённые заглушки ``torch`` и
``sentence_transformers``: сам код ``server.py`` при этом не меняется.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parents[1]


class FakeCrossEncoder:
    """Заглушка CrossEncoder: возвращает заранее заданные score."""

    def __init__(self, *args, **kwargs):
        self.predictions: list[float] = []

    def predict(self, pairs, batch_size=None):
        return list(self.predictions)


def _install_stub(name: str, **attrs) -> None:
    if name in sys.modules:
        return
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module


_install_stub("torch", set_num_threads=lambda n: None)
_install_stub("sentence_transformers", CrossEncoder=FakeCrossEncoder)


def _load_server():
    spec = importlib.util.spec_from_file_location(
        "reranker_service_server", SERVICE_DIR / "server.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["reranker_service_server"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def server():
    """Загружает модуль server.py со стабами torch/sentence_transformers."""
    return _load_server()


@pytest.fixture(autouse=True)
def reset_model(server):
    """Сбрасывает загруженную модель до и после каждого теста."""
    server._state["model"] = None
    yield
    server._state["model"] = None


@pytest.fixture()
def fake_encoder(server):
    """Подставляет фейковую модель в состояние сервиса."""
    encoder = FakeCrossEncoder()
    server._state["model"] = encoder
    return encoder
