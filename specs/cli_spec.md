# AI Chat CLI Specification

## 1. Overview

### 1.1 Purpose

This document provides a comprehensive specification for the Command Line Interface (CLI) of the AI Chat application. It serves as the single source of truth for:

- Regenerating the CLI frontend from scratch
- Writing comprehensive unit and integration tests
- Understanding all user interactions and system behaviors
- Onboarding new developers to the project

### 1.2 Scope

- **In Scope**: CLI interface, menu navigation, chat management, message handling, settings configuration, command processing
- **Out of Scope**: Backend LLM provider implementation, other frontends, API specifications

### 1.3 Definitions

| Term             | Definition                                           |
| ---------------- | ---------------------------------------------------- |
| Chat             | A conversation session identified by a unique UUID   |
| System Prompt    | Initial instruction message that sets agent behavior |
| Preview          | Short excerpt (max 50 chars) of the last message     |
| Active Chat      | Currently selected chat session in CLI state         |
| Disabled Setting | Parameter with `None` value, not passed to LLM       |

---

## 2. Architecture

### State Machine

```
[START] → [MAIN_MENU]
[MAIN_MENU] → [CREATE_CHAT] → [CHAT_LOOP] → [MAIN_MENU]
[MAIN_MENU] → [SELECT_CHAT] → [CHAT_LOOP] → [MAIN_MENU]
[MAIN_MENU] → [RETURN_TO_CHAT] → [CHAT_LOOP] → [MAIN_MENU]
[MAIN_MENU] → [EXIT] → [TERMINATED]
[CHAT_LOOP] → [SETTINGS_VIEW] → [CHAT_LOOP]
[CHAT_LOOP] → [SETTINGS_VIEW] → [SETTINGS_CHANGE] → [CHAT_LOOP]
```

## 3. Data Structures

### 3.1 Chat Object

```json
{
  "id": "string (UUID format)",
  "name": "string",
  "created_at": "ISO 8601 timestamp",
  "messages": [
    {
      "role": "system|user|assistant",
      "content": "string",
      "timestamp": "ISO 8601 timestamp"
    }
  ],
  "settings": {
    "model": "string (model identifier)",
    "temperature": "float|null (0.0-2.0)",
    "top_p": "float|null (0.0-1.0)",
    "top_k": "integer (0 = disabled)",
    "reasoning_effort": "string (none|low|medium|high)"
  }
}
```

### 3.2 AgentPreview Object

Returned by `Agents.get_chats_preview()` method:

```python
class AgentPreview:
    id: str                    # Chat UUID (first 8 chars displayed)
    name: str                  # Chat name
    message_count: int         # Total messages excluding system prompt
    last_message_time: str     # Formatted timestamp
    last_message_preview: str  # First 50 chars of last message content
```

### 3.4 Context Window Strategy Object

Strategy for managing context window when it exceeds limits:

```python
class ContextWindowStrategy:
    strategy_type: str         # "DefaultStrategy" | "SummarizationStrategy" | "KeyValueMemoryStrategy" | "SlidingWindowStrategy"
    non_compressible_count: int|null  # For summarization strategies only
    buffer_size: int|null             # For summarization strategies only
    window_size: int|null             # For SlidingWindowStrategy only
    summary: str|null                 # Current summary text (auto-managed)
```

#### Strategy Types:

| Strategy                 | Description                                                   | Parameters Required                 |
| ------------------------ | ------------------------------------------------------------- | ----------------------------------- |
| `DefaultStrategy`        | Passes all messages as-is, throws error on overflow           | None                                |
| `SummarizationStrategy`  | Summarizes old messages using free-form text summarization    | non_compressible_count, buffer_size |
| `KeyValueMemoryStrategy` | Summarizes into structured JSON format with predefined schema | non_compressible_count, buffer_size |
| `SlidingWindowStrategy`  | Keeps only last N messages, discards older ones               | window_size                         |

#### Default Values:

- `non_compressible_count`: 2 (messages kept in original form)
- `buffer_size`: 3 (messages grouped for summarization)
- `window_size`: 10 (for SlidingWindowStrategy)

---

### 3.5 Chat Settings Extended

```json
{
  "model": "string (model identifier)",
  "temperature": "float|null (0.0-2.0)",
  "top_p": "float|null (0.0-1.0)",
  "top_k": "integer (0 = disabled)",
  "reasoning_effort": "string (none|low|medium|high)",
  "context_window_size": "integer (default 200000, tokens)",
  "strategy": "ContextWindowStrategy object (see section 3.4)"
}
```

