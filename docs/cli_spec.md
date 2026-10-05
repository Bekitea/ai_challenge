# AI Chat CLI Specification

## 1. Overview

### 1.1 Purpose

This document provides a comprehensive specification for the Command Line Interface (CLI) of the AI Chat application. It serves as the single source of truth for:

- Regenerating the CLI frontend from scratch
- Writing comprehensive unit and integration tests
- Understanding all user interactions and system behaviors
- Onboarding new developers to the project

### 1.2 Scope

- **In Scope**: CLI interface (`cli_app.py`, class `CLIChat`), menu navigation, chat management, message handling, settings configuration, slash-command processing, task profiles management, global/task memory viewing, MCP connection management from the chat loop
- **Out of Scope**: Backend LLM provider implementation, other frontends, API specifications, Celery workers/beat and scheduled tasks (they are not part of the CLI application)

### 1.3 Definitions

| Term              | Definition                                                                        |
| ----------------- | --------------------------------------------------------------------------------- |
| Chat / Agent      | A conversation session; internal ID is a UUID (`conversation_id`), user-facing ID is a numeric `agent_id` |
| System Prompt     | Initial instruction message that sets agent behavior                              |
| Preview           | Short excerpt (max 50 chars) of the last visible message, suffixed with `...` if truncated |
| Active Chat       | Currently selected agent stored in CLI state (`current_agent`)                    |
| Disabled Setting  | Parameter with `None` value, not passed to LLM                                    |
| Phase             | Agent workflow stage: PLAN / EXECUTE / VALIDATE / REPORT                          |
| Invariant         | Strict rule attached to a task profile that the agent must never violate          |
| MCP               | Model Context Protocol server whose tools can be connected to a chat              |

---

## 2. Architecture

The presentation layer (`CLIChat` in `cli_app.py`) is separated from application initialization (`app_factory.py`, `main_cli.py`). `CLIChat` receives all its functionality through a `UseCasesBundle` container of use cases (`use_cases.py`) and never touches repositories or the LLM provider directly.

State model: the CLI keeps a single piece of state — `current_agent: Agent | None`. Menu option 5 ("Вернуться в чат") re-enters the chat loop for this agent. The active chat reference is kept when exiting a chat via `/menu`; it is replaced on chat creation/selection.

---

## 3. Memory Integration

Memory facts are injected into the system prompt constructed for every message exchange (see UC-004) in the following fixed order:

1. Global memory facts — section header `Память о пользователе:` (omitted when global memory is empty);
2. Task profile facts — section header `Память задачи ({profile_name}):`, then `Предпочтения задачи ({profile_name}):` and `--- ИНВАРИАНТЫ ЗАДАЧИ ({profile_name}) ---` (only when the chat has a task profile attached);
3. Per-chat task memory — section header `--- ПАМЯТЬ ЗАДАЧИ ---` with `Цель`, `Ограничения`, `Термины` and `Уже уточнено` (omitted when empty). Maintained per `conversation_id` by `Agent.update_task_memory` every `TASK_MEMORY_UPDATE_EVERY_N_MESSAGES` turns and on context compression; new clarifications override outdated values (see UC-022);
4. RAG context — section header `--- КОНТЕКСТ ИЗ БАЗ ЗНАНИЙ ---` (only when knowledge bases are attached, see UC-021).

Facts are extracted into global and task-profile memory by the `save_agent_memory` use case whenever the chat loop exits (via `/menu`, Ctrl+C or application start — see UC-004 exit rule), and on application start by the `save_unsaved_memories` use case (§4.2.3). The per-chat task memory is additionally refreshed on exit by the same use case.

---

## 4. Interface Specification

### 4.1 Visual Style Guidelines

- **No emojis** - Use text markers only
- **Status Markers**:
  - `[OK]` - Success operations
  - `[WARN]` - Warnings
  - `[ERROR]` - Errors
  - `[INFO]` - Informational messages
  - `[USER]` / `[AGENT]` - Message prefixes in the chat loop
  - `[OFFLINE]` - MCP server without a live connection
- **Separators**: Lines of 40 dashes (`----------------------------------------`)
- **Headers**: `--- ЗАГОЛОВОК ---` style; app header is a 60-char `=` border block:
  ```
  ============================================================
         AI CHAT CLI - Консольный чат с AI агентами
  ============================================================
  ```
- **Input Prompts**: Clear instructions with defaults in parentheses; pressing Enter accepts the default where one is documented
- **Screen clearing**: `clear_screen()` (os.system("cls"/"clear")) is called once on application start, before printing the header; the main menu is re-printed without clearing

### 4.2 Main Menu

#### 4.2.1 Display Format (`print_menu()`)

```
--- МЕНЮ ---
1. Новый чат
2. Выбрать чат
3. Профили задач
4. Просмотреть глобальную память
5. Вернуться в чат: {chat_name} | Вернуться в чат (нет активного чата)
6. Выход
7. Базы знаний
----------------------------------------
```

Prompt line: `Ваш выбор (1-7):`

#### 4.2.2 Dynamic Behavior

- Option 5 label depends on `current_agent` state:
  - Active chat exists: `5. Вернуться в чат: {chat_name}`
  - No active chat: `5. Вернуться в чат (нет активного чата)` (no colon)
