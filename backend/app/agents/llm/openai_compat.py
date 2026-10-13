"""Generic OpenAI-compatible provider (custom endpoints: OpenAI, Azure, vLLM, Ollama, ...)."""

import httpx

from app.agents.llm.base import BaseLLMProvider, LLMAuthError
from app.agents.llm.http import chat_completion
from app.agents.llm.model_registry import PROVIDERS, resolve_capability
from app.core.config import settings


class OpenAICompatibleLLMProvider(BaseLLMProvider):
    name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        super().__init__()
        cfg = PROVIDERS[self.name]
        self.api_key = api_key or settings.llm_api_key
        self.base_url = (base_url or settings.llm_base_url or cfg.default_base_url).rstrip("/")
        self.model = model or settings.llm_model or cfg.default_model
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
                f"{self.name}: missing API key — set LLM_API_KEY",
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
                client=client,
            )
        finally:
            if client is not None:
                client.close()
        self.last_usage = {"provider": self.name, "model": self.model, **usage}
        return text