### 3.6 Message Roles

| Role      | Description               | Display Prefix | Editable              |
| --------- | ------------------------- | -------------- | --------------------- |
| system    | Initial agent instruction | [SYSTEM]       | No (only at creation) |
| user      | User input                | [USER]         | No                    |
| assistant | AI response               | [AGENT]        | No                    |

---

### 4.1 Visual Style Guidelines

- **No emojis** - Use text markers only
- **Status Markers**:
  - `[OK]` - Success operations
  - `[WARN]` - Warnings
  - `[ERROR]` - Errors
  - `[USER]` - User messages
  - `[AGENT]` - Agent responses
  - `[SYSTEM]` - System prompts
  - `[INFO]` - Informational messages
- **Separators**: Lines of 40-50 dashes (`----------------------------------------`)
- **Headers**: Centered text with decorative borders
- **Input Prompts**: Clear instructions with default values in parentheses

### 4.2 Main Menu

#### 4.2.1 Display Format

```
============================================================
       AI CHAT CLI - Консольный чат с AI агентами
============================================================

--- МЕНЮ ---
1. Новый чат
2. Выбрать чат
3. Вернуться в чат: {chat_name}|(нет активного чата)
4. Выход
----------------------------------------

Ваш выбор (1-4):
```

#### 4.2.2 Dynamic Behavior

- Option 3 label changes based on `current_chat_id` state:
  - If active chat exists: `Вернуться в чат: {chat_name}`
  - If no active chat: `Вернуться в чат (нет активного чата)`

#### 4.2.3 Input Validation

- Accept only integers 1-4
- Invalid input: Display `[ERROR] Неверный выбор. Введите число от 1 до 4.` and re-prompt
- Empty input: Re-prompt without error message

### 4.3 Chat List Display (Select Chat Option)

#### 4.3.1 Display Format

```
--- ВАШИ ЧАТЫ ---
{index}. {chat_name}
   Сообщений: {count} | Последнее: {timestamp}
   Превью: {preview_text}
   ID: {short_id}
----------------------------------------

Выберите чат (1-{n}):
```

#### 4.3.2 Preview Logic

| Condition                   | Preview Text                           |
| --------------------------- | -------------------------------------- |
| No messages array           | `(нет сообщений)`                      |
| Only system message         | `(нет сообщений)`                      |
| Has user/assistant messages | First 50 chars of last message content |
| Message > 50 chars          | Truncate with `...`                    |

#### 4.3.3 Empty State

If no chats exist:

```
Нет доступных чатов. Создайте новый.

--- МЕНЮ ---
```

### 4.4 Chat Creation Workflow

#### 4.4.1 Step 1: Name Input

```
--- СОЗДАНИЕ НОВОГО ЧАТА ---
Введите название чата (по умолчанию 'Чат {N}'):
```

- Default naming: `Чат 1`, `Чат 2`, etc. (incremental counter)
- Empty input: Use default name
- Max length: 100 characters (truncate if exceeded)

#### 4.4.2 Step 2: System Prompt

```
Введите системный промпт (Enter для пропуска):
```

- Empty input: Skip, no system message added
- Non-empty: Add to messages array as `{"role": "system", "content": "{input}"}`
- Multi-line: Not supported (single line only)

#### 4.4.3 Step 3: Model Selection

```
--- НАСТРОЙКИ АГЕНТА ---

Выберите модель:
  1. GPT OSS 120B (gpt-oss-120b/latest)
  2. Qwen3.6-35B (qwen3.6-35b-a3b/latest)
  3. Alice AI LLM Flash (aliceai-llm-flash/latest)

Ваш выбор (1-3):
```

- Invalid input: Re-prompt with `[ERROR] Неверный выбор модели.`
- Default: No default, must select

#### 4.4.4 Step 4: Temperature

```
Температура (0.0 - 2.0, Enter для отключения):
```

- Valid range: 0.0 to 2.0 (inclusive)
- Empty input: Set to `None` (disabled)
- Invalid number: Set to `None` with warning `[WARN] Некорректное значение. Температура отключена.`
- Out of range: Set to `None` with warning `[WARN] Значение вне диапазона. Температура отключена.`

#### 4.4.5 Step 5: Top P

