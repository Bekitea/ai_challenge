# UC-023: List Available Models And Providers

> Part of the AI Chat CLI specification. Interface details appear in
> [cli_spec.md](../cli_spec.md) (§4.4.3 model/provider selection); all use
> cases are listed in the [UC index](../cli_spec.md#5-use-cases-index).

## Preconditions

- Application is running
- At least one LLM provider is configured: Yandex Cloud (production),
  Ollama (local, `OLLAMA_BASE_URL`) or the mock providers (test mode)

## Main Success Scenario

1. Whenever a model must be chosen (chat creation — UC-001, or settings change —
   UC-005) the CLI calls the `list_models` use case
2. The use case asks every provider in the `LlmProviderRegistry` for its models
   (`LlmProvider.list_models()`); unavailable providers are silently skipped
3. Yandex Cloud models are fetched from the OpenAI-compatible `/models`
   endpoint; Ollama chat models are fetched from `GET /api/tags`
4. The result is a flat list of `AvailableModel(provider, model_id,
   display_name)`; the same model offered by two providers appears twice, once
   per provider
5. The CLI prints the list labelled by provider:
   `{n}. [{provider}] {display_name} ({model_id})` (the parenthesised id is
   omitted when it equals the display name) and asks `Ваш выбор (1-{N}):`
6. The user picks a number; the corresponding `provider` and `model_id` are
   stored in `AgentSettings.provider` / `AgentSettings.model_id`
7. The per-chat provider is resolved at generation time from the registry; the
   agent calls the provider selected by `AgentSettings.provider`

## Alternative Flows

- **A1: No default model**
  - Step 6: at chat creation empty input prints
    `Выбор обязателен: введите номер модели.` and re-prompts. There is no
    default model for a chat.

- **A2: Keep current model**
  - Step 6 (UC-005 settings change only): empty input keeps the current
    provider/model instead of re-selecting.

- **A3: Invalid selection**
  - Step 6: out-of-range/non-numeric input prints
    `Неверный выбор, попробуйте снова.` and re-prompts.

- **A4: No models available**
  - Step 4: if no provider returns models, `(нет доступных моделей)` is shown,
    a hint about provider availability is printed, and chat creation is aborted
    with `[WARN] Чат не создан: нет доступных моделей.`

- **A5: Provider unavailable**
  - Step 2: a provider that raises or times out (e.g. no network for Yandex, or
    Ollama not running) is skipped; the remaining providers still populate the
    list. Detailed reason is logged at WARNING level.

- **A6: Embedding model filtering**
  - Step 3: Ollama embedding-only models (`bge-m3` and names containing
    `embed`) are excluded from the chat-model list.

## Postconditions

- `AgentSettings.provider` and `AgentSettings.model_id` are persisted in the
  chat's `settings_json` and restored on reload
- Chats created before provider selection existed (`provider=None`) default to
  `DEFAULT_PROVIDER` (`yandex`) at generation time

## Implementation Notes

- `core/infrastructure/llm/`: `LlmModelInfo`, `LlmProvider.list_models()`,
  `YandexCloudLlmProvider`, `OllamaLlmProvider`, `MockLlmProvider`,
  `LlmProviderRegistry`
- `core/application/use_cases/list_models.py`: `AvailableModel`, `ListModelsUseCase`
- `core/presentation/cli/cli_app.py`: `_select_model()`
- `config.py`: `DEFAULT_REPORT_PROVIDER` / `DEFAULT_REPORT_MODEL` (non-interactive
  Celery reports), `OLLAMA_OPENAI_BASE_URL`, `MODEL_LIST_TIMEOUT`,
  `DEFAULT_PROVIDER`
- In test mode both `yandex` and `ollama` mock providers return a deterministic
  list (`MOCK_MODELS`), so e2e tests can exercise provider selection and labels.

## Related Test Cases

### TC-001 (partial): Quick Chat Selects A Model

**Related UC**: UC-023 A1, UC-001 A1

The quick creation path still requires an explicit model number; the default
`/settings` block shows both `Провайдер:` and `Модель:`.

### TC-002 / TC-006 (partial): Manual Model Selection

**Related UC**: UC-023 A3, UC-001 A5

Out-of-range and non-numeric input re-prompt; empty input at creation re-prompts
(`Выбор обязателен...`).

### TC-085 (partial): Keep Current Model On Settings Change

**Related UC**: UC-023 A2, UC-005

Empty input at the model prompt in `/settings` keeps the current provider/model.
