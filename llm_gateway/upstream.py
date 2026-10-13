"""HTTP-клиент к реальной Ollama (upstream для gateway)."""

from __future__ import annotations

from typing import Any

import requests

from llm_gateway.queue import Result


class OllamaUpstream:
    """Синхронный клиент Ollama. Вызывается только потребителем очереди."""

    def __init__(self, base_url: str, timeout: int = 300) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(self, method: str, path: str, payload: Any = None) -> Result:
        """Вызывает upstream-эндпоинт и оборачивает ответ в ``Result``."""
        url = f"{self.base_url}{path}"
        try:
            if method.upper() == "GET":
                response = requests.get(url, timeout=self.timeout)
            else:
                response = requests.post(
                    url, json=payload, timeout=self.timeout
                )
        except requests.RequestException as exc:
            return Result(
                status=502,
                body={"error": f"Ollama недоступна: {exc}"},
                error=str(exc),
            )

        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text}
        return Result(status=response.status_code, body=body)