- Selecting option 5 with an active chat prints `[OK] Возврат в чат: {name}` and enters the chat loop.
- Selecting option 5 without an active chat prints `[WARN] Нет активного чата. Выберите или создайте чат.` and stays in the menu.
- Option 6 prints `До свидания!` and terminates the application.
- Option 7 enters the Knowledge Bases menu (§4.9).

#### 4.2.3 Input Validation

- Accept only strings "1".."7" (exact match after strip)
- Any other input: `[WARN] Неверный выбор, попробуйте снова.` and re-prompt
- `KeyboardInterrupt` / `EOFError` at the menu prompt: print `До свидания!` and exit cleanly
- On application start (before the menu loop) the system executes `save_unsaved_memories` use case: for every agent with unremembered prompts it extracts facts into global/task memory (technical token counters).

#### 4.2.4 State Model Overview

The CLI is a single-user, session-scoped console application. Its entire state is held in the `CLIChat` instance:

- `current_agent: Agent | None` — the active chat (see §2); it survives exits to the Main Menu and is replaced on chat creation or selection.
- Per-chat runtime data (settings, phase, connected MCP servers) lives on the `Agent` object and in storage; the CLI never caches message history beyond what the current loop needs.
- All persistent state (agents, messages, task profiles, global/task memories) is owned by repositories accessed exclusively through use cases (§2).

There is no cross-session UI state: restarting the application re-reads everything from storage.

### 4.3 Chat List Display (Select Chat Option)

#### 4.3.1 Display Format (`print_chat_list()`)

```
--- ВАШИ ЧАТЫ ---
{index}. {chat_name}
   Сообщений: {count} | Последнее: {YYYY-MM-DD HH:MM}
   Превью: {preview_text}|(нет сообщений)
   ID: {agent_id}
----------------------------------------
```

- `{index}` — position in the sorted list (1-based), not the DB ID
- Timestamp format `%Y-%m-%d %H:%M`; the `Последнее:` value is empty when `last_message_timestamp` is None
- Chats are ordered by last message time, newest first (chats without messages last)
- `{preview_text}` — stored `last_message_preview` or `(нет сообщений)` when absent
- Selection prompt: `Выберите чат (1-{n}):`; out-of-range number → `Введите число от 1 до {n}`, non-numeric → `Введите корректное число`, both re-prompt

#### 4.3.2 Preview Logic

| Condition                        | Preview Text                              |
| -------------------------------- | ----------------------------------------- |
| No visible messages              | `(нет сообщений)`                         |
| Only system message              | `(нет сообщений)`                         |
| Has user/assistant messages      | First 50 chars of last visible message    |
| Message > 50 chars               | Truncated to 50 chars + `...`             |

Visible messages exclude role="system", role="tool" and assistant messages carrying `tool_calls`. The preview is computed by the domain (`Agent.get_last_message_preview`) and persisted on each save; the CLI renders it verbatim.

#### 4.3.3 Empty State

`print_chat_list()` prints `Нет активных чатов.`; then `select_chat()` prints `Нет доступных чатов. Создайте новый.` and control returns to the Main Menu.

#### 4.3.4 After Selection

1. Agent is loaded via `select_chat.get_agent(agent_id)`; becomes `current_agent`
2. Memory is refreshed via `refresh_agent_memory` use case
3. Displays `[OK] Выбран чат: {name}`
4. Enters the chat loop immediately; after the loop ends (e.g. `/menu`), control returns to the Main Menu

### 4.4 Chat Creation Workflow

#### 4.4.0 Step 0: Configure Prompt

```
--- СОЗДАНИЕ НОВОГО ЧАТА ---
Хотите настроить чат? (y/n, по умолчанию n):
```

- Accepted affirmative answers: `y`, `да`, `д`; negative: `n`, `нет`, `н`; empty → `n`; anything else → re-prompt with `Введите 'y' (да) или 'n' (нет)`
- **Quick path (n)**: prints `Используются настройки по умолчанию.`; name is auto-generated, system prompt skipped, default settings (`get_default_agent_settings`: model = Alice AI LLM Flash (`aliceai-llm-flash/latest`), temperature/top_p/top_k disabled, reasoning_effort "none", context window 200k), strategy = DefaultStrategy, no task profile — steps 1–10 are skipped entirely
- **Manual path (y)**: steps 1–10 below

#### 4.4.1 Step 1: Name Input

```
Введите название чата (по умолчанию 'Чат N'):
```

- Empty input: default name `Чат {N}`, where N = (number of existing chats) + 1
- The CLI performs no length validation/truncation; the DB column limit is 255 characters (`String(255)`)

#### 4.4.2 Step 2: System Prompt

```
Введите системный промпт (Enter для пропуска):
```

- Empty input: Skip, no system message added
- Non-empty: stored as message `{"role": "system", "content": "{input}"}`
- Multi-line: Not supported (single line only)

#### 4.4.3 Step 3: Model Selection

```
--- НАСТРОЙКИ АГЕНТА ---

Выберите модель:
  1. GPT OSS 120B (gpt-oss-120b/latest)
  2. Qwen3.6-35B (qwen3.6-35b-a3b/latest)
  3. Alice AI LLM Flash (aliceai-llm-flash/latest)
  Enter — модель по умолчанию

Ваш выбор (1-3):
```

