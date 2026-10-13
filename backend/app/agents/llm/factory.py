"""LLM provider factory: configuration-driven selection, per-agent overrides,
and explicit opt-in fallback. Never silently switches providers."""

import os
import re

from app.agents.llm.base import BaseLLMProvider, LLMAPIError, LLMError
from app.agents.llm.model_registry import PROVIDERS, supported_providers
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("agentforge.llm")


def agent_env_key(agent_name: str | None) -> str:
    """Map an agent display name to its env-override suffix, e.g. 'Planning Agent' -> 'PLANNING_AGENT'."""
    if not agent_name:
        return ""
    return re.sub(r"[^A-Z0-9]+", "_", agent_name.upper()).strip("_")


class FallbackLLMProvider(BaseLLMProvider):
    """Wraps primary + explicitly configured fallback. Fails over only on transient or
    model-availability errors — never on auth, validation, filtering or context errors."""

    name = "fallback"
    NON_FALLBACK_ERRORS = (
        "LLMAuthError",
        "LLMValidationError",
        "LLMContentFilterError",
        "LLMContextLengthError",
    )

    def __init__(self, primary: BaseLLMProvider, fallback: BaseLLMProvider):
        super().__init__()
        self.primary = primary
        self.fallback = fallback
        self.supports_structured_output = primary.supports_structured_output
        self.supports_streaming = primary.supports_streaming

    def _should_fallback(self, err: Exception) -> bool:
        if not isinstance(err, LLMError):
            return True  # unexpected transport failure -> try the fallback once
        return type(err).__name__ not in self.NON_FALLBACK_ERRORS

    def complete(self, system: str, user: str, temperature=None, max_tokens=None, timeout=None) -> str:
        try:
            text = self.primary.complete(system, user, temperature, max_tokens, timeout)
            self.last_usage = dict(self.primary.last_usage or {})
            return text
        except Exception as exc:
            if not self._should_fallback(exc):
                raise
            logger.warning(
                "primary provider failed, using configured fallback",
                extra={"event": "llm_fallback", "error": str(exc)[:300]},
            )
            text = self.fallback.complete(system, user, temperature, max_tokens, timeout)
            self.last_usage = dict(self.fallback.last_usage or {})
            return text


def _build_adapter(provider: str, model: str) -> BaseLLMProvider:
    if provider == "mock":
        from app.agents.llm.mock import MockLLMProvider

        return MockLLMProvider()
    if provider in ("opencode_zen", "opencode-zen", "zen"):
        from app.agents.llm.opencode_zen import OpenCodeZenProvider

        return OpenCodeZenProvider(model=model or None)
    if provider == "openrouter":
        from app.agents.llm.openrouter import OpenRouterProvider

        return OpenRouterProvider(model=model or None)
    if provider in ("nvidia", "nim"):
        from app.agents.llm.nvidia import NvidiaProvider

        return NvidiaProvider(model=model or None)
    if provider in ("openai", "openai-compatible", "opencode"):
        from app.agents.llm.openai_compat import OpenAICompatibleLLMProvider

        return OpenAICompatibleLLMProvider(model=model or None)
    if provider in ("gemini", "google"):
        from app.agents.llm.gemini import GeminiProvider

        return GeminiProvider(model=model or None)
    raise ValueError(
        f"Unknown LLM provider '{provider}'. Supported: {', '.join(supported_providers())}. "
        "Set LLM_PROVIDER (or LLM_PRIMARY_PROVIDER) to one of them."
    )


def get_llm_provider(agent_name: str | None = None) -> BaseLLMProvider:
    """Resolve the provider for an agent run.

    Precedence: per-agent env (LLM_PROVIDER_<AGENT> / LLM_MODEL_<AGENT>) >
    LLM_PRIMARY_PROVIDER/LLM_PROVIDER + LLM_MODEL. An explicitly configured
    LLM_FALLBACK_PROVIDER wraps the primary; otherwise failures are raised clearly.
    """
    key = agent_env_key(agent_name)
    provider = os.environ.get(f"LLM_PROVIDER_{key}", "") if key else ""
    model = os.environ.get(f"LLM_MODEL_{key}", "") if key else ""
    provider = provider or settings.llm_primary_provider or settings.llm_provider or "mock"
    provider = provider.lower()
    model = model or settings.llm_model
    primary = _build_adapter(provider, model)

    fallback_name = (settings.llm_fallback_provider or "").lower()
    if fallback_name and fallback_name != provider and fallback_name in PROVIDERS:
        fallback_model = settings.llm_fallback_model or model
        fallback = _build_adapter(fallback_name, fallback_model)
        logger.info(
            "LLM fallback configured",
            extra={"event": "llm_fallback_config", "error": f"{provider}->{fallback_name}"},
        )
        return FallbackLLMProvider(primary, fallback)
    return primary
