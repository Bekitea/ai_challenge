# UC-020: Manage Knowledge Bases And RAG (/rag, Main Menu Option 7)

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md) (§4.5.3 `/rag`, §4.9); all use cases are listed
> in the [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- Application is running with a working embedding provider (local Ollama,
  model `bge-m3`, dimension 1024)
- For the chat part: a chat exists and is active

## Main Success Scenario

### Knowledge base management (Main Menu option 7)

1. User selects option `7` in the Main Menu
2. System displays the Knowledge Bases menu (§4.9) and loops until `0`
3. User selects `1`, enters a non-empty name and an optional description
4. System creates the knowledge base together with its sqlite-vec vector table
   and prints `[OK] База знаний '{name}' создана!` with id and embedding model
5. User selects `3`, picks the base and enters a path to a `.txt`/`.md`/`.py`
   file or a folder (folders are traversed recursively)
6. System extracts text, splits it into chunks, computes embeddings and stores
   chunks + vectors; each ready document prints `[OK] {file} — чанков: {n}`
7. User selects `2`, `4` or `5` to inspect bases, documents and chunks
8. User selects `8`, picks a base and enters a query; system prints the
   top-`RAG_FINAL_TOP_K` chunks from ready documents

### RAG in the chat (option `/rag`)

9. User enters `/rag` in the chat loop
10. System lists the knowledge bases attached to the current chat
11. User chooses action `1` (attach) and selects an available base
12. System stores the link in `agent_knowledge_bases` and prints
    `[OK] База знаний '{name}' подключена к чату.`
13. On every subsequent user message the agent retrieves relevant chunks from
    attached bases and injects them into the system prompt before the LLM call
14. User may detach a base via `/rag` action `2`

## Alternative Flows

- **A1: Empty knowledge base name**
  - Step 3: empty input → `[ERROR] Название базы знаний не может быть пустым.`
    and the name prompt is repeated

- **A2: Duplicate knowledge base name**
  - Step 3: a base with the same name (case-insensitive) exists →
    `[ERROR] База знаний '{name}' уже существует.`

- **A3: Document source errors**
  - Step 5: path not found / unsupported extension / empty folder → `[ERROR] {message}`, no document is created. Empty files are skipped silently; when scanning a folder, unreadable files (too large / unknown encoding) are skipped too so the rest of the batch is still indexed.

- **A4: Indexing error**
  - Step 6: embedding fails → the document keeps status `error` with
    `error_message`; its chunks and vectors do not participate in search;
    other files in the folder are still processed

- **A5: Model dimension mismatch**
  - Step 5: the current embedding model/dimension differs from the base's →
    `[ERROR] ...`, nothing is indexed

- **A6: No attached knowledge bases**
  - Step 13: if no base is attached, no embedding or search is performed;
    the dialogue proceeds as a normal conversation

- **A7: Embedding provider unavailable during a dialogue**
  - Step 13: retrieval fails → the dialogue degrades gracefully and continues
    without RAG context

- **A8: Attach / detach is idempotent**
  - Step 12: attaching an already-attached base or detaching a non-attached
    base reports success without side effects

## Postconditions

- Knowledge bases, documents, chunks and vectors are persisted; deleting a
  base removes its documents, chunks, vectors and agent links
- Attached bases are stored relationally; the agent retrieves context on each
  message only from attached bases and only from `ready` documents

## Related Test Cases

### TC-121: Create Knowledge Base

**Related UC**: UC-020 steps 3–4

| Step | Action                          | Expected Result                                    |
| ---- | ------------------------------- | -------------------------------------------------- |
| 1    | Menu `7` → `1`, enter name/desc | `[OK] База знаний '{name}' создана!` with id and model |

---

### TC-122: Create Knowledge Base With Empty Name

**Related UC**: UC-020 A1

| Step | Action                          | Expected Result                                    |
| ---- | ------------------------------- | -------------------------------------------------- |
| 1    | Enter empty name, then a valid name | `[ERROR] Название базы знаний не может быть пустым.` then success |

---

### TC-123: List Knowledge Bases

**Related UC**: UC-020 step 7

| Step | Action                | Expected Result                                   |
| ---- | --------------------- | ------------------------------------------------- |
| 1    | Create two bases, `2` | `--- СПИСОК БАЗ ЗНАНИЙ ---` with both bases and counts |

---

### TC-124: Add Document And List Documents

**Related UC**: UC-020 steps 5–7

| Step | Action                          | Expected Result                                    |
| ---- | ------------------------------- | -------------------------------------------------- |
| 1    | `3`, select base, enter file path | `[OK] {file} — чанков: {n}`                       |
| 2    | `4`, select base                | Document listed with status `[ready]`              |

---

### TC-125: List Document Chunks

**Related UC**: UC-020 step 7

| Step | Action                     | Expected Result                                  |
| ---- | -------------------------- | ------------------------------------------------ |
| 1    | `5`, select base, select document | `--- ЧАНКИ ДОКУМЕНТА '{name}' ---` in order |

---

### TC-126: Attach And Detach Knowledge Base

**Related UC**: UC-020 steps 9–14

| Step | Action                       | Expected Result                                  |
| ---- | ---------------------------- | ------------------------------------------------ |
| 1    | `/rag` → `1` → select base   | `[OK] База знаний '{name}' подключена к чату.`   |
| 2    | `/rag` → `2` → select base   | `[OK] База знаний '{name}' отключена от чата.`   |

---

### TC-127: Search Knowledge Base

**Related UC**: UC-020 step 8

| Step | Action                          | Expected Result                                   |
| ---- | ------------------------------- | ------------------------------------------------- |
| 1    | `8`, select base, enter query   | `--- РЕЗУЛЬТАТЫ ПОИСКА (база '{name}') ---` with relevant chunk |

---

### TC-128: RAG Context Used In Dialog

**Related UC**: UC-020 steps 12–13

| Step | Action                                | Expected Result                          |
| ---- | ------------------------------------- | ---------------------------------------- |
| 1    | Attach a base with indexed documents  | Attach confirmation shown                |
| 2    | Send a message                        | Normal agent response (RAG injected)     |

---

### TC-129: Dialog Without Knowledge Base

**Related UC**: UC-020 A6

| Step | Action                          | Expected Result                                  |
| ---- | ------------------------------- | ------------------------------------------------ |
| 1    | Send a message without any base | Normal response; no RAG-related errors           |

---

### TC-130: Delete Document

**Related UC**: UC-020 (delete flow)

| Step | Action                          | Expected Result                                  |
| ---- | ------------------------------- | ------------------------------------------------ |
| 1    | `6`, select base → document → `y` | `[OK] Документ '{name}' удалён.`                |
| 2    | `4`, select base                | `нет документов`                                 |

---

### TC-131: Delete Knowledge Base

**Related UC**: UC-020 (delete flow)

| Step | Action                       | Expected Result                                   |
| ---- | ---------------------------- | ------------------------------------------------- |
| 1    | `7`, select base → `y`       | `[OK] База знаний '{name}' удалена.`              |
| 2    | `2`                          | `Базы знаний отсутствуют.`                        |

---

### TC-132: Add Document With Missing Path

**Related UC**: UC-020 A3

| Step | Action                      | Expected Result                           |
| ---- | --------------------------- | ----------------------------------------- |
| 1    | `3`, select base, enter `/no/such/path.txt` | `[ERROR] ... не найден.`    |

---

### TC-133: Add Python File As Document

**Related UC**: UC-020 steps 5–7

**Precondition**: a `.py` file exists on disk

| Step | Action                                  | Expected Result                       |
| ---- | --------------------------------------- | ------------------------------------- |
| 1    | `3`, select base, enter path to a `.py` file | `[OK] {file} — чанков: {n}`      |
| 2    | `4`, select base                        | Document listed with status `[ready]` |

---

### TC-134: Empty Files Are Skipped

**Related UC**: UC-020 A3

**Precondition**: a folder containing an empty `.py` file and a non-empty `.txt` file

| Step | Action                                   | Expected Result                                  |
| ---- | ---------------------------------------- | ------------------------------------------------ |
| 1    | `3`, select base, enter the folder path   | Only the non-empty file is indexed: `[OK] notes.txt — чанков: {n}`; the empty file is skipped without `[ERROR]` |
| 2    | `4`, select base                          | Only the non-empty document listed as `[ready]`  |
