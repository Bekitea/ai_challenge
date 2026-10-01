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
5. On `ContextWindowExceededError`: print `[ERROR] {message}` plus `Необходимо очистить историю сообщений или создать новый чат.` and exit the chat loop back to the menu

#### 4.5.3 Commands Specification

All commands are matched case-insensitively. Unknown slash-commands are treated as regular messages and sent to the agent.

##### Phase commands: `/plan`, `/execute`, `/validate`, `/report`

- **Action**: Transition the agent workflow phase via `Agent.handle_phase_command`
- **Rules**: Forward transition allowed only to the next phase in order PLAN → EXECUTE → VALIDATE → REPORT; any backward transition is allowed; forward skips are rejected
- **Output**: `[INFO] {message}` where message is either `Фаза изменена: {OLD} -> {NEW}` or `Нельзя перескочить этап: переход из {OLD} сразу в {NEW} запрещен`, followed by updated header line `--- ЧАТ: {name} [Фаза: {PHASE}] ---`

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
  Текущая фаза: {phase}|(не установлена)
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
  1. Display current settings (format in 4.6.1)
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

- **Context window exceeded** — UC-004 A3 (`[ERROR] {message}` + hint, exit to Main Menu)
- **Backend exception during message send** — UC-004 A4 (`[ERROR] Ошибка: {message}`, exit to Main Menu)
- **KeyboardInterrupt / EOFError** — UC-003 A2 (menu prompt) and UC-004 A5 / UC-005 A3 (chat loop: `Прервано пользователем.`)
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

Model is shown by its identifier (not display name). Missing `context_window_size` is displayed as 200000.

#### 4.6.2 Change Settings (`change_settings`)

Same prompts as creation workflow (Section 4.4.3–4.4.8) applied sequentially; each answer fully replaces the previous value (empty input disables the parameter — there is no "keep current value" semantics). Strategy, task profile and phase cannot be changed for existing chats. Confirmation: `[OK] Настройки обновлены!` followed by the refreshed settings block.

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

Prompt: `Ваш выбор (1-3):`. Invalid choice: `[WARN] Неверный выбор, попробуйте снова.` Option 3 returns to the Main Menu.

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

Prompt: `Выберите действие (1-4):`. Invalid action: `[WARN] Неверный выбор, попробуйте снова.` Actions 1–3 first require profile selection by index (`Выберите профиль (1-{n}):` / `Выберите профиль для удаления (1-{n}):`; out-of-range → `Введите число от 1 до {n}`, non-numeric → `Введите корректное число`). After an action completes, control returns to the Task Profiles menu.

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
- Remove: `Выберите номер инварианта для удаления (1-{n}):`; unknown number → `[WARN] Некорректный номер.`; failure → `[ERROR] Не удалось удалить инвариант.`; success → `[OK] Инвариант удалён!`
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

- **A3: Context Window Exceeded**
  - Step 6: Backend raises `ContextWindowExceededError`
  - System clears the "печатает..." line, displays `[ERROR] {message}` followed by `Необходимо очистить историю сообщений или создать новый чат.`
  - System exits the chat loop and returns to Main Menu (the chat remains active for option 5)

- **A4: Any Other Backend Error**
  - Step 6: Any other exception is raised while sending/processing
  - System displays `[ERROR] Ошибка: {message}`
  - System exits the chat loop and returns to Main Menu

- **A5: KeyboardInterrupt During Exchange**
  - Any step: User presses Ctrl+C at the input prompt or during processing
  - System displays `Прервано пользователем.` and exits the chat loop back to Main Menu

- **A6: Long Response**
  - Step 8: Response exceeds terminal width
  - System wraps text appropriately

- **A7: Reasoning In Response**
  - After step 9: response carries reasoning content
  - System asks `Показать рассуждения модели? (y/n):`; on `y` it prints the indented `[Reasoning]:` block, otherwise nothing extra

#### 5.4.4 Postconditions

- Two new messages in history (user + assistant)
- Chat preview updated with last message

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
  - System displays `Прервано пользователем.` and exits the chat loop back to Main Menu

- **A4: Backend Error While Applying Settings**
  - Step 8: `change_settings` use case raises an exception
  - System displays `[ERROR] Ошибка: {message}` and exits the chat loop back to Main Menu

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
  - Step 11: Unknown/out-of-range number → `[WARN] Некорректный номер.`; failure to remove → `[ERROR] Не удалось удалить инвариант.`

