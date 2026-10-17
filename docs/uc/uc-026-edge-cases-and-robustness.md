# UC-026: Edge Cases and Robustness

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

This use case groups robustness scenarios that are not tied to a single
interactive flow but must hold across the application: graceful termination on
end of input and handling of unusually large input.

## Preconditions

- Application is running in normal (interactive) mode.

## Main Success Scenario

1. The application accepts arbitrary user input, including very large messages.
2. When the input stream ends (EOF), the application terminates gracefully
   without a traceback and without persisting half-finished state.

## Alternative Flows

- **A1: EOF During Chat Creation**
  - Step: the input stream ends in the middle of the chat-creation wizard
    (e.g. after the name, before the system prompt).
  - The process exits cleanly; no partial chat is persisted.

- **A2: Very Long User Message**
  - Step: the user submits a message far larger than a typical terminal line.
  - The message is accepted, stored verbatim in history and answered normally;
    the response line is not garbled or broken.

## Postconditions

- No partial state is left behind on EOF.
- Long messages round-trip intact through history.

## Related Test Cases

### TC-154: EOF During Chat Creation

**Related UC**: UC-026 A1

| Step | Action                                                          | Expected Result                                                        |
| ---- | --------------------------------------------------------------- | ---------------------------------------------------------------------- |
| 1    | Start the application and choose "New Chat", confirm configuration, enter a name, then end the input (EOF) before the system prompt | Process exits cleanly (return code 0, empty stderr), no traceback       |
| 2    | Verify persisted state                                          | No chat was created (`agents` table is empty)                           |

---

### TC-155: Very Long User Message

**Related UC**: UC-026 A2

| Step | Action                                                          | Expected Result                                                        |
| ---- | --------------------------------------------------------------- | ---------------------------------------------------------------------- |
| 1    | Enter a chat and send a very long message (e.g. 5000 characters) | The message is accepted                                             |
| 2    | Verify history                                                  | The user message is stored verbatim; an assistant answer follows        |
| 3    | Verify display                                                  | The response is printed without crash or garbling                       |

---
