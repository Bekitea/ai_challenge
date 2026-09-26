#!/usr/bin/env python3

import asyncio
import sys

from mcp.client.stdio import stdio_client

from mcp import ClientSession, StdioServerParameters

MCP_SERVER = "mcp/open_alex_mcp.py"


async def main():
    server_params = StdioServerParameters(command="python", args=[MCP_SERVER], env=None)

    try:
        async with (
            stdio_client(server_params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            tools = await session.list_tools()

            print("Доступные инструменты на сервере:")
            if not tools.tools:
                print("  (инструменты не найдены)")
                return

            for tool in tools.tools:
                print(f" - {tool.name}")
                print(f"   Описание: {tool.description}")
                print(f"   Схема ввода: {tool.input_schema}\n")

            print("=" * 50)
            print("Вызываем search_articles...")
            result = await session.call_tool(
                name="search_articles",
                arguments={
                    "keywords": ["screening", "deep learning", "tomography", "fundus"]
                },
            )

            for content in result.content:
                if content.type == "text":
                    print(content.text)

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
