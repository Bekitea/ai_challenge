# UC-004: Send Message and Receive Response

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- User is in chat interaction loop
- Chat has valid model configuration

## Main Success Scenario

1. System displays chat header and prompt
2. User types "Hello, how are you?"
3. User presses Enter
4. System prints `[AGENT] печатает...` (cleared once the response arrives)
5. System sends message to backend agent (`send_message` use case)
6. Backend calls LLM provider
7. LLM generates response
8. System displays "[AGENT]: {response}"
9. System displays token lines if usage was reported: `  [Токены: prompt: {p}, completion: {c}]` and `  [Заполненность контекста: {prompt_tokens}/{context_window_size} ({percent:.1f}%)]` (the fill line is printed only when prompt_tokens is not None)
10. System saves both messages to history
11. System re-displays prompt
12. Use case ends

## Alternative Flows

- **A1: Empty Message**
  - Step 2: User presses Enter without text
  - System re-displays prompt without sending

- **A2: Unknown Slash-Command**
  - Step 2: User enters an unrecognized slash-command (e.g. "/xyz")
  - It is not intercepted as a command; it is sent to the agent as a regular message (main flow continues from step 4)

- **A3: Whitespace-Only Input**
  - Step 2: User enters only spaces/tabs
  - System re-displays the prompt without sending anything to the backend (same handling as A1)

- **A4: Context Window Exceeded**
  - Step 6: Backend raises `ContextWindowExceededError`
  - System clears the "печатает..." line, displays `[ERROR] {message}` followed by `Необходимо очистить историю сообщений или создать новый чат.`
  - System saves the agent memory via the `save_agent_memory` use case (memory must not be lost on abnormal exit)
  - System exits the chat loop and returns to Main Menu (the chat remains active for option 5)

- **A5: Any Other Backend Error**
  - Step 6: Any other exception is raised while sending/processing
  - System displays `[ERROR] Ошибка: {message}`
  - System saves the agent memory via the `save_agent_memory` use case, then exits the chat loop and returns to Main Menu

- **A6: KeyboardInterrupt During Exchange**
  - Any step: User presses Ctrl+C at the input prompt or during processing
  - System displays `Прервано пользователем.`, saves the agent memory via the `save_agent_memory` use case and exits the chat loop back to Main Menu

- **A7: EOFError (End Of Input)**
  - Step 1/2: The input stream ends (piped input exhausted or Ctrl+D)
  - The chat loop terminates gracefully without a traceback; the agent memory is saved before exit (same rule as A6)

- **A8: Long Response**
  - Step 8: Response exceeds terminal width
  - System wraps text appropriately

- **A9: Reasoning In Response**
  - After step 9: response carries reasoning content
  - System asks `Показать рассуждения модели? (y/n):`; on `y` it prints the indented `[Reasoning]:` block, otherwise nothing extra

## Postconditions

- Two new messages in history (user + assistant)
- Chat preview updated with last message
- On any exit from the chat loop (`/menu`, A4, A5, A6, A7) the agent memory is saved before returning to the Main Menu

## Related Test Cases

### TC-014: Send Multiple Messages

**Related UC**: UC-004

| Step | Action           | Expected Result           |
| ---- | ---------------- | ------------------------- |
| 1    | Enter chat       | Prompt displayed          |
| 2    | Send "Message 1" | Agent responds            |
| 3    | Send "Message 2" | Agent responds            |
| 4    | Send "Message 3" | Agent responds            |
| 5    | Return to menu   | Preview shows "Message 3" |
| 6    | Re-enter chat    | All 3 exchanges visible   |

---

### TC-015: Empty And Whitespace-Only Message Handling

**Related UC**: UC-004 A1, UC-004 A3

| Step | Action                          | Expected Result                              |
| ---- | ------------------------------- | -------------------------------------------- |
| 1    | Enter chat                      | Prompt displayed                             |
| 2    | Press Enter (empty)             | No send, re-prompt (UC-004 A1)               |
| 3    | Press Enter again               | No send, re-prompt                           |
| 4    | Enter "   " (spaces only)       | No send, re-prompt (UC-004 A3)               |
| 5    | Send valid message              | Normal flow resumes                          |

---

### TC-078: Token Statistics Lines After Response