- **A3: Repository ValueError On Add**
  - Step 7: Repository raises `ValueError` (e.g. duplicate invariant)
  - Display `[ERROR] {e}`; the list is redisplayed

#### 5.16.4 Postconditions

- Invariants list updated in the profile storage
- User returned to the Task Profiles menu

---

### UC-017: Delete Task Profile

#### 5.16.1 Preconditions

- Application is running
- User is in the profiles list submenu (Task Profiles menu → option 2 → action 3)
- At least one task profile exists

#### 5.16.2 Main Success Scenario

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

#### 5.16.3 Alternative Flows

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

#### 5.16.4 Postconditions

- If confirmed and unlinked: TaskProfile deleted from repository
- If declined or linked to agents: Profile remains unchanged
- User returned to Task Profiles menu

---

## 6. Test Cases

### TC-001: Create Chat with Default Values

**Related UC**: UC-001

| Step | Action                      | Expected Result                        |
| ---- | --------------------------- | -------------------------------------- |
| 1    | Select option 1 (New Chat)  | Name prompt displayed                  |
| 2    | Press Enter (default name)  | System prompt prompt displayed         |
| 3    | Press Enter (skip prompt)   | Model selection displayed              |
| 4    | Select model 1              | Temperature prompt displayed           |
| 5    | Press Enter (disable temp)  | Top P prompt displayed                 |
| 6    | Press Enter (disable top_p) | Top K prompt displayed                 |
| 7    | Press Enter (default 0)     | Reasoning effort prompt                |
| 8    | Press Enter (default none)  | Success message with ID                |
| 9    | Verify chat created         | Chat name = "Чат N", settings disabled |

---

### TC-002: Create Chat with Custom Settings

**Related UC**: UC-001

| Step | Action              | Expected Result            |
| ---- | ------------------- | -------------------------- |
| 1    | Select option 1 (New Chat)   | Name prompt                |
| 2    | Enter "Test Chat"   | System prompt prompt       |
| 3    | Enter "Be concise"  | Model selection            |
| 4    | Select model 2      | Temperature prompt         |
| 5    | Enter "1.5"         | Top P prompt               |
| 6    | Enter "0.8"         | Top K prompt               |
| 7    | Enter "50"          | Reasoning effort prompt    |
| 8    | Select "3" (medium) | Success message            |
| 9    | Verify settings     | All values saved correctly |

---

### TC-003: Invalid Temperature Handling

**Related UC**: UC-001

| Step | Action                                | Expected Result               |
| ---- | ------------------------------------- | ----------------------------- |
| 1-3  | Create chat, reach temperature prompt | Temperature prompt displayed  |
| 4    | Enter "abc"                           | Warning, temperature disabled |
| 5    | Continue creation                     | Chat created with temp=None   |
| 6    | Enter "-1"                            | Warning, temperature disabled |
| 7    | Enter "3.0"                           | Warning, temperature disabled |

---

### TC-004: Select Chat from Empty List

**Related UC**: UC-002

| Step | Action                      | Expected Result               |
| ---- | --------------------------- | ----------------------------- |
| 1    | Ensure no chats exist       | Empty storage                 |
| 2    | Select option 2 (Select Chat)| Message "Нет доступных чатов" |
| 3    | Verify navigation           | Returns to Main Menu          |

---

### TC-005: Preview with System Prompt Only

**Related UC**: UC-002

| Step | Action                              | Expected Result            |
| ---- | ----------------------------------- | -------------------------- |
| 1    | Create chat with system prompt only | Chat with 1 system message |
| 2    | Return to menu                      | Chat list displayed        |
| 3    | Verify preview                      | Shows "(нет сообщений)"    |
| 4    | Verify count                        | Shows "Сообщений: 0"       |

---

### TC-006: Preview with User Message

**Related UC**: UC-002

| Step | Action                     | Expected Result              |
| ---- | -------------------------- | ---------------------------- |
| 1    | Create chat                | New chat                     |
| 2    | Send message "Hello world" | Message saved                |
| 3    | Return to menu             | Chat list displayed          |
| 4    | Verify preview             | Shows "Hello world"          |
| 5    | Send 60-char message       | Message saved                |
| 6    | Return to menu             | Preview truncated with "..." |

---

### TC-007: Return to Chat Without Active Chat

**Related UC**: UC-003

