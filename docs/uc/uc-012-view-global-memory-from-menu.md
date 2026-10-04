# UC-012: View Global Memory from Menu

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- Application is running
- User is in Main Menu
- No active chat required (global memory is independent of chats/agents)

## Main Success Scenario

1. User selects option 4 (Global Memory) from Main Menu
2. System retrieves global memory facts from GlobalMemoryRepository
3. System displays header: `--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---`
4. If memory is empty: displays `(память пуста)`
5. If memory has facts: displays numbered list of facts (one fact per line)
6. System displays separator line (40 dashes)
7. System returns to Main Menu
8. Use case ends

## Alternative Flows

- **A1: Empty Global Memory**
  - Step 3: Repository returns empty list of facts
  - System displays `(память пуста)` instead of fact list
  - Continue with step 6

## Postconditions

- User viewed global memory facts (or empty state)
- Returned to Main Menu
- No active chat required or changed

## Related Test Cases

### TC-046: View Global Memory from Main Menu (No Chat Required)

**Related UC**: UC-012

| Step | Action                                    | Expected Result                                       |
| ---- | ----------------------------------------- | ----------------------------------------------------- |
| 1    | Start application, stay in Main Menu      | No active chat selected                               |
| 2    | Select option 4 (Global Memory) from menu | System displays global memory view                    |
| 3    | Verify header displayed                   | `--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---` is shown                  |
| 4    | Verify facts or empty state               | Either numbered facts list OR `(память пуста)`        |
| 5    | Verify separator line                     | 40 dashes are displayed                               |
| 6    | Verify return to menu                     | Main Menu is displayed again                          |

---

### TC-047: View Global Memory - Empty State

**Related UC**: UC-012 A1

| Step | Action                                    | Expected Result                                       |
| ---- | ----------------------------------------- | ----------------------------------------------------- |
| 1    | Start application                         | Application running                                   |
| 2    | Ensure no chats exist and memory is empty | Repository returns empty list                         |
| 3    | Select option 4 (Global Memory) from menu | System displays global memory view                    |
| 4    | Verify header displayed                   | `--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---` is shown                  |
| 5    | Verify empty state message                | `(память пуста)` is displayed                         |
| 6    | Verify separator line                     | 40 dashes are displayed                               |
| 7    | Verify return to menu                     | Main Menu is displayed again                          |

---

### TC-048: View Global Memory - With Facts (End-to-End Flow)

**Related UC**: UC-012 (steps 4–7), UC-006
**Also related to**: UC-006 (cross-referenced)

**Purpose**: Verify that memory is populated during chat interaction, saved when exiting to menu, and correctly displayed from the repository.

| Step | Action                                           | Expected Result                                          |
| ---- | ------------------------------------------------ | -------------------------------------------------------- |
| 1    | Start application                                | Application running                                      |
| 2    | Select option 1 (New Chat) from menu             | Chat creation workflow starts                            |
| 3    | Complete chat creation with any settings         | Chat created, entered chat loop                          |
| 4    | Send a message to the agent                      | Agent responds (Mock provider generates test facts)      |
| 5    | Type `/menu` command to exit to main menu        | System saves agent state and global memory               |
| 6    | Select option 4 (Global Memory) from menu        | System retrieves facts from FileGlobalMemoryRepository   |
| 7    | Verify header displayed                          | `--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---` is shown                     |
| 8    | Verify facts are displayed as numbered list      | At least 1-2 test facts shown as `{i}. {fact}`           |
| 9    | Verify separator line                            | 40 dashes are displayed                                  |
| 10   | Verify return to menu                            | Main Menu is displayed again                             |

---