```
Top P (0.0 - 1.0, Enter для отключения):
```

- Valid range: 0.0 to 1.0 (inclusive)
- Empty input: Set to `None` (disabled)
- Invalid number: Set to `None` with warning
- Out of range: Set to `None` with warning

#### 4.4.6 Step 6: Top K

```
Top K (0 для отключения, по умолчанию 0):
```

- Valid: Non-negative integer
- Empty input: Default to 0 (disabled)
- Invalid: Default to 0 with warning

#### 4.4.7 Step 7: Reasoning Effort

```
Reasoning Effort:
  1. none
  2. low
  3. medium
  4. high

Ваш выбор (1-4, по умолчанию 1):
```

- Default: 1 (none)
- Invalid input: Default to 1

#### 4.4.8 Step 8: Context Window Size

```
Введите размер контекстного окна (Enter для 200k):
```

- Valid: Positive integer
- Empty input: Default to 200000 tokens
- Invalid number: Default to 200000 with warning `[WARN] Некорректное значение. Используется 200k.`
- Out of range (<=0): Default to 200000 with warning

#### 4.4.9 Step 9: Context Strategy Selection

```
--- ВЫБОР СТРАТЕГИИ УПРАВЛЕНИЯ КОНТЕКСТНЫМ ОКНОМ ---
1. DefaultStrategy (пересылка всех сообщений)
2. SummarizationStrategy (суммаризация истории)
3. KeyValueMemoryStrategy (JSON-суммаризация: цель, ограничения, предпочтения, решения, договоренности)
4. SlidingWindowStrategy (скользящее окно: последние N сообщений)

Выберите стратегию (1-4, по умолчанию 1):
```

- Default: 1 (DefaultStrategy)
- If strategy 2 or 3 selected, prompt for parameters:
  - `non_compressible_count` (default 2)
  - `buffer_size` (default 3)
- If strategy 4 selected, prompt for parameters:
  - `window_size` (default 10)
- Invalid input: Default to 1

#### 4.4.10 Completion Message

```
[OK] Чат '{name}' создан!
  ID: {short_id}
```

### 4.5 Chat Interaction Loop

#### 4.5.1 Display Header

```
--- ЧАТ: {chat_name} ---
Введите сообщение и нажмите Enter для отправки.
Команды:
  /menu - вернуться в меню
  /stop - остановить генерацию
  /settings - показать настройки и изменить их
  /summary - показать саммари диалога
  /info - показать информацию о чате (счетчики токенов)
  /branch - создать ветку текущего чата
  /help - показать список команд
----------------------------------------
```

#### 4.5.2 Message Flow

1. Display prompt
2. Wait for user input
3. If empty: Re-prompt
4. If command: Execute command handler
5. If text:
   - Display `[USER]: {message}`
   - Call backend agent
   - Display `[AGENT]: {response}`
   - Save to history
6. Repeat

#### 4.5.3 Commands Specification

##### `/menu`

- **Action**: Save current state, clear `current_chat_id`, return to Main Menu
- **Output**: None (direct transition)
- **Side Effects**: None

##### `/stop`

- **Action**: Interrupt current LLM generation (if active)
- **Output**: `Генерация остановлена.` if generation was active, or `Генерация не активна.` if idle
- **Side Effects**: Partial response may be saved

##### `/settings`

- **Action**: Execute `print_settings()` then prompt for change confirmation
- **Flow**:
  1. Display current settings using `print_settings()`
  2. Prompt: `Изменить настройки? (y/n):`
  3. If 'y': Execute `change_settings()` which prompts for all settings (same as creation workflow)
  4. If 'n' or other: Return to chat loop without changes
- **Output**: Current settings display, optionally followed by change prompts
- **Side Effects**: Settings updated only if user confirms with 'y'

##### `/help`

- **Action**: Display available commands
- **Output**:

```
--- ДОСТУПНЫЕ КОМАНДЫ ---
  /menu - вернуться в главное меню
  /stop - остановить текущую генерацию
  /settings - показать текущие настройки и изменить их
  /summary - показать саммари диалога
  /info - показать информацию о чате (счетчики токенов)
  /branch - создать ветку текущего чата (копируются настройки, история и саммари)
  /help - показать этот список команд
```

##### `/summary`

- **Action**: Display current conversation summary from active strategy
- **Output**:
  - If summary exists: Display the summary text
  - If no summary: Display `[INFO] Суммаризация еще не выполнялась.`