| Step | Action            | Expected Result              |
| ---- | ----------------- | ---------------------------- |
| 1    | Start application | Main Menu                    |
| 2    | Verify option 5   | Shows "(нет активного чата)" |
| 3    | Select option 5   | Warning displayed            |
| 4    | Verify state      | Remains in Main Menu         |

---

### TC-008: Return to Chat With Active Chat

**Related UC**: UC-003

| Step | Action                | Expected Result                 |
| ---- | --------------------- | ------------------------------- |
| 1    | Create or select chat | Chat loop entered               |
| 2    | Type "/menu"          | Main Menu displayed             |
| 3    | Verify option 5       | Shows "Вернуться в чат: {name}" |
| 4    | Select option 5       | Chat loop entered               |
| 5    | Verify context        | Same chat, history intact       |

---

### TC-009: Send Multiple Messages

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

### TC-010: Empty Message Handling

**Related UC**: UC-004

| Step | Action              | Expected Result     |
| ---- | ------------------- | ------------------- |
| 1    | Enter chat          | Prompt displayed    |
| 2    | Press Enter (empty) | No send, re-prompt  |
| 3    | Press Enter again   | No send, re-prompt  |
| 4    | Send valid message  | Normal flow resumes |

---

### TC-011: View Settings

**Related UC**: UC-005

| Step | Action                              | Expected Result                   |
| ---- | ----------------------------------- | --------------------------------- |
| 1    | Enter chat with configured settings | Prompt displayed                  |
| 2    | Type "/settings"                    | Current settings displayed        |
| 3    | Verify format                       | All 5 parameters shown            |
| 4    | Verify disabled display             | Shows "отключена" for None values |
| 5    | Verify return                       | Back to chat prompt               |

---

### TC-012: Change Partial Settings

**Related UC**: UC-005

| Step | Action                  | Expected Result          |
| ---- | ----------------------- | ------------------------ |
| 1    | Type "/settings"        | Settings view            |
| 2    | Change only temperature | Other prompts shown      |
| 3    | Press Enter for others  | Values unchanged         |
| 4    | Verify update           | Only temperature changed |

---

### TC-013: Menu Navigation from Chat

**Related UC**: UC-006

| Step | Action                  | Expected Result              |
| ---- | ----------------------- | ---------------------------- |
| 1    | Enter chat              | Chat loop                    |
| 2    | Type "/menu"            | Main Menu displayed          |
| 3    | Verify chat preserved   | Chat still exists in storage |
| 4    | Select "Return to Chat" | Same chat reloaded           |

---

### TC-014: Stop Command When Idle

**Related UC**: UC-007

| Step | Action                       | Expected Result                |
| ---- | ---------------------------- | ------------------------------ |
| 1    | Enter chat                   | Prompt displayed               |
| 2    | Type "/stop" (no generation) | Warning "Генерация не активна" |
| 3    | Verify state                 | Still in chat loop             |

---

### TC-015: Help Command

**Related UC**: UC-008

| Step | Action         | Expected Result        |
| ---- | -------------- | ---------------------- |
| 1    | Enter chat     | Prompt displayed       |
| 2    | Type "/help"   | Command list displayed |
| 3    | Verify content | All 12 commands listed |
| 4    | Verify return  | Back to prompt         |

---

### TC-016: Unknown Command Handling

**Related UC**: UC-004

| Step | Action                  | Expected Result               |
| ---- | ----------------------- | ----------------------------- |
| 1    | Enter chat              | Prompt displayed              |
| 2    | Type "/unknown"         | Treated as a regular message: sent to the agent (UC-004 A2), `[AGENT] печатает...` then `[AGENT]: {response}` |
| 3    | Verify state            | Back to prompt                |

---

### TC-017: System Prompt in History

**Related UC**: UC-001

| Step | Action                         | Expected Result            |
| ---- | ------------------------------ | -------------------------- |
| 1    | Create chat with system prompt | Prompt entered             |
| 2    | Verify history                 | System message present     |
| 3    | Check role                     | Role = "system"            |
| 4    | Check display                  | NOT displayed in the chat header (`[SYSTEM]` prefix does not exist; only `[USER]`/`[AGENT]` are printed, system messages are hidden) |

---

### TC-018: Special Characters in Input

**Related UC**: UC-001, UC-004

