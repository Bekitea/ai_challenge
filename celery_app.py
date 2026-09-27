"""Celery application for periodic (scheduled) agent tasks.

This is a second presentation layer alongside the interactive CLI:
it knows NOTHING about repositories, LLM providers or agents internals —
it communicates with the system exclusively through use cases provided
by ``app_factory.initialize_application()``.
"""

from datetime import timedelta

from celery import Celery

import config

celery_app = Celery(
    "agent_periodic_tasks",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND,
    include=["tasks"],
)

LOCAL_TIME_REPORT = {
    "id": "local_time_report",
    "chat_name": "[scheduled] Локальное время",
    "system_prompt": (
        "Ты — агент периодических сводок. Твоя задача — отвечать на запрос "
        "кратко и по делу, используя подключённые инструменты (MCP), когда "
        "они необходимы для получения точных данных."
    ),
    "task": (
        "Который сейчас час? Узнай локальное время с помощью инструмента "
        "get_current_time (часовой пояс 'local') и верни короткую сводку."
    ),
    "mcp_servers": ["time"],
}

SCHEDULED_REPORTS: dict[str, dict] = {
    LOCAL_TIME_REPORT["id"]: LOCAL_TIME_REPORT,
}

# Every registered report runs once a minute by default.
CELERY_BEAT_SCHEDULE = {
    report_id: {
        "task": "tasks.run_agent_report",
        "schedule": timedelta(minutes=1),
        "args": [report_id],
    }
    for report_id in SCHEDULED_REPORTS
}

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    beat_schedule=CELERY_BEAT_SCHEDULE,
)
