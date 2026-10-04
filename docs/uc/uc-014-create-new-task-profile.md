# UC-014: Create New Task Profile

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- Application is running
- User initiated profile creation from Task Profiles menu

## Main Success Scenario

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

## Alternative Flows

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

## Postconditions

- New TaskProfile created with unique UUID
- Profile saved to repository with empty facts list
- Profile saved with preferences (may be empty string)
- User returned to Task Profiles menu

## Related Test Cases

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
**Also related to**: UC-015 (cross-referenced)

**Precondition**: User is creating a new task profile

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter name and description                    | Preferences prompt displayed                 |
| 2    | Press Enter without entering preferences      | Empty preferences accepted (no error)        |
| 3    | Complete profile creation                     | Profile saved with empty preferences         |
| 4    | View created profile                          | The `Предпочтения:` line is omitted entirely |

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