| Step | Action                             | Expected Result             |
| ---- | ---------------------------------- | --------------------------- |
| 1    | Create chat with name "Тест @#$%"  | Name saved correctly        |
| 2    | Send message with emoji "Hello 👋" | Message saved               |
| 3    | Verify encoding                    | UTF-8 preserved             |
| 4    | Verify display                     | Characters render correctly |

---

### TC-019: Long Chat Name Handling

**Related UC**: UC-001

| Step | Action              | Expected Result       |
| ---- | ------------------- | --------------------- |
| 1    | Enter 150-char name | Accepted without truncation (CLI performs no length validation) |
| 2    | Verify storage      | Full 150-char name saved (DB column limit is 255 chars, see §4.4.1)   |
| 3    | Verify display      | Full name shown in chat list and header  |

---

### TC-020: Concurrent Chat Operations

**Related UC**: UC-002, UC-003

| Step | Action          | Expected Result  |
| ---- | --------------- | ---------------- |
| 1    | Create Chat A   | Active = A       |
| 2    | Type "/menu"    | Main Menu        |
| 3    | Select option 2, choose Chat B   | Active = B       |
| 4    | Type "/menu"    | Main Menu        |
| 5    | Select option 5 (Return to Chat)  | Returns to B     |
| 6    | Verify A intact | Chat A unchanged |

---

### TC-021: View Summary With Summarization

**Related UC**: UC-009

| Step | Action                       | Expected Result                    |
| ---- | ---------------------------- | ---------------------------------- |
| 1    | Open chat with summarization | Chat active                        |
| 2    | Type "/summary"              | Summary text displayed             |
| 3    | Verify summary content       | Matches strategy's current summary |
| 4    | Verify no state changes      | Chat remains active                |

---

### TC-022: View Summary Without Summarization

**Related UC**: UC-009

| Step | Action                         | Expected Result                                     |
| ---- | ------------------------------ | --------------------------------------------------- |
| 1    | Open new chat (no summary yet) | Chat active                                         |
| 2    | Type "/summary"                | `[INFO] Саммари пока недоступно.` displayed          |
| 3    | Verify no state changes        | Chat remains active                                 |

---

### TC-023: View Chat Info With Token Statistics

**Related UC**: UC-010

| Step | Action                  | Expected Result                        |
| ---- | ----------------------- | -------------------------------------- |
| 1    | Open chat with messages | Chat active                            |
| 2    | Type "/info"            | Chat info header displayed             |
| 3    | Verify token statistics | `Prompt токены` and `Completion токены` shown       |
| 4    | Verify strategy type    | Strategy name displayed                |
| 5    | Verify no state changes | Chat remains active                    |

---

### TC-024: Create Branch And Switch

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

### TC-025: Create Branch And Stay

**Related UC**: UC-011

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

### TC-026: Create Branch With Custom Name

**Related UC**: UC-011

| Step | Action                   | Expected Result                  |
| ---- | ------------------------ | -------------------------------- |
| 1    | Open chat                | Chat active                      |
| 2    | Type "/branch"           | Branch name prompt               |
| 3    | Enter "My Custom Branch" | Branch created with that name    |
| 4    | Verify branch name       | "My Custom Branch" used          |

---

### TC-027: Settings Change With Confirmation

**Related UC**: UC-005

| Step | Action                               | Expected Result                            |
| ---- | ------------------------------------ | ------------------------------------------ |
| 1    | Type "/settings"                     | Current settings displayed                 |
| 2    | Prompt: "Изменить настройки? (y/n):" | Displayed                                  |
| 3    | Enter "y"                            | All settings prompts shown (like creation) |
| 4    | Change temperature to 0.8            | Other settings kept as-is                  |
| 5    | Verify update                        | `[OK] Настройки обновлены!` displayed      |
| 6    | Verify only temperature changed      | Other settings preserved                   |

---

### TC-028: Settings Change Cancelled

**Related UC**: UC-005

| Step | Action                               | Expected Result                     |
| ---- | ------------------------------------ | ----------------------------------- |
| 1    | Type "/settings"                     | Current settings displayed          |
| 2    | Prompt: "Изменить настройки? (y/n):" | Displayed                           |
| 3    | Enter "n"                            | Return to chat loop without changes |
| 4    | Verify no changes                    | Settings remain unchanged           |

---

### TC-029: Stop Command Exits Chat Loop

**Related UC**: UC-007

