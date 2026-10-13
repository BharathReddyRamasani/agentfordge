"""Google Gemini provider (generative-language REST API)."""

import httpx

from app.agents.llm.base import BaseLLMProvider, LLMAuthError, LLMAPIError
from app.agents.llm.http import post_json
from app.agents.llm.model_registry import PROVIDERS, resolve_capability
from app.core.config import settings


class GeminiProvider(BaseLLMProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        super().__init__()
        cfg = PROVIDERS[self.name]
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model or cfg.default_model
        self.capability = resolve_capability(self.name, self.model)
        self.supports_streaming = self.capability.streaming
        self._transport = transport

    def complete(
        self,
        system: str,
        user: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> str:
        if not self.api_key:
            raise LLMAuthError(
                f"{self.name}: missing API key — set LLM_API_KEY",
                provider=self.name, model=self.model,
            )
        temperature, max_tokens, timeout = self._defaults(temperature, max_tokens, timeout)
        client = httpx.Client(transport=self._transport, timeout=timeout) if self._transport else None
        try:
            data = post_json(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
                payload={
                    "system_instruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": user}]}],
                    "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
                },
                timeout=timeout, max_retries=settings.llm_max_retries,
                provider=self.name, model=self.model, client=client,
            )
        finally:
            if client is not None:
                client.close()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMAPIError(
                f"{self.name}: malformed response", provider=self.name, model=self.model,
                details={"error": str(exc)[:200]},
            ) from exc
        usage = data.get("usageMetadata", {}) or {}
        self.last_usage = {
            "provider": self.name, "model": self.model,
            "prompt_tokens": usage.get("promptTokenCount", 0),
            "completion_tokens": usage.get("candidatesTokenCount", 0),
            "tokens": usage.get("totalTokenCount", 0),
        }
        return text