- **Side Effects**: None

##### `/info`

- **Action**: Display detailed chat statistics including token counts
- **Output**:

```
--- ИНФОРМАЦИЯ О ЧАТЕ ---
Название: {chat_name}
ID: {full_id}
Создан: {timestamp}
Сообщений: {count}
Стратегия: {strategy_type}
Токенов использовано:
  Prompt: {total_prompt_tokens}
  Completion: {total_completion_tokens}
  Всего: {total_tokens}
----------------------------------------
```

- **Side Effects**: None

##### `/branch`

- **Action**: Create a new chat branch copying current chat history and settings
- **Flow**:
  1. Prompt for branch name (default: `{current_name} (branch)`)
  2. Copy all messages, settings, and strategy from current chat
  3. Create new chat with copied data
  4. Ask if user wants to continue in new branch: `Продолжить в новой ветке? (y/n):`
  5. If 'y': Switch to new branch chat
  6. If 'n': Stay in current chat
- **Output**:
  - Success: `[OK] Ветка '{name}' создана!` with ID and message count
  - Continue prompt as described above
- **Side Effects**: New chat created in storage, optionally becomes active chat

#### 4.5.4 Error States

| Error             | Display                                                        | Recovery         |
| ----------------- | -------------------------------------------------------------- | ---------------- |
| Backend exception | `[ERROR] Ошибка: {message}`                                    | Return to prompt |
| Network timeout   | `[ERROR] Таймаут соединения`                                   | Return to prompt |
| Invalid command   | `[WARN] Неизвестная команда. Введите /help для списка команд.` | Return to prompt |

### 4.6 Settings Management

#### 4.6.1 Print Settings (`print_settings`)

```
--- ТЕКУЩИЕ НАСТРОЙКИ ---
Модель: {model_name}
Температура: {value}|отключена
Top P: {value}|отключен
Top K: {value}|отключен
Reasoning Effort: {effort}
Размер контекстного окна: {context_window_size}
Стратегия: {strategy_type}
----------------------------------------
```

#### 4.6.2 Change Settings (`change_settings`)

Same prompts as creation workflow (Section 4.4.3-4.4.9), but:

- Shows current value as hint
- Only changed settings are updated
- Confirmation: `[OK] Настройки обновлены!`

---

## 5. Comprehensive Use Cases

### UC-001: Create New Chat with All Settings

#### 5.1.1 Preconditions

- Application is running
- User is in Main Menu
- No active chat required

#### 5.1.2 Main Success Scenario

1. User selects option 1 (New Chat)
2. System displays name prompt
3. User enters "My Test Chat"
4. System displays system prompt input
5. User enters "You are a helpful assistant"
6. System displays model selection
7. User selects model 1
8. System prompts for temperature
9. User enters "0.7"
10. System prompts for Top P
11. User enters "0.9"
12. System prompts for Top K
13. User enters "40"
14. System prompts for reasoning effort
15. User selects "2" (low)
16. System creates chat with all settings
17. System displays success message with ID
18. System enters chat loop
19. Use case ends

#### 5.1.3 Alternative Flows

- **A1: Default Name**
  - Step 3: User presses Enter
  - System uses default "Чат N"

- **A2: Skip System Prompt**
  - Step 5: User presses Enter
  - No system message added to history

- **A3: Disable Temperature**
  - Step 9: User presses Enter
  - Temperature set to None

- **A4: Invalid Model Selection**
  - Step 7: User enters "5"
  - System displays error, re-prompts step 7

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
  - System displays "Нет доступных чатов. Создайте новый."
  - System returns to Main Menu

- **A2: Invalid Selection**
  - Step 4: User enters "0" or number > count
  - System displays error, re-prompts step 4

- **A3: Cancel Selection**
  - Step 4: User enters "q" or Ctrl+C
  - System returns to Main Menu

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

1. User observes option 3 shows "Вернуться в чат: {name}"
2. User selects option 3
3. System validates active chat exists
4. System enters chat loop for active chat
5. Use case ends

#### 5.3.3 Alternative Flows

