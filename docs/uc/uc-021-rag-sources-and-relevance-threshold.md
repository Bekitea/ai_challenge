# UC-021: RAG Sources, Citations And Relevance Threshold

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md) (§4.5 `/rag`, §4.5.3); all use cases are listed
> in the [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- Application is running with a working embedding provider (local Ollama,
  model `bge-m3`, dimension 1024)
- A chat exists, is active, and has at least one attached knowledge base
  (see [UC-020](uc-020-rag-knowledge-bases.md))

## Main Success Scenario

1. User sends a message in a chat with attached knowledge bases
2. System retrieves candidate chunks from the attached bases, optionally
   reranks them and computes a unified relevance score in `[0..1]`
   (reranker score, or `1 - vector_distance / 2` when reranking is off)
3. Chunks with relevance below `RAG_RELEVANCE_THRESHOLD` (default `0.3`) are
   discarded before the system prompt is built
4. The system prompt instructs the model to answer only from the provided
   fragments and to answer «Не знаю» and ask the user to clarify when the
   fragments are missing or insufficiently relevant
5. After the agent response, the CLI prints the `[Источники]:` block with one
   entry per used chunk: document name, `чанк #<chunk_id>`, fragment number,
   relevance score and a short quote (first 200 characters)
6. If knowledge bases are attached but no chunk passed the threshold, the CLI
   prints `[Источники] релевантных фрагментов не найдено (порог …).`

## Alternative Flows

- **A1: No attached knowledge bases**
  - Step 1: `response.rag_sources` is `None`; the `[Источники]` block is not
    printed at all (normal conversation)

- **A2: Reranking disabled**
  - Step 2: relevance is derived from vector distance; the same threshold and
    `[Источники]` output apply

- **A3: Embedding provider unavailable**
  - Step 2: retrieval fails, the dialogue degrades gracefully and continues
    without RAG context; no `[Источники]` block is printed

- **A4: Custom threshold via environment**
  - Step 3: `RAG_RELEVANCE_THRESHOLD` (env var) overrides the default for the
    whole process; set it above `1.0` to discard all chunks

## Postconditions

- The user sees which documents/chunks were used and the exact quotes
- Low-relevance answers are refused with «Не знаю» and a request for
  clarification instead of hallucinated facts
- Sources are not persisted in the message history; they are shown for the
  response that just arrived

## Related Test Cases

### TC-139: RAG Sources Shown In Dialog

**Related UC**: UC-021 steps 1–5

| Step | Action                                | Expected Result                                  |
| ---- | ------------------------------------- | ------------------------------------------------ |
| 1    | Attach a base with indexed documents  | Attach confirmation shown                        |
| 2    | Send a relevant question              | `[AGENT]: ...` followed by `[Источники]:` with `france.txt — чанк #` and `релевантность` |

---

### TC-140: Sources Below Threshold

**Related UC**: UC-021 step 6, A4

**Precondition**: `RAG_RELEVANCE_THRESHOLD` set above `1.0`

| Step | Action                     | Expected Result                                                  |
| ---- | -------------------------- | ---------------------------------------------------------------- |
| 1    | Send a relevant question   | Normal response, then `релевантных фрагментов не найдено`         |

---

### TC-141: Threshold And Unknown-Answer Rule

**Related UC**: UC-021 steps 3–4

Unit-level test (no network) in `cli_tests/test_rag_relevance.py` and
`cli_tests/test_prompt_builder.py`:

| Step | Action                                            | Expected Result                                       |
| ---- | ------------------------------------------------- | ----------------------------------------------------- |
| 1    | Retrieve with all chunks below the threshold      | Empty chunks, `below_threshold=True`                  |
| 2    | Build a prompt with `rag_enabled` and no chunks   | System prompt contains «Не знаю» / «уточнить вопрос»  |
