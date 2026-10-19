# UC-032: Automated AI Code Review Of Pull Requests

> Part of the AI Chat specification. The backend endpoint is part of the REST
> API (§6); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Purpose

Analyse a pull request and post an AI-generated review (potential bugs,
architecture problems, recommendations) as a PR comment. A lightweight
self-hosted GitHub Actions runner collects the diff and metadata and sends them
to the AI backend in a single HTTP request; the backend performs RAG over the
review knowledge base (documentation + source code) and calls the LLM. The
runner stores no LLM keys and no database access.

## Configuration

- `REVIEW_ENABLED` — global switch for the endpoint and the `/review` command
  (default `true`).
- `REVIEW_KB_NAME` — knowledge base name used for RAG (default `Ревью кода`).
- `REVIEW_DOCS_PATHS` — paths indexed into the review KB (default: README, docs,
  AGENTS.md + `core/domain`, `core/application`, `core/infrastructure`, `mcp`).
- `REVIEW_LLM_PROVIDER` / `REVIEW_LLM_MODEL` — provider/model for the review.
- `REVIEW_TOP_K`, `REVIEW_MAX_DIFF_CHARS`, `REVIEW_MAX_TOKENS`,
  `REVIEW_LLM_TIMEOUT`, `REVIEW_FOLDER_MAX_FILES`.
- GitHub secrets: `RUNNER_TOKEN` (runner registration), `REVIEW_API_KEY`
  (Bearer key for the backend, issued via the CLI, UC-025); repository variable
  `REVIEW_API_URL` (defaults to `http://web:8080` when the runner shares the
  Compose network).

## Preconditions

- The backend (`web`) is running and the review knowledge base is seeded
  (menu 7 → option 10; option 9 seeds the project and support bases).
- An API key exists (CLI → menu 6) and is stored as the `REVIEW_API_KEY`
  secret.
- The self-hosted runner is registered and online
  (`docker-compose.runner.yml`).

## Main Success Scenario

1. A developer opens or updates a pull request.
2. GitHub triggers `.github/workflows/ai-review.yml` on the self-hosted runner.
3. Runner checks out the repository (`fetch-depth: 0`) and computes
   `git diff origin/<base>...HEAD` plus the changed file list and PR metadata,
   assembling a JSON payload with `jq`.
4. Runner sends one `POST /api/review-pr` request (`Authorization: Bearer
   <REVIEW_API_KEY>`, `Content-Type: application/json`).
5. Backend (`ReviewPullRequestUseCase`):
   - finds the review knowledge base by `REVIEW_KB_NAME` and runs a RAG query
     built from the PR title and changed files (skipped if the KB is missing);
   - assembles a prompt: project rules (RAG fragments) + diff (truncated to
     `REVIEW_MAX_DIFF_CHARS`) + required Markdown structure;
   - calls the configured LLM provider directly (stateless — no chat history);
   - returns `{review, rag_sources, prompt_tokens, completion_tokens, model}`.
6. Runner extracts `.review` with `jq`, writes `comment.json` and posts it as a
   PR comment via the GitHub API using `GITHUB_TOKEN`.

## Alternative Flows

- **A1 (diff empty)**: the runner completes without calling the backend; no
  comment is posted.
- **A2 (backend unavailable / non-2xx)**: the call step does not fail the job;
  the runner posts a short comment stating that AI review is unavailable.
- **A3 (missing API key)**: backend returns `401`; the runner reports the
  failure in the PR comment.
- **A4 (`REVIEW_ENABLED=false`)**: endpoint returns `400`
  (`AI-ревью PR отключено`).
- **A5 (invalid payload — empty diff)**: Pydantic validation returns `422`.
- **A6 (review KB missing)**: the review is still produced from the diff, with
  an empty `rag_sources` list.
- **A7 (local CLI, `/review [base]`)**: uses the local working tree diff
  (`git diff <base>...HEAD`) and prints the review to the terminal.

## Postconditions

- A Markdown review comment is published on the pull request.
- The review knowledge base remains available for subsequent reviews.

## REST API

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/review-pr` | Run the AI review for a PR diff; returns `CodeReviewResponse`. |

## Related Test Cases

### TC-167: review endpoint returns a Markdown review

**Related UC**: UC-032 main success

| Step | Action | Expected Result |
| --- | --- | --- |
| 1 | `POST /api/review-pr` with a non-empty diff | `200`, `review` is a non-empty string, `rag_sources` is a list |
| 2 | No review KB seeded | `rag_sources` is `[]`; review still produced |

### TC-168: review endpoint rejects invalid input

**Related UC**: UC-032 A5

| Step | Action | Expected Result |
| --- | --- | --- |
| 1 | `POST /api/review-pr` with `diff` empty | `422` |

### TC-169: review endpoint requires an API key

**Related UC**: UC-032 A3

| Step | Action | Expected Result |
| --- | --- | --- |
| 1 | `POST /api/review-pr` without `Authorization` | `401` |

### TC-170: review endpoint honours the feature flag

**Related UC**: UC-032 A4

| Step | Action | Expected Result |
| --- | --- | --- |
| 1 | Set `REVIEW_ENABLED=false` and call the endpoint | `400` with `отключено` |

### TC-171: prompt building and diff truncation

**Related UC**: UC-032 main success / prompt

| Step | Action | Expected Result |
| --- | --- | --- |
| 1 | Run the use case with a review KB and a chunk available | Prompt contains the diff, RAG fragment and PR metadata; `rag_sources` populated |
| 2 | Run with a diff longer than `REVIEW_MAX_DIFF_CHARS` | Prompt contains the truncation marker |

---