| Step | Action                        | Expected Result                                        |
| ---- | ----------------------------- | ------------------------------------------------------ |
| 1    | In chat loop, type "/stop"    | `[INFO] Генерация не активна.` displayed               |
| 2    | Verify navigation             | Chat loop exits, Main Menu displayed                   |
| 3    | Verify active chat            | Option 5 still shows "Вернуться в чат: {name}"         |

---

### TC-030: Stop Command Output And State

**Related UC**: UC-007

| Step | Action                        | Expected Result                                          |
| ---- | ----------------------------- | -------------------------------------------------------- |
| 1    | Type "/stop" at any moment    | `[INFO] Генерация не активна.` displayed                 |
| 2    | Verify return to menu         | Main Menu displayed                                      |
| 3    | Verify chat state             | Chat preserved, remains the active chat                  |

---

### TC-031: SlidingWindowStrategy Creation

**Related UC**: UC-001

| Step | Action                          | Expected Result                         |
| ---- | ------------------------------- | --------------------------------------- |
| 1    | Create new chat                 | Strategy selection prompt               |
| 2    | Select option 4 (SlidingWindow) | window_size prompt with default 10      |
| 3    | Press Enter (accept default)    | Chat created with SlidingWindowStrategy |
| 4    | Verify strategy                 | Strategy type = "SlidingWindowStrategy" |
| 5    | Verify window_size              | window_size = 10                        |

---

### TC-032: SlidingWindowStrategy With Custom Window

**Related UC**: UC-001

| Step | Action                          | Expected Result                         |
| ---- | ------------------------------- | --------------------------------------- |
| 1    | Create new chat                 | Strategy selection prompt               |
| 2    | Select option 4 (SlidingWindow) | window_size prompt                      |
| 3    | Enter "20"                      | Chat created with window_size = 20      |
| 4    | Verify strategy                 | Strategy type = "SlidingWindowStrategy" |
| 5    | Verify window_size              | window_size = 20                        |

---

### TC-033: SummarizationStrategy Creation

**Related UC**: UC-001

| Step | Action                          | Expected Result                              |
| ---- | ------------------------------- | -------------------------------------------- |
| 1    | Create new chat                 | Strategy selection prompt                    |
| 2    | Select option 2 (Summarization) | non_compressible_count prompt with default 2 |
| 3    | Press Enter (accept default)    | buffer_size prompt with default 3            |
| 4    | Press Enter (accept default)    | Chat created with SummarizationStrategy      |
| 5    | Verify strategy                 | Strategy type = "SummarizationStrategy"      |
| 6    | Verify parameters               | non_compressible_count = 2, buffer_size = 3  |

---

### TC-034: SummarizationStrategy With Custom Parameters

**Related UC**: UC-001

| Step | Action                          | Expected Result                             |
| ---- | ------------------------------- | ------------------------------------------- |
| 1    | Create new chat                 | Strategy selection prompt                   |
| 2    | Select option 2 (Summarization) | non_compressible_count prompt               |
| 3    | Enter "5"                       | buffer_size prompt                          |
| 4    | Enter "4"                       | Chat created with custom parameters         |
| 5    | Verify strategy                 | Strategy type = "SummarizationStrategy"     |
| 6    | Verify parameters               | non_compressible_count = 5, buffer_size = 4 |

---

### TC-035: KeyValueMemoryStrategy Creation

**Related UC**: UC-001

| Step | Action                           | Expected Result                              |
| ---- | -------------------------------- | -------------------------------------------- |
| 1    | Create new chat                  | Strategy selection prompt                    |
| 2    | Select option 3 (KeyValueMemory) | non_compressible_count prompt with default 2 |
| 3    | Press Enter (accept default)     | buffer_size prompt with default 3            |
| 4    | Press Enter (accept default)     | Chat created with KeyValueMemoryStrategy     |
| 5    | Verify strategy                  | Strategy type = "KeyValueMemoryStrategy"     |
| 6    | Verify parameters                | non_compressible_count = 2, buffer_size = 3  |

---

### TC-036: KeyValueMemoryStrategy With Custom Parameters

**Related UC**: UC-001

| Step | Action                           | Expected Result                             |
| ---- | -------------------------------- | ------------------------------------------- |
| 1    | Create new chat                  | Strategy selection prompt                   |
| 2    | Select option 3 (KeyValueMemory) | non_compressible_count prompt               |
| 3    | Enter "3"                        | buffer_size prompt                          |
| 4    | Enter "5"                        | Chat created with custom parameters         |
| 5    | Verify strategy                  | Strategy type = "KeyValueMemoryStrategy"    |
| 6    | Verify parameters                | non_compressible_count = 3, buffer_size = 5 |

