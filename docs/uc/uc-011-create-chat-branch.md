# UC-011: Create Chat Branch

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- User is in chat interaction loop
- Current chat has at least one message

## Main Success Scenario

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

## Alternative Flows

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

## Postconditions

- New chat created in storage with copied data
- `current_agent` points to the branch chat
- Original chat preserved unchanged

## Related Test Cases

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
