# UC-028: Seed Project Knowledge Base (Main Menu 7, option 9)

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md) (§4.9); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- User is in the Knowledge Bases menu (Main Menu option 7)
- The project source paths (`PROJECT_DOCS_PATHS`: `README.md`, `docs/`,
  `AGENTS.md`) exist, at least partially

## Main Success Scenario

1. User selects option `9` → header
   `--- ЗАСЕВ ПРОЕКТНОЙ БАЗЫ '{PROJECT_KB_NAME}' ---`
2. System confirms `Продолжить? (y/n):`; anything but `y` cancels
3. System finds the base named `PROJECT_KB_NAME`, or creates it if missing
4. System deletes all existing documents of that base (chunks and vectors too),
   so stale information is not retained
5. System re-indexes each existing source path (a missing path is reported as
   `[SKIP] {path} — путь не найден` and skipped)
6. System prints the summary: removed documents, per-document results and
   `[OK] Готово: успешно {n}, с ошибками {m}.`

## Alternative Flows

- **A1 (cancel)**: confirmation is not `y` →
  `[INFO] Действие отменено.`
- **A2 (no matching source files)**: all paths missing → nothing indexed,
  `[OK] Готово: успешно 0, с ошибками 0.`
- **A3 (indexing error)**: a document may end up with status `error`; the batch
  continues (per-document `[ERROR] ...` line)

## Postconditions

- The project knowledge base exists and contains freshly indexed project docs
- Previously indexed documents of that base are removed

## Related Test Cases

### TC-159: seed creates and indexes the project base

**Related UC**: UC-028 main success

| Step | Action                                  | Expected Result                              |
| ---- | --------------------------------------- | -------------------------------------------- |
| 1    | Menu 7 → `9` → `y`                       | Seed runs, documents indexed                 |
| 2    | Verify ground truth                      | Base `PROJECT_KB_NAME` exists with documents |
| 3    | Verify README/docs are among documents   | README.md / docs files present               |

### TC-160: re-seed does not duplicate documents

**Related UC**: UC-028 main success (idempotency)

| Step | Action                     | Expected Result                          |
| ---- | -------------------------- | ---------------------------------------- |
| 1    | Seed twice in one session  | Removed stale docs then re-indexed       |
| 2    | Verify ground truth        | No duplicate document names in the base  |

---
