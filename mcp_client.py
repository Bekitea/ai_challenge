from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import dataclass, field
from typing import Any

from mcp.client.stdio import stdio_client

from mcp import ClientSession, StdioServerParameters
from mcp_registry import McpServerInfo


def run_async_in_new_loop(coro_factory: Any, timeout: float | None = None) -> Any:
    """Запускает корутину в НОВОМ event loop в текущем потоке.

    Важно: anyio-ресурсы (stdio-контексты MCP) привязаны к loops, в которых
    созданы, поэтому все операции с одним подключением должны выполняться
    в одном и том же типе запуска — новом loop в рабочем потоке.

    Args:
        coro_factory: Функция без аргументов, возвращающая корутину.
        timeout: Таймаут выполнения в секундах (None — без таймаута).

    Returns:
        Результат выполнения корутины.

    Raises:
        Любое исключение, брошенное внутри корутины.
        TimeoutError: если превышен таймаут.
    """
    loop = asyncio.new_event_loop()
    try:
        if timeout is not None:
            return loop.run_until_complete(
                asyncio.wait_for(coro_factory(), timeout=timeout)
            )
        return loop.run_until_complete(coro_factory())
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
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


@dataclass
class McpToolInfo:
    """Информация об инструменте MCP-сервера."""

    server_name: str
    name: str  # оригинальное имя инструмента на сервере
    prefixed_name: str  # имя инструмента, передаваемое в LLM (server__name)
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)

    def to_openai_tool(self) -> dict[str, Any]:
        """Преобразует инструмент в OpenAI-compatible описание tool."""
        schema = self.input_schema if isinstance(self.input_schema, dict) else {}
        return {
            "type": "function",
            "function": {
                "name": self.prefixed_name,
                "description": self.description or "",
                "parameters": schema
                if schema
                else {"type": "object", "properties": {}},
            },
        }


def strip_prefix(prefixed_name: str) -> tuple[str, str]:
    """Разбивает 'server__tool' на ('server', 'tool').

    Если разделителя нет — возвращает ('', prefixed_name).
    Разделитель '__' может встречаться в имени инструмента, поэтому
    разбиваем по первому вхождению.
    """
    if "__" in prefixed_name:
        server, tool = prefixed_name.split("__", 1)
        return server, tool
    return "", prefixed_name


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
        return StdioServerParameters(command=command, args=args, env=None)

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
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
            return None
        stderr_text = ""
        try:
            assert proc.stderr is not None
            stderr_text = proc.stderr.read().decode("utf-8", errors="replace").strip()
        except Exception:
            pass
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
        async with (
            stdio_client(self._server_params()) as (read, write),
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
        async with (
            stdio_client(self._server_params()) as (read, write),
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


class McpClientManager:
    """Хранит живые подключения к MCP-серверам по именам агентов/чатов."""

    def __init__(self):
        self._connections: dict[int, dict[str, McpConnection]] = {}
        self._lock = threading.Lock()

    def get_connections(self, agent_id: int) -> dict[str, McpConnection]:
        """Возвращает словарь подключений агента (name -> McpConnection)."""
        with self._lock:
            return dict(self._connections.get(agent_id, {}))

    def add_connection(self, agent_id: int, connection: McpConnection) -> None:
        """Регистрирует (или заменяет) подключение к серверу для агента."""
        with self._lock:
            self._connections.setdefault(agent_id, {})[connection.name] = connection

    def remove_connection(self, agent_id: int, server_name: str) -> bool:
        """Отключает сервер у агента. Возвращает True, если отключали."""
        with self._lock:
            conns = self._connections.get(agent_id)
            if not conns or server_name not in conns:
                return False
            conn = conns.pop(server_name)
            conn.close()
            return True

    def clear_agent(self, agent_id: int) -> None:
        """Полностью очищает подключения агента (например, при удалении чата)."""
        with self._lock:
            for conn in self._connections.pop(agent_id, {}).values():
                conn.close()

    def shutdown(self) -> None:
        """Закрывает все подключения (вызывается при выходе из приложения)."""
        with self._lock:
            for conns in self._connections.values():
                for conn in conns.values():
                    conn.close()
            self._connections.clear()


MCP_MANAGER = McpClientManager()


def parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
    """Разбирает аргументы tool_call из ответа LLM (JSON-строка или dict)."""
    if raw_arguments is None or raw_arguments == "":
        return {}
    if isinstance(raw_arguments, dict):
        return raw_arguments
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError, TypeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