---

### TC-037: DefaultStrategy Creation

**Related UC**: UC-001

| Step | Action                     | Expected Result                                                       |
| ---- | -------------------------- | --------------------------------------------------------------------- |
| 1    | Create new chat            | Strategy selection prompt                                             |
| 2    | Select option 1 (Default)  | Chat created immediately without extra prompts                        |
| 3    | Verify strategy            | Strategy type = "DefaultStrategy"                                     |
| 4    | Verify no extra parameters | non_compressible_count = null, buffer_size = null, window_size = null |

---

### TC-038: View Info For Different Strategies

**Related UC**: UC-010

| Step | Action                                | Expected Result                                       |
| ---- | ------------------------------------- | ----------------------------------------------------- |
| 1    | Open chat with DefaultStrategy        | Type /info, verify strategy displayed                 |
| 2    | Open chat with SummarizationStrategy  | Type /info, verify strategy and params displayed      |
| 3    | Open chat with KeyValueMemoryStrategy | Type /info, verify strategy and params displayed      |
| 4    | Open chat with SlidingWindowStrategy  | Type /info, verify strategy and window_size displayed |

---

### TC-039: Branch Preserves Strategy Type

**Related UC**: UC-011

| Step | Action                               | Expected Result                                  |
| ---- | ------------------------------------ | ------------------------------------------------ |
| 1    | Open chat with SummarizationStrategy | Type /branch, create branch                      |
| 2    | Verify new branch                    | Strategy type = "SummarizationStrategy"          |
| 3    | Verify parameters copied             | non_compressible_count and buffer_size preserved |

---

### TC-040: Branch Preserves SlidingWindow Configuration

**Related UC**: UC-011

| Step | Action                                                | Expected Result                         |
| ---- | ----------------------------------------------------- | --------------------------------------- |
| 1    | Open chat with SlidingWindowStrategy (window_size=15) | Type /branch, create branch             |
| 2    | Verify new branch                                     | Strategy type = "SlidingWindowStrategy" |
| 3    | Verify window_size copied                             | window_size = 15 in new branch          |

---

### TC-041: View Global Memory from Main Menu (No Chat Required)

**Related UC**: UC-012

| Step | Action                                    | Expected Result                                       |
| ---- | ----------------------------------------- | ----------------------------------------------------- |
| 1    | Start application, stay in Main Menu      | No active chat selected                               |
| 2    | Select option 4 (Global Memory) from menu | System displays global memory view                    |
| 3    | Verify header displayed                   | `--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---` is shown                  |
| 4    | Verify facts or empty state               | Either numbered facts list OR `(память пуста)`        |
| 5    | Verify separator line                     | 40 dashes are displayed                               |
| 6    | Verify return to menu                     | Main Menu is displayed again                          |

### TC-042: View Global Memory - Empty State

**Related UC**: UC-012

| Step | Action                                    | Expected Result                                       |
| ---- | ----------------------------------------- | ----------------------------------------------------- |
| 1    | Start application                         | Application running                                   |
| 2    | Ensure no chats exist and memory is empty | Repository returns empty list                         |
| 3    | Select option 4 (Global Memory) from menu | System displays global memory view                    |
| 4    | Verify header displayed                   | `--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---` is shown                  |
| 5    | Verify empty state message                | `(память пуста)` is displayed                         |
| 6    | Verify separator line                     | 40 dashes are displayed                               |
| 7    | Verify return to menu                     | Main Menu is displayed again                          |

### TC-043: View Global Memory - With Facts (End-to-End Flow)

**Related UC**: UC-012

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

### TC-044: Create Task Profile with Valid Data

**Related UC**: UC-014

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From Main Menu, select option 3 (Task Profiles) | Task Profiles menu displayed                 |
| 2    | Select option 1 (Create new profile)          | Name prompt displayed                        |
| 3    | Enter "Project Alpha"                         | Description prompt displayed                 |
| 4    | Enter "Development of Project Alpha system"   | Success message displayed with ID and timestamp |
| 5    | Verify profile saved                          | Profile exists in repository with empty facts |

---

### TC-045: Create Task Profile - Empty Name Validation

