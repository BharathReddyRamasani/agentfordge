"""OpenRouter provider: unified multi-model gateway, OpenAI-compatible chat endpoint.

Base: https://openrouter.ai/api/v1 (+ /chat/completions).
Key from OPENROUTER_API_KEY (falls back to LLM_API_KEY).
Sends HTTP-Referer / X-Title app headers per OpenRouter policy.
"""

import httpx

from app.agents.llm.base import BaseLLMProvider, LLMAuthError
from app.agents.llm.http import chat_completion
from app.agents.llm.model_registry import PROVIDERS, resolve_capability
from app.core.config import settings


class OpenRouterProvider(BaseLLMProvider):
    name = "openrouter"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        super().__init__()
        cfg = PROVIDERS[self.name]
        self.api_key = api_key or settings.openrouter_api_key or settings.llm_api_key
        self.base_url = (base_url or settings.openrouter_base_url or cfg.default_base_url).rstrip("/")
        self.model = model or settings.llm_model or cfg.default_model
        if not self.model:
            raise LLMAuthError(
                f"{self.name}: no model configured — set LLM_MODEL",
                provider=self.name, model="",
            )
        self.capability = resolve_capability(self.name, self.model)
        self.supports_structured_output = self.capability.structured_output
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
                f"{self.name}: missing API key — set OPENROUTER_API_KEY",
                provider=self.name, model=self.model,
            )
        temperature, max_tokens, timeout = self._defaults(temperature, max_tokens, timeout)
        client = httpx.Client(transport=self._transport, timeout=timeout) if self._transport else None
        try:
            text, usage = chat_completion(
                self.base_url, api_key=self.api_key, model=self.model,
                system=system, user=user, temperature=temperature, max_tokens=max_tokens,
                timeout=timeout, max_retries=settings.llm_max_retries,
                provider=self.name, use_json_mode=self.supports_structured_output,
                extra_headers={"HTTP-Referer": settings.openrouter_referer, "X-Title": "AgentForge"},
                client=client,
            )
        finally:
            if client is not None:
                client.close()
        self.last_usage = {"provider": self.name, "model": self.model, **usage}
        return text
