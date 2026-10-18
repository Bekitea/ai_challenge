# BACKLOG

Известные несоответствия и потенциальные баги, обнаруженные при работе с приложением. **Не исправлять без явного указания
пользователя** (см. `AGENTS.md`).

## 1. Периодические задачи Celery временно законсервированы (нужна переработка)

- **Где**: `core/presentation/celery/celery_app.py` (`SCHEDULED_REPORTS`, `CELERY_BEAT_SCHEDULE`),
  `core/presentation/celery/tasks.py` (`run_agent_report`),
  `core/application/use_cases/run_scheduled_agent_task.py`
  (`RunScheduledAgentTaskUseCase`, DTO `ScheduledReport`), `config.py`
  (`SCHEDULED_REPORTS_ENABLED`, `DEFAULT_REPORT_*`, `CELERY_*`),
  `docker-compose.yml` (сервисы `worker`/`beat`).
- **Текущее состояние**: функция **отключена флагом**. `config.SCHEDULED_REPORTS_ENABLED`
  по умолчанию `false`; при выключенном флаге `CELERY_BEAT_SCHEDULE` пуст и
  `beat` ничего не диспатчит, хотя `worker`/`beat` и весь код задачи, реестр
  отчётов и use case сохранены без изменений. Для возврата достаточно выставить
  `SCHEDULED_REPORTS_ENABLED=true`.
- **Симптом/почему мешает**: при включённом расписании `beat` безусловно
  планирует каждый отчёт раз в минуту (`timedelta(minutes=1)`), а
  `RunScheduledAgentTaskUseCase` на каждый запуск создаёт **новый чат**. В
  результате `./data/agents.db` растёт без ограничений, а LLM и MCP-серверы
  постоянно нагружаются — это мешает основной работе (особенно при
  `docker compose up`, где `worker`/`beat` поднимаются всегда).
- **Направление переработки** (сделать, когда функция снова понадобится):
  1. Планирование opt-in и настраиваемое: включение per-report, отдельная
     частота на отчёт (из конфига/БД) вместо жёсткого «раз в минуту».
  2. Жизненный цикл чатов отчётов: сейчас unbounded «новый чат на каждый
     запуск»; нужна политика ретеншна/TTL или контролируемое переиспользование.
  3. Runtime-управление реестром: добавлять/приостанавливать/удалять отчёты
     из конфига или БД и через CLI/UI, а не править статический `dict` в коде.
  4. Наблюдаемость: статус прогонов, расход токенов, ошибки (сейчас виден
     только ответ в логе воркера и результат в result backend).
  5. Провайдер/модель на конкретный отчёт через DTO, а не глобальные
     `DEFAULT_REPORT_PROVIDER`/`DEFAULT_REPORT_MODEL`.
  6. Учесть хранение MCP-соединений in-process (ограничение «ровно один
     воркер»): при нескольких воркерах живые подключения после перезапуска
     «протухают».
- **Действие до переработки**: не включать `SCHEDULED_REPORTS_ENABLED`; код не
  удалять.

## 2. Ассистентские команды `/help`, `/support`, `/files` временно законсервированы (нужна переработка)

- **Где**: `config.py` (`ASSISTANT_COMMANDS_ENABLED`),
  `core/presentation/cli/cli_app.py` (`HELP_COMMANDS`, `ASSISTANT_HELP_COMMANDS`,
  `_print_hint`, перехват в `chat_loop`, методы `project_help`,
  `support_assistant`, `files_assistant`),
  `core/presentation/api/routers/commands.py` (проверка флага),
  `core/application/use_cases/prepare_assistant_context.py`
  (`PrepareAssistantContextUseCase`), `core/application/use_cases/run_file_assistant.py`
  (`RunFileAssistantUseCase`, `FILE_ASSISTANT_INSTRUCTION`),
  `core/di/app_factory.py` (три контекста `prepare_*_context`),
  MCP-серверы `git`/`files`/`support`, `docs/uc/uc-027`, `uc-029`, `uc-030`.
- **Текущее состояние**: команды **отключены флагом**.
  `config.ASSISTANT_COMMANDS_ENABLED` по умолчанию `false`; при выключенном
  флаге они скрыты из `/commands` и подсказки, а вызов в CLI печатает
  `[INFO] Команда /help временно отключена ...`, REST API возвращает `400`.
  Код use cases, конфигурация `PrepareAssistantContextUseCase` и обработчики
  CLI/API сохранены без изменений. Для возврата достаточно выставить
  `ASSISTANT_COMMANDS_ENABLED=true`. Пункт меню «Засеять БЗ ассистентов» (9)
  не блокируется — это отдельный функционал RAG.
- **Почему мешает / что не так в текущей логике**:
  1. Три команды смешивают разные concerns: привязку выделенной БЗ, подключение
     MCP-серверов и (для `/files`) обёртку цели в жёстко заданную prompt-инструкцию
     `FILE_ASSISTANT_INSTRUCTION`.
  2. Логика продублирована: отдельные ветки в `cli_app.py` и в
     `api/routers/commands.py`, включая парсинг `[тикет]` и подсказки.
  3. Неявные side effects без отдельного подтверждения: команды меняют
     привязки БЗ/MCP текущего чата, а `/files` пишет файлы в рабочее
     пространство (`PROJECT_FILES_ROOT`).
  4. Три почти одинаковых `PrepareAssistantContextUseCase` собираются вручную в
     `app_factory.py` (различия только в имени БЗ/метках и списке MCP).
  5. Команды встроены в статический список `HELP_COMMANDS`, из-за чего их набор
     нельзя менять в рантайме.
- **Направление переработки** (сделать, когда функция снова понадобится):
  1. Единый реестр ассистентских команд с метаданными (имя, описание, контекст,
     builder промпта, политика side effects), общий для CLI и API.
  2. Разделить «подготовку контекста» (БЗ/MCP), шаблоны промптов и агентский
     файловый цикл; убрать дублирование веток представления.
  3. Явная политика side effects: подтверждение записи файлов, контроль
     изменения привязок MCP/БЗ, sandbox и лимиты.
  4. Устранить ручную проводку трёх контекстов в `app_factory.py` и вынести их
     параметры в конфиг/реестр.
  5. Наблюдаемость и UX в веб-интерфейсе (список команд, статусы, ошибки).
  6. Покрыть переработку e2e-тестами (сейчас тесты UC-027/029/030 временно
     включают флаг в окружении).
- **Действие до переработки**: не включать `ASSISTANT_COMMANDS_ENABLED` в
  проде; код не удалять.