- **A1: No Active Chat**
  - Step 1: Option 3 shows "(нет активного чата)"
  - Step 2: User selects option 3 anyway
  - System displays warning "[WARN] Нет активного чата."
  - System remains in Main Menu

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
4. System displays "[USER]: Hello, how are you?"
5. System sends message to backend agent
6. Backend calls LLM provider
7. LLM generates response
8. System displays "[AGENT]: {response}"
9. System saves both messages to history
10. System re-displays prompt
11. Use case ends

#### 5.4.3 Alternative Flows

- **A1: Empty Message**
  - Step 2: User presses Enter without text
  - System re-displays prompt without sending

- **A2: Backend Error**
  - Step 6: Backend raises exception
  - System displays "[ERROR] Ошибка: {message}"
  - System re-displays prompt

- **A3: Long Response**
  - Step 7: Response exceeds terminal width
  - System wraps text appropriately

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
3. System displays current settings
4. System executes `change_settings()`
5. System prompts for each setting
6. User changes temperature to "1.0"
7. User presses Enter for other settings (keep unchanged)
8. System updates settings in backend
9. System displays "[OK] Настройки обновлены!"
10. System returns to chat prompt
11. Use case ends

#### 5.5.3 Alternative Flows

- **A1: Cancel During Change**
  - Step 6: User presses Ctrl+C
  - System aborts changes
  - System returns to chat prompt

- **A2: Invalid Input During Change**
  - Step 6: User enters "abc"
  - System displays warning, disables parameter
  - Continues to next setting

#### 5.5.4 Postconditions

- Updated settings saved to chat
- Changes apply to future messages

---

### UC-006: Navigate to Menu from Chat

#### 5.6.1 Preconditions

- User is in chat interaction loop

#### 5.6.2 Main Success Scenario

1. User types "/menu"
2. System saves chat state
3. System clears active chat reference (optional)
4. System displays Main Menu
5. Use case ends

#### 5.6.3 Postconditions

- Chat preserved in backend storage
- User in Main Menu
- Chat may remain as "active" for quick return

---

### UC-007: Stop Ongoing Generation

#### 5.7.1 Preconditions

- User is in chat interaction loop
- Agent is currently generating response

#### 5.7.2 Main Success Scenario

1. User observes "Thinking..." indicator
2. User types "/stop"
3. System interrupts backend generation
4. System displays "Прервано пользователем."
5. System returns to prompt
6. Use case ends

#### 5.7.3 Alternative Flows

- **A1: No Active Generation**
  - Step 2: User types "/stop" when idle
  - System displays "[WARN] Генерация не активна."
  - System returns to prompt

#### 5.7.4 Postconditions

- Partial response may be saved
- User can send new message

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
  - System displays `[INFO] Суммаризация еще не выполнялась.`
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
2. System calculates total token usage from message history
3. System displays chat information header
4. System displays token statistics (prompt, completion, total)
5. System displays strategy type
6. System returns to prompt
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
2. System prompts for branch name with default
3. User enters name or accepts default
4. System creates new chat copying:
   - All messages
   - All settings
   - Context strategy with current state
5. System displays success message with ID and message count
6. System asks: `Продолжить в новой ветке? (y/n):`
7. User enters "y"
8. System switches to new branch chat
9. Use case ends

#### 5.11.3 Alternative Flows

- **A1: Stay in Current Chat**
  - Step 7: User enters "n"
  - System remains in current chat
  - Use case ends

- **A2: Custom Branch Name**
  - Step 3: User enters custom name
  - System uses provided name for new branch

#### 5.11.4 Postconditions

- New chat created with copied data
- Optionally: new chat becomes active chat
- Original chat preserved unchanged

---

## 6. Test Cases

### TC-001: Create Chat with Default Values

**Related UC**: UC-001

| Step | Action                      | Expected Result                        |
| ---- | --------------------------- | -------------------------------------- |
| 1    | Select "New Chat"           | Name prompt displayed                  |
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
| 1    | Select "New Chat"   | Name prompt                |
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

| Step | Action                | Expected Result               |
| ---- | --------------------- | ----------------------------- |
| 1    | Ensure no chats exist | Empty storage                 |
| 2    | Select "Выбрать чат"  | Message "Нет доступных чатов" |
| 3    | Verify navigation     | Returns to Main Menu          |

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
| 2    | Verify option 3   | Shows "(нет активного чата)" |
| 3    | Select option 3   | Warning displayed            |
| 4    | Verify state      | Remains in Main Menu         |

---

### TC-008: Return to Chat With Active Chat

**Related UC**: UC-003

