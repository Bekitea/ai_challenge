from __future__ import annotations

import asyncio
import contextlib
import io
import sys
import threading
from typing import Any

from core.infrastructure.mcp.null_device import _NullDevice

# Кэш настоящих stdout/stderr процесса (см. _real_std_streams).
_CACHED_REAL_STREAMS: tuple[Any, Any] | None = None


def _real_std_streams() -> tuple[Any, Any]:
    """Возвращает настоящие stdout/stderr процесса.

    Celery на Windows подменяет sys.stdout/sys.stderr объектом LoggingProxy
    (для перехвата вывода в лог воркера). У этого прокси нет метода fileno,
    и anyio падает с AttributeError при запуске stdio-процесса MCP. Поэтому
    перед каждым запуском event loop используются реальные потоки:
    sys.__stdout__/__stderr__, а если и они уже заменены — оригинальные
    файловые дескрипторы 1/2, восстановленные через os.dup().

    Результат кэшируется на весь срок жизни процесса: дескрипторы не меняются,
    а лишний dup() при каждом обращении только копировал бы fd.
    """
    global _CACHED_REAL_STREAMS
    if _CACHED_REAL_STREAMS is not None:
        return _CACHED_REAL_STREAMS

    import os

    def _has_fileno(stream: Any) -> bool:
        try:
            stream.fileno()
            return True
        except (AttributeError, OSError, ValueError, io.UnsupportedOperation):
            return False

    if _has_fileno(sys.__stdout__) and _has_fileno(sys.__stderr__):
        _CACHED_REAL_STREAMS = (sys.__stdout__, sys.__stderr__)
        return _CACHED_REAL_STREAMS

    # Стандартные потоки заменены — восстанавливаем дескрипторы через dup.
    def _make(fd: int) -> Any:
        try:
            saved_fd = os.dup(fd)
        except OSError:
            return _NullDevice()
        return open(saved_fd, "wb", buffering=0, closefd=True)

    _CACHED_REAL_STREAMS = (_make(1), _make(2))
    return _CACHED_REAL_STREAMS


def _stderr_for_child() -> Any:
    """Поток для stderr дочернего MCP-процесса (гарантированно с fileno).

    stdio_client передаёт errlog напрямую в Popen(stderr=...). Если там
    окажется Celery-прокси LoggingProxy (у него нет fileno), запуск процесса
    упадёт с AttributeError. Поэтому всегда отдаём реальный поток из
    _real_std_streams(), а если достать его не удалось — заглушку, которую
    subprocess превращает в DEVNULL (вывод сервера в логах потерян, но
    подключение работает).
    """
    _, real_err = _real_std_streams()
    if hasattr(real_err, "fileno"):
        return real_err
    return _NullDevice()


def run_async_in_new_loop(coro_factory: Any, timeout: float | None = None) -> Any:
    """Запускает корутину в НОВОМ event loop в текущем потоке.

    Важно: anyio-ресурсы (stdio-контексты MCP) привязаны к loops, в которых
    созданы, поэтому все операции с одним подключением должны выполняться
    в одном и том же типе запуска — новом loop в рабочем потоке.

    Перед запуском временно восстанавливает настоящие stdout/stderr: под
    Celery на Windows они заменены LoggingProxy без fileno().

    Args:
        coro_factory: Асинхронная функция (не вызванная!) либо фабрика,
            возвращающая корутину.
        timeout: Таймаут выполнения в секундах (None — без таймаута).

    Returns:
        Результат выполнения корутины.

    Raises:
        Любое исключение, брошенное внутри корутины.
        TimeoutError: если превышен таймаут.
    """
    # Нормализуем аргумент: раньше сюда передавали уже созданную корутину
    # (например, connection.connect_and_list_tools()), что приводило к
    # «coroutine was never awaited» и утечке coroutine-origin контекста
    # (sys.exc_info) в чужие потоки.
    if callable(coro_factory):
        make_coro = coro_factory
    else:
        created = coro_factory  # уже готовая корутина (обратная совместимость)

        def make_coro():
            return created

    loop = asyncio.new_event_loop()
    try:
        # Коруину создаём ВНУТРИ восстановленного окружения потоков:
        # stdio_client(server_params, errlog=sys.stderr) вычисляет значение
        # errlog в МОМЕНТ создания корутины. Если создать её до замены
        # sys.stderr, в дочерний процесс Popen(stderr=...) улетит LoggingProxy
        # Celery и anyio/asyncio упадут с «'LoggingProxy' object has no
        # attribute 'fileno'».
        saved_streams = (sys.stdout, sys.stderr)
        real_out, real_err = _real_std_streams()
        sys.stdout, sys.stderr = real_out, real_err
        try:
            coro = make_coro()
        finally:
            sys.stdout, sys.stderr = saved_streams
        if timeout is not None:
            return loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
        return loop.run_until_complete(coro)
    finally:
        with contextlib.suppress(Exception):
            loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


def describe_exception(exc: BaseException) -> str:
    """Извлекает настоящую причину из исключения anyio/TaskGroup.

    anyio заворачивает ошибки в ExceptionGroup («unhandled errors in a
    TaskGroup (1 sub-exception)»), из-за чего исходная причина (например,
    ImportError упавшего MCP-сервера) не видна пользователю. Эта функция
    рекурсивно спускается по sub-exceptions и возвращает читаемое сообщение.
    """
    seen: set[int] = set()

    def _leaves(e: BaseException) -> list[BaseException]:
        if id(e) in seen:
            return []
        seen.add(id(e))
        subs = getattr(e, "exceptions", None)
        if subs:
            leaves: list[BaseException] = []
            for sub in subs:
                leaves.extend(_leaves(sub))
            return leaves or [e]
        return [e]

    leaves = _leaves(exc)
    messages: list[str] = []
    for leaf in leaves:
        text = str(leaf).strip()
        msg = f"{type(leaf).__name__}: {text}" if text else type(leaf).__name__
        if msg not in messages:
            messages.append(msg)
    return "; ".join(messages) if messages else repr(exc)


def submit_to_new_loop(
    coro_factory: Any, timeout: float | None = None
) -> tuple[Any, BaseException | None]:
    """Запускает корутину в новом потоке (со своим event loop) и ждёт результата.

    Используется для операций, которые могут блокироваться (например,
    initialize handshake с зависшим сервером): при таймауте поток-«убийца»
    просто остаётся «висячим», но основной поток не блокируется.

    Returns:
        Кортеж (result, exception).
    """
    result: list[Any] = []
    error: list[BaseException | None] = []

    def _worker() -> None:
        try:
            result.append(run_async_in_new_loop(coro_factory))
        except BaseException as exc:  # noqa: BLE001
            error.append(exc)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        return None, TimeoutError("Операция с MCP-сервером превысила таймаут")
    if error:
        return None, error[0]
    return (result[0] if result else None), None
