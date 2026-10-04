# UC-010: View Chat Information and Token Statistics

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- User is in chat interaction loop

## Main Success Scenario

1. User types "/info"
2. System retrieves chat statistics via `show_chat_info` use case (`ChatInfo`)
3. System displays header `--- ИНФОРМАЦИЯ О ЧАТЕ ---` with name, ID, strategy, task profile, phase, message count (§4.5.3 `/info`)
4. System displays token counters (`Prompt токены`, `Completion токены`)
5. System displays conditional lines: `Есть саммари: Да` (if summary exists), `Несжимаемые сообщения`, `Размер буфера` (if the strategy exposes them)
6. System displays a 40-dash separator and returns to the chat prompt
7. Use case ends

## Postconditions

- No state changes
- User sees detailed chat statistics

## Related Test Cases

### TC-028: View Chat Info With Token Statistics

**Related UC**: UC-010

| Step | Action                  | Expected Result                        |
| ---- | ----------------------- | -------------------------------------- |
| 1    | Open chat with messages | Chat active                            |
| 2    | Type "/info"            | Header `--- ИНФОРМАЦИЯ О ЧАТЕ ---` displayed |
| 3    | Verify token statistics | `Prompt токены` and `Completion токены` shown       |
| 4    | Verify strategy type    | Strategy name displayed                |
| 5    | Verify no state changes | Chat remains active                    |

---

### TC-043: View Info For Different Strategies

**Related UC**: UC-010 (steps 3–5)

| Step | Action                                | Expected Result                                       |
| ---- | ------------------------------------- | ----------------------------------------------------- |
| 1    | Open chat with DefaultStrategy        | Type /info, verify strategy displayed                 |
| 2    | Open chat with SummarizationStrategy  | Type /info, verify strategy and params displayed      |
| 3    | Open chat with KeyValueMemoryStrategy | Type /info, verify strategy and params displayed      |
| 4    | Open chat with SlidingWindowStrategy  | Type /info, verify strategy and window_size displayed |

---