- Invalid input: Re-prompt with `Неверный выбор, попробуйте снова.`
- Empty input: default model `aliceai-llm-flash/latest`

#### 4.4.4 Step 4: Temperature

```
Температура (0.0 - 2.0, Enter для отключения):
```

- Valid range: 0.0 to 2.0 (inclusive)
- Empty input: Set to `None` (disabled)
- Invalid number: Set to `None` with warning `Некорректное число. Используется значение по умолчанию (отключено).`
- Out of range: Set to `None` with warning `Температура должна быть от 0.0 до 2.0. Используется значение по умолчанию (отключено).`

#### 4.4.5 Step 5: Top P

```
Top P (0.0 - 1.0, Enter для отключения):
```

- Valid range: 0.0 to 1.0 (inclusive)
- Empty input / invalid number / out of range: `None` (disabled), warnings analogous to Temperature (`Top P должен быть от 0.0 до 1.0. ...`)

#### 4.4.6 Step 6: Top K

```
Top K (0 для отключения, по умолчанию 0):
```

- Valid: integer >= 0, re-prompt loop on negative (`Top K должен быть >= 0`) or non-integer (`Введите корректное число`)
- Value 0 is stored as `None` (disabled); values > 0 stored as int

#### 4.4.7 Step 7: Reasoning Effort

```
Reasoning Effort:
  1. none
  2. low
  3. medium
  4. high

Ваш выбор (1-4, по умолчанию 1):
```

- Default: 1 (none); empty input → 1
- Invalid/out-of-range: re-prompt (`Введите корректное число` / `Выбор должен быть от 1 до 4`)

#### 4.4.8 Step 8: Context Window Size

```
Размер контекстного окна (в токенах):
  По умолчанию: 200000 токенов (200k)
  Примеры: 4000, 8000, 32000, 128000, 200000
Введите размер контекстного окна (Enter для 200k):
```

- Empty input: Default to 200000 tokens
- Invalid number: Default to 200000 with warning `Некорректное число. Используется 200k.`
- Non-positive: Default to 200000 with warning `Размер должен быть положительным числом. Используется 200k.`

#### 4.4.9 Step 9: Context Strategy Selection

```
--- ВЫБОР СТРАТЕГИИ УПРАВЛЕНИЯ КОНТЕКСТНЫМ ОКНОМ ---
1. DefaultStrategy (пересылка всех сообщений)
2. SummarizationStrategy (суммаризация истории)
3. KeyValueMemoryStrategy (JSON-суммаризация: цель, ограничения, предпочтения, решения, договоренности)
4. SlidingWindowStrategy (скользящее окно: последние N сообщений)

Выберите стратегию (1-4, по умолчанию 1):
```

- Default: 1 (DefaultStrategy); invalid choice → re-prompt (`Неверный выбор, попробуйте снова.`)
- If strategy 2 or 3 selected, prompt for parameters:
  - `Количество несжимаемых сообщений (по умолчанию 2):`
  - `Размер буфера для суммаризации (по умолчанию 3):`
- If strategy 4 selected, prompt for parameter:
  - `Размер скользящего окна N (по умолчанию 10):`
- Non-integer parameter: `Ошибка: {e}. Попробуйте снова.` → strategy selection repeats

#### 4.4.10 Step 10: Task Profile Selection (Optional)

```
--- ПРИВЯЗКА ПРОФИЛЯ ЗАДАЧИ ---
Доступные профили задач:
  1. {profile_name_1}
  2. {profile_name_2}
  ...
  0. Не привязывать профиль

Выберите профиль задачи (0-{n}, по умолчанию 0):
```

- Profiles are listed sorted by profile ID ascending (only names are shown)
- If no profiles exist: Display `(нет доступных профилей)` and continue without attachment
- Default: 0 (no profile attached)
- Invalid/out-of-range input: `[WARN] Некорректный выбор. Профиль не привязан.` → continue without attachment
- **Note**: Once set, `task_profile_id` cannot be changed for this chat

#### 4.4.11 Completion Message

```
[OK] Чат '{name}' создан!
```

Then the chat loop starts immediately (history is displayed in its header). The numeric agent ID is available later via `/info`.

### 4.5 Chat Interaction Loop

#### 4.5.1 Display Header (`chat_loop()` entry)

```
--- ЧАТ: {chat_name} [Фаза: {PLAN|EXECUTE|VALIDATE|REPORT}] ---
[USER]: {message}
[AGENT]: {message}
...
----------------------------------------

--- Подсказка ---
Введите сообщение /help и нажмите Enter для просмотра списка команд
----------------------------------------
```

- Full visible history is replayed on entering the loop (system and technical tool-calling messages hidden; roles mapped to `[USER]`/`[AGENT]`)
- Input prompt for each iteration: `\n[USER]: `

#### 4.5.2 Message Flow

