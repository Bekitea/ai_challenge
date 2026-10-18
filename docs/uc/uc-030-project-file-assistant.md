# UC-030: Project File Assistant (/files)

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md) (§4.5.3 `/files`); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- User is in the chat interaction loop
- An active chat is selected
- (Optional) The project knowledge base was seeded (UC-028)
- The `files` MCP server can start (workspace root — project root or
  `PROJECT_FILES_ROOT`)
- (Optional) `git` is available so the `git` MCP server can start

## Main Success Scenario

1. User types `/files <цель>` (e.g.
   `/files найди все места, где используется McpGateway`)
2. System ensures project context:
   - if the project knowledge base (`PROJECT_KB_NAME`) exists and is not attached
     to the chat, it is attached via the `attach_knowledge_base` use case
   - the `files` and `git` MCP servers are connected via the `connect_mcp` use
     case (idempotent; not-found/errors are warned, not fatal)
3. System wraps the goal in a goal-level instruction and sends it to the agent
   as a regular message via `send_message`:
   - the agent itself decides which files to search/read/modify (no need to name
     concrete files)
   - it works with at least 2-3 files when the task requires it
   - for changes it calls `write_file`/`replace_in_file` first with `apply=False`
     (preview-diff, file unchanged), then repeats with `apply=True`
   - it finishes with a list of read/changed files and the resulting diff
4. System returns to the chat prompt; the answer is part of the chat history

## Alternative Flows

- **A1 (bare `/files`)**: no goal provided → prints
  `[INFO] Задайте задачу по файлам проекта: /files <цель>. ...` and
  `[INFO] Список команд — /commands.`; no MCP server is connected and no message
  is sent
- **A2 (no active chat)**: `[WARN] Сначала выберите или создайте чат!`
- **A3 (project knowledge base missing)**: prints
  `[WARN] Проектная БЗ '{name}' не найдена. Засеять её можно в меню 'Базы знаний' (пункт 9).`
  and continues; the agent works with the file tools only
- **A4 (MCP server cannot start)**: prints a `[WARN]` and continues; the agent
  reports that the tool is unavailable
- **A5 (path outside workspace)**: the `files` server refuses the operation and
  returns a readable error to the agent
- **A6 (secrets/binary/too large)**: `.env*`, binary and oversized files cannot
  be read or written

## Postconditions

- The project knowledge base may become attached to the chat
- `files` and `git` may be added to the chat's MCP server list
- Files may be created/modified inside the workspace (only after an explicit
  `apply=True` call)
- The goal, tool calls, diffs and answer are part of the chat history

## Related Test Cases

### TC-163: /files connects files and git MCP

**Related UC**: UC-030

| Step | Action                         | Expected Result                                   |
| ---- | ------------------------------ | ------------------------------------------------- |
| 1    | Enter chat                     | Prompt displayed                                  |
| 2    | Type `/files <цель>`           | `[INFO] ... files ... git ...`, then `[AGENT]: ...` |
| 3    | Verify MCP servers connected   | `files` and `git` present in the chat's MCP list  |
| 4    | Verify return                  | Back to prompt                                    |

### TC-164: /files searches, reads several files and writes with a diff

**Related UC**: UC-030 main success

| Step | Action                                   | Expected Result                                                  |
| ---- | ---------------------------------------- | ---------------------------------------------------------------- |
| 1    | Prepare an isolated workspace with 2 files | Workspace exists under the test data directory                  |
| 2    | Type `/files создай CHANGELOG.md ...`     | `[AGENT]: ...`; tool calls search/read/write are executed        |
| 3    | Verify ground truth                       | `CHANGELOG.md` exists with the expected content                  |
| 4    | Verify diff and multi-file work           | History contains a `PREVIEW (dry-run)` tool result and reads of at least 2 files |

### TC-165: bare /files shows usage hint

**Related UC**: UC-030 A1

| Step | Action          | Expected Result                                        |
| ---- | --------------- | ------------------------------------------------------ |
| 1    | Enter chat      | Prompt displayed                                       |
| 2    | Type `/files`   | Hint to provide a goal; no agent call                  |
| 3    | Verify MCP list | No MCP server was connected                            |

### TC-166: result is reproducible

**Related UC**: UC-030

| Step | Action                              | Expected Result                                     |
| ---- | ----------------------------------- | --------------------------------------------------- |
| 1    | Run the same `/files <цель>` twice  | Both answers are produced                           |
| 2    | Verify ground truth                 | Final file content is unchanged after the rerun     |

---
