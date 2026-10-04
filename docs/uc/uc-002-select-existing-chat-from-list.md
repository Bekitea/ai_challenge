# UC-002: Select Existing Chat from List

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- At least one chat exists in storage
- User is in Main Menu

## Main Success Scenario

1. User selects option 2 (Select Chat)
2. System retrieves all chats from backend
3. System displays numbered list with previews
4. User selects chat number 2
5. System loads chat into active state
6. System displays chat header
7. System enters chat loop
8. Use case ends

## Alternative Flows

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

## Postconditions

- Selected chat becomes active chat
- Full message history loaded
- User in chat interaction loop

## Related Test Cases

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

### TC-122: Concurrent Chat Operations

**Related UC**: UC-002 (main success scenario), UC-003 (main success scenario)
**Also related to**: UC-003 (cross-referenced)

| Step | Action          | Expected Result  |
| ---- | --------------- | ---------------- |
| 1    | Create Chat A   | Active = A       |
| 2    | Type "/menu"    | Main Menu        |
| 3    | Select option 2, choose Chat B   | Active = B       |
| 4    | Type "/menu"    | Main Menu        |
| 5    | Select option 5 (Return to Chat)  | Returns to B     |
| 6    | Verify A intact | Chat A unchanged |

---