1. Display prompt, wait for user input
2. If empty: re-prompt (no message sent)
3. If command (see 4.5.3): execute command handler
4. If plain text:
   - Display `[AGENT] печатает...` (cleared once the response arrives)
   - Send to backend agent via `send_message` use case
   - Display `[AGENT]: {response.content}`
   - If token usage reported, display two lines:
     ```
       [Токены: prompt: {p}, completion: {c}]
       [Заполненность контекста: {prompt_tokens}/{context_window_size} ({percent:.1f}%)]
     ```
   - If the response contains reasoning, ask `Показать рассуждения модели? (y/n):`; on `y` print indented `[Reasoning]:` block
   - Save to history (automatic per-message save), repeat
5. On chat loop exit (any path: `/menu`, `ContextWindowExceededError`, backend exception, KeyboardInterrupt): the system MUST save the agent memory via the `save_agent_memory` use case before returning to the Main Menu — unsaved memory must never be lost when leaving a chat

#### 4.5.3 Commands Specification

All commands are matched case-insensitively. Unknown slash-commands are treated as regular messages and sent to the agent.

##### Phase commands: `/plan`, `/execute`, `/validate`, `/report`

- **Action**: Transition the agent workflow phase via `Agent.handle_phase_command`
- **Rules**: Forward transition allowed only to the next phase in order PLAN → EXECUTE → VALIDATE → REPORT; any backward transition is allowed; forward skips are rejected
- **Output**: `[INFO] {message}` where message is either `Фаза изменена: {OLD} -> {NEW}` or `Нельзя перескочить этап: переход из {OLD} сразу в {NEW} запрещен`, followed by updated header line `--- ЧАТ: {name} [Фаза: {PHASE}] ---`
- **Phase casing**: the header line and both `[INFO]` messages use the phase's UPPERCASE name (`PLAN`/`EXECUTE`/`VALIDATE`/`REPORT`); `/info` displays the lowercase phase value (`plan`/`execute`/`validate`/`report`) — see §4.5.3 `/info`

##### `/menu`

- **Action**: Save agent memory via `save_agent_memory` use case (LLM fact extraction into global and task-profile memory), then return to Main Menu
- **Output**: `Возврат в меню...`
- **Side Effects**: Active chat reference is preserved (option 5 can return to it)

##### `/stop`

- **Action**: In the current synchronous implementation generation is never active while input is read
- **Output**: `[INFO] Генерация не активна.` and the chat loop exits (returns to menu)

##### `/help`

- **Action**: Display available commands (`HELP_COMMANDS` constant)
- **Output** (exact order of the `HELP_COMMANDS` list):

```
--- ДОСТУПНЫЕ КОМАНДЫ ---
  /menu - вернуться в главное меню
  /stop - остановить текущую генерацию
  /settings - показать текущие настройки и изменить их
  /summary - показать саммари диалога
  /info - показать информацию о чате (счетчики токенов, профиль задачи)
  /branch - создать ветку текущего чата (копируются настройки, история и саммари)
  /plan - перейти в фазу планирования
  /execute - перейти в фазу исполнения
  /validate - перейти в фазу тестирования
  /report - перейти в фазу отчета
  /mcp - показать подключённые к чату MCP и подключить новые
  /rag - базы знаний чата: подключить или отключить
  /rerank - включить или отключить реранкинг (on|off)
  /help - показать этот список команд
```

##### `/summary`

- **Action**: Display current conversation summary from active strategy (`show_summary` use case)
- **Output**:
  - If summary exists: header `--- САММАРИ ДИАЛОГА ---`, the summary text and a 40-dash separator
  - If no summary: `[INFO] Саммари пока недоступно.`
- **Side Effects**: None

##### `/info`

- **Action**: Display detailed chat statistics (`show_chat_info` use case → `ChatInfo`)
- **Output** (two-space indentation, fields printed in this exact order):

```
--- ИНФОРМАЦИЯ О ЧАТЕ ---
  Название: {name}
  ID: {agent_id}
  Стратегия: {strategy_type}
  Профиль задачи: {profile_name}|(не привязан)
  Текущая фаза: {phase}|(не установлена)     # lowercase phase value: plan|execute|validate|report
  Сообщений: {message_count}
  Prompt токены: {total_prompt_tokens}
  Completion токены: {total_completion_tokens}
  Есть саммари: Да                      # only if has_summary
  Несжимаемые сообщения: {non_compressible_count}   # only if not None
  Размер буфера: {buffer_size}          # only if not None
----------------------------------------
```

- **Side Effects**: None

##### `/settings`

- **Action**: Execute `print_settings()`, then prompt `Изменить настройки? (y/n):`
- **Flow**:
  1. Display current settings (format in §4.6.1)
  2. Prompt: `Изменить настройки? (y/n):`
  3. If 'y': Execute `change_settings()` which re-prompts all `AgentSettings` values (same prompts as creation workflow steps 3–8) and applies them via `change_settings` use case
  4. If 'n' or other: Return to chat loop without changes
- **Output**: `Настройки для '{chat_name}'` header, then `[OK] Настройки обновлены!` and refreshed settings view
- **Side Effects**: Settings updated only if user confirms with 'y'; strategy, task profile and phase are never changed here

##### `/branch`

