# UC-027: Project Help Assistant (/help)

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md) (§4.5.3 `/help`); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- User is in the chat interaction loop
- An active chat is selected
- (Optional) The project knowledge base was seeded (UC-028)
- (Optional) `git` is available so the `git` MCP server can start

## Main Success Scenario

1. User types `/help <вопрос>` (e.g. `/help как устроена архитектура проекта?`)
2. System ensures project context:
   - if the project knowledge base (`PROJECT_KB_NAME`) exists and is not attached
     to the chat, it is attached via the `attach_knowledge_base` use case
   - the `git` MCP server is connected via the `connect_mcp` use case
     (idempotent; not-found/errors are warned, not fatal)
3. System sends the question to the agent as a regular message
4. The answer uses the RAG context from the project knowledge base and the
   `git` tools (branch/status/diff) when relevant
5. System returns to the chat prompt

## Alternative Flows

- **A1 (bare `/help`)**: no question provided → prints
  `[INFO] Задайте вопрос о проекте: /help <вопрос>. ...` and
  `[INFO] Список команд — /commands.`; no message is sent
- **A2 (no active chat)**: `[WARN] Сначала выберите или создайте чат!`
- **A3 (project knowledge base missing)**: prints
  `[WARN] Проектная БЗ '{name}' не найдена. Засеять её можно в меню 'Базы знаний' (пункт 9).`
  and continues; the answer falls back to git context only

## Postconditions

- The project knowledge base may become attached to the chat
- `git` may be added to the chat's MCP server list
- The question and answer are part of the chat history

## Related Test Cases

### TC-157: /help asks about the project

**Related UC**: UC-027

| Step | Action                     | Expected Result                                  |
| ---- | -------------------------- | ------------------------------------------------ |
| 1    | Enter chat                 | Prompt displayed                                 |
| 2    | Type `/help <вопрос>`      | `[INFO] ... git ... API ...`, then `[AGENT]: ...` |
| 3    | Verify git MCP connected   | `git` present in the chat's MCP server list      |
| 4    | Verify return              | Back to prompt                                   |

### TC-158: bare /help shows usage hint

**Related UC**: UC-027 A1

| Step | Action             | Expected Result                                       |
| ---- | ------------------ | ----------------------------------------------------- |
| 1    | Enter chat         | Prompt displayed                                      |
| 2    | Type `/help`       | Hint to provide a question; no agent call             |
| 3    | Verify the list is shown only by `/commands` | Command list not printed for `/help` |

---
