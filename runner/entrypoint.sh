#!/usr/bin/env bash
# Тонкая точка входа self-hosted runner'а: конфигурирует агента только при
# первой регистрации (состояние сохраняется в volume) и запускает его.
# Внутри образа нет ничего, кроме runner'а и jq: git/curl уже присутствуют в
# базовом образе. Никаких LLM-ключей и доступов к БД здесь нет.
set -euo pipefail

cd /home/runner

if [ ! -f .runner ]; then
  : "${RUNNER_TOKEN:?RUNNER_TOKEN обязателен при первой регистрации}"
  : "${REPO_URL:?REPO_URL обязателен (например, https://github.com/owner/repo)}"
  ./config.sh \
    --url "$REPO_URL" \
    --token "$RUNNER_TOKEN" \
    --name "${RUNNER_NAME:-ai-challenge-runner}" \
    --labels "${LABELS:-self-hosted,linux,x64}" \
    --unattended \
    --replace
fi

exec ./run.sh
