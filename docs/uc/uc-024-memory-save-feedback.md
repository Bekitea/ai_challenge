# UC-024: Memory Save Feedback

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- Global/task-profile memory extraction (`save_agent_memory`) is potentially
  slow (LLM calls), so the user must be told when it starts and finishes.

## Main Success Scenario — Chat Exit

1. User leaves the chat loop (`/menu`, Ctrl+C or EOF)
2. System displays the usual exit line (`Возврат в меню...` or
   `Прервано пользователем.`)
3. System displays `[INFO] Сохранение памяти чата '{name}'...`
4. System fills global and task-profile memory via the `save_agent_memory`
   use case (single timed operation)
5. On success system displays
   `[OK] Память чата '{name}' сохранена за {seconds:.2f} с.`
6. System exits the chat loop and returns to the Main Menu
7. Use case ends

## Main Success Scenario — Application Start

1. On application start, **before the application header is printed**, the
   system displays `[INFO] Проверка несохранённой памяти...`
2. The system collects all agents with unsaved memory (see UC-004 exit rule).
   This scan MUST NOT restore MCP connections or otherwise hydrate agents that
   have no unremembered messages (startup performance)
3. If there are none, the system displays `[INFO] Несохранённой памяти нет.`
4. Otherwise, for every agent with unsaved memory, the system displays
   `[INFO] Сохранение памяти чата '{name}'...`, fills its memory via the
   `save_unsaved_memories` use case and prints the per-chat result:
   - `[OK] '{name}': сохранено за {seconds:.2f} с.`
   - `[ERROR] '{name}': не удалось за {seconds:.2f} с: {error}`
5. A failure of one chat MUST NOT stop processing of the remaining chats
6. The system displays `[INFO] Проверка памяти завершена за {seconds:.2f} с.`
   and only then prints the application header and the Main Menu
7. Use case ends

Each LLM call that extracts memory (global, task-profile and dialogue task
memory) uses `MEMORY_LLM_TIMEOUT` (`5` s by default) with
`MEMORY_LLM_MAX_RETRIES` (`0` by default), so the limit is not multiplied by
SDK retries. If any memory call for a chat times out, the remaining memory
calls for that chat are NOT performed (a timeout of the dialogue task memory
stops global/profile extraction, and vice versa). A timeout while updating the
dialogue task memory displays `[WARN] Не удалось обновить память задачи: {error}`
(via the `on_memory_warning` callback). At application start a timeout during
global/profile extraction aborts the whole series (circuit breaker): the
remaining chats are skipped and the system displays
`[WARN] Сохранение памяти прервано из-за таймаута модели; пропущено чатов: {n}.`

## Alternative Flows

- **A1: Chat memory save fails (chat exit)**
  - Step 4 of the exit flow: `save_agent_memory` raises
  - System displays
    `[ERROR] Не удалось сохранить память чата '{name}' за {seconds:.2f} с: {error}`
    and still exits the chat loop to the Main Menu

- **A2: Startup batch fails entirely**
  - Step 4 of the start flow: `save_unsaved_memories` itself raises
  - System displays `[ERROR] Не удалось сохранить память при старте: {error}`,
    then `[INFO] Проверка памяти завершена за {seconds:.2f} с.` and continues
    to the Main Menu

## Postconditions

- The user always sees a start notice and a timed finish (or error) notice
  whenever memory filling actually runs
- At application start the feedback is reported separately for each chat
- Memory filling itself is unchanged: only global and task-profile facts are
  extracted; a timing is measured around the whole `agent.save_memory()` call

## Related Test Cases

### TC-146: Memory Save Feedback On Chat Exit

**Related UC**: UC-024 (chat exit), UC-006

| Step | Action                                                    | Expected Result                                                              |
| ---- | --------------------------------------------------------- | ---------------------------------------------------------------------------- |
| 1    | Enter a chat, send a message, type `/menu`                | `Возврат в меню...` followed by `[INFO] Сохранение памяти чата '{name}'...` |
| 2    | Verify finish notice                                      | `[OK] Память чата '{name}' сохранена за {seconds:.2f} с.` displayed           |
| 3    | Verify Main Menu                                          | Chat loop exited, Main Menu displayed                                        |

---

### TC-147: Memory Save Feedback On Application Start (per chat)

**Related UC**: UC-024 (application start), UC-004 A4

| Step | Action                                                             | Expected Result                                                              |
| ---- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| 1    | Create chat `A`, send a message, type `/stop` (exits without save) | Chat `A` keeps unremembered prompts                                          |
| 2    | End the process, start the application again                       | `[INFO] Проверка несохранённой памяти...` displayed, then `[INFO] Сохранение памяти чата 'A'...` before the Main Menu |
| 3    | Verify per-chat result                                             | `[OK] 'A': сохранено за {seconds:.2f} с.` displayed                           |
| 4    | Repeat with two chats `A` and `B`                                  | Both per-chat start and result lines displayed, one pair per chat            |

---

### TC-148: Empty Chat Is Not Unsaved Memory

**Related UC**: UC-024 (application start), UC-004 A4

| Step | Action                                                             | Expected Result                                                              |
| ---- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| 1    | Create a chat and immediately leave its loop via `/stop` (no messages) | The chat keeps `is_dialog_remembered == False` but has no unremembered messages |
| 2    | End the process, start the application again                       | `[INFO] Проверка несохранённой памяти...` and `[INFO] Несохранённой памяти нет.` displayed |
| 3    | Verify no spurious save                                            | No `[INFO] Сохранение памяти чата '...'` line displayed; startup is not blocked by MCP restore |

---
