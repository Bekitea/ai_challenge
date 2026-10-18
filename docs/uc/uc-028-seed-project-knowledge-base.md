# UC-028: Seed Assistant Knowledge Bases (Main Menu 7, option 9)

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md) (§4.9); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- User is in the Knowledge Bases menu (Main Menu option 7)
- The source paths of the assistant bases exist, at least partially:
  - project base `PROJECT_DOCS_PATHS`: `README.md`, `docs/`, `AGENTS.md`
  - support base `SUPPORT_DOCS_PATHS`: `docs/support/`

## Main Success Scenario

1. User selects option `9` → header
   `--- ЗАСЕВ БАЗ АССИСТЕНТОВ (проект + поддержка) ---`
2. System confirms `Продолжить? (y/n):`; anything but `y` cancels
3. For each assistant base, in order (project, then support), the system:
   1. prints `--- ЗАСЕВ БАЗЫ '{name}' ---`
   2. finds the base named `PROJECT_KB_NAME` / `SUPPORT_KB_NAME`, or creates it
      if missing
   3. deletes all existing documents of that base (chunks and vectors too), so
      stale information is not retained
   4. re-indexes each existing source path (a missing path is reported as
      `[SKIP] {path} — путь не найден` and skipped)
   5. prints the summary: removed documents, per-document results and
      `[OK] Готово: успешно {n}, с ошибками {m}.`

## Alternative Flows

- **A1 (cancel)**: confirmation is not `y` → `[INFO] Действие отменено.`
- **A2 (no matching source files)**: all paths missing → nothing indexed,
  `[OK] Готово: успешно 0, с ошибками 0.`
- **A3 (indexing error)**: a document may end up with status `error`; the batch
  continues (per-document `[ERROR] ...` line)

## Postconditions

- Both assistant knowledge bases exist and contain freshly indexed documents
- Previously indexed documents of those bases are removed

## Related Test Cases

### TC-159: seed creates and indexes the assistant bases

**Related UC**: UC-028 main success

| Step | Action                                  | Expected Result                              |
| ---- | --------------------------------------- | -------------------------------------------- |
| 1    | Menu 7 → `9` → `y`                       | Seed runs, documents indexed                 |
| 2    | Verify ground truth                      | Bases `PROJECT_KB_NAME` / `SUPPORT_KB_NAME` exist with documents |
| 3    | Verify sources are among documents       | README.md / docs files; faq.md present       |

### TC-160: re-seed does not duplicate documents

**Related UC**: UC-028 main success (idempotency)

| Step | Action                     | Expected Result                          |
| ---- | -------------------------- | ---------------------------------------- |
| 1    | Seed twice in one session  | Removed stale docs then re-indexed       |
| 2    | Verify ground truth        | No duplicate document names in either base |

---
