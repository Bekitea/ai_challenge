# UC-016: Manage Task Profile Invariants

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

This use case covers adding, listing and removing the strict invariants of a task
profile. Profile deletion is covered separately in
[UC-017](uc-017-delete-task-profile.md).

## Preconditions

- Application is running
- User is in the profiles list submenu (Task Profiles menu → option 2 → action 2)
- At least one task profile exists

## Main Success Scenario

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

## Alternative Flows

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

## Postconditions

- Invariants list updated in the profile storage
- User returned to the Task Profiles menu

## Related Test Cases

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

### TC-111: Manage Invariants - Removal Failure Message

**Related UC**: UC-016 A2

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Open invariants management with existing invariants, choose action "remove" (UC-016 step 9) | Removal prompt `Выберите номер инварианта для удаления (1-{n}):` displayed |
| 2    | Arrange the repository removal to fail for a syntactically valid number | `[ERROR] Не удалось удалить инвариант.` displayed; the invariant remains in the list (UC-016 A2) |
| 3    | Enter a valid number for a removable invariant | `[OK] Инвариант удалён!`; updated list shown |

---
