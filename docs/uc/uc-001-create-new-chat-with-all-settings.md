# UC-001: Create New Chat with All Settings

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- Application is running
- User is in Main Menu
- No active chat required

## Main Success Scenario

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

## Alternative Flows

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

## Postconditions

- New chat created in backend storage
- Chat becomes active chat
- User in chat interaction loop

## Related Test Cases

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
**Also related to**: UC-004 (cross-referenced)

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

### TC-120: Quick Creation Default Name Counter

**Related UC**: UC-001 A1, UC-001 A3

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Ensure exactly 2 chats exist in storage                          | Main Menu displayed                                                                    |
| 2    | Select option 1 (New Chat), press Enter at the configure prompt (default "n") | `Используются настройки по умолчанию.` printed (UC-001 A1)                  |
| 3    | Verify completion message                                       | `[OK] Чат 'Чат 3' создан!` — auto-generated name uses N = existing chats + 1 (UC-001 A3) |
| 4    | Verify chat settings                                            | Defaults applied (`aliceai-llm-flash/latest`, disabled temperature/top_p/top_k, DefaultStrategy, no profile) |

---