**Related UC**: UC-004 (steps 4–11)

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Enter chat, send a message                                      | `[AGENT] печатает...` shown while processing, cleared on response                       |
| 2    | Verify response display                                         | `[AGENT]: {response}` printed; prompt re-displayed afterwards                            |
| 3    | Verify token line                                               | `  [Токены: prompt: {p}, completion: {c}]` displayed when usage reported                 |
| 4    | Verify context fill line                                        | `  [Заполненность контекста: {prompt_tokens}/{context_window_size} ({percent:.1f}%)]` displayed when prompt_tokens is not None |
| 5    | Verify history                                                  | Both user and assistant messages saved; chat preview updated with last message          |

---

### TC-079: Context Window Exceeded Error

**Related UC**: UC-004 A4

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Fill chat history until the backend raises `ContextWindowExceededError` | "печатает..." line cleared                                              |
| 2    | Verify error output                                             | `[ERROR] {message}` followed by `Необходимо очистить историю сообщений или создать новый чат.` |
| 3    | Verify navigation                                               | Chat loop exited, Main Menu displayed                                                   |
| 4    | Select option 5 (Return to Chat)                                | The same chat is still active and reachable (chat remains active)                        |

---

### TC-081: Keyboard Interrupt During Exchange

**Related UC**: UC-004 A6

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Enter chat loop                                                 | Prompt displayed                                                                        |
| 2    | Send Ctrl+C at the input prompt (or during processing)          | `Прервано пользователем.` displayed                                                      |
| 3    | Verify navigation                                               | Chat loop exited, Main Menu displayed; chat remains active                               |

---

### TC-082: Long Response Wrapping

**Related UC**: UC-004 A8

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Request a response longer than the terminal width               | Agent returns a long response                                                            |
| 2    | Verify display                                                  | Text wraps appropriately; no lines broken/garbled                                       |

---

### TC-083: Reasoning Display Prompt

**Related UC**: UC-004 A9

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Configure reasoning effort (e.g. "low"), send a message         | Response carries reasoning content                                                      |
| 2    | Verify extra prompt                                             | `Показать рассуждения модели? (y/n):` displayed after token lines                        |
| 3    | Enter "y"                                                       | Indented `[Reasoning]:` block printed                                                    |
| 4    | Repeat exchange, enter "n"                                      | No reasoning block printed; back to prompt                                               |

---

### TC-021: Unknown Command Handling

**Related UC**: UC-004 A2

| Step | Action                  | Expected Result               |
| ---- | ----------------------- | ----------------------------- |
| 1    | Enter chat              | Prompt displayed              |
| 2    | Type "/unknown"         | Treated as a regular message: sent to the agent (UC-004 A2), `[AGENT] печатает...` then `[AGENT]: {response}` |
| 3    | Verify state            | Back to prompt                |

---

### TC-064: Memory Integration - Global + Task Profile in System Prompt

**Related UC**: §3 Memory Integration, UC-004

**Precondition**: Global memory has facts, task profile has facts and preferences, agent attached to task profile

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter chat loop with agent attached to task profile | Send message to agent                        |
| 2    | Verify system prompt construction             | Global memory facts appear first with header `--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---` |
| 3    | Verify task profile memory                    | Task facts appear after with header `--- ПАМЯТЬ ЗАДАЧИ: {profile_name} ---` |
| 4    | Verify user preferences                       | Preferences text appears after task memory with header `--- ПРЕДПОЧТЕНИЯ ПОЛЬЗОВАТЕЛЯ ---` |
| 5    | Verify correct ordering                       | Global → Task profile → Preferences          |

---

### TC-065: Preferences Display in System Prompt - Empty Preferences

**Related UC**: §3 Memory Integration, UC-004

**Precondition**: Global memory has facts, task profile has no preferences (empty string), agent attached to task profile

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter chat loop with agent attached to task profile | Send message to agent                        |
| 2    | Verify system prompt construction             | Global memory facts appear with header `--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---` |
| 3    | Verify task profile memory                    | Task facts appear with header `--- ПАМЯТЬ ЗАДАЧИ: {profile_name} ---` |
| 4    | Verify preferences section                    | Preferences section is NOT displayed (skipped when empty) |

---

### TC-115: Chat Loop Graceful Exit On End Of Input

**Related UC**: UC-004 A7

| Step | Action                                                          | Expected Result                                                                       |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Start the application, create a chat (quick path), feed input that ends right after one message exchange (no `/menu`, no option 6) | The message is sent and answered; then the input stream ends                            |
| 2    | Verify termination                                              | The chat loop terminates gracefully: no traceback in stderr, process exits cleanly      |
| 3    | Verify memory save                                              | Agent memory is saved before exit (UC-004 A7, exit rule in 5.4.4); restart shows the exchange intact |

---
