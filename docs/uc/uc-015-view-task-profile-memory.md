# UC-015: View Task Profile Memory

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- Application is running
- User is in the profiles list submenu (Task Profiles menu → option 2 → action 1)
- At least one task profile exists

## Main Success Scenario

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

## Alternative Flows

- **A1: Invalid Profile Selection**
  - Step 2: Out-of-range number → `Введите число от 1 до {n}`; non-numeric → `Введите корректное число`; re-prompt until valid

- **A2: Empty Memory**
  - Step 5: Repository returns empty facts list
  - Display `(память пуста)` instead of fact list

- **A3: Profile Not Found**
  - Step 3: `get_task_profile_memory` returns None
  - Display `[ERROR] Профиль не найден.` and return to the Task Profiles menu

## Postconditions

- User viewed task profile details, memory facts and invariants
- Returned to Task Profiles menu

## Related Test Cases

### TC-055: View Task Profile Memory - With Facts

**Related UC**: UC-015

**Precondition**: Task profile exists with at least 2 facts in memory

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 1 (View memory) | Profile selection prompt `Выберите профиль (1-{n}):` displayed |
| 2    | Select profile by index                       | `--- ИНФОРМАЦИЯ О ПРОФИЛЕ ЗАДАЧИ ---`: ID, Название, Описание, Дата создания (+ Предпочтения if non-empty) |
| 3    | Verify memory section                         | `--- ПАМЯТЬ ПРОФИЛЯ ---` header + numbered facts; `--- ИНВАРИАНТЫ ---` section shown |
| 4    | Verify return                                 | Control returns to the Task Profiles menu    |

---

### TC-056: View Task Profile Memory - Empty State

**Related UC**: UC-015 A2

**Precondition**: Task profile exists with empty facts list

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 1   | Select profile                               |
| 2    | Verify memory display                         | `(память пуста)` shown instead of facts (UC-015 A2); `(инварианты не заданы)` if no invariants |
| 3    | Verify return                                 | Return to the Task Profiles menu             |

---

### TC-092: View Task Profile Memory - Profile Not Found

**Related UC**: UC-015 A3

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Arrange `get_task_profile_memory` to return None for the selected profile | Action 1 chosen from the profiles list submenu |
| 2    | Verify error                                  | `[ERROR] Профиль не найден.` displayed        |
| 3    | Verify navigation                             | Control returns to the Task Profiles menu     |

---

### TC-094: View Task Profile Memory - Invalid Selection Re-Prompts

**Related UC**: UC-015 A1

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 1 (View memory) | Prompt `Выберите профиль (1-{n}):` displayed |
| 2    | Enter out-of-range number                     | `Введите число от 1 до {n}`; selection re-prompted (UC-015 A1) |
| 3    | Enter "abc"                                   | `Введите корректное число`; selection re-prompted (UC-015 A1) |
| 4    | Enter a valid index                           | Profile information and memory are displayed  |

---

### TC-066: Preferences Display in View Profile - With Preferences

**Related UC**: UC-015 (step 6)

**Precondition**: Task profile exists with non-empty preferences text

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Navigate to Task Profiles menu, select "View memory" | Profile selection prompt displayed           |
| 2    | Select profile with preferences               | Profile details displayed                    |
| 3    | Verify preferences display                    | `Предпочтения: {preferences_text}` shown     |

---

### TC-067: Preferences Display in View Profile - Empty Preferences

**Related UC**: UC-015 (step 6, §4.7.3)

**Precondition**: Task profile exists with empty preferences

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Navigate to Task Profiles menu, select "View memory" | Profile selection prompt displayed           |
| 2    | Select profile with empty preferences         | Profile details displayed                    |
| 3    | Verify preferences display                    | The `Предпочтения:` line is omitted entirely (no placeholder like `(не указаны)`) |

---
