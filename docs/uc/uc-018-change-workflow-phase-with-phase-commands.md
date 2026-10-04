# UC-018: Change Workflow Phase With Phase Commands

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- User is in chat interaction loop
- Agent has a current workflow phase (new chats start in `PLAN`; a chat loaded from storage restores its saved phase)

## Main Success Scenario

1. User types `/execute` while the agent is in phase PLAN
2. System transitions the phase via `Agent.handle_phase_command` (§4.5.3)
3. System displays `[INFO] Фаза изменена: PLAN -> EXECUTE`
4. System displays the updated header line `--- ЧАТ: {name} [Фаза: EXECUTE] ---`
5. System returns to the chat prompt; subsequent messages are processed in the new phase
6. Use case ends

## Alternative Flows

- **A1: Forward Skip Rejected**
  - Step 1: From PLAN the user enters `/validate` or `/report` (or from EXECUTE — `/report`)
  - The transition is rejected: `[INFO] Нельзя перескочить этап: переход из {OLD} сразу в {NEW} запрещен` followed by the unchanged header line `--- ЧАТ: {name} [Фаза: {OLD}] ---`
  - The phase is NOT changed; the chat loop continues

- **A2: Backward Transition Allowed**
  - Step 1: From any phase the user enters a command of an earlier phase (e.g. `/plan` while in VALIDATE)
  - Any backward transition is allowed: `[INFO] Фаза изменена: {OLD} -> PLAN`, header updated

- **A3: Case-Insensitive Command**
  - Step 1: User enters the command in uppercase/mixed case (e.g. `/EXECUTE`)
  - Commands are matched case-insensitively; the transition succeeds exactly as in the main scenario

- **A4: Phase Visible In Chat Header And /info**
  - After any successful transition: entering the chat loop replays the header `--- ЧАТ: {name} [Фаза: {PHASE}] ---` (§4.5.1) and `/info` shows the lowercase phase value `Текущая фаза: {plan|execute|validate|report}` (§4.5.3 `/info`)

## Postconditions

- On accepted transition: `Agent.current_phase` equals the target phase; the change is persisted with the agent (auto-save)
- On rejected transition: phase unchanged
- No messages are added to history by phase commands

## Related Test Cases

### TC-096: Phase Command - Forward Transition PLAN to EXECUTE

**Related UC**: UC-018 (main success scenario)

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Open a newly created chat                     | Header shows `--- ЧАТ: {name} [Фаза: PLAN] ---` (new chats start in PLAN) |
| 2    | Enter `/execute`                              | `[INFO] Фаза изменена: PLAN -> EXECUTE` displayed |
| 3    | Verify header                                 | Updated line `--- ЧАТ: {name} [Фаза: EXECUTE] ---` shown |
| 4    | Enter `/validate`                             | `[INFO] Фаза изменена: EXECUTE -> VALIDATE` (sequential forward transition allowed) |
| 5    | Send a regular message                        | Message processed normally in the new phase; chat loop continues |

---

### TC-097: Phase Command - Forward Skip Rejected

**Related UC**: UC-018 A1

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | In a chat in phase PLAN enter `/validate`     | `[INFO] Нельзя перескочить этап: переход из PLAN сразу в VALIDATE запрещен` (UC-018 A1) |
| 2    | Verify header unchanged                       | `--- ЧАТ: {name} [Фаза: PLAN] ---` displayed after the rejection |
| 3    | From PLAN enter `/report`                     | Same rejection message; phase remains PLAN   |
| 4    | Advance to EXECUTE (`/execute`), then enter `/report` | Rejection message `из EXECUTE сразу в REPORT`; phase remains EXECUTE |

---

### TC-098: Phase Command - Backward Transition Allowed

**Related UC**: UC-018 A2

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Advance the chat phase through `/execute`, `/validate` | Phase is VALIDATE                          |
| 2    | Enter `/plan`                                 | `[INFO] Фаза изменена: VALIDATE -> PLAN` (any backward transition allowed, UC-018 A2) |
| 3    | Verify header                                 | `--- ЧАТ: {name} [Фаза: PLAN] ---`           |
| 4    | From PLAN enter `/execute`, then `/plan` again | Backward transition EXECUTE -> PLAN succeeds |

---

### TC-099: Phase Command - Case Insensitive Matching

**Related UC**: UC-018 A3

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | In phase PLAN enter `/EXECUTE`                | `[INFO] Фаза изменена: PLAN -> EXECUTE` (commands matched case-insensitively, UC-018 A3) |
| 2    | In phase EXECUTE enter `/Validate`            | `[INFO] Фаза изменена: EXECUTE -> VALIDATE`  |
| 3    | Verify header after each step                 | Header reflects the new phase                |

---

### TC-100: Phase Visible In Header And /info

**Related UC**: UC-018 A4

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter `/execute`, then return to menu via `/menu` | Phase changed to EXECUTE before exiting the loop |
| 2    | Return to the chat (option 5)                 | Header replayed as `--- ЧАТ: {name} [Фаза: EXECUTE] ---` (UC-018 A4, §4.5.1) |
| 3    | Enter `/info`                                 | Line `Текущая фаза: execute` displayed (lowercase phase value) |

---
