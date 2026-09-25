import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["server.py"],
    )

    print("🔄 Подключаемся к локальному MCP-серверу...\n")

    async with (
        stdio_client(server_params, errlog=sys.stderr) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        print("✅ Соединение успешно установлено!\n")

        tools = await session.list_tools()

        print(f"Найдено инструментов: {len(tools.tools)}\n")
        print("Список доступных инструментов:")
        print("=" * 50)

        for tool in tools.tools:
            print(f"🔹 Название: {tool.name}")
            print(f"   Описание: {tool.description}")
            print("-" * 50)


if __name__ == "__main__":
    asyncio.run(main())
