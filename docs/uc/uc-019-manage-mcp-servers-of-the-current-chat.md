# UC-019: Manage MCP Servers Of The Current Chat (/mcp)

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- User is in chat interaction loop
- At least one MCP server is registered in the registry (`mcp_registry`)

## Main Success Scenario

1. User types `/mcp`
2. System displays the connected-servers block (§4.5.3 `/mcp`): header `--- MCP-СЕРВЕРЫ ЧАТА: {chat_name} ---`, then per server either `[OK] {title} ({name}) — инструменты: {tool1, tool2}` (connected) or `[OFFLINE] {title} ({name}) — подключение не установлено` (connection not established); if none are connected: `К этому чату ещё не подключено ни одного MCP-сервера.`
3. System prompts: `Подключить новые MCP? (y/n):`
4. User enters "y"
5. System lists registry servers not yet connected to this chat under `--- ДОСТУПНЫЕ ДЛЯ ПОДКЛЮЧЕНИЯ MCP ---` as `{idx}. {title} ({name}) — {description}`
6. System prompts: `Введите номер сервера для подключения (или название, 0 — отмена):`
7. User enters a valid number (or a server name)
8. System displays `[INFO] Подключаю MCP '{name}'...`
9. System executes the `connect_mcp` use case and displays `[OK] {message}` on success
10. The server list is persisted on the agent; tools become available to the LLM in subsequent messages (tool-calling loop inside `continue_dialog`)
11. Control returns to the chat prompt; use case ends

## Alternative Flows

- **A1: Decline Connecting New Servers**
  - Step 4: User enters anything other than `y` (including empty input)
  - The flow ends immediately after the connected-servers block; control returns to the chat prompt with no changes

- **A2: All Servers Already Connected**
  - Step 5: `list_available_mcp` returns an empty list
  - System displays `[INFO] Все доступные MCP-серверы уже подключены к этому чату.` and returns to the chat prompt

- **A3: Cancel Connection**
  - Step 7: User presses Enter (empty input) or enters `0`
  - System displays `[INFO] Подключение отменено.` and returns to the chat prompt

- **A4: Numeric Selection Out Of Range**
  - Step 7: User enters a digit outside 1…n
  - System displays `[ERROR] Неверный номер сервера.` and ends the flow (no re-prompt)

- **A5: Connection Fails**
  - Step 9: `connect_mcp` returns failure (unknown server name or unreachable server)
  - System displays `[ERROR] {message}` from the use case; the chat's server list is unchanged; control returns to the chat prompt

- **A6: EOFError / KeyboardInterrupt During /mcp Prompts**
  - Step 4/7: End of input or Ctrl+C at a `/mcp` prompt
  - The exception is handled locally inside the `/mcp` flow: the chat loop is NOT exited, control returns to the chat prompt

- **A7: Offline Server Display**
  - Step 2: A connected-to-chat server cannot be reached
  - It is listed with the `[OFFLINE]` line instead of `[OK]` (see §4.5.3)

## Postconditions

- On success: the server is appended to the chat's MCP list and persisted; its tools are available in subsequent exchanges
- On cancel/decline/failure: no state changes
- User remains in the chat interaction loop

## Related Test Cases

### TC-101: MCP Menu - No Servers Connected Yet

**Related UC**: UC-019 (steps 1–2)

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | In a chat with no MCP servers enter `/mcp`    | Header `--- MCP-СЕРВЕРЫ ЧАТА: {chat_name} ---` displayed |
| 2    | Verify empty state                            | `К этому чату ещё не подключено ни одного MCP-сервера.` shown |
| 3    | Verify prompt                                 | `Подключить новые MCP? (y/n):` displayed      |

---

### TC-102: MCP Menu - Decline Connecting New Servers

**Related UC**: UC-019 A1

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter `/mcp`                                  | Connected-servers block displayed            |
| 2    | Enter "n" (or any text other than `y`, or press Enter) at `Подключить новые MCP? (y/n):` | Flow ends immediately after the block (UC-019 A1) |
| 3    | Verify return                                 | Control returns to the chat prompt; no state changes |

---

### TC-103: MCP Menu - Connect Server By Number

