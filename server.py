from mcp.server import MCPServer

mcp = MCPServer("Homework Server")


@mcp.tool()
def calculate_sum(a: int, b: int) -> int:
    """Складывает два числа. Используется для проверки подключения."""
    return a + b


@mcp.tool()
def get_greeting(name: str) -> str:
    """Возвращает приветствие для указанного имени."""
    return f"Привет, {name}! MCP-соединение работает корректно."


if __name__ == "__main__":
    mcp.run()
