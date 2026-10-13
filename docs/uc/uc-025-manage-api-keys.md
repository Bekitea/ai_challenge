# UC-025: Manage API Keys

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md); all use cases are listed in the
> [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- Application is running and the Main Menu is displayed (no active chat required)
- The REST API (`main_api.py`) requires a valid API key for every `/api/*`
  endpoint except `/api/health`

## Main Success Scenario

1. User selects option 6 (`API-ключи`) in the Main Menu
2. System displays the API Keys menu: `1. Создать ключ`, `2. Показать список ключей`, `3. Удалить ключ`, `0. Назад в главное меню`
3. User selects `1` (create)
4. System prompts for the key name; a non-empty name is required
5. System generates a random secret, stores only its SHA-256 hash together
   with a short display prefix, and prints the secret exactly once, warning that
   it will not be shown again
6. User selects `2` (list); system prints all keys' id, name, masked prefix,
   creation time and last-used time — never the secret
7. User selects `3` (delete), enters the key id and confirms `y`; the key is
   revoked and can no longer authorize API requests
8. User selects `0`; system returns to the Main Menu
9. Use case ends

## Alternative Flows

- **A1 — Empty key name (step 4)**: `[ERROR] Название API-ключа не может быть пустым.` and the name is requested again
- **A2 — No keys to list (step 6)**: `[INFO] API-ключи отсутствуют. Создайте первый ключ.`
- **A3 — Delete cancelled (step 7)**: empty id or confirmation other than `y` prints `[INFO] Удаление отменено.` and nothing is deleted
- **A4 — Non-numeric id (step 7)**: `[WARN] ID должен быть числом.`
- **A5 — Unknown id (step 7)**: `[ERROR] API-ключ #{id} не найден.`
- **A6 — Invalid menu choice**: `[WARN] Неверный выбор, попробуйте снова.` and the menu is re-displayed

## Postconditions

- A created key exists only as a hash; its plaintext is unrecoverable from the
  CLI or the database
- A deleted key is removed from `api_keys` and any further request with it is
  rejected with HTTP 401
- Non-`/api/health` REST API requests without a valid `Authorization: Bearer`
  header are rejected

## Related Test Cases

### TC-149: Create API Key Shows Secret Once

**Related UC**: UC-025 (steps 1–5)

| Step | Action                          | Expected Result                                                        |
| ---- | ------------------------------- | ---------------------------------------------------------------------- |
| 1    | Main Menu → `6` → `1`           | `--- API-КЛЮЧИ ---` displayed; name prompt shown                        |
| 2    | Enter name                      | `[OK] API-ключ '{name}' создан.`, `Ключ: aic_...`, one-time warning     |

### TC-150: Empty Name Re-Prompts

**Related UC**: UC-025 A1

| Step | Action                | Expected Result                                              |
| ---- | --------------------- | ------------------------------------------------------------ |
| 1    | `1` then empty name   | `Название API-ключа не может быть пустым.` and re-prompt      |
| 2    | Enter a valid name    | `[OK] API-ключ '{name}' создан.`                              |

### TC-151: List Keys Hides Secret

**Related UC**: UC-025 step 6

| Step | Action                     | Expected Result                                                  |
| ---- | -------------------------- | ---------------------------------------------------------------- |
| 1    | Create a key, then `2`     | `--- СПИСОК API-КЛЮЧЕЙ ---` shown                                |
| 2    | Verify secret not listed   | Full `aic_...` secret absent; only masked prefix `aic_...…` shown |

### TC-152: Delete Key

**Related UC**: UC-025 step 7

| Step | Action                          | Expected Result                                    |
| ---- | ------------------------------- | -------------------------------------------------- |
| 1    | Create a key, `3`, enter id, `y`| `[OK] API-ключ '{name}' отозван.`                  |
| 2    | List again (`2`)                | `API-ключи отсутствуют.`                           |

### TC-153: Invalid Menu Choice

**Related UC**: UC-025 A6

| Step | Action          | Expected Result                                   |
| ---- | --------------- | ------------------------------------------------- |
| 1    | `6` then `9`    | `Неверный выбор, попробуйте снова.` and re-prompt  |

---
