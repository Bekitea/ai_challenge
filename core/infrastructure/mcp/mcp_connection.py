from __future__ import annotations

import contextlib
import os
from typing import Any

from mcp.client.stdio import stdio_client

from core.infrastructure.mcp.async_runner import (
    _stderr_for_child,
    describe_exception,
    submit_to_new_loop,
)
from core.infrastructure.mcp.mcp_server_info import McpServerInfo
from core.infrastructure.mcp.mcp_tool_info import McpToolInfo
from mcp import ClientSession, StdioServerParameters


class McpConnection:
    """Живое stdio-подключение к одному MCP-серверу.

    Все операции выполняются в отдельных потоках с новыми event loop
    (см. run_async_in_new_loop), что позволяет использовать один объект
    из синхронного кода CLI.
    """

    CONNECT_TIMEOUT = 30.0  # секунд на запуск сервера и initialize handshake
    CALL_TIMEOUT = 120.0  # секунд на вызов инструмента

    def __init__(self, server_info: McpServerInfo):
        self.server_info = server_info
        self.name = server_info.name
        self._tools: list[McpToolInfo] = []
        self._connected = False
        self._connect_error: str | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def connect_error(self) -> str | None:
        return self._connect_error

    @property
    def tools(self) -> list[McpToolInfo]:
        return list(self._tools)

    def _server_params(self) -> StdioServerParameters:
        command, args = self.server_info.build_command()
        # Передаём окружение процесса целиком: по умолчанию SDK отдаёт
        # дочернему процессу лишь «безопасный» поднабор переменных, из-за чего
        # серверы не видели своих настроек (PROJECT_FILES_ROOT,
        # SUPPORT_DATA_PATH, OPENALEX_* и т.п.).
        return StdioServerParameters(
            command=command, args=args, env=dict(os.environ)
        )

    @staticmethod
    def _is_proxy_stream_error(exc: BaseException) -> bool:
        """Проверяет, что ошибка вызвана подменёнными stdin/stdout процесса.

        Celery на Windows подменяет стандартные потоки своего лога объектом
        LoggingProxy (без метода fileno). Если такой поток каким-либо образом
        попал в окружение воркера, anyio падает с AttributeError при запуске
        дочернего stdio-процесса — это не ошибка сервера, а особенность
        среды, поэтому её нужно переживать, а не считать фатальной.
        """
        candidates: list[BaseException] = []
        seen: set[int] = set()

        def _collect(e: BaseException | None) -> None:
            if e is None or id(e) in seen:
                return
            seen.add(id(e))
            candidates.append(e)
            _collect(e.__cause__)
            _collect(e.__context__)
            for sub in getattr(e, "exceptions", []) or []:
                _collect(sub)

        _collect(exc)
        return any(
            isinstance(e, AttributeError) and "fileno" in str(e) for e in candidates
        )

    def _precheck_spawn(self) -> str | None:
        """Быстрая проверка, что сервер вообще можно запустить.

        Запускает серверный процесс и ждёт несколько секунд: если он упал
        (например, из-за ImportError или синтаксической ошибки в скрипте),
        возвращает понятное сообщение с его stderr. Возвращает None, если
        процесс жив (или запускается медленно — дальше решит handshake).
        """
        import subprocess

        command, args = self.server_info.build_command()
        try:
            proc = subprocess.Popen(
                [command, *args],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            return f"Не удалось запустить процесс сервера: {exc}"
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            with contextlib.suppress(subprocess.TimeoutExpired, OSError):
                proc.wait(timeout=5)
            return None
        stderr_text = ""
        with contextlib.suppress(OSError, ValueError, AssertionError):
            assert proc.stderr is not None
            stderr_text = proc.stderr.read().decode("utf-8", errors="replace").strip()
        code = proc.returncode
        tail = "\n".join(stderr_text.splitlines()[-15:]) if stderr_text else ""
        message = f"MCP-сервер завершился при запуске с кодом {code}."
        if tail:
            message += f"\nВывод сервера:\n{tail}"
        return message

    def connect_and_list_tools(self) -> list[McpToolInfo]:
        """Подключается к серверу, инициализирует сессию и получает список инструментов.

        Запускается в отдельном потоке: если сервер «висит», основной поток
        не блокируется дольше CONNECT_TIMEOUT.

        Returns:
            Список инструментов сервера (пустой при ошибке).
        """
        precheck_error = self._precheck_spawn()
        if precheck_error is not None:
            self._connected = False
            self._connect_error = precheck_error
            self._tools = []
            return []
        tools, error = submit_to_new_loop(
            self._connect_and_list_async, timeout=self.CONNECT_TIMEOUT
        )
        if error is not None:
            self._connected = False
            self._connect_error = describe_exception(error)
            self._tools = []
            return []
        self._tools = tools or []
        self._connected = True
        self._connect_error = None
        return self.tools

    async def _connect_and_list_async(self) -> list[McpToolInfo]:
        # errlog передаём ЯВНО: у stdio_client значение аргумента по умолчанию
        # (sys.stderr) вычисляется в момент определения функции в модуле mcp,
        # где уже мог быть захвачен Celery-прокси LoggingProxy без fileno().
        # Дочерний MCP-процесс не должен получать stderr-поток без fd.
        async with (
            stdio_client(self._server_params(), errlog=_stderr_for_child()) as (
                read,
                write,
            ),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            result = await session.list_tools()
            return [
                McpToolInfo(
                    server_name=self.name,
                    name=tool.name,
                    prefixed_name=f"{self.name}__{tool.name}",
                    description=tool.description or "",
                    input_schema=(
                        dict(tool.input_schema)
                        if isinstance(tool.input_schema, dict)
                        else {}
                    ),
                )
                for tool in result.tools
            ]

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Вызывает инструмент сервера (по оригинальному имени) и возвращает текст.

        Args:
            tool_name: Оригинальное имя инструмента (без префикса сервера).
            arguments: Аргументы инструмента.

        Returns:
            Текстовый результат (или текст ошибки — исключения не пробрасываются,
            чтобы агент мог продолжить диалог).
        """
        result, error = submit_to_new_loop(
            lambda: self._call_async(tool_name, arguments),
            timeout=self.CALL_TIMEOUT,
        )
        if error is not None:
            return f"[MCP:{self.name}] Ошибка вызова инструмента '{tool_name}': {error}"
        return result if result is not None else ""

    async def _call_async(self, tool_name: str, arguments: dict[str, Any]) -> str:
        # errlog — явно, см. комментарий в _connect_and_list_async.
        async with (
            stdio_client(self._server_params(), errlog=_stderr_for_child()) as (
                read,
                write,
            ),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            result = await session.call_tool(name=tool_name, arguments=arguments)

            texts: list[str] = []
            for content in result.content or []:
                text = getattr(content, "text", None)
                if text is not None:
                    texts.append(text)
                elif getattr(content, "type", "") == "resource":
                    resource = getattr(content, "resource", None)
                    body = getattr(resource, "text", None)
                    if body is not None:
                        texts.append(body)
            output = "\n".join(texts) if texts else "(пустой ответ)"
            if getattr(result, "isError", False):
                return f"[MCP:{self.name}] Инструмент вернул ошибку: {output}"
            return output

    def close(self) -> None:
        """Закрывает подключение (сессия одноразовая, ресурсов не держим)."""
        self._connected = False
        self._tools = []