**Related UC**: UC-019 (main success scenario, steps 4–11)

**Precondition**: At least one registered MCP server not yet connected to the chat

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter `/mcp`, answer `y`                      | `--- ДОСТУПНЫЕ ДЛЯ ПОДКЛЮЧЕНИЯ MCP ---` lists registry servers not connected to this chat as `{idx}. {title} ({name}) — {description}` |
| 2    | Verify prompt                                 | `Введите номер сервера для подключения (или название, 0 — отмена):` displayed |
| 3    | Enter a valid number                          | `[INFO] Подключаю MCP '{name}'...` displayed  |
| 4    | Wait for connection result                    | `[OK] {message}` from the `connect_mcp` use case (UC-019 step 9) |
| 5    | Enter `/mcp` again                            | The server now listed as `[OK] {title} ({name}) — инструменты: {tool1, tool2}` |

---

### TC-104: MCP Menu - Connect Server By Name

**Related UC**: UC-019 (steps 7–9)

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter `/mcp`, answer `y`                      | Available servers listed                     |
| 2    | Enter a non-numeric server name at the selection prompt | Text treated as a server name (UC-019 step 7); `[INFO] Подключаю MCP '{name}'...` |
| 3    | Wait for connection result                    | `[OK] {message}` on success                   |

---

### TC-105: MCP Menu - All Servers Already Connected

**Related UC**: UC-019 A2

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Connect all registry servers to the chat       | —                                            |
| 2    | Enter `/mcp`, answer `y`                      | `[INFO] Все доступные MCP-серверы уже подключены к этому чату.` displayed (UC-019 A2) |
| 3    | Verify return                                 | Control returns to the chat prompt            |

---

### TC-106: MCP Menu - Cancel Connection

**Related UC**: UC-019 A3

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter `/mcp`, answer `y`                      | Available servers listed                     |
| 2    | Press Enter (empty input) at the selection prompt | `[INFO] Подключение отменено.` displayed (UC-019 A3) |
| 3    | Repeat: reach the server-selection prompt, enter `0` | `[INFO] Подключение отменено.` displayed      |
| 4    | Verify return                                 | Control returns to the chat prompt; server list unchanged |

---

### TC-107: MCP Menu - Numeric Selection Out Of Range

**Related UC**: UC-019 A4

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter `/mcp`, answer `y`                      | Available servers listed (n servers)         |
| 2    | Enter a number outside 1…n (e.g. `99`)        | `[ERROR] Неверный номер сервера.` displayed; flow ends without re-prompt (UC-019 A4) |
| 3    | Verify return                                 | Control returns to the chat prompt; no server connected |

---

### TC-108: MCP Menu - Connection Fails

**Related UC**: UC-019 A5

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter `/mcp`, answer `y`                      | Available servers listed                     |
| 2    | Enter an unknown server name                  | `[INFO] Подключаю MCP '{name}'...` then `[ERROR] {message}` from the failed `connect_mcp` use case (UC-019 A5) |
| 3    | Verify state                                  | The chat's MCP server list is unchanged       |
| 4    | Verify return                                 | Control returns to the chat prompt            |

---

### TC-109: MCP Menu - Offline Server Display

**Related UC**: UC-019 A7

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Arrange a chat-connected MCP server to be unreachable | —                                       |
| 2    | Enter `/mcp`                                  | The server listed as `[OFFLINE] {title} ({name}) — подключение не установлено` instead of `[OK]` (UC-019 A7) |

---

### TC-110: MCP Menu - Ctrl+C During Prompts Does Not Exit Chat

**Related UC**: UC-019 A6

| Step | Action                                        | Expected Result                              |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | Enter `/mcp`, press Ctrl+C (or EOF) at `Подключить новые MCP? (y/n):` | Exception handled locally inside the `/mcp` flow (UC-019 A6) |
| 2    | Verify chat loop                              | Chat loop is NOT exited; control returns to the chat prompt |
| 3    | Repeat: reach the server-selection prompt, press Ctrl+C there | Same behavior — back at the chat prompt |
| 4    | Send a regular message                        | Normal exchange continues                     |

---
