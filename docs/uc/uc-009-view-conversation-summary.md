# UC-009: View Conversation Summary

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- User is in chat interaction loop
- Chat uses SummarizationStrategy or KeyValueMemoryStrategy
- At least one summarization has been performed

## Main Success Scenario

1. User types "/summary"
2. System retrieves summary from active strategy
3. System displays summary text
4. System returns to prompt
5. Use case ends

## Alternative Flows

- **A1: No Summary Yet**
  - Step 2: Strategy has no summary (summarization not triggered yet)
  - System displays `[INFO] Саммари пока недоступно.`
  - Continue to step 4

## Postconditions

- No state changes
- User sees conversation summary

## Related Test Cases

### TC-026: View Summary With Summarization

**Related UC**: UC-009

| Step | Action                       | Expected Result                    |
| ---- | ---------------------------- | ---------------------------------- |
| 1    | Open chat with summarization | Chat active                        |
| 2    | Type "/summary"              | Summary text displayed             |
| 3    | Verify summary content       | Matches strategy's current summary |
| 4    | Verify no state changes      | Chat remains active                |

---

### TC-027: View Summary Without Summarization

**Related UC**: UC-009 A1

| Step | Action                         | Expected Result                                     |
| ---- | ------------------------------ | --------------------------------------------------- |
| 1    | Open new chat (no summary yet) | Chat active                                         |
| 2    | Type "/summary"                | `[INFO] Саммари пока недоступно.` displayed          |
| 3    | Verify no state changes        | Chat remains active                                 |

---