**Related UC**: UC-014

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From Task Profiles menu, select Create        | Name prompt displayed                        |
| 2    | Press Enter (empty input)                     | `[ERROR] Название не может быть пустым.` + re-prompt |
| 3    | Enter valid name                              | Proceed to description prompt                |

---

### TC-046: Create Task Profile - Long Name Accepted

**Related UC**: UC-014

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From Task Profiles menu, select Create        | Name prompt displayed                        |
| 2    | Enter 150-character string                    | Accepted without error or truncation warning |
| 3    | Verify saved name                             | Full 150-character name stored and displayed |

---

### TC-047: Create Task Profile - Empty Description Validation

**Related UC**: UC-014

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From Task Profiles menu, select Create        | Name prompt → enter valid name               |
| 2    | Description prompt displayed                  | Press Enter (empty input)                    |
| 3    | Verify error                                  | `[ERROR] Описание задачи не может быть пустым.` + re-prompt |

---

### TC-048: View Task Profiles List - Empty State

**Related UC**: UC-013

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From Main Menu, select option 3 (Task Profiles) | Task Profiles menu displayed (options 1-3)   |
| 2    | Select option 2 (View profiles list)          | `Нет доступных профилей задач.` + separator displayed |
| 3    | Verify return                                 | Control returns to the Task Profiles menu    |

---

### TC-049: View Task Profiles List - Multiple Profiles

**Related UC**: UC-013

**Precondition**: At least 2 task profiles exist in repository

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From Main Menu, select option 3, then option 2 | `--- СПИСОК ПРОФИЛЕЙ ЗАДАЧ ---` header displayed |
| 2    | Verify profile block format                   | Each profile shows: index+name, ID, Дата создания (`%Y-%m-%d %H:%M`), Фактов в памяти, Инвариантов, Описание (50 chars + `...` if longer) |
| 3    | Verify action options                         | `Действия:` with 4 options (View Memory, Manage Invariants, Delete, Back to list) and prompt `Выберите действие (1-4):` |

---

### TC-050: View Task Profile Memory - With Facts

**Related UC**: UC-015

**Precondition**: Task profile exists with at least 2 facts in memory

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 1 (View memory) | Profile selection prompt `Выберите профиль (1-{n}):` displayed |
| 2    | Select profile by index                       | `--- ИНФОРМАЦИЯ О ПРОФИЛЕ ЗАДАЧИ ---`: ID, Название, Описание, Дата создания (+ Предпочтения if non-empty) |
| 3    | Verify memory section                         | `--- ПАМЯТЬ ПРОФИЛЯ ---` header + numbered facts; `--- ИНВАРИАНТЫ ---` section shown |
| 4    | Verify return                                 | Control returns to the Task Profiles menu    |

---

### TC-051: View Task Profile Memory - Empty State

**Related UC**: UC-015

**Precondition**: Task profile exists with empty facts list

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 1   | Select profile                               |
| 2    | Verify memory display                         | `(память пуста)` shown instead of facts; `(инварианты не заданы)` if no invariants |
| 3    | Verify return                                 | Return to the Task Profiles menu             |

---

### TC-052: Delete Task Profile - Not Attached

**Related UC**: UC-016

**Precondition**: Task profile exists, not attached to any agents

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 3 (Delete) | Profile selection prompt `Выберите профиль для удаления (1-{n}):` displayed |
| 2    | Select profile by index                       | Confirmation prompt: `Вы уверены, что хотите удалить профиль '{name}'? (y/n):` |
| 3    | Enter 'y'                                     | `[OK] Профиль '{name}' успешно удалён.`      |
| 4    | Verify deletion                               | Profile no longer in repository              |

---

### TC-053: Delete Task Profile - Attached to Agents

**Related UC**: UC-016

**Precondition**: Task profile exists, attached to 2 agents

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 3   | Select profile                               |
| 2    | Verify block message                          | `[WARN] Невозможно удалить профиль '{name}': он привязан к одному или нескольким агентам.` + `Сначала удалите или пересоздайте агентов, использующих этот профиль.` — NO confirmation prompt |
| 3    | Verify profile not deleted                    | Profile still in repository                  |
| 4    | Verify agents unchanged                       | Agents keep their task_profile_id link       |

---

### TC-054: Delete Task Profile - Cancelled

**Related UC**: UC-016

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 3   | Select profile (profile must be unlinked)    |
| 2    | Confirmation prompt displayed                 | Enter 'n'                                    |
| 3    | Verify cancellation                           | `[INFO] Удаление отменено.`                  |
| 4    | Verify profile exists                         | Profile still in repository                  |

