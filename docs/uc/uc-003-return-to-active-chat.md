# UC-003: Return to Active Chat

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- An active chat exists in CLI state
- User is in Main Menu

## Main Success Scenario

1. User observes option 5 shows "Вернуться в чат: {name}"
2. User selects option 5
3. System validates active chat exists
4. System enters chat loop for active chat
5. Use case ends

## Alternative Flows

- **A1: No Active Chat**
  - Step 1: Option 5 shows `Вернуться в чат (нет активного чата)`
  - Step 2: User selects option 5 anyway
  - System displays `[WARN] Нет активного чата. Выберите или создайте чат.`
  - System remains in Main Menu

- **A2: KeyboardInterrupt / EOFError At Menu Prompt**
  - Any step: User presses Ctrl+C or the input stream ends at `Ваш выбор (1-6):`
  - System prints `До свидания!` and terminates the application cleanly (same as option 6)

## Postconditions

- Same active chat remains active
- User in chat interaction loop

## Related Test Cases

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

### TC-095: Return To Active Chat - Ctrl+C At Menu Prompt

**Related UC**: UC-003 A2

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | In Main Menu press Ctrl+C at `Ваш выбор (1-6):` (or feed end of input — EOFError) | System handles the exception at the menu prompt (UC-003 A2) |
| 2    | Verify exit message                           | `До свидания!` printed                        |
| 3    | Verify termination                            | Application terminates cleanly, no traceback  |

---

### TC-119: Return To Active Chat After EOF At Menu Prompt

**Related UC**: UC-003 A2

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Create a chat, return to Main Menu via `/menu`                   | Option 5 shows `Вернуться в чат: {name}`                                                 |
| 2    | Feed end of input (EOF) at `Ваш выбор (1-6):` without selecting an option | `До свидания!` printed; application terminates cleanly (UC-003 A2)                        |
| 3    | Restart the application                                         | The chat from step 1 is still present and selectable via option 2                       |

---
