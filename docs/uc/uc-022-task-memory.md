# UC-022: Task Memory Of The Dialogue

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md) (§4.5 `/info`, §Memory Integration); all use
> cases are listed in the [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- A chat exists and is active
- Task memory is enabled (`TASK_MEMORY_ENABLED=true`, default)

## Main Success Scenario

1. During the dialogue the agent maintains a per-chat task memory: dialogue
   goal, fixed constraints, glossary terms and clarifications already made by
   the user
2. Every `TASK_MEMORY_UPDATE_EVERY_N_MESSAGES` user turns (default `3`) and on
   every context compression event the agent asks the LLM to return the full
   updated memory for the last `TASK_MEMORY_WINDOW_MESSAGES` messages
3. The extraction replaces outdated values: a new clarification/constraint
   overrides the previous one; fields absent from the model answer are kept
4. The memory is stored per `conversation_id` and injected into the system
   prompt on every message (`--- ПАМЯТЬ ЗАДАЧИ ---` section), so the goal is
   not lost in long dialogues
5. On exit (`/menu`, Ctrl+C, app start) the memory is updated one final time
   and persisted
6. `/info` displays the current task memory (goal, constraints, terms,
   clarifications); when empty, the block is not printed

## Alternative Flows

- **A1: Memory disabled**
  - Step 1: `TASK_MEMORY_ENABLED=false` → no extraction, no prompt section,
    `/info` shows no task-memory block

- **A2: No messages**
  - Step 2: nothing to analyse → no LLM call

- **A3: LLM returns invalid/empty JSON**
  - Step 2: the update is skipped, the previous memory is preserved

- **A4: Branch created**
  - Step 4: `/branch` starts with **empty** task memory (new
    `conversation_id`); branch and parent keep separate memories

- **A5: Task profile attached**
  - Step 2: the profile name/description is passed to the extractor as extra
    context; profile facts/invariants remain a separate shared memory

## Postconditions

- Task memory lives exactly as long as its dialogue and is deleted with the chat
- `TaskProfile` (facts/preferences/invariants) is unchanged and independent;
  branches share the profile but not the per-chat task memory

## Related Test Cases

### TC-142: Task Memory Shown In /info

**Related UC**: UC-022 steps 1–6

**Precondition**: `TASK_MEMORY_UPDATE_EVERY_N_MESSAGES=1`

| Step | Action                     | Expected Result                                                |
| ---- | -------------------------- | -------------------------------------------------------------- |
| 1    | Send a message, enter `/info` | `Память задачи:` with goal, constraints, terms and clarifications |

---

### TC-143: No Task Memory Before Update

**Related UC**: UC-022 steps 1–2, A2

| Step | Action                    | Expected Result                          |
| ---- | ------------------------- | ---------------------------------------- |
| 1    | Send one message, `/info` | No `Память задачи:` block (below threshold) |

---

### TC-144: Persistence And Clean Branch

**Related UC**: UC-022 steps 4–5, A4

| Step | Action                                       | Expected Result                                  |
| ---- | -------------------------------------------- | ------------------------------------------------ |
| 1    | Fill memory, exit via `/menu`, re-enter chat | `/info` shows the persisted goal                 |

Unit-level tests (no network) in `cli_tests/test_task_memory.py` cover the
repository roundtrip, overriding semantics, missing-field preservation and the
prompt section; `cli_tests/test_prompt_builder.py` covers the
`--- ПАМЯТЬ ЗАДАЧИ ---` section presence/absence.
