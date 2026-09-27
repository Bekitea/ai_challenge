#!/usr/bin/env python3
import asyncio
import sys

from mcp.client.stdio import stdio_client

from mcp import ClientSession, StdioServerParameters

MCP_SERVER = "mcp/time_mcp.py"


async def main():
    server_params = StdioServerParameters(
        command="python",
        args=[MCP_SERVER],
        env=None,
    )

    try:
        async with (
            stdio_client(server_params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            tools = await session.list_tools()

            print("Доступные инструменты на сервере:")
            print("-" * 60)

            if not tools.tools:
                print("  (инструменты не найдены)")
                return

            for tool in tools.tools:
                print(f"  • {tool.name}")
                print(f"    Описание: {tool.description}")
                print(f"    Схема ввода: {tool.input_schema}\n")

            print("=" * 60)

            test_cases = [
                {
                    "label": "⏰ Время по умолчанию (UTC)",
                    "tool": "get_current_time",
                    "args": {},
                },
                {
                    "label": "🇷🇺 Время в Москве",
                    "tool": "get_current_time",
                    "args": {"timezone": "Europe/Moscow"},
                },
                {
                    "label": "🇯🇵 Время в Токио",
                    "tool": "get_current_time",
                    "args": {"timezone": "Asia/Tokyo"},
                },
                {
                    "label": "🇺🇸 Время в Нью-Йорке",
                    "tool": "get_current_time",
                    "args": {"timezone": "America/New_York"},
                },
                {
                    "label": "🖥️  Локальное время сервера",
                    "tool": "get_current_time",
                    "args": {"timezone": "local"},
                },
                {
                    "label": "❌ Невалидный часовой пояс (проверка ошибки)",
                    "tool": "get_current_time",
                    "args": {"timezone": "Mars/Olympus"},
                },
                {
                    "label": "🌍 Список поясов для региона Europe",
                    "tool": "list_available_timezones",
                    "args": {"region": "Europe"},
                },
            ]

            for i, tc in enumerate(test_cases, 1):
                print(f"\n[{i}/{len(test_cases)}] {tc['label']}")
                print(f"  Вызов: {tc['tool']}({tc['args']})")
                print("  " + "-" * 56)

                result = await session.call_tool(
                    name=tc["tool"],
                    arguments=tc["args"],
                )

                for content in result.content:
                    if content.type == "text":
                        for line in content.text.splitlines():
                            print(f"  {line}")

                await asyncio.sleep(0.5)

            print("\n" + "=" * 60)
            print("✅ Все тесты завершены успешно!")

    except BaseExceptionGroup as eg:
        unhandled = [
            e for e in eg.exceptions if not isinstance(e, asyncio.CancelledError)
        ]
        if unhandled:
            print(f"Критичная ошибка при закрытии: {unhandled}", file=sys.stderr)
            raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:  # noqa: BLE001
        print(f"Ошибка клиента: {e}", file=sys.stderr)
        sys.exit(1)