- **Action**: Create a new chat branch copying current chat state (`create_branch` use case → `Agent.branch`)
- **Flow**:
  1. Display header `--- СОЗДАНИЕ ВЕТКИ ОТ '{current_name}' ---`
  2. Prompt for branch name: `Введите название ветки (Enter для автогенерации):`; empty → auto-name `{current_name} (branch {YYYY-MM-DD HH:MM:SS})`
  3. Copy all messages, settings, token counters and strategy (with its accumulated state); the branch receives a new `conversation_id` (UUID) and no ID until saved
  4. `current_agent` is switched to the branch immediately after creation
  5. Ask: `Продолжить в новой ветке? (y/n):`
  6. If 'y': enter the chat loop for the branch
  7. Otherwise: print `Ветка создана. Вы можете вернуться к ней через меню.` and stay in the current chat loop (note: `current_agent` already points to the branch; the original chat is reachable via "Выбрать чат")
- **Error handling** (alternative flow of UC-011): if `create_branch` raises any exception, print `[ERROR] Ошибка при создании ветки: {e}` and return to the chat prompt
- **Side Effects**: New chat created in storage; original chat unchanged

##### `/mcp`

- **Action**: Manage MCP servers connected to the current chat (`mcp_menu`)
- **Flow**:
  1. Display connected servers:
     ```
     --- MCP-СЕРВЕРЫ ЧАТА: {chat_name} ---
       [OK] {title} ({name}) — инструменты: {tool1, tool2}
       [OFFLINE] {title} ({name}) — подключение не установлено
     ```
     If none: `К этому чату ещё не подключено ни одного MCP-сервера.`
  2. Prompt: `Подключить новые MCP? (y/n):` — anything other than `y` ends the flow
  3. List registry servers not yet connected to this chat:
     ```
     --- ДОСТУПНЫЕ ДЛЯ ПОДКЛЮЧЕНИЯ MCP ---
       {idx}. {title} ({name}) — {description}
     ```
     If all already connected: `[INFO] Все доступные MCP-серверы уже подключены к этому чату.`
  4. Prompt: `Введите номер сервера для подключения (или название, 0 — отмена):`
     - Empty input or `0`: `[INFO] Подключение отменено.` → end of flow
     - Numeric out of range: `[ERROR] Неверный номер сервера.` → end of flow
     - Non-numeric text is treated as a server name and passed to the use case
  5. On selection: `[INFO] Подключаю MCP '{name}'...`, then result `[OK] {message}` or `[ERROR] {message}` from `connect_mcp` use case
- **Side Effects**: Successful connection persists the server list on the agent; tools become available to the LLM in subsequent messages (tool-calling loop inside `continue_dialog`)

##### `/rag`

- **Action**: Manage knowledge bases attached to the current chat (`rag_menu`)
- **Flow**:
  1. Display attached knowledge bases:
     ```
     --- БАЗЫ ЗНАНИЙ ЧАТА: {chat_name} ---
     [INFO] Реранкинг: включён|отключён.
       1. {name} (документов: {n}, чанков: {m})
     ```
     If none: `К этому чату ещё не подключено ни одной базы знаний.`
  2. Action menu:
     ```
     Действия:
     1. Подключить базу знаний
     2. Отключить базу знаний
     0. Назад
     ```
     Prompt: `Выберите действие (0-2):`
  3. **Attach**: lists knowledge bases not yet attached; selection prompt `Выберите базу знаний (номер, 0 - отмена):`. Success/idempotent message `[OK] База знаний '{name}' подключена к чату.` / `[OK] ... уже подключена к чату.`; no available bases → `[INFO] Нет доступных баз знаний для подключения. Создайте их в меню 'Базы знаний'.`
  4. **Detach**: selects from attached; message `[OK] База знаний '{name}' отключена от чата.` or `[INFO] К чату не подключено ни одной базы знаний.`
- **RAG behaviour**: while at least one knowledge base is attached, every user message triggers a RAG search before the LLM request; with none attached, no embedding or search is performed. Search results are injected into the system prompt (see UC-020). If the chat's reranking is enabled, candidates are re-scored by the reranker service before the top chunks are selected; when the service is unavailable the search degrades to vector order.
- **Sources & threshold**: chunks with relevance below `RAG_RELEVANCE_THRESHOLD` (unified `[0..1]` scale: reranker score, or `1 - vector_distance / 2`) are discarded; when nothing passes, the agent is instructed to answer «Не знаю» and ask for clarification. After every answer in a chat with attached bases the CLI prints:
  ```
    [Источники]:
      1. {document_name} — чанк #{chunk_id} (фрагмент {n}, релевантность {score})
         «{краткая цитата}»
  ```
  If bases are attached but no chunk passed the threshold: `  [Источники] релевантных фрагментов не найдено (порог {threshold}).` See UC-021.
- **Side Effects**: attachment is stored in the `agent_knowledge_bases` table; detach removes the link.

##### `/rerank`

- **Action**: Toggle per-chat reranking of RAG search results (`set_reranker_enabled`)
- **Flow**:
  1. `/rerank on` → `[OK] Реранкинг включён.`
  2. `/rerank off` → `[OK] Реранкинг отключён.`
  3. Bare `/rerank` → `[INFO] Реранкинг: включён|отключён.`
  4. Any other argument → `[WARN] Использование: /rerank on|off`
- **Behaviour**: reranking is enabled by default for every chat (`AgentSettings.reranker_enabled=True`). The flag is persisted with the chat settings and copied when branching. It only takes effect when the reranker provider is configured/available (see `RERANKER_ENABLED`); otherwise RAG falls back to vector order.
- **Side Effects**: the flag is stored in the agent's `settings_json`

#### 4.5.4 Error Handling

Error handling in the chat loop is not centralized in a separate matrix: every error case is specified as an alternative flow of the corresponding use case (see the files in [`docs/uc/`](uc/)):

- **Context window exceeded** — UC-004 A4 (`[ERROR] {message}` + hint, memory saved, exit to Main Menu)
- **Backend exception during message send** — UC-004 A5 (`[ERROR] Ошибка: {message}`, memory saved, exit to Main Menu)
- **KeyboardInterrupt / EOFError** — UC-003 A2 (menu prompt) and UC-004 A6–A7 / UC-005 A3 (chat loop: `Прервано пользователем.`, memory saved before exit)
- **Errors while applying settings** — UC-005 A4
- **Unknown slash-command** — not an error: treated as a regular message (UC-004 A2)

### 4.6 Settings Management

#### 4.6.1 Print Settings (`_print_current_settings`)

```
--- ТЕКУЩИЕ НАСТРОЙКИ ---
  Модель: {model_id}
  Температура: {value}|отключена
  Top P: {value}|отключен
  Top K: {value}|отключено
  Reasoning Effort: {effort}
  Размер контекстного окна: {context_window_size} токенов
----------------------------------------
```

Model is shown by its identifier (not display name). Missing `context_window_size` is displayed as 200000. Unlike temperature/top_p/top_k, `Reasoning Effort` has no disable placeholder: the raw value is printed as-is, so when the effort is `None` the line reads `Reasoning Effort: None` (default effort values such as `low`/`medium`/`high` are printed verbatim).

#### 4.6.2 Change Settings (`change_settings`)

Same prompts as creation workflow (§4.4.3–§4.4.8) applied sequentially; each answer fully replaces the previous value (empty input disables the parameter — there is no "keep current value" semantics). Strategy, task profile and phase cannot be changed for existing chats. Confirmation: `[OK] Настройки обновлены!` followed by the refreshed settings block.

### 4.7 Task Profiles Menu

Entered from Main Menu option 3 (`task_profiles_menu`).

#### 4.7.1 Task Profiles Menu (`task_profiles_menu`)

```
--- ПРОФИЛИ ЗАДАЧ ---
1. Создать новый профиль
2. Просмотреть список профилей
3. Назад в главное меню
----------------------------------------
```

Prompt: `Ваш выбор (1-3):`. Invalid choice: `[WARN] Неверный выбор, попробуйте снова.` and the menu is re-displayed. Option 3 returns to the Main Menu.

#### 4.7.1.1 Profiles List (`_view_task_profiles_list`)

Empty list: prints `Нет доступных профилей задач.` and a separator, then returns to the Task Profiles menu.

```
--- СПИСОК ПРОФИЛЕЙ ЗАДАЧ ---
{i}. {name}
   ID: {profile_id}
   Дата создания: {YYYY-MM-DD HH:MM}
   Фактов в памяти: {facts_count}
   Инвариантов: {invariants_count}
   Описание: {description truncated to 50 chars + "..." if longer, else full text}

----------------------------------------
Действия:
1. Просмотреть память профиля
2. Управление инвариантами
3. Удалить профиль
4. Назад к списку
```

Prompt: `Выберите действие (1-4):`. Invalid action: `[WARN] Неверный выбор, попробуйте снова.` and the action prompt is re-displayed. Actions 1–3 first require profile selection by index (`Выберите профиль (1-{n}):` / `Выберите профиль для удаления (1-{n}):`; out-of-range → `Введите число от 1 до {n}`, non-numeric → `Введите корректное число`). After an action completes, control returns to the Task Profiles menu.

#### 4.7.2 Create Profile (`_create_task_profile`)

```
--- СОЗДАНИЕ НОВОГО ПРОФИЛЯ ЗАДАЧИ ---
Введите название профиля:
Введите описание задачи:
Введите предпочтения/инструкции (Enter для пропуска):

--- ИНВАРИАНТЫ (строгие правила/ограничения) ---
Примеры: 'Использовать только Kotlin', 'Не использовать Java',
         'Стек: PostgreSQL + Redis', 'Пользователь — веган'
Введите инварианты по одному. Пустая строка для завершения:
  >
```

- Name and description are required: empty input re-prompts in place with `[ERROR] Название профиля не может быть пустым.` / `[ERROR] Описание задачи не может быть пустым.`; the CLI performs no length validation/truncation
- Preferences: single line, optional (empty allowed)
- Invariants: entered one per line until an empty line terminates input
- Success output:
  ```
  [OK] Профиль задачи '{name}' создан!
    ID: {profile_id}
    Дата создания: {YYYY-MM-DD HH:MM:SS}
    Инвариантов: {count}      # printed only when at least one invariant was entered
  ```

#### 4.7.3 View Profile Memory (`_view_profile_memory`)

Profile is selected by index from the listed profiles (`Выберите профиль (1-{n}):`). Output:

```
--- ИНФОРМАЦИЯ О ПРОФИЛЕ ЗАДАЧИ ---
  ID: {full_uuid}
  Название: {name}
  Описание: {description}
  Дата создания: {YYYY-MM-DD HH:MM:SS}
  Предпочтения: {preferences}          # строка отсутствует, если пусто

--- ПАМЯТЬ ПРОФИЛЯ ---
  1. {fact_1} ... |(память пуста)

--- ИНВАРИАНТЫ ---
  1. {invariant_1} ... |(инварианты не заданы)
----------------------------------------
```

#### 4.7.4 Manage Invariants (`_manage_invariants`)

After profile selection, shows numbered invariants (`--- ИНВАРИАНТЫ ПРОФИЛЯ: {name} ---`, `(инварианты не заданы)` if empty) and actions:

```
Действия:
1. Добавить инвариант
2. Удалить инвариант
3. Назад
```

- Add: `Введите текст инварианта:`; empty → `[WARN] Инвариант не может быть пустым.`; success → `[OK] Инвариант добавлен!`; repository `ValueError` → `[ERROR] {e}`
- Remove: if the list is empty → `[WARN] Нет инвариантов для удаления.`; otherwise `Выберите номер инварианта для удаления (1-{n}):`; unknown number → `[WARN] Некорректный номер.`; non-numeric → `[WARN] Введите корректное число.`; failure → `[ERROR] Не удалось удалить инвариант.`; success → `[OK] Инвариант удалён!`
- Invalid action number (outside 1–3): `[WARN] Неверный выбор.` (no `попробуйте снова` tail in this submenu)
- The list is redisplayed after each action until `3. Назад`

#### 4.7.5 Delete Profile (`_delete_profile`)

1. Select profile by index
2. If the profile is linked to any agents:
   ```
   [WARN] Невозможно удалить профиль '{name}': он привязан к одному или нескольким агентам.
   Сначала удалите или пересоздайте агентов, использующих этот профиль.
   ```
   and the operation aborts (deletion is blocked, not confirmable)
3. Otherwise confirmation: `Вы уверены, что хотите удалить профиль '{name}'? (y/n):`
   - Not `y`: `[INFO] Удаление отменено.`
   - `y`: `[OK] Профиль '{name}' успешно удалён.` or `[ERROR] Не удалось удалить профиль '{name}'.`

### 4.8 Global Memory View

Main Menu option 4 (`print_global_memory`), available without an active chat:

```
--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---
  1. {fact_1}
  2. {fact_2}
----------------------------------------
```

Empty memory: `(память пуста)`. Returns to Main Menu (no confirmation prompt).

### 4.9 Knowledge Bases Menu (Main Menu Option 7)

Entered from Main Menu option 7 (`knowledge_bases_menu`). Loops until `0`.

```
--- БАЗЫ ЗНАНИЙ ---
1. Создать базу знаний
2. Показать список баз знаний
3. Добавить документы (файл или папка)
4. Показать документы базы знаний
5. Показать чанки документа
6. Удалить документ
7. Удалить базу знаний
8. Проверить поиск
0. Назад в главное меню
----------------------------------------
```

Prompt: `Ваш выбор (0-8):`. Invalid choice: `[WARN] Неверный выбор, попробуйте снова.` and the menu is re-displayed. Option 0 returns to the Main Menu.

- **Create (1)**: prompts `Введите название базы знаний:` (empty re-prompts with `[ERROR] Название базы знаний не может быть пустым.`) and `Введите описание (Enter для пропуска):`. Success:
  ```
  [OK] База знаний '{name}' создана!
    ID: {id}
    Модель эмбеддинга: {model} ({dimension})
  ```
  Duplicate name → `[ERROR] База знаний '{name}' уже существует.`
- **List (2)**: prints `--- СПИСОК БАЗ ЗНАНИЙ ---` with each base's id, model, document and chunk counts; empty list → `[INFO] Базы знаний отсутствуют. Создайте первую базу знаний.`
- **Add documents (3)**: select a base (`Выберите базу знаний (номер, 0 - отмена):`), then `Введите путь к файлу (.md/.py/.txt) или папке с файлами:` (the extension list is built from `RAG_FILE_EXTENSIONS`). Files are chunked, embedded and indexed synchronously; a folder is traversed recursively and each supported file becomes a separate document. Empty files are skipped silently (when scanning a folder, unreadable files are skipped too, so one bad file does not abort the batch). Per-document result lines `[OK] {file} — чанков: {n}` or `[ERROR] {file} — {reason}`, followed by `[OK] Готово: успешно {n}, с ошибками {m}.` Missing path / unsupported extension / empty folder → `[ERROR] {message}`.
- **Documents (4)**: prints `--- ДОКУМЕНТЫ БАЗЫ '{name}' ---` with name, status, id and chunk count; empty → `[INFO] В базе знаний '{name}' нет документов.`
- **Chunks (5)**: select a document, then prints `--- ЧАНКИ ДОКУМЕНТА '{name}' ---` in `chunk_index` order, without embeddings.
- **Delete document (6)**: select a document, confirm `Удалить документ '{name}'? (y/n):`; on `y` deletes the document, its chunks and vectors.
- **Delete knowledge base (7)**: select a base, confirm; deletes the base, its documents, chunks, vectors and agent links.
- **Search (8)**: select a base, enter `Введите поисковый запрос:`; prints `--- РЕЗУЛЬТАТЫ ПОИСКА (база '{name}') ---` with the top-`RAG_FINAL_TOP_K` chunks, their document and vector distance. Empty result → `[INFO] Ничего не найдено.`

All list-selection prompts accept a number or `0` to cancel; non-numeric input prints `[WARN] Введите корректное число.`

---

## 5. Use Cases Index

All use cases live in [`docs/uc/`](uc/) — one file per use case, each with its
alternative flows and related test cases. Interface details (§3–§4) remain in
this document.

| UC | Name | Summary | File |
| --- | --- | --- | --- |
| UC-001 | Create New Chat with All Settings | Create a chat manually with all settings, or accept defaults. | [uc-001-create-new-chat-with-all-settings.md](uc/uc-001-create-new-chat-with-all-settings.md) |
| UC-002 | Select Existing Chat from List | Pick a saved chat from the numbered list and enter it. | [uc-002-select-existing-chat-from-list.md](uc/uc-002-select-existing-chat-from-list.md) |
| UC-003 | Return to Active Chat | Re-enter the previously active chat via menu option 5. | [uc-003-return-to-active-chat.md](uc/uc-003-return-to-active-chat.md) |
| UC-004 | Send Message and Receive Response | Exchange messages with the agent in the chat loop. | [uc-004-send-message-and-receive-response.md](uc/uc-004-send-message-and-receive-response.md) |
| UC-005 | View and Change Settings In-Chat | Show current settings and optionally change them. | [uc-005-view-and-change-settings-in-chat.md](uc/uc-005-view-and-change-settings-in-chat.md) |
| UC-006 | Navigate to Menu from Chat | Leave the chat loop to the Main Menu via /menu. | [uc-006-navigate-to-menu-from-chat.md](uc/uc-006-navigate-to-menu-from-chat.md) |
| UC-007 | Stop Command | Handle /stop and return to the Main Menu. | [uc-007-stop-command.md](uc/uc-007-stop-command.md) |
| UC-008 | Display Help Commands | Show the available slash-commands via /help. | [uc-008-display-help-commands.md](uc/uc-008-display-help-commands.md) |
| UC-009 | View Conversation Summary | Display the current conversation summary. | [uc-009-view-conversation-summary.md](uc/uc-009-view-conversation-summary.md) |
| UC-010 | View Chat Information and Token Statistics | Show chat details, phase and token counters. | [uc-010-view-chat-information-and-token-statistics.md](uc/uc-010-view-chat-information-and-token-statistics.md) |
| UC-011 | Create Chat Branch | Fork the current chat into a new branch. | [uc-011-create-chat-branch.md](uc/uc-011-create-chat-branch.md) |
| UC-012 | View Global Memory from Menu | Display global memory facts from the Main Menu. | [uc-012-view-global-memory-from-menu.md](uc/uc-012-view-global-memory-from-menu.md) |
| UC-013 | View Task Profiles List from Menu | Browse task profiles and their available actions. | [uc-013-view-task-profiles-list-from-menu.md](uc/uc-013-view-task-profiles-list-from-menu.md) |
| UC-014 | Create New Task Profile | Create a task profile with description, preferences and invariants. | [uc-014-create-new-task-profile.md](uc/uc-014-create-new-task-profile.md) |
| UC-015 | View Task Profile Memory | Show a profile's details, memory facts and invariants. | [uc-015-view-task-profile-memory.md](uc/uc-015-view-task-profile-memory.md) |
| UC-016 | Manage Task Profile Invariants | Add or remove strict invariants of a task profile. | [uc-016-manage-task-profile-invariants.md](uc/uc-016-manage-task-profile-invariants.md) |
| UC-017 | Delete Task Profile | Delete an unattached task profile with confirmation. | [uc-017-delete-task-profile.md](uc/uc-017-delete-task-profile.md) |
| UC-018 | Change Workflow Phase With Phase Commands | Move the agent between PLAN/EXECUTE/VALIDATE/REPORT phases. | [uc-018-change-workflow-phase-with-phase-commands.md](uc/uc-018-change-workflow-phase-with-phase-commands.md) |
| UC-019 | Manage MCP Servers Of The Current Chat (/mcp) | Connect MCP servers to the current chat. | [uc-019-manage-mcp-servers-of-the-current-chat.md](uc/uc-019-manage-mcp-servers-of-the-current-chat.md) |
| UC-020 | Manage Knowledge Bases And RAG (/rag, menu 7) | Create bases, index .txt/.md/.py documents, attach bases to a chat and search. | [uc-020-rag-knowledge-bases.md](uc/uc-020-rag-knowledge-bases.md) |
| UC-021 | RAG Sources, Citations And Relevance Threshold | Show used sources/quotes after an answer and refuse below-threshold answers with «Не знаю». | [uc-021-rag-sources-and-relevance-threshold.md](uc/uc-021-rag-sources-and-relevance-threshold.md) |
| UC-022 | Task Memory Of The Dialogue | Keep goal, constraints, terms and clarifications per chat and inject them every turn. | [uc-022-task-memory.md](uc/uc-022-task-memory.md) |
