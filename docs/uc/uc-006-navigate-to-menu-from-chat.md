# UC-006: Navigate to Menu from Chat

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- User is in chat interaction loop

## Main Success Scenario

1. User types "/menu"
2. System displays `Возврат в меню...`
3. System saves chat memory via `save_agent_memory` use case (LLM fact extraction into global and task-profile memory)
4. System exits the chat loop and displays Main Menu
5. Use case ends

## Postconditions

- Chat preserved in backend storage
- User in Main Menu
- Chat remains the "active" chat for quick return (option 5)

## Related Test Cases

### TC-018: Menu Navigation from Chat

**Related UC**: UC-006

| Step | Action                  | Expected Result              |
| ---- | ----------------------- | ---------------------------- |
| 1    | Enter chat              | Chat loop                    |
| 2    | Type "/menu"            | `Возврат в меню...`, memory saved via `save_agent_memory`, Main Menu displayed |
| 3    | Verify chat preserved   | Chat still exists in storage |
| 4    | Select option 5 (Return to Chat) | Same chat reloaded        |

---
