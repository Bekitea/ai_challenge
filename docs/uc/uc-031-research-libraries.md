# UC-031: Research Libraries Per Chat (research MCP)

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md) (§4.5 `/mcp`); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Purpose

Turn each chat into a separate research workspace for a dissertation / scientific
field. Every chat has its own **research library** with its own knowledge base
and article metadata; libraries never mix. The conversational agent drives the
workflow through MCP tools of the `research` server.

## Preconditions

- An active chat is selected, or a new chat is created.
- (Recommended) An LLM with reliable tool-calling is selected for the chat.
- The `research` MCP server can start (`mcp/research_mcp.py`).
- (Optional) `OPENALEX_MAILTO` / `UNPAYWALL_EMAIL` are set for polite access and
  PDF fallback; without a download link the abstract is indexed instead.
- (Optional) A working embedding provider (Ollama `bge-m3`) for full-text
  indexing; metadata-only tools work without it.

## Main Success Scenario

1. In the chat the user runs `/mcp` and connects the `research` server
   (`Research Library`).
2. The user talks naturally; the agent calls research tools. On the first call
   that needs a library, a library is auto-created for the chat
   (`Исследования: {chat_name} (#{agent_id})`) together with its own knowledge
   base `Научная библиотека: {library_name}`, and it is bound to the chat.
3. Discovery: `search_articles` searches OpenAlex with year range / language
   defaults taken from the library profile, marks articles already in the
   library, and returns metadata, abstract and OA links.
4. Import: `import_articles` accepts DOI / OpenAlex IDs (up to
   `RESEARCH_IMPORT_BATCH_LIMIT`, default 5 per call), downloads the OA PDF,
   extracts text and indexes it into the library knowledge base; if no PDF is
   available, the abstract is indexed (`abstract_only`). Duplicate DOIs are not
   re-created; `force=true` re-indexes an existing article.
5. Summaries: `summarize_articles` produces structured Russian summaries
   (problem, method, data, results, limitations, contribution) and stores them.
6. Q&A: `search_library` performs RAG over the library knowledge base and
   returns passages with citation metadata; the agent answers only from them.
7. Reading advice: `recommend_articles` ranks library articles for a question
   and returns the most relevant articles with snippets.
8. Review: `get_review_context` returns compact article cards (citation,
   summary/abstract) within a character budget; the agent synthesizes trends,
   progress, achievements, methods and gaps.
9. Hypotheses: `get_hypothesis_context` returns profile, summaries and relevant
   passages; the agent proposes testable hypotheses with method, data, metrics
   and risks.
10. Library management: `create_library`, `switch_library`, `get_library_info`,
    `update_library_profile`, `get_library_stats`, `list_articles`,
    `detach_library`, `delete_library`.
11. **Deterministic article listing**: `/library articles [--year 2020-2026]
    [--status indexed|abstract_only] [--query TEXT] [--limit N]` in the CLI,
    `GET /api/chats/{chat_id}/library/articles` and
    `GET /api/libraries/{library_id}/articles` in REST. The response includes
    the library card, `total`, `limit`, `offset` and article metadata with
    status and summary.
12. **Reuse across chats**: a library is global; any chat can attach the same
    library via `switch_library("<name>")` or the `library="<name>"` parameter.
    Its knowledge base is always used together with the library — the research
    tools query `library.knowledge_base_id` directly. When
    `RESEARCH_AUTO_ATTACH_KB=true` (default), binding a library also attaches
    its knowledge base to the chat, so ordinary RAG (`/rag`) works as well.
13. **CLI and API management**: `/library` shows the active library and offers
    list / articles / use / create / detach / delete without relying on
    tool-calling; the same operations are exposed under
    `/api/chats/{chat_id}/library` and `/api/libraries/{library_id}`.
14. **Branches inherit the library**: `/branch` copies the parent's active
    library (and its knowledge base), so a branch continues work on the same
    scientific field.

## Alternative Flows

- **A1 (no chat context)**: if `AI_CHAT_AGENT_ID` is absent (direct server run),
  tools requiring a library return `[ERROR] ... AI_CHAT_AGENT_ID ...`.
- **A2 (no library yet)**: the first library-dependent tool call auto-creates a
  library; `get_library_stats` on an empty library returns zero counts.
- **A3 (article not found)**: `import_articles` returns a per-article error; the
  rest of the batch is still processed.
- **A4 (no OA PDF)**: the abstract is indexed with status `abstract_only`; the
  agent must not claim full text was read.
- **A5 (no text at all)**: status `error`, no document is created.
- **A6 (batch too large)**: more than the limit identifiers raise a readable
  error asking to split the call.
- **A7 (embedding/LLM unavailable)**: metadata and search still work; import of
  full text or summarization returns a readable error; the library is not lost.
- **A8 (switching to another field)**: `switch_library <name>` rebinds the chat;
  previously imported articles remain with their original library.
- **A9 (same DOI in two libraries)**: allowed; rows, summaries and documents are
  independent per `library_id` (unique `(library_id, doi)`).
- **A10 (detach vs delete)**: `detach_library` removes only the chat binding and
  its knowledge base link (the library, articles and KB are kept and can be
  reused); `delete_library` is irreversible, removes all bindings, articles,
  the knowledge base (documents, chunks, vectors) and files, and requires the
  exact library name as `confirm_name`.
- **A11 (manual /rag attachment)**: switching a library detaches only the
  previous library's knowledge base; knowledge bases attached manually through
  `/rag` are left untouched.

## Postconditions

- The chat is bound to exactly one active research library.
- Each library owns one knowledge base and a set of `research_articles` rows;
  indexed articles have a `documents` row in that knowledge base.
