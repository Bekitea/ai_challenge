# UC-008: Display Help Commands

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- User is in chat interaction loop

## Main Success Scenario

1. User types "/commands"
2. System displays command list
3. System returns to prompt
4. Use case ends

## Alternative Flows

- **A1 (project question)**: `/help <вопрос>` does not display the command list —
  it is the project assistant (UC-027). `/commands` is the command-list command.

## Postconditions

- No state changes
- User informed of available commands

## Related Test Cases

### TC-121: Commands Command

**Related UC**: UC-008

| Step | Action           | Expected Result        |
| ---- | ---------------- | ---------------------- |
| 1    | Enter chat       | Prompt displayed       |
| 2    | Type "/commands" | Command list displayed |
| 3    | Verify content   | All 15 commands listed in the exact `HELP_COMMANDS` order (§4.5.3 `/commands`) |
| 4    | Verify return    | Back to prompt         |

---
