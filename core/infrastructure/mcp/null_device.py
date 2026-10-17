from __future__ import annotations

from typing import Any


class _NullDevice:
    """Заглушка потока вывода для дочерних процессов (бросает вывод в void)."""

    def read(self, *_args: Any, **_kwargs: Any) -> bytes:
        return b""

    def readline(self, *_args: Any, **_kwargs: Any) -> bytes:
        return b""

    def write(self, *_args: Any, **_kwargs: Any) -> int:
        return 0

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass
