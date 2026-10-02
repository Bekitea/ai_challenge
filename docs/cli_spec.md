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

1. Global memory facts — section header `--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---` (omitted when global memory is empty);
2. Task profile memory facts — section header `--- ПАМЯТЬ ЗАДАЧИ: {profile_name} ---` (only when the chat has a task profile attached and the profile has facts);
3. User preferences — section header `--- ПРЕДПОЧТЕНИЯ ПОЛЬЗОВАТЕЛЯ ---` (only when the attached profile has non-empty preferences).

Facts are extracted into global and task-profile memory by the `save_agent_memory` use case whenever the chat loop exits (via `/menu`, `/stop`, an error or Ctrl+C — see UC-004 exit rule), and on application start by the `save_unsaved_memories` use case (§4.2.3).

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
----------------------------------------
```

Prompt line: `Ваш выбор (1-6):`

#### 4.2.2 Dynamic Behavior

- Option 5 label depends on `current_agent` state:
  - Active chat exists: `5. Вернуться в чат: {chat_name}`
  - No active chat: `5. Вернуться в чат (нет активного чата)` (no colon)
- Selecting option 5 with an active chat prints `[OK] Возврат в чат: {name}` and enters the chat loop.
- Selecting option 5 without an active chat prints `[WARN] Нет активного чата. Выберите или создайте чат.` and stays in the menu.
- Option 6 prints `До свидания!` and terminates the application.

#### 4.2.3 Input Validation

- Accept only strings "1".."6" (exact match after strip)
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

#### 4.5.4 Error Handling

Error handling in the chat loop is not centralized in a separate matrix: every error case is specified as an alternative flow of the corresponding use case (§5):

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

---

## 5. Comprehensive Use Cases

### UC-001: Create New Chat with All Settings

#### 5.1.1 Preconditions

- Application is running
- User is in Main Menu
- No active chat required

#### 5.1.2 Main Success Scenario

1. User selects option 1 (New Chat)
2. System displays `--- СОЗДАНИЕ НОВОГО ЧАТА ---` and asks `Хотите настроить чат? (y/n, по умолчанию n):`
3. User enters "y" (manual configuration path)
4. System displays name prompt
5. User enters "My Test Chat"
6. System displays system prompt input
7. User enters "You are a helpful assistant"
8. System displays model selection
9. User selects model 1
10. System prompts for temperature
11. User enters "0.7"
12. System prompts for Top P
13. User enters "0.9"
14. System prompts for Top K
15. User enters "40"
16. System prompts for reasoning effort
17. User selects "2" (low)
18. System prompts for context window size; user enters "128000"
19. System prompts for context strategy; user selects "1" (DefaultStrategy)
20. System prompts for task profile; user selects "0" (no attachment)
21. System creates chat with all settings
22. System displays `[OK] Чат '{name}' создан!`
23. System enters chat loop
24. Use case ends

#### 5.1.3 Alternative Flows

- **A1: Quick Creation With Defaults**
  - Step 3: User enters "n" or presses Enter (default is "n")
  - System prints `Используются настройки по умолчанию.` and skips steps 4–20 entirely
  - Chat is created with auto-generated name and `get_default_agent_settings()` (model = Alice AI LLM Flash `aliceai-llm-flash/latest`, temperature/top_p/top_k disabled, reasoning_effort "none", context window 200000), DefaultStrategy, no task profile
  - Continue from step 21

- **A2: Invalid Answer To Configure Prompt**
  - Step 3: User enters text other than `y`/`да`/`д`/`n`/`нет`/`н`
  - System displays `Введите 'y' (да) или 'n' (нет)` and re-prompts the same question

- **A3: Default Name**
  - Step 5: User presses Enter
  - System generates default name `Чат {N}`, where N = (number of existing chats) + 1

- **A4: Skip System Prompt**
  - Step 7: User presses Enter
  - No system message added to history

- **A5: Invalid Model Selection**
  - Step 9: User enters "5"
  - System displays `Неверный выбор, попробуйте снова.` and re-prompts step 9
  - Empty input at step 9 selects the default model (`aliceai-llm-flash/latest`)

- **A6: Disable Temperature / Top P**
  - Step 11/13: User presses Enter
  - Parameter is set to `None` (disabled)

- **A7: Invalid Or Out-Of-Range Temperature**
  - Step 11: User enters "abc" → warning `Некорректное число. Используется значение по умолчанию (отключено).`, temperature = None, creation continues
  - Step 11: User enters value < 0 or > 2.0 → warning `Температура должна быть от 0.0 до 2.0. Используется значение по умолчанию (отключено).`, temperature = None, creation continues
  - Top P (step 13) behaves analogously: non-numeric → `Некорректное число...`; out of 0.0–1.0 → `Top P должен быть от 0.0 до 1.0. Используется значение по умолчанию (отключено).`

- **A8: Invalid Top K**
  - Step 15: Negative integer → warning `Top K должен быть >= 0`, re-prompt step 15
  - Step 15: Non-integer → warning `Введите корректное число`, re-prompt step 15
  - Value 0 is stored as `None` (disabled)

- **A9: Invalid Reasoning Effort**
  - Step 17: Non-integer → `Введите корректное число`; out of range 1–4 → `Выбор должен быть от 1 до 4`; both re-prompt step 17
  - Empty input selects the default (1 — none)

- **A10: Invalid Context Window Size**
  - Step 18: Non-integer → warning `Некорректное число. Используется 200k.`, value = 200000, creation continues
  - Step 18: Zero or negative → warning `Размер должен быть положительным числом. Используется 200k.`, value = 200000, creation continues
  - Empty input → 200000 without any warning

- **A11: Invalid Strategy Choice**
  - Step 19: Input outside "1"–"4" → `Неверный выбор, попробуйте снова.`, re-prompt step 19

- **A12: Invalid Strategy Parameters**
  - Step 19: After choosing strategy 2/3/4, a non-integer value for its parameters (non-compressible count, buffer size, window size) → `Ошибка: {e}. Попробуйте снова.`; the whole strategy selection (step 19) repeats

- **A13: Invalid Task Profile Choice**
  - Step 20: Non-numeric or out-of-range (not 0…n) input → `[WARN] Некорректный выбор. Профиль не привязан.`, creation continues without profile attachment (no re-prompt)

#### 5.1.4 Postconditions

- New chat created in backend storage
- Chat becomes active chat
- User in chat interaction loop

---

### UC-002: Select Existing Chat from List

#### 5.2.1 Preconditions

- At least one chat exists in storage
- User is in Main Menu

#### 5.2.2 Main Success Scenario

1. User selects option 2 (Select Chat)
2. System retrieves all chats from backend
3. System displays numbered list with previews
4. User selects chat number 2
5. System loads chat into active state
6. System displays chat header
7. System enters chat loop
8. Use case ends

#### 5.2.3 Alternative Flows

- **A1: No Chats Exist**
  - Step 2: Backend returns empty list
  - `print_chat_list()` prints `Нет активных чатов.`; then the system displays `Нет доступных чатов. Создайте новый.`
  - System returns to Main Menu

- **A2: Invalid Selection (Out Of Range)**
  - Step 4: User enters "0" or number > count
  - System displays `Введите число от 1 до {n}` and re-prompts step 4

- **A3: Non-Numeric Selection**
  - Step 4: User enters non-integer text (e.g. "abc")
  - System displays `Введите корректное число` and re-prompts step 4
  - Note: selection input is parsed with `int()`, so values such as "2.5" also fall into this flow

#### 5.2.4 Postconditions

- Selected chat becomes active chat
- Full message history loaded
- User in chat interaction loop

---

### UC-003: Return to Active Chat

#### 5.3.1 Preconditions

- An active chat exists in CLI state
- User is in Main Menu

#### 5.3.2 Main Success Scenario

1. User observes option 5 shows "Вернуться в чат: {name}"
2. User selects option 5
3. System validates active chat exists
4. System enters chat loop for active chat
5. Use case ends

#### 5.3.3 Alternative Flows

- **A1: No Active Chat**
  - Step 1: Option 5 shows `Вернуться в чат (нет активного чата)`
  - Step 2: User selects option 5 anyway
  - System displays `[WARN] Нет активного чата. Выберите или создайте чат.`
  - System remains in Main Menu

- **A2: KeyboardInterrupt / EOFError At Menu Prompt**
  - Any step: User presses Ctrl+C or the input stream ends at `Ваш выбор (1-6):`
  - System prints `До свидания!` and terminates the application cleanly (same as option 6)

#### 5.3.4 Postconditions

- Same active chat remains active
- User in chat interaction loop

---

### UC-004: Send Message and Receive Response

#### 5.4.1 Preconditions

- User is in chat interaction loop
- Chat has valid model configuration

#### 5.4.2 Main Success Scenario

1. System displays chat header and prompt
2. User types "Hello, how are you?"
3. User presses Enter
4. System prints `[AGENT] печатает...` (cleared once the response arrives)
5. System sends message to backend agent (`send_message` use case)
6. Backend calls LLM provider
7. LLM generates response
8. System displays "[AGENT]: {response}"
9. System displays token lines if usage was reported: `  [Токены: prompt: {p}, completion: {c}]` and `  [Заполненность контекста: {prompt_tokens}/{context_window_size} ({percent:.1f}%)]` (the fill line is printed only when prompt_tokens is not None)
10. System saves both messages to history
11. System re-displays prompt
12. Use case ends

#### 5.4.3 Alternative Flows

- **A1: Empty Message**
  - Step 2: User presses Enter without text
  - System re-displays prompt without sending

- **A2: Unknown Slash-Command**
  - Step 2: User enters an unrecognized slash-command (e.g. "/xyz")
  - It is not intercepted as a command; it is sent to the agent as a regular message (main flow continues from step 4)

- **A3: Whitespace-Only Input**
  - Step 2: User enters only spaces/tabs
  - System re-displays the prompt without sending anything to the backend (same handling as A1)

- **A4: Context Window Exceeded**
  - Step 6: Backend raises `ContextWindowExceededError`
  - System clears the "печатает..." line, displays `[ERROR] {message}` followed by `Необходимо очистить историю сообщений или создать новый чат.`
  - System saves the agent memory via the `save_agent_memory` use case (memory must not be lost on abnormal exit)
  - System exits the chat loop and returns to Main Menu (the chat remains active for option 5)

- **A5: Any Other Backend Error**
  - Step 6: Any other exception is raised while sending/processing
  - System displays `[ERROR] Ошибка: {message}`
  - System saves the agent memory via the `save_agent_memory` use case, then exits the chat loop and returns to Main Menu

- **A6: KeyboardInterrupt During Exchange**
  - Any step: User presses Ctrl+C at the input prompt or during processing
  - System displays `Прервано пользователем.`, saves the agent memory via the `save_agent_memory` use case and exits the chat loop back to Main Menu

- **A7: EOFError (End Of Input)**
  - Step 1/2: The input stream ends (piped input exhausted or Ctrl+D)
  - The chat loop terminates gracefully without a traceback; the agent memory is saved before exit (same rule as A6)

- **A8: Long Response**
  - Step 8: Response exceeds terminal width
  - System wraps text appropriately

- **A9: Reasoning In Response**
  - After step 9: response carries reasoning content
  - System asks `Показать рассуждения модели? (y/n):`; on `y` it prints the indented `[Reasoning]:` block, otherwise nothing extra

#### 5.4.4 Postconditions

- Two new messages in history (user + assistant)
- Chat preview updated with last message
- On any exit from the chat loop (`/menu`, A4, A5, A6, A7) the agent memory is saved before returning to the Main Menu

---

### UC-005: View and Change Settings In-Chat

#### 5.5.1 Preconditions

- User is in chat interaction loop
- Chat has existing settings

#### 5.5.2 Main Success Scenario

1. User types "/settings"
2. System executes `print_settings()`
3. System displays current settings (`--- ТЕКУЩИЕ НАСТРОЙКИ ---` block)
4. System prompts: `Изменить настройки? (y/n):`
5. User enters "y"
6. System executes `change_settings()`: displays header `--- НАСТРОЙКИ ДЛЯ '{chat_name}' ---` and re-prompts ALL agent settings (model, temperature, top_p, top_k, reasoning effort, context window size — the same prompts as chat creation steps; empty input disables a parameter, there is no "keep current value" semantics)
7. User enters new values (e.g. temperature "1.0")
8. System updates settings via `change_settings` use case
9. System displays "[OK] Настройки обновлены!" followed by the refreshed `--- ТЕКУЩИЕ НАСТРОЙКИ ---` block
10. System returns to chat prompt
11. Use case ends

#### 5.5.3 Alternative Flows

- **A1: Decline Changing**
  - Step 5: User enters "n", presses Enter, or enters any text other than "y"
  - No changes are made; system returns to the chat prompt

- **A2: Invalid Input During Re-Prompting**
  - Step 6: Each individual setting validates exactly like during chat creation (see UC-001 A7–A10): out-of-range/non-numeric temperature and top_p disable the parameter with a warning; top_k, reasoning effort re-prompt on invalid input; context window falls back to 200k with a warning

- **A3: KeyboardInterrupt / EOFError During Settings Flow**
  - Any step: Ctrl+C or end of input propagates to the chat loop handler
  - System displays `Прервано пользователем.`, saves the agent memory (UC-004 exit rule) and exits the chat loop back to Main Menu

- **A4: Backend Error While Applying Settings**
  - Step 8: `change_settings` use case raises an exception
  - System displays `[ERROR] Ошибка: {message}`, saves the agent memory (UC-004 exit rule) and exits the chat loop back to Main Menu

#### 5.5.4 Postconditions

- Updated settings saved to chat
- Changes apply to future messages

---

### UC-006: Navigate to Menu from Chat

#### 5.6.1 Preconditions

- User is in chat interaction loop

#### 5.6.2 Main Success Scenario

1. User types "/menu"
2. System displays `Возврат в меню...`
3. System saves chat memory via `save_agent_memory` use case (LLM fact extraction into global and task-profile memory)
4. System exits the chat loop and displays Main Menu
5. Use case ends

#### 5.6.3 Postconditions

- Chat preserved in backend storage
- User in Main Menu
- Chat remains the "active" chat for quick return (option 5)

---

### UC-007: Stop Command

#### 5.7.1 Preconditions

- User is in chat interaction loop

#### 5.7.2 Main Success Scenario

1. User types "/stop"
2. System displays `[INFO] Генерация не активна.` (in the synchronous implementation generation is never active while input is being read)
3. System exits the chat loop and returns to Main Menu
4. Use case ends

#### 5.7.3 Postconditions

- Chat remains the active chat (option 5 can return to it)
- User is in Main Menu
- Per the UC-004 exit rule, the agent memory is saved on exiting the chat loop via `/stop`

---

### UC-008: Display Help Commands

#### 5.8.1 Preconditions

- User is in chat interaction loop

#### 5.8.2 Main Success Scenario

1. User types "/help"
2. System displays command list
3. System returns to prompt
4. Use case ends

#### 5.8.3 Postconditions

- No state changes
- User informed of available commands

---

### UC-009: View Conversation Summary

#### 5.9.1 Preconditions

- User is in chat interaction loop
- Chat uses SummarizationStrategy or KeyValueMemoryStrategy
- At least one summarization has been performed

#### 5.9.2 Main Success Scenario

1. User types "/summary"
2. System retrieves summary from active strategy
3. System displays summary text
4. System returns to prompt
5. Use case ends

#### 5.9.3 Alternative Flows

- **A1: No Summary Yet**
  - Step 2: Strategy has no summary (summarization not triggered yet)
  - System displays `[INFO] Саммари пока недоступно.`
  - Continue to step 4

#### 5.9.4 Postconditions

- No state changes
- User sees conversation summary

---

### UC-010: View Chat Information and Token Statistics

#### 5.10.1 Preconditions

- User is in chat interaction loop

#### 5.10.2 Main Success Scenario

1. User types "/info"
2. System retrieves chat statistics via `show_chat_info` use case (`ChatInfo`)
3. System displays header `--- ИНФОРМАЦИЯ О ЧАТЕ ---` with name, ID, strategy, task profile, phase, message count (§4.5.3 `/info`)
4. System displays token counters (`Prompt токены`, `Completion токены`)
5. System displays conditional lines: `Есть саммари: Да` (if summary exists), `Несжимаемые сообщения`, `Размер буфера` (if the strategy exposes them)
6. System displays a 40-dash separator and returns to the chat prompt
7. Use case ends

#### 5.10.3 Postconditions

- No state changes
- User sees detailed chat statistics

---

### UC-011: Create Chat Branch

#### 5.11.1 Preconditions

- User is in chat interaction loop
- Current chat has at least one message

#### 5.11.2 Main Success Scenario

1. User types "/branch"
2. System displays header `--- СОЗДАНИЕ ВЕТКИ ОТ '{current_name}' ---`
3. System prompts: `Введите название ветки (Enter для автогенерации):`
4. User enters name or presses Enter (auto-name `{current_name} (branch {YYYY-MM-DD HH:MM:SS})`)
5. System creates the branch via `create_branch` use case, copying all messages, settings, token counters and the context strategy with its accumulated state; a new `conversation_id` (UUID) is generated
6. System switches `current_agent` to the branch
7. System asks: `Продолжить в новой ветке? (y/n):`
8. User enters "y"
9. System enters the chat loop for the branch chat
10. Use case ends

#### 5.11.3 Alternative Flows

- **A1: Stay In Current Chat Loop**
  - Step 8: User enters anything other than "y"
  - System prints `Ветка создана. Вы можете вернуться к ней через меню.` and stays in the current chat loop
  - Note: `current_agent` already points to the branch; the original chat is reachable via Main Menu option 2 ("Выбрать чат")

- **A2: Custom Branch Name**
  - Step 4: User enters a custom name
  - System uses the provided name for the new branch

- **A3: Backend Error While Creating Branch**
  - Step 5: `create_branch` use case raises an exception
  - System displays `[ERROR] Ошибка при создании ветки: {e}`
  - System returns to the chat prompt; no switch happens

#### 5.11.4 Postconditions

- New chat created in storage with copied data
- `current_agent` points to the branch chat
- Original chat preserved unchanged

---

### UC-012: View Global Memory from Menu

#### 5.12.1 Preconditions

- Application is running
- User is in Main Menu
- No active chat required (global memory is independent of chats/agents)

#### 5.12.2 Main Success Scenario

1. User selects option 4 (Global Memory) from Main Menu
2. System retrieves global memory facts from GlobalMemoryRepository
3. System displays header: `--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---`
4. If memory is empty: displays `(память пуста)`
5. If memory has facts: displays numbered list of facts (one fact per line)
6. System displays separator line (40 dashes)
7. System returns to Main Menu
8. Use case ends

#### 5.12.3 Alternative Flows

- **A1: Empty Global Memory**
  - Step 3: Repository returns empty list of facts
  - System displays `(память пуста)` instead of fact list
  - Continue with step 6

#### 5.12.4 Postconditions

- User viewed global memory facts (or empty state)
- Returned to Main Menu
- No active chat required or changed

---

### UC-013: View Task Profiles List from Menu

#### 5.13.1 Preconditions

- Application is running
- User is in Main Menu
- No active chat required

#### 5.13.2 Main Success Scenario

1. User selects option 3 (Task Profiles) from Main Menu
2. System displays the Task Profiles menu:
   ```
   --- ПРОФИЛИ ЗАДАЧ ---
   1. Создать новый профиль
   2. Просмотреть список профилей
   3. Назад в главное меню
   ----------------------------------------
   ```
3. User selects option 2 (View profiles list)
4. System retrieves all task profiles via `list_task_profiles.execute()`
5. If no profiles exist: display `Нет доступных профилей задач.` + separator, return to the Task Profiles menu
6. If profiles exist: display header `--- СПИСОК ПРОФИЛЕЙ ЗАДАЧ ---` and a block per profile:
   ```
   {index}. {name}
      ID: {profile_id}
      Дата создания: {YYYY-MM-DD HH:MM}
      Фактов в памяти: {facts_count}
      Инвариантов: {invariants_count}
      Описание: {description[:50] + "..." if longer than 50 chars, else full description}
   ```
7. System displays actions (`Действия:` / `1. Просмотреть память профиля` / `2. Управление инвариантами` / `3. Удалить профиль` / `4. Назад к списку`) and prompts `Выберите действие (1-4):`
8. System processes user choice:
   - Action 1: profile selection by index, then UC-015 (view memory)
   - Action 2: profile selection by index, then manage invariants (§4.7.4)
   - Action 3: profile selection by index, then UC-016 (delete)
   - Action 4: return to the Task Profiles menu
9. Use case ends

#### 5.13.3 Alternative Flows

- **A1: Empty Task Profiles List**
  - Step 5: Repository returns empty list
  - System shows `Нет доступных профилей задач.` and returns to the Task Profiles menu (no action submenu)

- **A2: Invalid Menu Choice**
  - Step 3/8: User enters an option outside the displayed range
  - Display `[WARN] Неверный выбор, попробуйте снова.` and re-prompt

- **A3: Invalid Profile Index**
  - Step 8: Out-of-range number → `Введите число от 1 до {n}`; non-numeric → `Введите корректное число`; re-prompt until valid

- **A4: Invalid Action In Profiles List Submenu**
  - Step 9: User enters an action number outside 1–4 at `Выберите действие (1-4):`
  - Display `[WARN] Неверный выбор, попробуйте снова.` and re-prompt the action

#### 5.13.4 Postconditions

- User viewed task profiles list (or empty state)
- Optionally viewed memory, managed invariants, or deleted a profile
- Returned to the Task Profiles menu / Main Menu when requested

---

### UC-014: Create New Task Profile

#### 5.14.1 Preconditions

- Application is running
- User initiated profile creation from Task Profiles menu

#### 5.14.2 Main Success Scenario

1. System displays name prompt: `Введите название профиля:`
2. User enters profile name
3. System validates name (non-empty; no length limit enforced by the CLI) and re-prompts on empty input with `[ERROR] Название профиля не может быть пустым.`
4. System displays description prompt: `Введите описание задачи:`
5. User enters description
6. System validates description (non-empty; no length limit enforced by the CLI) and re-prompts on empty input with `[ERROR] Описание задачи не может быть пустым.`
7. System displays preferences prompt: `Введите предпочтения/инструкции (Enter для пропуска):`
8. User enters preferences text (or presses Enter to skip)
9. System accepts preferences (no validation, empty input allowed)
10. System displays the invariants block header (`--- ИНВАРИАНТЫ (строгие правила/ограничения) ---`, examples and `Введите инварианты по одному. Пустая строка для завершения:`) and reads invariants one per line until an empty line
11. System creates the profile via `create_task_profile.execute(name, description, preferences, invariants)`
12. System records current timestamp as `created_at`
13. System saves profile to TaskProfileRepository
14. System displays success message:
    ```
    [OK] Профиль задачи '{name}' создан!
      ID: {profile_id}
      Дата создания: {YYYY-MM-DD HH:MM:SS}
      Инвариантов: {count}   # only when at least one invariant was entered
    ```
15. System returns to Task Profiles menu
16. Use case ends

#### 5.14.3 Alternative Flows

- **A1: Empty Name**
  - Step 3: User enters empty string
  - Display `[ERROR] Название профиля не может быть пустым.` and re-prompt the same question

- **A2: Empty Description**
  - Step 6: User enters empty string
  - Display `[ERROR] Описание задачи не может быть пустым.` and re-prompt the same question

- **A3: Empty Preferences**
  - Step 9: User presses Enter without entering text
  - Accept empty string as valid preferences value (no error)

- **A4: No Invariants**
  - Step 10: User presses Enter immediately on the first `>` prompt
  - Profile is created with an empty invariants list; the `Инвариантов:` line is omitted from the success output

#### 5.14.4 Postconditions

- New TaskProfile created with unique UUID
- Profile saved to repository with empty facts list
- Profile saved with preferences (may be empty string)
- User returned to Task Profiles menu

---

### UC-015: View Task Profile Memory

#### 5.15.1 Preconditions

- Application is running
- User is in the profiles list submenu (Task Profiles menu → option 2 → action 1)
- At least one task profile exists

#### 5.15.2 Main Success Scenario

1. System displays prompt: `Выберите профиль (1-{n}):`
2. User selects profile by index
3. System retrieves profile details, facts and invariants via `get_task_profile_memory.execute(profile_id)`
4. System displays profile information:
   ```
   --- ИНФОРМАЦИЯ О ПРОФИЛЕ ЗАДАЧИ ---
     ID: {profile_id}
     Название: {name}
     Описание: {description}
     Дата создания: {YYYY-MM-DD HH:MM:SS}
     Предпочтения: {preferences}    # строка выводится только если preferences непустые

   --- ПАМЯТЬ ПРОФИЛЯ ---
     1. {fact_1}
     2. {fact_2}
     ...              |(память пуста)

   --- ИНВАРИАНТЫ ---
     1. {invariant_1}
     ...              |(инварианты не заданы)
   ----------------------------------------
   ```
5. If memory is empty: display `(память пуста)` instead of the facts list
6. If preferences are empty: the `Предпочтения:` line is omitted entirely
7. If invariants are empty: display `(инварианты не заданы)`
8. Use case ends; control returns to the Task Profiles menu

#### 5.15.3 Alternative Flows

- **A1: Invalid Profile Selection**
  - Step 2: Out-of-range number → `Введите число от 1 до {n}`; non-numeric → `Введите корректное число`; re-prompt until valid

- **A2: Empty Memory**
  - Step 5: Repository returns empty facts list
  - Display `(память пуста)` instead of fact list

- **A3: Profile Not Found**
  - Step 3: `get_task_profile_memory` returns None
  - Display `[ERROR] Профиль не найден.` and return to the Task Profiles menu

#### 5.15.4 Postconditions

- User viewed task profile details, memory facts and invariants
- Returned to Task Profiles menu

---

### UC-016: Manage Task Profile Invariants

#### 5.16.0 Overview

This section covers invariants management (UC-016) and profile deletion (UC-017).

#### 5.16.1 Preconditions

- Application is running
- User is in the profiles list submenu (Task Profiles menu → option 2 → action 2)
- At least one task profile exists

#### 5.16.2 Main Success Scenario

1. System displays prompt: `Выберите профиль (1-{n}):`
2. User selects profile by index
3. System displays header `--- ИНВАРИАНТЫ ПРОФИЛЯ: {name} ---` with numbered invariants (`(инварианты не заданы)` if empty) and actions:
   ```
   Действия:
   1. Добавить инвариант
   2. Удалить инвариант
   3. Назад
   ```
4. User selects action 1 (Add invariant)
5. System prompts: `Введите текст инварианта:`
6. User enters invariant text
7. System adds invariant via repository and displays `[OK] Инвариант добавлен!`
8. System redisplays the invariants list (with the new invariant)
9. User selects action 2 (Remove invariant)
10. System prompts: `Выберите номер инварианта для удаления (1-{n}):`
11. User enters a valid number
12. System removes the invariant and displays `[OK] Инвариант удалён!`
13. System redisplays the list; user selects `3. Назад`
14. Control returns to the Task Profiles menu; use case ends

#### 5.16.3 Alternative Flows

- **A1: Empty Invariant Text**
  - Step 6: User presses Enter without text
  - Display `[WARN] Инвариант не может быть пустым.`; no invariant is added, the list is redisplayed

- **A2: Invalid Invariant Number**
  - Step 10: Unknown/out-of-range number → `[WARN] Некорректный номер.`; non-numeric input → `[WARN] Введите корректное число.`; repository removal returns failure → `[ERROR] Не удалось удалить инвариант.`

- **A3: Repository ValueError On Add**
  - Step 7: Repository raises `ValueError` (e.g. duplicate invariant)
  - Display `[ERROR] {e}`; the list is redisplayed

- **A4: Invalid Action Choice**
  - Step 4/9: User enters an action number outside 1–3 at `Выберите действие (1-3):`
  - Display `[WARN] Неверный выбор.` (without the `попробуйте снова` tail); the invariants list and action prompt are re-displayed

- **A5: No Invariants To Remove**
  - Step 9: User selects action 2 while the invariants list is empty
  - Display `[WARN] Нет инвариантов для удаления.`; the list and action prompt are re-displayed

#### 5.16.4 Postconditions

- Invariants list updated in the profile storage
- User returned to the Task Profiles menu

---

### UC-017: Delete Task Profile

#### 5.17.1 Preconditions

- Application is running
- User is in the profiles list submenu (Task Profiles menu → option 2 → action 3)
- At least one task profile exists

#### 5.17.2 Main Success Scenario

1. System displays prompt: `Выберите профиль для удаления (1-{n}):`
2. User selects profile by index
3. System checks whether the profile is linked to any agents (`is_profile_linked_to_agents`)
4. If not linked, system prompts for confirmation: `Вы уверены, что хотите удалить профиль '{name}'? (y/n):`
5. If user confirms with 'y':
   - System deletes profile from TaskProfileRepository
   - Display success: `[OK] Профиль '{name}' успешно удалён.`
6. If user declines (any input other than `y`):
   - Display `[INFO] Удаление отменено.`
7. If deletion fails: `[ERROR] Не удалось удалить профиль '{name}'.`
8. System returns to Task Profiles menu
9. Use case ends

#### 5.17.3 Alternative Flows

- **A1: Invalid Profile Selection**
  - Step 2: Out-of-range number → `Введите число от 1 до {n}`; non-numeric → `Введите корректное число`; re-prompt until valid

- **A2: Confirmation Declined**
  - Step 5: User enters anything other than `y`
  - Deletion cancelled with `[INFO] Удаление отменено.`, return to menu

- **A3: Profile Attached to Agents (deletion blocked)**
  - Step 3: System detects attached agents; deletion is NOT offered at all:
    ```
    [WARN] Невозможно удалить профиль '{name}': он привязан к одному или нескольким агентам.
    Сначала удалите или пересоздайте агентов, использующих этот профиль.
    ```
  - Operation aborts, return to the Task Profiles menu

#### 5.17.4 Postconditions

- If confirmed and unlinked: TaskProfile deleted from repository
- If declined or linked to agents: Profile remains unchanged
- User returned to Task Profiles menu

---

### UC-018: Change Workflow Phase With Phase Commands

#### 5.18.1 Preconditions

- User is in chat interaction loop
- Agent has a current workflow phase (new chats start in `PLAN`; a chat loaded from storage restores its saved phase)

#### 5.18.2 Main Success Scenario

1. User types `/execute` while the agent is in phase PLAN
2. System transitions the phase via `Agent.handle_phase_command` (§4.5.3)
3. System displays `[INFO] Фаза изменена: PLAN -> EXECUTE`
4. System displays the updated header line `--- ЧАТ: {name} [Фаза: EXECUTE] ---`
5. System returns to the chat prompt; subsequent messages are processed in the new phase
6. Use case ends

#### 5.18.3 Alternative Flows

- **A1: Forward Skip Rejected**
  - Step 1: From PLAN the user enters `/validate` or `/report` (or from EXECUTE — `/report`)
  - The transition is rejected: `[INFO] Нельзя перескочить этап: переход из {OLD} сразу в {NEW} запрещен` followed by the unchanged header line `--- ЧАТ: {name} [Фаза: {OLD}] ---`
  - The phase is NOT changed; the chat loop continues

- **A2: Backward Transition Allowed**
  - Step 1: From any phase the user enters a command of an earlier phase (e.g. `/plan` while in VALIDATE)
  - Any backward transition is allowed: `[INFO] Фаза изменена: {OLD} -> PLAN`, header updated

- **A3: Case-Insensitive Command**
  - Step 1: User enters the command in uppercase/mixed case (e.g. `/EXECUTE`)
  - Commands are matched case-insensitively; the transition succeeds exactly as in the main scenario

- **A4: Phase Visible In Chat Header And /info**
  - After any successful transition: entering the chat loop replays the header `--- ЧАТ: {name} [Фаза: {PHASE}] ---` (§4.5.1) and `/info` shows `Текущая фаза: {PHASE}` (§4.5.3 `/info`)

#### 5.18.4 Postconditions

- On accepted transition: `Agent.current_phase` equals the target phase; the change is persisted with the agent (auto-save)
- On rejected transition: phase unchanged
- No messages are added to history by phase commands

---

### UC-019: Manage MCP Servers Of The Current Chat (/mcp)

#### 5.19.1 Preconditions

- User is in chat interaction loop
- At least one MCP server is registered in the registry (`mcp_registry`)

#### 5.19.2 Main Success Scenario

1. User types `/mcp`
2. System displays the connected-servers block (§4.5.3 `/mcp`): header `--- MCP-СЕРВЕРЫ ЧАТА: {chat_name} ---`, then per server either `[OK] {title} ({name}) — инструменты: {tool1, tool2}` (connected) or `[OFFLINE] {title} ({name}) — подключение не установлено` (connection not established); if none are connected: `К этому чату ещё не подключено ни одного MCP-сервера.`
3. System prompts: `Подключить новые MCP? (y/n):`
4. User enters "y"
5. System lists registry servers not yet connected to this chat under `--- ДОСТУПНЫЕ ДЛЯ ПОДКЛЮЧЕНИЯ MCP ---` as `{idx}. {title} ({name}) — {description}`
6. System prompts: `Введите номер сервера для подключения (или название, 0 — отмена):`
7. User enters a valid number (or a server name)
8. System displays `[INFO] Подключаю MCP '{name}'...`
9. System executes the `connect_mcp` use case and displays `[OK] {message}` on success
10. The server list is persisted on the agent; tools become available to the LLM in subsequent messages (tool-calling loop inside `continue_dialog`)
11. Control returns to the chat prompt; use case ends

#### 5.19.3 Alternative Flows

- **A1: Decline Connecting New Servers**
  - Step 4: User enters anything other than `y` (including empty input)
  - The flow ends immediately after the connected-servers block; control returns to the chat prompt with no changes

- **A2: All Servers Already Connected**
  - Step 5: `list_available_mcp` returns an empty list
  - System displays `[INFO] Все доступные MCP-серверы уже подключены к этому чату.` and returns to the chat prompt

- **A3: Cancel Connection**
  - Step 7: User presses Enter (empty input) or enters `0`
  - System displays `[INFO] Подключение отменено.` and returns to the chat prompt

- **A4: Numeric Selection Out Of Range**
  - Step 7: User enters a digit outside 1…n
  - System displays `[ERROR] Неверный номер сервера.` and ends the flow (no re-prompt)

- **A5: Connection Fails**
  - Step 9: `connect_mcp` returns failure (unknown server name or unreachable server)
  - System displays `[ERROR] {message}` from the use case; the chat's server list is unchanged; control returns to the chat prompt

- **A6: EOFError / KeyboardInterrupt During /mcp Prompts**
  - Step 4/7: End of input or Ctrl+C at a `/mcp` prompt
  - The exception is handled locally inside the `/mcp` flow: the chat loop is NOT exited, control returns to the chat prompt

- **A7: Offline Server Display**
  - Step 2: A connected-to-chat server cannot be reached
  - It is listed with the `[OFFLINE]` line instead of `[OK]` (see §4.5.3)

#### 5.19.4 Postconditions

- On success: the server is appended to the chat's MCP list and persisted; its tools are available in subsequent exchanges
- On cancel/decline/failure: no state changes
- User remains in the chat interaction loop

---

## 6. Test Cases

### TC-001: Quick Chat Creation With Defaults

**Related UC**: UC-001 A1

| Step | Action                                       | Expected Result                                                                                                   |
| ---- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| 1    | Select option 1 (New Chat)                   | Header `--- СОЗДАНИЕ НОВОГО ЧАТА ---` and prompt `Хотите настроить чат? (y/n, по умолчанию n):` displayed        |
| 2    | Press Enter (empty input → default "n")      | `Используются настройки по умолчанию.` printed; steps 4–20 of UC-001 skipped entirely; creation continues from UC-001 step 21 |
| 3    | Verify completion message                    | `[OK] Чат 'Чат {N}' создан!` (auto-generated name), then chat loop entered                                        |
| 4    | Verify chat settings                         | Model = `aliceai-llm-flash/latest`, temperature/top_p/top_k disabled (None), reasoning_effort "none", context window 200000 |
| 5    | Verify strategy and profile                  | DefaultStrategy, task_profile_id = null                                                                            |

---

### TC-002: Create Chat with Custom Settings

**Related UC**: UC-001 (main success scenario, steps 1–23)

| Step | Action                             | Expected Result                                          |
| ---- | ---------------------------------- | -------------------------------------------------------- |
| 1    | Select option 1 (New Chat)         | Header `--- СОЗДАНИЕ НОВОГО ЧАТА ---` and configure prompt `Хотите настроить чат? (y/n, по умолчанию n):` displayed |
| 2    | Enter "y"                          | Name prompt displayed                                    |
| 3    | Enter "Test Chat"                  | System prompt input displayed                            |
| 4    | Enter "Be concise"                 | Model selection displayed                                |
| 5    | Select model 2                     | Temperature prompt displayed                             |
| 6    | Enter "1.5"                        | Valid value (within 0.0–2.0): applied without warning; Top P prompt displayed |
| 7    | Enter "0.8"                        | Top K prompt displayed                                   |
| 8    | Enter "50"                         | Reasoning effort prompt displayed                        |
| 9    | Select "3" (medium)                | Context window prompt displayed                          |
| 10   | Enter "128000"                     | Strategy selection displayed                             |
| 11   | Select "1" (DefaultStrategy)       | Task profile selection displayed                         |
| 12   | Select "0" (no attachment)         | `[OK] Чат 'Test Chat' создан!`, chat loop entered        |
| 13   | Verify settings                    | All entered values saved correctly: temperature = 1.5, top_p = 0.8, top_k = 50, reasoning_effort = "medium", context window = 128000, DefaultStrategy |

**Note**: The main success scenario of UC-001 uses different sample values (model 1, temperature "0.7", Top P "0.9", Top K "40", reasoning effort "2" — low). This test intentionally exercises the same flow with other valid values; every step of UC-001's main scenario is covered.

---

### TC-003: Invalid Temperature Handling

**Related UC**: UC-001 A7

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Start chat creation with "y", pass name/system prompt, select model | Temperature prompt displayed                                                       |
| 2    | Enter "abc"                                                     | Warning `Некорректное число. Используется значение по умолчанию (отключено).`; temperature = None; creation continues (Top P prompt) |
| 3    | Press Enter at Top P/Top K prompts, answer remaining steps, finish creation | Chat created with temp=None                                                 |
| 4    | Repeat creation, enter "-1" at temperature prompt               | Warning `Температура должна быть от 0.0 до 2.0. ...`; temperature = None, creation continues |
| 5    | Repeat creation, enter "3.0" at temperature prompt              | Warning `Температура должна быть от 0.0 до 2.0. ...`; temperature = None, creation continues |

---

### TC-004: Invalid Answer To Configure Prompt

**Related UC**: UC-001 A2

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Select option 1 (New Chat)                                      | Configure prompt `Хотите настроить чат? (y/n, по умолчанию n):` displayed             |
| 2    | Enter "maybe" (not y/да/д/n/нет/н and not empty)                | `Введите 'y' (да) или 'n' (нет)` displayed; the same question re-prompted (UC-001 A2) |
| 3    | Enter "да"                                                      | Accepted as affirmative: manual path starts, name prompt displayed (§4.4.0)           |

---

### TC-005: Default Chat Name On Empty Input

**Related UC**: UC-001 A3

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Ensure exactly 2 chats exist in storage                         | Main Menu displayed                                                                    |
| 2    | Select option 1 (New Chat), enter "y"                           | Name prompt `Введите название чата (по умолчанию 'Чат N'):` displayed                 |
| 3    | Press Enter (empty input)                                       | System uses default name `Чат 3` (N = existing chats + 1, §4.4.1); system prompt step follows |
| 4    | Complete creation (any valid answers)                           | `[OK] Чат 'Чат 3' создан!`                                                            |
| 5    | Verify chat list                                                | New chat listed with name `Чат 3`                                                      |

---

### TC-006: Out-Of-Range Model Selection Re-Prompts

**Related UC**: UC-001 A5

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Start manual creation, pass name/system prompt                  | Model selection block `--- НАСТРОЙКИ АГЕНТА ---` displayed                             |
| 2    | Enter "5" (outside 1–3)                                         | `Неверный выбор, попробуйте снова.` displayed; model selection re-prompted (UC-001 A5)|
| 3    | Enter "abc" (non-numeric)                                       | Same warning; model selection re-prompted again                                        |
| 4    | Press Enter (empty input)                                       | Default model `aliceai-llm-flash/latest` selected; temperature prompt displayed (§4.4.3)|

---

### TC-007: Task Profile Selection - Invalid Choice Does Not Block Creation

**Related UC**: UC-001 A13

**Precondition**: At least one task profile exists

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Complete manual creation through strategy selection             | Task profile block `--- ПРИВЯЗКА ПРОФИЛЯ ЗАДАЧИ ---` displayed                        |
| 2    | Enter "99" (out of range 0–n)                                   | `[WARN] Некорректный выбор. Профиль не привязан.` displayed; creation continues without attachment (no re-prompt, UC-001 A13) |
| 3    | Verify completion                                               | `[OK] Чат '{name}' создан!`, chat loop entered                                         |
| 4    | Type "/info"                                                    | Line `Профиль задачи: (не привязан)` shown                                             |

---

### TC-008: Non-Integer Strategy Parameter Repeats Strategy Selection

**Related UC**: UC-001 A12

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Reach strategy selection during manual creation                 | Strategy block `--- ВЫБОР СТРАТЕГИИ УПРАВЛЕНИЯ КОНТЕКСТНЫМ ОКНОМ ---` displayed       |
| 2    | Select "2" (SummarizationStrategy)                              | Prompt `Количество несжимаемых сообщений (по умолчанию 2):` displayed                 |
| 3    | Enter "abc"                                                     | `Ошибка: {e}. Попробуйте снова.` displayed; the whole strategy selection repeats (UC-001 A12) |
| 4    | Select "2", enter valid integers for both parameters            | SummarizationStrategy created with entered values; task profile step follows          |

---

### TC-070: Skip System Prompt On Empty Input

**Related UC**: UC-001 A4

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Start manual creation ("y"), enter a name                        | System prompt input displayed                                                         |
| 2    | Press Enter (empty input)                                        | Model selection displayed; no error                                                    |
| 3    | Complete creation and send one message                           | Normal exchange                                                                        |
| 4    | Verify history                                                   | History contains only user + assistant messages — no system message was added         |

---

### TC-071: Empty Inputs Disable Temperature And Top P

**Related UC**: UC-001 A6

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Reach temperature prompt during manual creation                  | Temperature prompt displayed                                                            |
| 2    | Press Enter (empty input)                                        | No warning; parameter set to None (disabled); Top P prompt displayed                    |
| 3    | Press Enter at Top P prompt                                     | top_p = None; Top K prompt displayed                                                    |
| 4    | Finish creation, type "/settings"                                | Температура and Top P shown as "отключена"/None (§4.6.1)                                |

---

### TC-072: Invalid Top K Re-Prompts; Zero Disables

**Related UC**: UC-001 A8

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Reach Top K prompt during manual creation                        | Top K prompt displayed                                                                  |
| 2    | Enter "-5"                                                       | Warning `Top K должен быть >= 0`; Top K re-prompted                                      |
| 3    | Enter "abc"                                                      | Warning `Введите корректное число`; Top K re-prompted                                    |
| 4    | Enter "0"                                                        | Accepted; value stored as None (disabled); reasoning effort prompt displayed            |

---

### TC-073: Invalid Reasoning Effort Re-Prompts; Empty Selects Default

**Related UC**: UC-001 A9

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Reach reasoning effort prompt during manual creation             | Numbered options block displayed                                                        |
| 2    | Enter "abc"                                                      | `Введите корректное число`; re-prompted                                                  |
| 3    | Enter "5" (outside 1–4)                                          | `Выбор должен быть от 1 до 4`; re-prompted                                               |
| 4    | Press Enter (empty input)                                        | Default selected — reasoning_effort "none"; context window prompt displayed             |

---

### TC-074: Invalid Context Window Falls Back To 200k

**Related UC**: UC-001 A10

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Reach context window prompt during manual creation               | Context window prompt displayed                                                         |
| 2    | Enter "abc"                                                      | Warning `Некорректное число. Используется 200k.`; value = 200000; creation continues     |
| 3    | Repeat creation, enter "0" at the same prompt                    | Warning `Размер должен быть положительным числом. Используется 200k.`; value = 200000   |
| 4    | Repeat creation, press Enter (empty input)                       | Value = 200000 without any warning                                                      |

---

### TC-075: Invalid Strategy Choice Re-Prompts

**Related UC**: UC-001 A11

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Reach strategy selection during manual creation                  | Strategy block `--- ВЫБОР СТРАТЕГИИ УПРАВЛЕНИЯ КОНТЕКСТНЫМ ОКНОМ ---` displayed         |
| 2    | Enter "5" (outside 1–4)                                          | `Неверный выбор, попробуйте снова.`; strategy selection re-prompted                     |
| 3    | Enter "abc" (non-numeric)                                        | Same warning; strategy selection re-prompted again                                      |
| 4    | Select "1"                                                       | Task profile step follows; chat created with DefaultStrategy                            |

---

### TC-009: Select Chat from Empty List

**Related UC**: UC-002 A1

| Step | Action                       | Expected Result                                                            |
| ---- | ---------------------------- | ---------------------------------------------------------------------------- |
| 1    | Ensure no chats exist        | Empty storage                                                              |
| 2    | Select option 2 (Select Chat)| `print_chat_list()` prints `Нет активных чатов.`; then `Нет доступных чатов. Создайте новый.` |
| 3    | Verify navigation            | Returns to Main Menu                                                       |

---

### TC-010: Preview with System Prompt Only

**Related UC**: UC-002 (§4.3.2)

| Step | Action                                             | Expected Result                                     |
| ---- | -------------------------------------------------- | ----------------------------------------------------- |
| 1    | Create chat with system prompt only (manual path)  | Chat with 1 system message, chat loop entered       |
| 2    | Type "/menu"                                       | `Возврат в меню...`, Main Menu displayed            |
| 3    | Select option 2 (Select Chat)                      | Chat list displayed                                 |
| 4    | Verify preview                                     | Shows `(нет сообщений)` (system messages are not visible) |
| 5    | Verify count                                       | Shows `Сообщений: 0`                                |

---

### TC-011: Preview with User Message

**Related UC**: UC-002 (§4.3.2)

| Step | Action                     | Expected Result              |
| ---- | -------------------------- | ---------------------------- |
| 1    | Create chat                | New chat                     |
| 2    | Send message "Hello world" | Message saved                |
| 3    | Return to menu             | Chat list displayed          |
| 4    | Verify preview             | Shows "Hello world"          |
| 5    | Send 60-char message       | Message saved                |
| 6    | Return to menu             | Preview truncated with "..." |

---

### TC-076: Chat List Selection Out Of Range

**Related UC**: UC-002 A2

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Ensure exactly 2 chats exist, select option 2 (Select Chat)      | Numbered list of 2 chats displayed                                                     |
| 2    | Enter "0"                                                        | `Введите число от 1 до 2` displayed; selection re-prompted                             |
| 3    | Enter "3" (greater than count)                                   | Same message; selection re-prompted again                                              |
| 4    | Enter "1"                                                        | Chat loaded, header displayed, chat loop entered                                        |

---

### TC-077: Chat List Non-Numeric Selection

**Related UC**: UC-002 A3

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Ensure at least one chat exists, select option 2                 | Chat list displayed                                                                    |
| 2    | Enter "abc"                                                      | `Введите корректное число` displayed; selection re-prompted                            |
| 3    | Enter "2.5" (parsed with int())                                  | Same message — falls into the non-integer flow (UC-002 A3 note); re-prompted            |
| 4    | Enter a valid number                                             | Chat selected, chat loop entered                                                        |

---

### TC-012: Return to Chat Without Active Chat

**Related UC**: UC-003 A1

| Step | Action            | Expected Result              |
| ---- | ----------------- | ---------------------------- |
| 1    | Start application | Main Menu                    |
| 2    | Verify option 5   | Shows "Вернуться в чат (нет активного чата)" |
| 3    | Select option 5   | `[WARN] Нет активного чата. Выберите или создайте чат.` displayed |
| 4    | Verify state      | Remains in Main Menu         |

---

### TC-013: Return to Chat With Active Chat

**Related UC**: UC-003

| Step | Action                | Expected Result                 |
| ---- | --------------------- | ------------------------------- |
| 1    | Create or select chat | Chat loop entered               |
| 2    | Type "/menu"          | Main Menu displayed             |
| 3    | Verify option 5       | Shows "Вернуться в чат: {name}" |
| 4    | Select option 5       | `[OK] Возврат в чат: {name}` (§4.2.2), chat loop entered |
| 5    | Verify context        | Same chat, history intact       |

---

### TC-014: Send Multiple Messages

**Related UC**: UC-004

| Step | Action           | Expected Result           |
| ---- | ---------------- | ------------------------- |
| 1    | Enter chat       | Prompt displayed          |
| 2    | Send "Message 1" | Agent responds            |
| 3    | Send "Message 2" | Agent responds            |
| 4    | Send "Message 3" | Agent responds            |
| 5    | Return to menu   | Preview shows "Message 3" |
| 6    | Re-enter chat    | All 3 exchanges visible   |

---

### TC-015: Empty And Whitespace-Only Message Handling

**Related UC**: UC-004 A1, UC-004 A3

| Step | Action                          | Expected Result                              |
| ---- | ------------------------------- | -------------------------------------------- |
| 1    | Enter chat                      | Prompt displayed                             |
| 2    | Press Enter (empty)             | No send, re-prompt (UC-004 A1)               |
| 3    | Press Enter again               | No send, re-prompt                           |
| 4    | Enter "   " (spaces only)       | No send, re-prompt (UC-004 A3)               |
| 5    | Send valid message              | Normal flow resumes                          |

---

### TC-078: Token Statistics Lines After Response

**Related UC**: UC-004 (steps 4–11)

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Enter chat, send a message                                      | `[AGENT] печатает...` shown while processing, cleared on response                       |
| 2    | Verify response display                                         | `[AGENT]: {response}` printed; prompt re-displayed afterwards                            |
| 3    | Verify token line                                               | `  [Токены: prompt: {p}, completion: {c}]` displayed when usage reported                 |
| 4    | Verify context fill line                                        | `  [Заполненность контекста: {prompt_tokens}/{context_window_size} ({percent:.1f}%)]` displayed when prompt_tokens is not None |
| 5    | Verify history                                                  | Both user and assistant messages saved; chat preview updated with last message          |

---

### TC-079: Context Window Exceeded Error

**Related UC**: UC-004 A4

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Fill chat history until the backend raises `ContextWindowExceededError` | "печатает..." line cleared                                              |
| 2    | Verify error output                                             | `[ERROR] {message}` followed by `Необходимо очистить историю сообщений или создать новый чат.` |
| 3    | Verify navigation                                               | Chat loop exited, Main Menu displayed                                                   |
| 4    | Select option 5 (Return to Chat)                                | The same chat is still active and reachable (chat remains active)                        |

---

### TC-080: Backend Error During Message Exchange

**Related UC**: UC-004 A5

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Arrange the backend to raise an arbitrary exception on send     | Chat loop entered                                                                       |
| 2    | Send any message                                                | `[ERROR] Ошибка: {message}` displayed                                                    |
| 3    | Verify navigation                                               | Chat loop exited, Main Menu displayed                                                   |

---

### TC-081: Keyboard Interrupt During Exchange

**Related UC**: UC-004 A5

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Enter chat loop                                                 | Prompt displayed                                                                        |
| 2    | Send Ctrl+C at the input prompt (or during processing)          | `Прервано пользователем.` displayed                                                      |
| 3    | Verify navigation                                               | Chat loop exited, Main Menu displayed; chat remains active                               |

---

### TC-082: Long Response Wrapping

**Related UC**: UC-004 A7

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Request a response longer than the terminal width               | Agent returns a long response                                                            |
| 2    | Verify display                                                  | Text wraps appropriately; no lines broken/garbled                                       |

---

### TC-083: Reasoning Display Prompt

**Related UC**: UC-004 A8

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Configure reasoning effort (e.g. "low"), send a message         | Response carries reasoning content                                                      |
| 2    | Verify extra prompt                                             | `Показать рассуждения модели? (y/n):` displayed after token lines                        |
| 3    | Enter "y"                                                       | Indented `[Reasoning]:` block printed                                                    |
| 4    | Repeat exchange, enter "n"                                      | No reasoning block printed; back to prompt                                               |

---

### TC-016: View Settings

**Related UC**: UC-005 (steps 1–4, 11), UC-005 A1

| Step | Action                              | Expected Result                   |
| ---- | ----------------------------------- | --------------------------------- |
| 1    | Enter chat with configured settings | Prompt displayed                  |
| 2    | Type "/settings"                    | `--- ТЕКУЩИЕ НАСТРОЙКИ ---` block displayed, then prompt `Изменить настройки? (y/n):` |
| 3    | Verify format                       | All 6 parameters shown: Модель, Температура, Top P, Top K, Reasoning Effort, Размер контекстного окна (§4.6.1) |
| 4    | Verify disabled display             | Shows "отключена"/"отключен"/"отключено" for None values |
| 5    | Enter "n" at change prompt          | Back to chat prompt, no changes (UC-005 A1) |

---

### TC-017: Change Settings With Empty Inputs Disables Parameters

**Related UC**: UC-005 (steps 6–9, §4.6.2)

| Step | Action                                                  | Expected Result                                             |
| ---- | ------------------------------------------------------- | ------------------------------------------------------------- |
| 1    | Type "/settings", enter "y"                             | Header `--- НАСТРОЙКИ ДЛЯ '{chat_name}' ---`, all prompts re-displayed sequentially |
| 2    | Enter new temperature "1.0"                             | Value applied                                                |
| 3    | Press Enter at Top P prompt                             | top_p = None (empty input disables the parameter; there is no "keep current value" semantics) |
| 4    | Press Enter at remaining prompts, finish flow           | `[OK] Настройки обновлены!` + refreshed `--- ТЕКУЩИЕ НАСТРОЙКИ ---` block |
| 5    | Verify update                                           | Temperature changed; Top P and other skipped parameters disabled (None), not preserved |

---

### TC-018: Menu Navigation from Chat

**Related UC**: UC-006

| Step | Action                  | Expected Result              |
| ---- | ----------------------- | ---------------------------- |
| 1    | Enter chat              | Chat loop                    |
| 2    | Type "/menu"            | `Возврат в меню...`, memory saved via `save_agent_memory`, Main Menu displayed |
| 3    | Verify chat preserved   | Chat still exists in storage |
| 4    | Select option 5 (Return to Chat) | Same chat reloaded        |

---

### TC-019: Stop Command When Idle

**Related UC**: UC-007

| Step | Action                       | Expected Result                                          |
| ---- | ---------------------------- | ---------------------------------------------------------- |
| 1    | Enter chat                   | Prompt displayed                                         |
| 2    | Type "/stop" (no generation) | `[INFO] Генерация не активна.` displayed                 |
| 3    | Verify state                 | Chat loop exits, Main Menu displayed (UC-007 step 3)     |

---

### TC-121: Help Command

**Related UC**: UC-008

| Step | Action         | Expected Result        |
| ---- | -------------- | ---------------------- |
| 1    | Enter chat     | Prompt displayed       |
| 2    | Type "/help"   | Command list displayed |
| 3    | Verify content | All 12 commands listed in the exact `HELP_COMMANDS` order (§4.5.3 `/help`) |
| 4    | Verify return  | Back to prompt         |

---

### TC-021: Unknown Command Handling

**Related UC**: UC-004 A2

| Step | Action                  | Expected Result               |
| ---- | ----------------------- | ----------------------------- |
| 1    | Enter chat              | Prompt displayed              |
| 2    | Type "/unknown"         | Treated as a regular message: sent to the agent (UC-004 A2), `[AGENT] печатает...` then `[AGENT]: {response}` |
| 3    | Verify state            | Back to prompt                |

---

### TC-022: System Prompt in History

**Related UC**: UC-001 (steps 6–7), §4.4.2

| Step | Action                         | Expected Result            |
| ---- | ------------------------------ | -------------------------- |
| 1    | Create chat with system prompt | Prompt entered             |
| 2    | Verify history                 | System message present     |
| 3    | Check role                     | Role = "system"            |
| 4    | Check display                  | NOT displayed in the chat header (`[SYSTEM]` prefix does not exist; only `[USER]`/`[AGENT]` are printed, system messages are hidden) |

---

### TC-023: Special Characters in Input

**Related UC**: UC-001 (steps 5, 7), UC-004 (main success scenario)

| Step | Action                             | Expected Result             |
| ---- | ---------------------------------- | --------------------------- |
| 1    | Create chat with name "Тест @#$%"  | Name saved correctly        |
| 2    | Send message with emoji "Hello 👋" | Message saved               |
| 3    | Verify encoding                    | UTF-8 preserved             |
| 4    | Verify display                     | Characters render correctly |

---

### TC-024: Long Chat Name Handling

**Related UC**: UC-001 (step 5, §4.4.1)

| Step | Action              | Expected Result       |
| ---- | ------------------- | --------------------- |
| 1    | Enter 150-char name | Accepted without truncation (CLI performs no length validation) |
| 2    | Verify storage      | Full 150-char name saved (DB column limit is 255 chars, see §4.4.1)   |
| 3    | Verify display      | Full name shown in chat list and header  |

---

### TC-122: Concurrent Chat Operations

**Related UC**: UC-002 (main success scenario), UC-003 (main success scenario)

| Step | Action          | Expected Result  |
| ---- | --------------- | ---------------- |
| 1    | Create Chat A   | Active = A       |
| 2    | Type "/menu"    | Main Menu        |
| 3    | Select option 2, choose Chat B   | Active = B       |
| 4    | Type "/menu"    | Main Menu        |
| 5    | Select option 5 (Return to Chat)  | Returns to B     |
| 6    | Verify A intact | Chat A unchanged |

---

### TC-026: View Summary With Summarization

**Related UC**: UC-009

| Step | Action                       | Expected Result                    |
| ---- | ---------------------------- | ---------------------------------- |
| 1    | Open chat with summarization | Chat active                        |
| 2    | Type "/summary"              | Summary text displayed             |
| 3    | Verify summary content       | Matches strategy's current summary |
| 4    | Verify no state changes      | Chat remains active                |

---

### TC-027: View Summary Without Summarization

**Related UC**: UC-009 A1

| Step | Action                         | Expected Result                                     |
| ---- | ------------------------------ | --------------------------------------------------- |
| 1    | Open new chat (no summary yet) | Chat active                                         |
| 2    | Type "/summary"                | `[INFO] Саммари пока недоступно.` displayed          |
| 3    | Verify no state changes        | Chat remains active                                 |

---

### TC-028: View Chat Info With Token Statistics

**Related UC**: UC-010

| Step | Action                  | Expected Result                        |
| ---- | ----------------------- | -------------------------------------- |
| 1    | Open chat with messages | Chat active                            |
| 2    | Type "/info"            | Header `--- ИНФОРМАЦИЯ О ЧАТЕ ---` displayed |
| 3    | Verify token statistics | `Prompt токены` and `Completion токены` shown       |
| 4    | Verify strategy type    | Strategy name displayed                |
| 5    | Verify no state changes | Chat remains active                    |

---

### TC-029: Create Branch And Switch

**Related UC**: UC-011

| Step | Action                                     | Expected Result                                   |
| ---- | ------------------------------------------ | ------------------------------------------------- |
| 1    | Open chat with messages                    | Chat active                                       |
| 2    | Type "/branch"                             | Header `--- СОЗДАНИЕ ВЕТКИ ОТ '{name}' ---` + name prompt |
| 3    | Press Enter (accept auto-name)             | Branch created with name `{name} (branch {timestamp})` |
| 4    | Prompt: "Продолжить в новой ветке? (y/n):" | Displayed (`current_agent` already switched to branch) |
| 5    | Enter "y"                                  | Chat loop entered for the branch chat             |
| 6    | Verify new chat                            | Has same messages, settings, strategy as original |
| 7    | Verify original chat                       | Unchanged                                         |

---

### TC-030: Create Branch And Stay

**Related UC**: UC-011 A1

| Step | Action                                     | Expected Result                                        |
| ---- | ------------------------------------------ | ------------------------------------------------------ |
| 1    | Open chat with messages                    | Chat active                                            |
| 2    | Type "/branch"                             | Branch name prompt                                     |
| 3    | Press Enter                                | Branch created                                         |
| 4    | Prompt: "Продолжить в новой ветке? (y/n):" | Displayed                                              |
| 5    | Enter "n"                                  | `Ветка создана. Вы можете вернуться к ней через меню.` |
| 6    | Verify branch created                      | New chat exists in storage                             |
| 7    | Verify CLI state                           | `current_agent` points to the branch (UC-011 A1 note)  |

---

### TC-031: Create Branch With Custom Name

**Related UC**: UC-011 A2

| Step | Action                   | Expected Result                  |
| ---- | ------------------------ | -------------------------------- |
| 1    | Open chat                | Chat active                      |
| 2    | Type "/branch"           | Branch name prompt               |
| 3    | Enter "My Custom Branch" | Branch created with that name    |
| 4    | Verify branch name       | "My Custom Branch" used          |

---

### TC-032: Settings Change With Confirmation

**Related UC**: UC-005 (steps 5–10)

| Step | Action                               | Expected Result                                                     |
| ---- | ------------------------------------ | ---------------------------------------------------------------------- |
| 1    | Type "/settings"                     | `--- ТЕКУЩИЕ НАСТРОЙКИ ---` block displayed                         |
| 2    | Prompt: `Изменить настройки? (y/n):` | Displayed                                                           |
| 3    | Enter "y"                            | Header `--- НАСТРОЙКИ ДЛЯ '{chat_name}' ---`, all settings prompts shown (like creation) |
| 4    | Enter valid values at ALL prompts (model, temperature, top_p, top_k, reasoning effort, context window) | Values applied; nothing skipped — no "keep as-is" semantics exists (§4.6.2) |
| 5    | Verify update                        | `[OK] Настройки обновлены!` + refreshed `--- ТЕКУЩИЕ НАСТРОЙКИ ---` block |
| 6    | Verify return                        | Back to chat prompt                                                 |

---

### TC-033: Settings Change Cancelled

**Related UC**: UC-005 A1

| Step | Action                               | Expected Result                     |
| ---- | ------------------------------------ | ----------------------------------- |
| 1    | Type "/settings"                     | Current settings displayed          |
| 2    | Prompt: "Изменить настройки? (y/n):" | Displayed                           |
| 3    | Enter "n"                            | Return to chat loop without changes |
| 4    | Verify no changes                    | Settings remain unchanged           |

---

### TC-084: Decline Settings Change With Empty Or Other Input

**Related UC**: UC-005 A1

| Step | Action                               | Expected Result                     |
| ---- | ------------------------------------ | ----------------------------------- |
| 1    | Type "/settings", press Enter at `Изменить настройки? (y/n):` | No settings prompts shown; back to chat prompt |
| 2    | Type "/settings", enter "maybe"      | Treated as decline (any input other than "y"); no changes made |
| 3    | Verify state                         | Settings unchanged, chat loop continues |

---

### TC-085: Invalid Input During Settings Re-Prompting

**Related UC**: UC-005 A2

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Type "/settings", enter "y", reach temperature prompt            | All settings prompts re-displayed like during creation                                  |
| 2    | Enter "abc" at temperature                                      | Warning `Некорректное число. Используется значение по умолчанию (отключено).`; parameter disabled; flow continues (UC-001 A7 semantics) |
| 3    | Enter "-1" at Top P                                             | Out-of-range warning; top_p = None; flow continues                                      |
| 4    | Enter negative value at Top K                                   | `Top K должен быть >= 0`; Top K re-prompted (UC-001 A8 semantics)                       |
| 5    | Complete the flow                                               | `[OK] Настройки обновлены!` with the resulting values                                    |

---

### TC-086: KeyboardInterrupt During Settings Flow

**Related UC**: UC-005 A3

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Type "/settings", enter "y"                                     | Settings prompts displayed                                                              |
| 2    | Press Ctrl+C mid-flow (or feed end of input — EOFError)         | `Прервано пользователем.` displayed                                                     |
| 3    | Verify navigation                                               | Chat loop exited, Main Menu displayed                                                    |

---

### TC-087: Backend Error While Applying Settings

**Related UC**: UC-005 A4

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Arrange the `change_settings` use case to raise an exception    | Chat loop entered                                                                        |
| 2    | Type "/settings", enter "y", complete all prompts               | `[ERROR] Ошибка: {message}` displayed                                                    |
| 3    | Verify navigation                                               | Chat loop exited, Main Menu displayed                                                    |

---

### TC-034: Stop Command Keeps Active Chat

**Related UC**: UC-007 (postconditions)

| Step | Action                        | Expected Result                                        |
| ---- | ----------------------------- | ------------------------------------------------------ |
| 1    | In chat loop, type "/stop"    | `[INFO] Генерация не активна.` displayed               |
| 2    | Verify navigation             | Chat loop exits, Main Menu displayed                   |
| 3    | Verify active chat            | Option 5 still shows "Вернуться в чат: {name}"         |

---

### TC-035: Stop Command Preserves Chat State

**Related UC**: UC-007 (postconditions), UC-003

| Step | Action                        | Expected Result                                          |
| ---- | ----------------------------- | -------------------------------------------------------- |
| 1    | Send a message in chat        | Exchange saved to history                                |
| 2    | Type "/stop" at any moment    | `[INFO] Генерация не активна.` displayed                 |
| 3    | Verify return to menu         | Main Menu displayed                                      |
| 4    | Select option 5 (Return to Chat) | Same chat reloaded with the exchange intact          |

---

### TC-036: SlidingWindowStrategy Creation

**Related UC**: UC-001 (step 19, §4.4.9)

| Step | Action                          | Expected Result                         |
| ---- | ------------------------------- | --------------------------------------- |
| 1    | Create new chat                 | Strategy selection prompt               |
| 2    | Select option 4 (SlidingWindow) | window_size prompt with default 10      |
| 3    | Press Enter (accept default)    | Chat created with SlidingWindowStrategy |
| 4    | Verify strategy                 | Strategy type = "SlidingWindowStrategy" |
| 5    | Verify window_size              | window_size = 10                        |

---

### TC-037: SlidingWindowStrategy With Custom Window

**Related UC**: UC-001 (step 19, §4.4.9)

| Step | Action                          | Expected Result                         |
| ---- | ------------------------------- | --------------------------------------- |
| 1    | Create new chat                 | Strategy selection prompt               |
| 2    | Select option 4 (SlidingWindow) | window_size prompt                      |
| 3    | Enter "20"                      | Chat created with window_size = 20      |
| 4    | Verify strategy                 | Strategy type = "SlidingWindowStrategy" |
| 5    | Verify window_size              | window_size = 20                        |

---

### TC-038: SummarizationStrategy Creation

**Related UC**: UC-001 (step 19, §4.4.9)

| Step | Action                          | Expected Result                              |
| ---- | ------------------------------- | -------------------------------------------- |
| 1    | Create new chat                 | Strategy selection prompt                    |
| 2    | Select option 2 (Summarization) | non_compressible_count prompt with default 2 |
| 3    | Press Enter (accept default)    | buffer_size prompt with default 3            |
| 4    | Press Enter (accept default)    | Chat created with SummarizationStrategy      |
| 5    | Verify strategy                 | Strategy type = "SummarizationStrategy"      |
| 6    | Verify parameters               | non_compressible_count = 2, buffer_size = 3  |

---

### TC-039: SummarizationStrategy With Custom Parameters

**Related UC**: UC-001 (step 19, §4.4.9)

| Step | Action                          | Expected Result                             |
| ---- | ------------------------------- | ------------------------------------------- |
| 1    | Create new chat                 | Strategy selection prompt                   |
| 2    | Select option 2 (Summarization) | non_compressible_count prompt               |
| 3    | Enter "5"                       | buffer_size prompt                          |
| 4    | Enter "4"                       | Chat created with custom parameters         |
| 5    | Verify strategy                 | Strategy type = "SummarizationStrategy"     |
| 6    | Verify parameters               | non_compressible_count = 5, buffer_size = 4 |

---

### TC-040: KeyValueMemoryStrategy Creation

**Related UC**: UC-001 (step 19, §4.4.9)

| Step | Action                           | Expected Result                              |
| ---- | -------------------------------- | -------------------------------------------- |
| 1    | Create new chat                  | Strategy selection prompt                    |
| 2    | Select option 3 (KeyValueMemory) | non_compressible_count prompt with default 2 |
| 3    | Press Enter (accept default)     | buffer_size prompt with default 3            |
| 4    | Press Enter (accept default)     | Chat created with KeyValueMemoryStrategy     |
| 5    | Verify strategy                  | Strategy type = "KeyValueMemoryStrategy"     |
| 6    | Verify parameters                | non_compressible_count = 2, buffer_size = 3  |

---

### TC-041: KeyValueMemoryStrategy With Custom Parameters

**Related UC**: UC-001 (step 19, §4.4.9)

| Step | Action                           | Expected Result                             |
| ---- | -------------------------------- | ------------------------------------------- |
| 1    | Create new chat                  | Strategy selection prompt                   |
| 2    | Select option 3 (KeyValueMemory) | non_compressible_count prompt               |
| 3    | Enter "3"                        | buffer_size prompt                          |
| 4    | Enter "5"                        | Chat created with custom parameters         |
| 5    | Verify strategy                  | Strategy type = "KeyValueMemoryStrategy"    |
| 6    | Verify parameters                | non_compressible_count = 3, buffer_size = 5 |

---

### TC-042: DefaultStrategy Creation

**Related UC**: UC-001 (step 19, §4.4.9)

| Step | Action                     | Expected Result                                                       |
| ---- | -------------------------- | --------------------------------------------------------------------- |
| 1    | Create new chat            | Strategy selection prompt                                             |
| 2    | Select option 1 (Default)  | Task profile selection displayed without extra parameter prompts      |
| 3    | Verify strategy            | Strategy type = "DefaultStrategy"                                     |
| 4    | Verify no extra parameters | non_compressible_count = null, buffer_size = null, window_size = null |

---

### TC-043: View Info For Different Strategies

**Related UC**: UC-010 (steps 3–5)

| Step | Action                                | Expected Result                                       |
| ---- | ------------------------------------- | ----------------------------------------------------- |
| 1    | Open chat with DefaultStrategy        | Type /info, verify strategy displayed                 |
| 2    | Open chat with SummarizationStrategy  | Type /info, verify strategy and params displayed      |
| 3    | Open chat with KeyValueMemoryStrategy | Type /info, verify strategy and params displayed      |
| 4    | Open chat with SlidingWindowStrategy  | Type /info, verify strategy and window_size displayed |

---

### TC-044: Branch Preserves Strategy Type

**Related UC**: UC-011 (step 5)

| Step | Action                               | Expected Result                                  |
| ---- | ------------------------------------ | ------------------------------------------------ |
| 1    | Open chat with SummarizationStrategy | Type /branch, create branch                      |
| 2    | Verify new branch                    | Strategy type = "SummarizationStrategy"          |
| 3    | Verify parameters copied             | non_compressible_count and buffer_size preserved |

---

### TC-045: Branch Preserves SlidingWindow Configuration

**Related UC**: UC-011 (step 5)

| Step | Action                                                | Expected Result                         |
| ---- | ----------------------------------------------------- | --------------------------------------- |
| 1    | Open chat with SlidingWindowStrategy (window_size=15) | Type /branch, create branch             |
| 2    | Verify new branch                                     | Strategy type = "SlidingWindowStrategy" |
| 3    | Verify window_size copied                             | window_size = 15 in new branch          |

---

### TC-088: Branch Creation Backend Error

**Related UC**: UC-011 A3

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Arrange the `create_branch` use case to raise an exception       | Chat loop entered                                                                        |
| 2    | Type "/branch", provide a name                                    | `[ERROR] Ошибка при создании ветки: {e}` displayed                                       |
| 3    | Verify state                                                    | Back to chat prompt; no switch happened — `current_agent` still points to original chat |

---

### TC-046: View Global Memory from Main Menu (No Chat Required)

**Related UC**: UC-012

| Step | Action                                    | Expected Result                                       |
| ---- | ----------------------------------------- | ----------------------------------------------------- |
| 1    | Start application, stay in Main Menu      | No active chat selected                               |
| 2    | Select option 4 (Global Memory) from menu | System displays global memory view                    |
| 3    | Verify header displayed                   | `--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---` is shown                  |
| 4    | Verify facts or empty state               | Either numbered facts list OR `(память пуста)`        |
| 5    | Verify separator line                     | 40 dashes are displayed                               |
| 6    | Verify return to menu                     | Main Menu is displayed again                          |

---

### TC-047: View Global Memory - Empty State

**Related UC**: UC-012 A1

| Step | Action                                    | Expected Result                                       |
| ---- | ----------------------------------------- | ----------------------------------------------------- |
| 1    | Start application                         | Application running                                   |
| 2    | Ensure no chats exist and memory is empty | Repository returns empty list                         |
| 3    | Select option 4 (Global Memory) from menu | System displays global memory view                    |
| 4    | Verify header displayed                   | `--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---` is shown                  |
| 5    | Verify empty state message                | `(память пуста)` is displayed                         |
| 6    | Verify separator line                     | 40 dashes are displayed                               |
| 7    | Verify return to menu                     | Main Menu is displayed again                          |

---

### TC-048: View Global Memory - With Facts (End-to-End Flow)

**Related UC**: UC-012 (steps 4–7), UC-006

**Purpose**: Verify that memory is populated during chat interaction, saved when exiting to menu, and correctly displayed from the repository.

| Step | Action                                           | Expected Result                                          |
| ---- | ------------------------------------------------ | -------------------------------------------------------- |
| 1    | Start application                                | Application running                                      |
| 2    | Select option 1 (New Chat) from menu             | Chat creation workflow starts                            |
| 3    | Complete chat creation with any settings         | Chat created, entered chat loop                          |
| 4    | Send a message to the agent                      | Agent responds (Mock provider generates test facts)      |
| 5    | Type `/menu` command to exit to main menu        | System saves agent state and global memory               |
| 6    | Select option 4 (Global Memory) from menu        | System retrieves facts from FileGlobalMemoryRepository   |
| 7    | Verify header displayed                          | `--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---` is shown                     |
| 8    | Verify facts are displayed as numbered list      | At least 1-2 test facts shown as `{i}. {fact}`           |
| 9    | Verify separator line                            | 40 dashes are displayed                                  |
| 10   | Verify return to menu                            | Main Menu is displayed again                             |

---

### TC-049: Create Task Profile with Valid Data

**Related UC**: UC-014

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From Main Menu, select option 3 (Task Profiles) | Task Profiles menu displayed                 |
| 2    | Select option 1 (Create new profile)          | Name prompt `Введите название профиля:` displayed |
| 3    | Enter "Project Alpha"                         | Description prompt `Введите описание задачи:` displayed |
| 4    | Enter "Development of Project Alpha system"   | Preferences prompt `Введите предпочтения/инструкции (Enter для пропуска):` displayed |
| 5    | Enter preferences text                        | Invariants block displayed (`--- ИНВАРИАНТЫ (строгие правила/ограничения) ---`, prompt `>` per line) |
| 6    | Enter one invariant, then press Enter (empty line) | Creation proceeds; success message `[OK] Профиль задачи '{name}' создан!` + ID + Дата создания + `Инвариантов: 1` |
| 7    | Verify profile saved                          | Profile exists in repository with empty facts, entered preferences and 1 invariant |
| 8    | Verify return                                 | Control returns to the Task Profiles menu    |

---

### TC-050: Create Task Profile - Empty Name Validation

**Related UC**: UC-014 A1

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From Task Profiles menu, select Create        | Name prompt displayed                        |
| 2    | Press Enter (empty input)                     | `[ERROR] Название профиля не может быть пустым.` + re-prompt |
| 3    | Enter valid name                              | Proceed to description prompt                |

---

### TC-051: Create Task Profile - Long Name Accepted

**Related UC**: UC-014 (step 3)

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From Task Profiles menu, select Create        | Name prompt displayed                        |
| 2    | Enter 150-character string                    | Accepted without error or truncation warning |
| 3    | Verify saved name                             | Full 150-character name stored and displayed |

---

### TC-052: Create Task Profile - Empty Description Validation

**Related UC**: UC-014 A2

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From Task Profiles menu, select Create        | Name prompt → enter valid name               |
| 2    | Description prompt displayed                  | Press Enter (empty input)                    |
| 3    | Verify error                                  | `[ERROR] Описание задачи не может быть пустым.` + re-prompt |

---

### TC-089: Create Task Profile - No Invariants Omits Count Line

**Related UC**: UC-014 A4

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Reach the invariants block during profile creation | Header `--- ИНВАРИАНТЫ (строгие правила/ограничения) ---` and prompt `>` displayed |
| 2    | Press Enter immediately (empty first line)    | Profile created with an empty invariants list |
| 3    | Verify success message                        | `[OK] Профиль задачи '{name}' создан!` + ID + Дата создания; the `Инвариантов:` line is omitted |

---

### TC-053: View Task Profiles List - Empty State

**Related UC**: UC-013 A1

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From Main Menu, select option 3 (Task Profiles) | Task Profiles menu displayed (options 1-3)   |
| 2    | Select option 2 (View profiles list)          | `Нет доступных профилей задач.` + separator displayed |
| 3    | Verify return                                 | Control returns to the Task Profiles menu    |

---

### TC-054: View Task Profiles List - Multiple Profiles

**Related UC**: UC-013 (steps 5–7)

**Precondition**: At least 2 task profiles exist in repository

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From Main Menu, select option 3, then option 2 | `--- СПИСОК ПРОФИЛЕЙ ЗАДАЧ ---` header displayed |
| 2    | Verify profile block format                   | Each profile shows: index+name, ID, Дата создания (`%Y-%m-%d %H:%M`), Фактов в памяти, Инвариантов, Описание (50 chars + `...` if longer) |
| 3    | Verify action options                         | `Действия:` with 4 options (View Memory, Manage Invariants, Delete, Back to list) and prompt `Выберите действие (1-4):` |

---

### TC-055: View Task Profile Memory - With Facts

**Related UC**: UC-015

**Precondition**: Task profile exists with at least 2 facts in memory

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 1 (View memory) | Profile selection prompt `Выберите профиль (1-{n}):` displayed |
| 2    | Select profile by index                       | `--- ИНФОРМАЦИЯ О ПРОФИЛЕ ЗАДАЧИ ---`: ID, Название, Описание, Дата создания (+ Предпочтения if non-empty) |
| 3    | Verify memory section                         | `--- ПАМЯТЬ ПРОФИЛЯ ---` header + numbered facts; `--- ИНВАРИАНТЫ ---` section shown |
| 4    | Verify return                                 | Control returns to the Task Profiles menu    |

---

### TC-056: View Task Profile Memory - Empty State

**Related UC**: UC-015 A2

**Precondition**: Task profile exists with empty facts list

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 1   | Select profile                               |
| 2    | Verify memory display                         | `(память пуста)` shown instead of facts (UC-015 A2); `(инварианты не заданы)` if no invariants |
| 3    | Verify return                                 | Return to the Task Profiles menu             |

---

### TC-057: Delete Task Profile - Not Attached

**Related UC**: UC-017 (steps 4–6)

**Precondition**: Task profile exists, not attached to any agents

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 3 (Delete) | Profile selection prompt `Выберите профиль для удаления (1-{n}):` displayed |
| 2    | Select profile by index                       | Confirmation prompt: `Вы уверены, что хотите удалить профиль '{name}'? (y/n):` |
| 3    | Enter 'y'                                     | `[OK] Профиль '{name}' успешно удалён.`      |
| 4    | Verify deletion                               | Profile no longer in repository              |
| 5    | Verify return                                 | Control returns to the Task Profiles menu    |

---

### TC-058: Delete Task Profile - Attached to Agents

**Related UC**: UC-017 A3

**Precondition**: Task profile exists, attached to 2 agents

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 3   | Select profile                               |
| 2    | Verify block message                          | `[WARN] Невозможно удалить профиль '{name}': он привязан к одному или нескольким агентам.` + `Сначала удалите или пересоздайте агентов, использующих этот профиль.` — NO confirmation prompt |
| 3    | Verify profile not deleted                    | Profile still in repository                  |
| 4    | Verify agents unchanged                       | Agents keep their task_profile_id link       |

---

### TC-059: Delete Task Profile - Cancelled

**Related UC**: UC-017 A2

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 3   | Select profile (profile must be unlinked)    |
| 2    | Confirmation prompt displayed                 | Enter 'n'                                    |
| 3    | Verify cancellation                           | `[INFO] Удаление отменено.`                  |
| 4    | Verify profile exists                         | Profile still in repository                  |

---

### TC-060: Manage Invariants - Add and Remove

**Related UC**: UC-016

**Precondition**: At least one task profile exists

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 2 (Manage invariants) | Profile selection prompt `Выберите профиль (1-{n}):` displayed |
| 2    | Select profile by index                       | Header `--- ИНВАРИАНТЫ ПРОФИЛЯ: {name} ---` with numbered invariants (`(инварианты не заданы)` if empty) and actions `1. Добавить инвариант / 2. Удалить инвариант / 3. Назад` |
| 3    | Select action 1, enter invariant text         | `[OK] Инвариант добавлен!`, invariants list redisplayed with the new entry |
| 4    | Select action 2, enter a valid number         | `[OK] Инвариант удалён!`, list redisplayed   |
| 5    | Select action 2, enter an unknown number      | `[WARN] Некорректный номер.` (UC-016 A2)     |
| 6    | Select action 3 (Назад)                       | Control returns to the Task Profiles menu    |

---

### TC-090: Manage Invariants - Repository ValueError On Add

**Related UC**: UC-016 A3

**Precondition**: Profile with an existing invariant "Rule A"

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Open invariants submenu for the profile       | Invariant list displayed                     |
| 2    | Select action 1, enter duplicate/invalid text causing repository `ValueError` | `[ERROR] {e}` displayed; nothing added, list redisplayed (UC-016 A3) |

---

### TC-112: Manage Invariants - Empty Invariant Text

**Related UC**: UC-016 A1

**Precondition**: At least one task profile exists

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Open invariants management submenu for the profile | Header `--- ИНВАРИАНТЫ ПРОФИЛЯ: {name} ---` with actions displayed |
| 2    | Select action 1, press Enter without entering text | `[WARN] Инвариант не может быть пустым.` displayed (UC-016 A1) |
| 3    | Verify the invariants list                    | Nothing added; list redisplayed unchanged (invariant count unchanged in storage) |
| 4    | Select action 1 again, enter valid text       | `[OK] Инвариант добавлен!`; list redisplayed with the new entry |

---

### TC-113: Manage Invariants - Invalid Action Choice Re-Prompts

**Related UC**: UC-016 A4

**Precondition**: At least one task profile exists

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Open invariants management submenu for the profile | Invariants list and prompt `Выберите действие (1-3):` displayed |
| 2    | Enter "9" (outside 1–3)                       | `[WARN] Неверный выбор.`; invariants list and action prompt re-displayed (UC-016 A4) |
| 3    | Enter non-numeric input (e.g. "abc")          | Same warning; list and action prompt re-displayed (UC-016 A4) |
| 4    | Enter a valid action ("3" — Назад)            | Control returns to the Task Profiles menu    |

---

### TC-114: Manage Invariants - Remove With Empty List

**Related UC**: UC-016 A5

**Precondition**: At least one task profile with no invariants (`(инварианты не заданы)`)

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Open invariants management submenu for the empty profile | `(инварианты не заданы)` and actions displayed |
| 2    | Select action 2 (Удалить инвариант)           | `[WARN] Нет инвариантов для удаления.` displayed; removal number prompt NOT shown (UC-016 A5) |
| 3    | Verify the display                            | Invariants list and action prompt re-displayed |
| 4    | Select action 1, add an invariant, then select action 2 | Removal prompt `Выберите номер инварианта для удаления (1-{n}):` is now displayed |

---

### TC-091: Profiles Menu And Submenu Invalid Choices Re-Prompt

**Related UC**: UC-013 A2, UC-013 A3, UC-013 A4

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From Main Menu select option 3, enter "9" at the Task Profiles menu prompt | `[WARN] Неверный выбор, попробуйте снова.`; menu re-displayed (UC-013 A2) |
| 2    | Open profiles list, enter "99" at `Выберите действие (1-4):` | Same warning; action prompt re-displayed (UC-013 A4) |
| 3    | Choose action 1, enter out-of-range index     | `Введите число от 1 до {n}`; profile selection re-prompted (UC-013 A3) |
| 4    | Enter "abc" as profile index                  | `Введите корректное число`; re-prompted (UC-013 A3) |
| 5    | Enter valid index                             | Requested action proceeds                     |

---

### TC-092: View Task Profile Memory - Profile Not Found

**Related UC**: UC-015 A3

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Arrange `get_task_profile_memory` to return None for the selected profile | Action 1 chosen from the profiles list submenu |
| 2    | Verify error                                  | `[ERROR] Профиль не найден.` displayed        |
| 3    | Verify navigation                             | Control returns to the Task Profiles menu     |

---

### TC-093: Delete Task Profile - Invalid Selection Re-Prompts

**Related UC**: UC-017 A1

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 3 (Delete) | Prompt `Выберите профиль для удаления (1-{n}):` displayed |
| 2    | Enter out-of-range number                     | `Введите число от 1 до {n}`; selection re-prompted (UC-017 A1) |
| 3    | Enter "abc"                                   | `Введите корректное число`; selection re-prompted |
| 4    | Enter a valid index                           | Confirmation prompt displayed for the chosen profile |

---

### TC-094: View Task Profile Memory - Invalid Selection Re-Prompts

**Related UC**: UC-015 A1

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 1 (View memory) | Prompt `Выберите профиль (1-{n}):` displayed |
| 2    | Enter out-of-range number                     | `Введите число от 1 до {n}`; selection re-prompted (UC-015 A1) |
| 3    | Enter "abc"                                   | `Введите корректное число`; selection re-prompted (UC-015 A1) |
| 4    | Enter a valid index                           | Profile information and memory are displayed  |

---

### TC-095: Return To Active Chat - Ctrl+C At Menu Prompt

**Related UC**: UC-003 A2

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | In Main Menu press Ctrl+C at `Ваш выбор (1-6):` (or feed end of input — EOFError) | System handles the exception at the menu prompt (UC-003 A2) |
| 2    | Verify exit message                           | `До свидания!` printed                        |
| 3    | Verify termination                            | Application terminates cleanly, no traceback  |

---

### TC-096: Phase Command - Forward Transition PLAN to EXECUTE

**Related UC**: UC-018 (main success scenario)

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Open a newly created chat                     | Header shows `--- ЧАТ: {name} [Фаза: PLAN] ---` (new chats start in PLAN) |
| 2    | Enter `/execute`                              | `[INFO] Фаза изменена: PLAN -> EXECUTE` displayed |
| 3    | Verify header                                 | Updated line `--- ЧАТ: {name} [Фаза: EXECUTE] ---` shown |
| 4    | Enter `/validate`                             | `[INFO] Фаза изменена: EXECUTE -> VALIDATE` (sequential forward transition allowed) |
| 5    | Send a regular message                        | Message processed normally in the new phase; chat loop continues |

---

### TC-097: Phase Command - Forward Skip Rejected

**Related UC**: UC-018 A1

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | In a chat in phase PLAN enter `/validate`     | `[INFO] Нельзя перескочить этап: переход из PLAN сразу в VALIDATE запрещен` (UC-018 A1) |
| 2    | Verify header unchanged                       | `--- ЧАТ: {name} [Фаза: PLAN] ---` displayed after the rejection |
| 3    | From PLAN enter `/report`                     | Same rejection message; phase remains PLAN   |
| 4    | Advance to EXECUTE (`/execute`), then enter `/report` | Rejection message `из EXECUTE сразу в REPORT`; phase remains EXECUTE |

---

### TC-098: Phase Command - Backward Transition Allowed

**Related UC**: UC-018 A2

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Advance the chat phase through `/execute`, `/validate` | Phase is VALIDATE                          |
| 2    | Enter `/plan`                                 | `[INFO] Фаза изменена: VALIDATE -> PLAN` (any backward transition allowed, UC-018 A2) |
| 3    | Verify header                                 | `--- ЧАТ: {name} [Фаза: PLAN] ---`           |
| 4    | From PLAN enter `/execute`, then `/plan` again | Backward transition EXECUTE -> PLAN succeeds |

---

### TC-099: Phase Command - Case Insensitive Matching

**Related UC**: UC-018 A3

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | In phase PLAN enter `/EXECUTE`                | `[INFO] Фаза изменена: PLAN -> EXECUTE` (commands matched case-insensitively, UC-018 A3) |
| 2    | In phase EXECUTE enter `/Validate`            | `[INFO] Фаза изменена: EXECUTE -> VALIDATE`  |
| 3    | Verify header after each step                 | Header reflects the new phase                |

---

### TC-100: Phase Visible In Header And /info

**Related UC**: UC-018 A4

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter `/execute`, then return to menu via `/menu` | Phase changed to EXECUTE before exiting the loop |
| 2    | Return to the chat (option 5)                 | Header replayed as `--- ЧАТ: {name} [Фаза: EXECUTE] ---` (UC-018 A4, §4.5.1) |
| 3    | Enter `/info`                                 | Line `Текущая фаза: EXECUTE` displayed        |

---

### TC-101: MCP Menu - No Servers Connected Yet

**Related UC**: UC-019 (steps 1–2)

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | In a chat with no MCP servers enter `/mcp`    | Header `--- MCP-СЕРВЕРЫ ЧАТА: {chat_name} ---` displayed |
| 2    | Verify empty state                            | `К этому чату ещё не подключено ни одного MCP-сервера.` shown |
| 3    | Verify prompt                                 | `Подключить новые MCP? (y/n):` displayed      |

---

### TC-102: MCP Menu - Decline Connecting New Servers

**Related UC**: UC-019 A1

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter `/mcp`                                  | Connected-servers block displayed            |
| 2    | Enter "n" (or any text other than `y`, or press Enter) at `Подключить новые MCP? (y/n):` | Flow ends immediately after the block (UC-019 A1) |
| 3    | Verify return                                 | Control returns to the chat prompt; no state changes |

---

### TC-103: MCP Menu - Connect Server By Number

**Related UC**: UC-019 (main success scenario, steps 4–11)

**Precondition**: At least one registered MCP server not yet connected to the chat

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter `/mcp`, answer `y`                      | `--- ДОСТУПНЫЕ ДЛЯ ПОДКЛЮЧЕНИЯ MCP ---` lists registry servers not connected to this chat as `{idx}. {title} ({name}) — {description}` |
| 2    | Verify prompt                                 | `Введите номер сервера для подключения (или название, 0 — отмена):` displayed |
| 3    | Enter a valid number                          | `[INFO] Подключаю MCP '{name}'...` displayed  |
| 4    | Wait for connection result                    | `[OK] {message}` from the `connect_mcp` use case (UC-019 step 9) |
| 5    | Enter `/mcp` again                            | The server now listed as `[OK] {title} ({name}) — инструменты: {tool1, tool2}` |

---

### TC-104: MCP Menu - Connect Server By Name

**Related UC**: UC-019 (steps 7–9)

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter `/mcp`, answer `y`                      | Available servers listed                     |
| 2    | Enter a non-numeric server name at the selection prompt | Text treated as a server name (UC-019 step 7); `[INFO] Подключаю MCP '{name}'...` |
| 3    | Wait for connection result                    | `[OK] {message}` on success                   |

---

### TC-105: MCP Menu - All Servers Already Connected

**Related UC**: UC-019 A2

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Connect all registry servers to the chat       | —                                            |
| 2    | Enter `/mcp`, answer `y`                      | `[INFO] Все доступные MCP-серверы уже подключены к этому чату.` displayed (UC-019 A2) |
| 3    | Verify return                                 | Control returns to the chat prompt            |

---

### TC-106: MCP Menu - Cancel Connection

**Related UC**: UC-019 A3

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter `/mcp`, answer `y`                      | Available servers listed                     |
| 2    | Press Enter (empty input) at the selection prompt | `[INFO] Подключение отменено.` displayed (UC-019 A3) |
| 3    | Repeat: reach the server-selection prompt, enter `0` | `[INFO] Подключение отменено.` displayed      |
| 4    | Verify return                                 | Control returns to the chat prompt; server list unchanged |

---

### TC-107: MCP Menu - Numeric Selection Out Of Range

**Related UC**: UC-019 A4

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter `/mcp`, answer `y`                      | Available servers listed (n servers)         |
| 2    | Enter a number outside 1…n (e.g. `99`)        | `[ERROR] Неверный номер сервера.` displayed; flow ends without re-prompt (UC-019 A4) |
| 3    | Verify return                                 | Control returns to the chat prompt; no server connected |

---

### TC-108: MCP Menu - Connection Fails

**Related UC**: UC-019 A5

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter `/mcp`, answer `y`                      | Available servers listed                     |
| 2    | Enter an unknown server name                  | `[INFO] Подключаю MCP '{name}'...` then `[ERROR] {message}` from the failed `connect_mcp` use case (UC-019 A5) |
| 3    | Verify state                                  | The chat's MCP server list is unchanged       |
| 4    | Verify return                                 | Control returns to the chat prompt            |

---

### TC-109: MCP Menu - Offline Server Display

**Related UC**: UC-019 A7

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Arrange a chat-connected MCP server to be unreachable | —                                       |
| 2    | Enter `/mcp`                                  | The server listed as `[OFFLINE] {title} ({name}) — подключение не установлено` instead of `[OK]` (UC-019 A7) |

---

### TC-110: MCP Menu - Ctrl+C During Prompts Does Not Exit Chat

**Related UC**: UC-019 A6

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter `/mcp`, press Ctrl+C (or EOF) at `Подключить новые MCP? (y/n):` | Exception handled locally inside the `/mcp` flow (UC-019 A6) |
| 2    | Verify chat loop                              | Chat loop is NOT exited; control returns to the chat prompt |
| 3    | Repeat: reach the server-selection prompt, press Ctrl+C there | Same behavior — back at the chat prompt |
| 4    | Send a regular message                        | Normal exchange continues                     |

---

### TC-111: Manage Invariants - Removal Failure Message

**Related UC**: UC-016 A2

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Open invariants management with existing invariants, choose action "remove" (UC-016 step 9) | Removal prompt `Выберите номер инварианта для удаления (1-{n}):` displayed |
| 2    | Arrange the repository removal to fail for a syntactically valid number | `[ERROR] Не удалось удалить инвариант.` displayed; the invariant remains in the list (UC-016 A2) |
| 3    | Enter a valid number for a removable invariant | `[OK] Инвариант удалён!`; updated list shown |

---

### TC-061: Create Chat with Task Profile Attachment

**Related UC**: UC-001 (steps 20–23), §4.4.10

**Precondition**: At least one task profile exists

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From Main Menu, select option 1 (New Chat), enter "y" | Chat creation workflow starts (manual path)  |
| 2    | Complete steps 1–9 (name, system prompt, model, settings, context window, strategy) | Task profile selection block `--- ПРИВЯЗКА ПРОФИЛЯ ЗАДАЧИ ---` displayed |
| 3    | Select profile index (e.g., 1)                | Chat created with profile attached           |
| 4    | Verify completion                             | `[OK] Чат '{name}' создан!`; chat loop entered |
| 5    | Type "/info"                                  | Line `Профиль задачи: {profile_name}` shown  |
| 6    | Verify agent saved                            | Agent has task_profile_id set to selected UUID |

---

### TC-062: Create Chat Without Task Profile

**Related UC**: UC-001 (steps 20–23), §4.4.10

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From Main Menu, select option 1 (New Chat), enter "y" | Complete manual creation through step 9 (strategy) |
| 2    | At profile selection, choose 0 (none) or press Enter | Chat created without profile attachment      |
| 3    | Type "/info" in chat loop                     | Shows `Профиль задачи: (не привязан)`        |
| 4    | Verify agent saved                            | Agent has task_profile_id = null             |

---

### TC-063: Task Profile Selection - No Profiles Available

**Related UC**: UC-001 (§4.4.10)

**Precondition**: No task profiles exist in repository

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Create new chat via manual path, reach profile selection step (step 10 of §4.4) | `(нет доступных профилей)` displayed, creation continues without attachment |
| 2    | Verify chat created                           | Chat has task_profile_id = null              |

---

### TC-064: Memory Integration - Global + Task Profile in System Prompt

**Related UC**: §3 Memory Integration, UC-004

**Precondition**: Global memory has facts, task profile has facts and preferences, agent attached to task profile

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter chat loop with agent attached to task profile | Send message to agent                        |
| 2    | Verify system prompt construction             | Global memory facts appear first with header `--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---` |
| 3    | Verify task profile memory                    | Task facts appear after with header `--- ПАМЯТЬ ЗАДАЧИ: {profile_name} ---` |
| 4    | Verify user preferences                       | Preferences text appears after task memory with header `--- ПРЕДПОЧТЕНИЯ ПОЛЬЗОВАТЕЛЯ ---` |
| 5    | Verify correct ordering                       | Global → Task profile → Preferences          |

---

### TC-065: Preferences Display in System Prompt - Empty Preferences

**Related UC**: §3 Memory Integration, UC-004

**Precondition**: Global memory has facts, task profile has no preferences (empty string), agent attached to task profile

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter chat loop with agent attached to task profile | Send message to agent                        |
| 2    | Verify system prompt construction             | Global memory facts appear with header `--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---` |
| 3    | Verify task profile memory                    | Task facts appear with header `--- ПАМЯТЬ ЗАДАЧИ: {profile_name} ---` |
| 4    | Verify preferences section                    | Preferences section is NOT displayed (skipped when empty) |

---

### TC-066: Preferences Display in View Profile - With Preferences

**Related UC**: UC-015 (step 6)

**Precondition**: Task profile exists with non-empty preferences text

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Navigate to Task Profiles menu, select "View memory" | Profile selection prompt displayed           |
| 2    | Select profile with preferences               | Profile details displayed                    |
| 3    | Verify preferences display                    | `Предпочтения: {preferences_text}` shown     |

---

### TC-067: Preferences Display in View Profile - Empty Preferences

**Related UC**: UC-015 (step 6, §4.7.3)

**Precondition**: Task profile exists with empty preferences

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Navigate to Task Profiles menu, select "View memory" | Profile selection prompt displayed           |
| 2    | Select profile with empty preferences         | Profile details displayed                    |
| 3    | Verify preferences display                    | The `Предпочтения:` line is omitted entirely (no placeholder like `(не указаны)`) |

---

### TC-068: Create Profile With Preferences

**Related UC**: UC-014 (steps 7–9)

**Precondition**: User is creating a new task profile

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter name and description                    | Preferences prompt displayed                 |
| 2    | Enter preferences text (single line; multi-line input is not supported by the CLI) | Preferences accepted without validation      |
| 3    | Complete profile creation (invariants block → empty line) | Profile saved with preferences text          |
| 4    | View created profile                          | Preferences displayed correctly              |

---

### TC-069: Create Profile Without Preferences

**Related UC**: UC-014 A3, UC-015 (step 6)

**Precondition**: User is creating a new task profile

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter name and description                    | Preferences prompt displayed                 |
| 2    | Press Enter without entering preferences      | Empty preferences accepted (no error)        |
| 3    | Complete profile creation                     | Profile saved with empty preferences         |
| 4    | View created profile                          | The `Предпочтения:` line is omitted entirely |

---

### TC-115: Chat Loop Graceful Exit On End Of Input

**Related UC**: UC-004 A6

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Start the application, create a chat (quick path), feed input that ends right after one message exchange (no `/menu`, no option 6) | The message is sent and answered; then the input stream ends                            |
| 2    | Verify termination                                              | The chat loop terminates gracefully: no traceback in stderr, process exits cleanly      |
| 3    | Verify memory save                                              | Agent memory is saved before exit (UC-004 A6, exit rule in 5.4.4); restart shows the exchange intact |

---

### TC-116: Profiles List Submenu Non-Numeric Action Re-Prompts

**Related UC**: UC-013 A4

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Open profiles list with at least one profile                     | Actions block and prompt `Выберите действие (1-4):` displayed                            |
| 2    | Enter "abc" (non-numeric)                                       | `[WARN] Неверный выбор, попробуйте снова.` displayed; action prompt re-displayed (UC-013 A4) |
| 3    | Enter "0"                                                       | Same warning; action prompt re-displayed                                                |
| 4    | Enter "4" (Back to list)                                        | Control returns to the Task Profiles menu                                               |

---

### TC-117: Create Profile With Empty Preferences

**Related UC**: UC-014 A3

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Reach the preferences prompt during profile creation             | Prompt `Введите предпочтения/инструкции (Enter для пропуска):` displayed                 |
| 2    | Press Enter (empty input)                                       | No error; the invariants block follows (UC-014 A3)                                      |
| 3    | Finish creation with an empty invariants line                    | `[OK] Профиль задачи '{name}' создан!`                                                  |
| 4    | View the created profile (action 1 in the profiles list)         | The `Предпочтения:` line is omitted entirely (cross-check with UC-015 step 6)           |

---

### TC-118: Delete Task Profile - Repository Failure

**Related UC**: UC-017 (step 7)

**Precondition**: Unlinked task profile exists; repository deletion is arranged to fail

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | From profiles list submenu, select action 3 (Delete), choose the profile | Confirmation prompt `Вы уверены, что хотите удалить профиль '{name}'? (y/n):` displayed     |
| 2    | Enter 'y'                                                       | `[ERROR] Не удалось удалить профиль '{name}'.` displayed (UC-017 step 7)                 |
| 3    | Verify state                                                    | Profile still exists in repository                                                      |
| 4    | Verify navigation                                               | Control returns to the Task Profiles menu                                               |

---

### TC-119: Return To Active Chat After EOF At Menu Prompt

**Related UC**: UC-003 A2

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Create a chat, return to Main Menu via `/menu`                   | Option 5 shows `Вернуться в чат: {name}`                                                 |
| 2    | Feed end of input (EOF) at `Ваш выбор (1-6):` without selecting an option | `До свидания!` printed; application terminates cleanly (UC-003 A2)                        |
| 3    | Restart the application                                         | The chat from step 1 is still present and selectable via option 2                       |

---

### TC-120: Quick Creation Default Name Counter

**Related UC**: UC-001 A1, UC-001 A3

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Ensure exactly 2 chats exist in storage                          | Main Menu displayed                                                                    |
| 2    | Select option 1 (New Chat), press Enter at the configure prompt (default "n") | `Используются настройки по умолчанию.` printed (UC-001 A1)                  |
| 3    | Verify completion message                                       | `[OK] Чат 'Чат 3' создан!` — auto-generated name uses N = existing chats + 1 (UC-001 A3) |
| 4    | Verify chat settings                                            | Defaults applied (`aliceai-llm-flash/latest`, disabled temperature/top_p/top_k, DefaultStrategy, no profile) |