| Step | Action                | Expected Result                 |
| ---- | --------------------- | ------------------------------- |
| 1    | Create or select chat | Chat loop entered               |
| 2    | Type "/menu"          | Main Menu displayed             |
| 3    | Verify option 3       | Shows "Вернуться в чат: {name}" |
| 4    | Select option 3       | Chat loop entered               |
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
| 3    | Verify content | All 4 commands listed  |
| 4    | Verify return  | Back to prompt         |

---

### TC-016: Unknown Command Handling

**Related UC**: UC-004

| Step | Action                  | Expected Result               |
| ---- | ----------------------- | ----------------------------- |
| 1    | Enter chat              | Prompt displayed              |
| 2    | Type "/unknown"         | Warning about unknown command |
| 3    | Suggestion to use /help | Displayed                     |
| 4    | Verify state            | Back to prompt                |

---

### TC-017: System Prompt in History

**Related UC**: UC-001

| Step | Action                         | Expected Result            |
| ---- | ------------------------------ | -------------------------- |
| 1    | Create chat with system prompt | Prompt entered             |
| 2    | Verify history                 | System message present     |
| 3    | Check role                     | Role = "system"            |
| 4    | Check display                  | Shown with [SYSTEM] prefix |

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
| 1    | Enter 150-char name | Name truncated to 100 |
| 2    | Verify storage      | Max 100 chars saved   |
| 3    | Verify display      | Truncated name shown  |

---

### TC-020: Concurrent Chat Operations

**Related UC**: UC-002, UC-003

| Step | Action          | Expected Result  |
| ---- | --------------- | ---------------- |
| 1    | Create Chat A   | Active = A       |
| 2    | Type "/menu"    | Main Menu        |
| 3    | Select Chat B   | Active = B       |
| 4    | Type "/menu"    | Main Menu        |
| 5    | Return to Chat  | Returns to B     |
| 6    | Verify A intact | Chat A unchanged |

---

## 7. Error Handling Matrix

| Error Type            | Trigger                  | Display Message                                                | Recovery Action  |
| --------------------- | ------------------------ | -------------------------------------------------------------- | ---------------- |
| InvalidMenuChoice     | Menu input not 1-4       | `[ERROR] Неверный выбор. Введите число от 1 до 4.`             | Re-prompt        |
| InvalidModelSelection | Model input not 1-3      | `[ERROR] Неверный выбор модели.`                               | Re-prompt        |
| InvalidTemperature    | Temp < 0 or > 2.0        | `[WARN] Значение вне диапазона. Температура отключена.`        | Set None         |
| NonNumericTemperature | Temp = "abc"             | `[WARN] Некорректное значение. Температура отключена.`         | Set None         |
| InvalidTopP           | TopP < 0 or > 1.0        | `[WARN] Значение вне диапазона. Top P отключен.`               | Set None         |
| EmptyChatList         | Select chat with 0 chats | `Нет доступных чатов. Создайте новый.`                         | Return to menu   |
| NoActiveChat          | Return to chat with none | `[WARN] Нет активного чата.`                                   | Stay in menu     |
| BackendException      | LLM provider error       | `[ERROR] Ошибка: {message}`                                    | Return to prompt |
| UnknownCommand        | Input "/xyz"             | `[WARN] Неизвестная команда. Введите /help для списка команд.` | Return to prompt |
| EmptyInput            | Chat prompt Enter        | (no message)                                                   | Re-prompt        |

---

## 8. Implementation Requirements

### 8.1 Coding Standards

- **Language**: Python 3.12+
- **Style**: PEP 8 compliant
- **Encoding**: UTF-8 for all I/O
- **Error Handling**: Try-catch around all backend calls
- **Logging**: Optional debug logging to file

### 8.2 Performance Requirements

- Menu render time: < 100ms
- Message send latency: < 500ms (excluding LLM response time)
- Chat list load: < 200ms for up to 100 chats

### 8.3 Security Considerations

- No sensitive data in logs
- Input sanitization for file paths
- No command injection via chat messages

### 8.4 Accessibility

- High contrast text (white on black)
- Clear error messages
- Consistent navigation patterns

---

## 9. Testing Strategy

### 9.1 Unit Tests

- Test individual functions: `print_menu()`, `get_user_input()`, `validate_temperature()`
- Mock backend calls
- Coverage target: 90%

### 9.2 Integration Tests