---

### TC-055: Create Chat with Task Profile Attachment

**Related UC**: UC-001, UC-013

**Precondition**: At least one task profile exists

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From Main Menu, select option 1 (New Chat)    | Chat creation workflow starts                |
| 2    | Complete steps 1-8 (name, prompt, model, settings, strategy) | Task profile selection prompt displayed      |
| 3    | Select profile index (e.g., 1)                | Chat created with profile attached           |
| 4    | Verify completion message                     | Shows `Профиль задачи: {profile_name}`       |
| 5    | Verify agent saved                            | Agent has task_profile_id set to selected UUID |

---

### TC-056: Create Chat Without Task Profile

**Related UC**: UC-001

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From Main Menu, select option 1 (New Chat)    | Complete chat creation through step 9        |
| 2    | At profile selection, choose 0 (none) or press Enter | Chat created without profile attachment      |
| 3    | Verify completion message                     | Shows `Профиль задачи: (не привязан)`        |
| 4    | Verify agent saved                            | Agent has task_profile_id = null             |

---

### TC-057: Task Profile Selection - No Profiles Available

**Related UC**: UC-001

**Precondition**: No task profiles exist in repository

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Create new chat, reach step 9 (profile selection) | `(нет доступных профилей)` displayed, skip to completion |
| 2    | Verify chat created                           | Chat has task_profile_id = null              |

---

### TC-058: Memory Integration - Global + Task Profile in System Prompt

**Related UC**: UC-004

**Precondition**: Global memory has facts, task profile has facts and preferences, agent attached to task profile

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter chat loop with agent attached to task profile | Send message to agent                        |
| 2    | Verify system prompt construction             | Global memory facts appear first with header `--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---` |
| 3    | Verify task profile memory                    | Task facts appear after with header `--- ПАМЯТЬ ЗАДАЧИ: {profile_name} ---` |
| 4    | Verify user preferences                       | Preferences text appears after task memory with header `--- ПРЕДПОЧТЕНИЯ ПОЛЬЗОВАТЕЛЯ ---` |
| 5    | Verify correct ordering                       | Global → Task profile → Preferences          |

---

### TC-059: Preferences Display in System Prompt - Empty Preferences

**Related UC**: UC-004

**Precondition**: Global memory has facts, task profile has no preferences (empty string), agent attached to task profile

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter chat loop with agent attached to task profile | Send message to agent                        |
| 2    | Verify system prompt construction             | Global memory facts appear with header `--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---` |
| 3    | Verify task profile memory                    | Task facts appear with header `--- ПАМЯТЬ ЗАДАЧИ: {profile_name} ---` |
| 4    | Verify preferences section                    | Preferences section is NOT displayed (skipped when empty) |

---

### TC-060: Preferences Display in View Profile - With Preferences

**Related UC**: UC-015

**Precondition**: Task profile exists with non-empty preferences text

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Navigate to Task Profiles menu, select "View memory" | Profile selection prompt displayed           |
| 2    | Select profile with preferences               | Profile details displayed                    |
| 3    | Verify preferences display                    | `Предпочтения: {preferences_text}` shown     |

---

### TC-061: Preferences Display in View Profile - Empty Preferences

**Related UC**: UC-015

**Precondition**: Task profile exists with empty preferences

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Navigate to Task Profiles menu, select "View memory" | Profile selection prompt displayed           |
| 2    | Select profile with empty preferences         | Profile details displayed                    |
| 3    | Verify preferences display                    | `Предпочтения: (не указаны)` shown           |

---

### TC-062: Create Profile With Preferences

**Related UC**: UC-014

**Precondition**: User is creating a new task profile

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter name and description                    | Preferences prompt displayed                 |
| 2    | Enter multi-line preferences text             | Preferences accepted without validation      |
| 3    | Complete profile creation                     | Profile saved with preferences text          |
| 4    | View created profile                          | Preferences displayed correctly              |

---

### TC-063: Create Profile Without Preferences

**Related UC**: UC-014

**Precondition**: User is creating a new task profile

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter name and description                    | Preferences prompt displayed                 |
| 2    | Press Enter without entering preferences      | Empty preferences accepted (no error)        |
| 3    | Complete profile creation                     | Profile saved with empty preferences         |
| 4    | View created profile                          | `Предпочтения: (не указаны)` displayed       |
