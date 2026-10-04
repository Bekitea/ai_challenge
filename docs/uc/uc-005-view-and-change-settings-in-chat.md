# UC-005: View and Change Settings In-Chat

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- User is in chat interaction loop
- Chat has existing settings

## Main Success Scenario

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

## Alternative Flows

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

## Postconditions

- Updated settings saved to chat
- Changes apply to future messages

## Related Test Cases

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


