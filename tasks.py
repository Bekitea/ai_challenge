"""Celery tasks: periodic agent reports (second presentation layer).

This module is the ONLY place where the Celery layer touches the rest of
the system, and it does so strictly through use cases:

    celery_app (scheduling data) -> run_agent_report (task wrapper)
        -> app_factory.initialize_application()  -> UseCasesBundle
        -> use_cases.run_scheduled_agent_task    -> ScheduledReport DTO

No repositories, no LLM providers, no Agent objects are imported here.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import logging

from celery_app import SCHEDULED_REPORTS, celery_app

logger = logging.getLogger("celery.tasks")

# Use cases bundle is initialized lazily once per worker process
# (SQLite connections / event loops must not be shared between processes).
_use_cases = None


def _get_use_cases():
    """Возвращает (создавая при первом вызове) набор use cases."""
    global _use_cases
    if _use_cases is None:
        from app_factory import initialize_application

        _use_cases = initialize_application()
        logger.info("Use cases initialized for Celery worker process")
    return _use_cases


@celery_app.task(
    name="tasks.run_agent_report",
    bind=True,
    acks_late=True,
    max_retries=2,
    default_retry_delay=10,
)
def run_agent_report(self, report_id: str) -> dict:
    """Запускает периодическую агентную сводку через RunScheduledAgentTaskUseCase.

    Args:
        report_id: Идентификатор отчёта из реестра SCHEDULED_REPORTS.

    Returns:
        Сериализуемый dict с результатом (ScheduledReport DTO).
    """
    report_config = SCHEDULED_REPORTS.get(report_id)
    if report_config is None:
        raise ValueError(f"Неизвестный периодический отчёт: {report_id!r}")

    use_cases = _get_use_cases()

    try:
        result = use_cases.run_scheduled_agent_task.execute(
            chat_name=report_config["chat_name"],
            system_prompt=report_config["system_prompt"],
            task=report_config["task"],
            mcp_servers=report_config.get("mcp_servers"),
        )
    except Exception as exc:
        logger.exception("Agent report %s failed, retrying", report_id)
        raise self.retry(exc=exc)

    logger.info(
        "Agent report %s ready (chat #%s, tokens p/c=%s/%s):\n%s",
        report_id,
        result.agent_id,
        result.prompt_tokens,
        result.completion_tokens,
        result.answer,
    )

    # Возвращаем плоский сериализуемый dict (ScheduledReport -> JSON-safe).
    return {
        "report_id": report_id,
        "chat_name": result.chat_name,
        "agent_id": result.agent_id,
        "task": result.task,
        "answer": result.answer,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
    }