- Test complete workflows: UC-001 through UC-008
- Use temporary test storage
- Verify state transitions

### 9.3 End-to-End Tests

- Simulate user input via stdin
- Capture stdout for verification
- Test with real backend (mocked LLM)

### 9.4 Test Data

```json
{
  "test_chats": [
    {
      "name": "Test Empty",
      "messages": [],
      "settings": { "model": "test", "temperature": null }
    },
    {
      "name": "Test System Only",
      "messages": [{ "role": "system", "content": "Test prompt" }],
      "settings": { "model": "test" }
    },
    {
      "name": "Test With Messages",
      "messages": [
        { "role": "user", "content": "Hello" },
        { "role": "assistant", "content": "Hi there!" }
      ],
      "settings": { "model": "test", "temperature": 0.7 }
    }
  ]
}
```

### 9.5 Test Execution

```bash
# Run unit tests
pytest tests/unit/

# Run integration tests
pytest tests/integration/

# Run E2E tests
pytest tests/e2e/

# Generate coverage report
pytest --cov=cli --cov-report=html
```

---

## 10. Version History

| Version | Date       | Author       | Changes                                 |
| ------- | ---------- | ------------ | --------------------------------------- |
| 1.0     | 2026-09-13 | AI Assistant | Initial comprehensive specification     |
| 1.1     | 2026-09-13 | AI Assistant | Added detailed test cases, error matrix |

---

## 11. Appendix

### 11.1 Sample Session Log

```
============================================================
       AI CHAT CLI - Консольный чат с AI агентами
============================================================

--- МЕНЮ ---
1. Новый чат
2. Выбрать чат
3. Вернуться в чат (нет активного чата)
4. Выход
----------------------------------------

Ваш выбор (1-4): 1

--- СОЗДАНИЕ НОВОГО ЧАТА ---
Введите название чата (по умолчанию 'Чат 1'): Мой первый чат
Введите системный промпт (Enter для пропуска): Ты полезный ассистент

--- НАСТРОЙКИ АГЕНТА ---
Выберите модель:
  1. GPT OSS 120B (gpt-oss-120b/latest)
  2. Qwen3.6-35B (qwen3.6-35b-a3b/latest)
  3. Alice AI LLM Flash (aliceai-llm-flash/latest)

Ваш выбор (1-3): 1
Температура (0.0 - 2.0, Enter для отключения): 0.7
Top P (0.0 - 1.0, Enter для отключения):
Top K (0 для отключения, по умолчанию 0): 40

Reasoning Effort:
  1. none
  2. low
  3. medium
  4. high

Ваш выбор (1-4, по умолчанию 1): 2

[OK] Чат 'Мой первый чат' создан!
  ID: a1b2c3d4...

--- ЧАТ: Мой первый чат ---
Введите сообщение и нажмите Enter для отправки.
Команды: /menu, /stop, /settings, /help
----------------------------------------

[USER]: Привет!
[AGENT]: Здравствуйте! Чем я могу помочь?

[USER]: /settings

--- ТЕКУЩИЕ НАСТРОЙКИ ---
Модель: GPT OSS 120B
Температура: 0.7
Top P: отключен
Top K: 40
Reasoning Effort: low
----------------------------------------

Изменить температуру (0.0-2.0, Enter без изменений):
...

[USER]: /menu

--- МЕНЮ ---
1. Новый чат
2. Выбрать чат
3. Вернуться в чат: Мой первый чат
4. Выход
----------------------------------------
```

### 11.2 Configuration File Example

```json
{
  "cli": {
    "max_preview_length": 50,
    "max_name_length": 100,
    "default_top_k": 0,
    "default_reasoning_effort": "none"
  },
  "models": [
    { "id": "gpt-oss-120b/latest", "name": "GPT OSS 120B" },
    { "id": "qwen3.6-35b-a3b/latest", "name": "Qwen3.6-35B" },
    { "id": "aliceai-llm-flash/latest", "name": "Alice AI LLM Flash" }
  ]
}
```

### 11.3 Glossary

- **Backend**: The `agents.py` module managing chat state and LLM communication
- **CLI**: Command Line Interface implemented in `cli.py`
- **Chat Loop**: Interactive mode where user exchanges messages with AI
- **Main Menu**: Top-level navigation screen
- **Active Chat**: Currently selected chat session in CLI memory
- **Preview**: Short excerpt of last message shown in chat list
