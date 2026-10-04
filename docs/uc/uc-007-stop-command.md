# UC-007: Stop Command

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- User is in chat interaction loop

## Main Success Scenario

1. User types "/stop"
2. System displays `[INFO] Генерация не активна.` (in the synchronous implementation generation is never active while input is being read)
3. System exits the chat loop and returns to Main Menu
4. Use case ends

## Postconditions

- Chat remains the active chat (option 5 can return to it)
- User is in Main Menu
- Per the UC-004 exit rule, the agent memory is saved on exiting the chat loop via `/stop`

## Related Test Cases

### TC-019: Stop Command When Idle

**Related UC**: UC-007

| Step | Action                       | Expected Result                                          |
| ---- | ---------------------------- | ---------------------------------------------------------- |
| 1    | Enter chat                   | Prompt displayed                                         |
| 2    | Type "/stop" (no generation) | `[INFO] Генерация не активна.` displayed                 |
| 3    | Verify state                 | Chat loop exits, Main Menu displayed (UC-007 step 3)     |

---

### TC-034: Stop Command Keeps Active Chat

**Related UC**: UC-007 (postconditions)

| Step | Action                        | Expected Result                                        |
| ---- | ----------------------------- | ------------------------------------------------------ |
| 1    | In chat loop, type "/stop"    | `[INFO] Генерация не активна.` displayed               |
| 2    | Verify navigation             | Chat loop exits, Main Menu displayed                   |
| 3    | Verify active chat            | Option 5 still shows "Вернуться в чат: {name}"         |

---

### TC-035: Stop Command Preserves Chat State

**Related UC**: UC-007 (postconditions), UC-003
**Also related to**: UC-003 (cross-referenced)

| Step | Action                        | Expected Result                                          |
| ---- | ----------------------------- | -------------------------------------------------------- |
| 1    | Send a message in chat        | Exchange saved to history                                |
| 2    | Type "/stop" at any moment    | `[INFO] Генерация не активна.` displayed                 |
| 3    | Verify return to menu         | Main Menu displayed                                      |
| 4    | Select option 5 (Return to Chat) | Same chat reloaded with the exchange intact          |

---
