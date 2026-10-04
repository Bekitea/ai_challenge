# UC-013: View Task Profiles List from Menu

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- Application is running
- User is in Main Menu
- No active chat required

## Main Success Scenario

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

## Alternative Flows

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

## Postconditions

- User viewed task profiles list (or empty state)
- Optionally viewed memory, managed invariants, or deleted a profile
- Returned to the Task Profiles menu / Main Menu when requested

## Related Test Cases

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

### TC-116: Profiles List Submenu Non-Numeric Action Re-Prompts

**Related UC**: UC-013 A4

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Open profiles list with at least one profile                     | Actions block and prompt `Выберите действие (1-4):` displayed                            |
| 2    | Enter "abc" (non-numeric)                                       | `[WARN] Неверный выбор, попробуйте снова.` displayed; action prompt re-displayed (UC-013 A4) |
| 3    | Enter "0"                                                       | Same warning; action prompt re-displayed                                                |
| 4    | Enter "4" (Back to list)                                        | Control returns to the Task Profiles menu                                               |

---
