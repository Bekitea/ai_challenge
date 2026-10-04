# UC-017: Delete Task Profile

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- Application is running
- User is in the profiles list submenu (Task Profiles menu → option 2 → action 3)
- At least one task profile exists

## Main Success Scenario

1. System displays prompt: `Выберите профиль для удаления (1-{n}):`
2. User selects profile by index
3. System checks whether the profile is linked to any agents (`is_profile_linked_to_agents`)
4. If not linked, system prompts for confirmation: `Вы уверены, что хотите удалить профиль '{name}'? (y/n):`
5. If user confirms with 'y':
   - System deletes profile from TaskProfileRepository
   - Display success: `[OK] Профиль '{name}' успешно удалён.`
6. If user declines (any input other than `y`):
   - Display `[INFO] Удаление отменено.`
7. If deletion fails: `[ERROR] Не удалось удалить профиль '{name}'.`
8. System returns to Task Profiles menu
9. Use case ends

## Alternative Flows

- **A1: Invalid Profile Selection**
  - Step 2: Out-of-range number → `Введите число от 1 до {n}`; non-numeric → `Введите корректное число`; re-prompt until valid

- **A2: Confirmation Declined**
  - Step 5: User enters anything other than `y`
  - Deletion cancelled with `[INFO] Удаление отменено.`, return to menu

- **A3: Profile Attached to Agents (deletion blocked)**
  - Step 3: System detects attached agents; deletion is NOT offered at all:
    ```
    [WARN] Невозможно удалить профиль '{name}': он привязан к одному или нескольким агентам.
    Сначала удалите или пересоздайте агентов, использующих этот профиль.
    ```
  - Operation aborts, return to the Task Profiles menu

## Postconditions

- If confirmed and unlinked: TaskProfile deleted from repository
- If declined or linked to agents: Profile remains unchanged
- User returned to Task Profiles menu

## Related Test Cases

### TC-057: Delete Task Profile - Not Attached

**Related UC**: UC-017 (steps 4–6)

**Precondition**: Task profile exists, not attached to any agents

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 3 (Delete) | Profile selection prompt `Выберите профиль для удаления (1-{n}):` displayed |
| 2    | Select profile by index                       | Confirmation prompt: `Вы уверены, что хотите удалить профиль '{name}'? (y/n):` |
| 3    | Enter 'y'                                     | `[OK] Профиль '{name}' успешно удалён.`      |
| 4    | Verify deletion                               | Profile no longer in repository              |
| 5    | Verify return                                 | Control returns to the Task Profiles menu    |

---

### TC-058: Delete Task Profile - Attached to Agents

**Related UC**: UC-017 A3

**Precondition**: Task profile exists, attached to 2 agents

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 3   | Select profile                               |
| 2    | Verify block message                          | `[WARN] Невозможно удалить профиль '{name}': он привязан к одному или нескольким агентам.` + `Сначала удалите или пересоздайте агентов, использующих этот профиль.` — NO confirmation prompt |
| 3    | Verify profile not deleted                    | Profile still in repository                  |
| 4    | Verify agents unchanged                       | Agents keep their task_profile_id link       |

---

### TC-059: Delete Task Profile - Cancelled

**Related UC**: UC-017 A2

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 3   | Select profile (profile must be unlinked)    |
| 2    | Confirmation prompt displayed                 | Enter 'n'                                    |
| 3    | Verify cancellation                           | `[INFO] Удаление отменено.`                  |
| 4    | Verify profile exists                         | Profile still in repository                  |

---

### TC-093: Delete Task Profile - Invalid Selection Re-Prompts

**Related UC**: UC-017 A1

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | From profiles list submenu, select action 3 (Delete) | Prompt `Выберите профиль для удаления (1-{n}):` displayed |
| 2    | Enter out-of-range number                     | `Введите число от 1 до {n}`; selection re-prompted (UC-017 A1) |
| 3    | Enter "abc"                                   | `Введите корректное число`; selection re-prompted |
| 4    | Enter a valid index                           | Confirmation prompt displayed for the chosen profile |