- Library state is isolated: queries filter by `library_id`, so different chats
  working on different fields never see each other's articles.

## Configuration

`RESEARCH_KB_PREFIX`, `RESEARCH_LIBRARY_AUTO_NAME`, `RESEARCH_MAX_RESULTS`,
`RESEARCH_IMPORT_BATCH_LIMIT`, `RESEARCH_MAX_PDF_BYTES`, `RESEARCH_MAX_PDF_PAGES`,
`RESEARCH_MAX_FULLTEXT_CHARS`, `RESEARCH_SUMMARY_MAX_CHARS`,
`RESEARCH_REVIEW_MAX_CHARS`, `RESEARCH_OUTPUT_LANGUAGE`,
`RESEARCH_LLM_PROVIDER`, `RESEARCH_LLM_MODEL`, `RESEARCH_MCP_CALL_TIMEOUT`,
`OPENALEX_MAILTO`, `OPENALEX_RPS`, `UNPAYWALL_EMAIL`, `RESEARCH_DATA_DIR`.

## Related Test Cases

### TC-167: research server is registered

**Related UC**: UC-031

| Step | Action                    | Expected Result                          |
| ---- | ------------------------- | ---------------------------------------- |
| 1    | Read the MCP registry     | `research` is among available servers    |

### TC-168: connect research MCP and create a chat library

**Related UC**: UC-031 main success steps 1-2

| Step | Action                                        | Expected Result                                          |
| ---- | --------------------------------------------- | -------------------------------------------------------- |
| 1    | `/mcp` → `y` → `research`                     | `[OK] MCP 'Research Library' ...`                        |
| 2    | Send a message that triggers a research tool  | Tool is executed; `[AGENT]: ...` answer                  |
| 3    | Verify ground truth                           | Chat has a bound library with its own knowledge base     |

### TC-169: two chats get separate libraries

**Related UC**: UC-031 A9

| Step | Action                                       | Expected Result                                        |
| ---- | -------------------------------------------- | ------------------------------------------------------ |
| 1    | Create two chats in one session              | Both chats exist                                       |
| 2    | Connect `research` and call a tool in each   | Each chat gets its own library and knowledge base      |
| 3    | Verify ground truth                          | Library ids and KB ids differ between the chats        |

### TC-170: research tool without chat context reports an error

**Related UC**: UC-031 A1

| Step | Action                              | Expected Result                          |
| ---- | ----------------------------------- | ---------------------------------------- |
| 1    | Call a tool with no `AI_CHAT_AGENT_ID` | `[ERROR] ... AI_CHAT_AGENT_ID ...`     |
| 2    | Connect `research` from the CLI     | Connection succeeds without a tool call  |

### TC-171: /library creates, shows and detaches a library

**Related UC**: UC-031 step 12

| Step | Action                                  | Expected Result                                    |
| ---- | --------------------------------------- | -------------------------------------------------- |
| 1    | `/library create Test Library` + profile | `[OK] ... создана ...`, active library shown        |
| 2    | `/library info`                         | Active library with KB name and article count       |
| 3    | `/library detach`                       | `откреплена`, active library becomes empty          |
| 4    | Verify ground truth                     | Library kept in `research_libraries`, binding gone  |

### TC-172: one library is shared between chats

**Related UC**: UC-031 step 11

| Step | Action                                   | Expected Result                                  |
| ---- | ---------------------------------------- | ------------------------------------------------ |
| 1    | Create library in chat 1                 | Library created and attached                     |
| 2    | Create chat 2 and `/library use <name>`  | Same `library_id` bound to chat 2                |
| 3    | Verify ground truth                      | Both chats point to the same library             |

### TC-173: branch inherits the research library

**Related UC**: UC-031 step 13

| Step | Action                       | Expected Result                                   |
| ---- | ---------------------------- | ------------------------------------------------- |
| 1    | Create library, then `/branch` | Branch created with the parent's library          |
| 2    | Verify ground truth          | Parent and branch share the same `library_id`     |

### TC-175: /library articles lists library articles

**Related UC**: UC-031 step 11

| Step | Action                                        | Expected Result                                   |
| ---- | --------------------------------------------- | ------------------------------------------------- |
| 1    | `/library articles`                           | Header with library name and article rows         |
| 2    | `/library articles --status abstract_only`    | Empty state when no such articles                 |
| 3    | Verify REST                                  | `GET .../library/articles` returns `total`/items  |

### TC-174: /library delete requires name confirmation

**Related UC**: UC-031 A10

| Step | Action                                   | Expected Result                                  |
| ---- | ---------------------------------------- | ------------------------------------------------ |
| 1    | `/library create Delete Library`         | Library created                                  |
| 2    | `/library delete Delete Library` + confirm | Library removed; KB removed; binding cleared    |
| 3    | Verify ground truth                      | `research_libraries` no longer has the library   |

## REST API

| Method | Path                                    | Purpose                              |
| ------ | --------------------------------------- | ------------------------------------ |
| GET    | `/api/chats/{chat_id}/library`          | Active library (or null)             |
| GET    | `/api/chats/{chat_id}/library/available`| All libraries                        |
| GET    | `/api/chats/{chat_id}/library/articles` | Articles of the active library       |
| GET    | `/api/libraries/{library_id}/articles`  | Articles of a library by id          |
| POST   | `/api/chats/{chat_id}/library/switch`   | Attach an existing library by name   |
| POST   | `/api/chats/{chat_id}/library/create`   | Create and attach a library          |
| DELETE | `/api/chats/{chat_id}/library`          | Detach the active library            |
| DELETE | `/api/libraries/{library_id}`           | Delete globally (`confirm_name`)     |
