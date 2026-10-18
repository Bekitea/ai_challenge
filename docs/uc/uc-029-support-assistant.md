# UC-029: Support Assistant (/support)

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md) (§4.5.3 `/support`); all use cases are listed in
> the [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- User is in the chat interaction loop
- An active chat is selected
- (Optional) The support knowledge base (`SUPPORT_KB_NAME`) was seeded (UC-028)
- (Optional) The `support` MCP server can start (reads `mcp/data/support_seed.json`)

## Main Success Scenario

1. User types `/support [тикет] <вопрос>` (e.g.
   `/support T-1001 почему не работает авторизация?`)
2. System ensures support context via `prepare_support_context`:
   - if the support knowledge base (`SUPPORT_KB_NAME`) exists and is not attached
     to the chat, it is attached via the `attach_knowledge_base` use case
   - the `support` MCP server is connected via the `connect_mcp` use case
     (idempotent; not-found/errors are warned, not fatal)
3. If the leading token looks like a ticket/user id (`T-…`, `u-…`, `ticket…`), it
   is prefixed to the question (`Тикет {id}. {вопрос}`) so the agent fetches the
   ticket with the `get_ticket` tool
4. System sends the question to the agent as a regular message
5. The answer uses the RAG context from the support knowledge base (product FAQ)
   and the `support` tools (`get_ticket`, `find_user`, `list_tickets`)
6. System returns to the chat prompt

## Alternative Flows

- **A1 (bare `/support`)**: no question provided → prints
  `[INFO] Задайте вопрос поддержки: /support [тикет] <вопрос>. ...` and
  `[INFO] Список команд — /commands.`; no message is sent
- **A2 (no active chat)**: `[WARN] Сначала выберите или создайте чат!`
- **A3 (support knowledge base missing)**: prints
  `[WARN] БЗ поддержки '{name}' не найдена. Засеять её можно в меню 'Базы знаний' (пункт 9).`
  and continues; the answer falls back to MCP ticket context only

## Postconditions

- The support knowledge base may become attached to the chat
- `support` may be added to the chat's MCP server list
- The question and answer are part of the chat history

## Web UI

In the web frontend the same commands are available: a message starting with `/`
is sent to `POST /api/chats/{chat_id}/commands` (`{command}`); the response
contains informational `messages` (context preparation) and the agent
`response` (or `null` for a bare command). The UI shows `messages` as notices.

## Related Test Cases

### TC-161: /support answers with ticket context

**Related UC**: UC-029

| Step | Action                                                     | Expected Result                                  |
| ---- | ---------------------------------------------------------- | ------------------------------------------------ |
| 1    | Enter chat                                                 | Prompt displayed                                 |
| 2    | Type `/support T-1001 почему не работает авторизация?`      | `[INFO] ... support ...`, then `[AGENT]: ...`     |
| 3    | Verify support MCP connected                               | `support` present in the chat's MCP server list   |
| 4    | Verify return                                              | Back to prompt                                   |

### TC-162: bare /support shows usage hint

**Related UC**: UC-029 A1

| Step | Action             | Expected Result                                  |
| ---- | ------------------ | ------------------------------------------------ |
| 1    | Enter chat         | Prompt displayed                                 |
| 2    | Type `/support`    | Hint to provide a question; no agent call         |

---
