from datetime import datetime
from zoneinfo import ZoneInfo

from mcp.server import MCPServer

mcp = MCPServer(
    "TimezoneServer",
    description="Сервер для получения текущего времени с учетом часовых поясов.",
)


@mcp.tool()
def get_current_time(timezone: str = "UTC") -> str:
    """
    Получает текущие дату и время для указанного часового пояса.

    Args:
        timezone: Часовой пояс в формате IANA (например, 'Europe/Moscow', 'America/New_York', 'Asia/Tokyo', 'UTC').
                  Если параметр не передан, возвращается время UTC.
                  Для получения локального времени сервера используйте значение 'local'.
    """
    try:
        if timezone.lower() == "local":
            tz = datetime.now().astimezone().tzinfo
            tz_name = "Local (Server Time)"
        else:
            tz = ZoneInfo(timezone)
            tz_name = timezone

        now = datetime.now(tz)
        formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
        utc_offset = now.strftime("%z")

        utc_offset_formatted = (
            f"{utc_offset[:3]}:{utc_offset[3:]}" if utc_offset else "+00:00"
        )

        return (
            f"Текущее время ({tz_name}): {formatted_time} (UTC{utc_offset_formatted})"
        )

    except Exception as e:  # noqa: BLE001
        return (
            f"Ошибка: Не удалось определить часовой пояс '{timezone}'. "
            f"Убедитесь, что используется корректный формат IANA (например, 'Europe/Moscow', а не 'MSK'). "
            f"Детали ошибки: {e!s}"
        )


@mcp.tool()
def list_available_timezones(region: str = "") -> str:
    """
    Показывает список доступных часовых поясов. Можно отфильтровать по региону.

    Args:
        region: Часть названия региона для фильтрации (например, 'Europe', 'America', 'Asia').
                Если оставить пустым, вернет все доступные пояса.
    """
    from zoneinfo import available_timezones

    all_zones = sorted(available_timezones())

    if region:
        filtered_zones = [z for z in all_zones if region.lower() in z.lower()]
        if not filtered_zones:
            return f"Часовые пояса с регионом '{region}' не найдены."
        return f"Доступные часовые пояса для '{region}':\n" + "\n".join(
            filtered_zones[:50]
        )

    return f"Всего доступно {len(all_zones)} часовых поясов. Используйте параметр region для фильтрации."


if __name__ == "__main__":
    mcp.run()
