"""LLM provider layer: selection, fallback, error normalization, retries, registry."""

import httpx
import pytest
from pydantic import BaseModel

from app.agents.llm import factory as factory_module
from app.agents.llm.base import (
    LLMAuthError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMAPIError,
    LLMValidationError,
)
from app.agents.llm.factory import FallbackLLMProvider, agent_env_key, get_llm_provider
from app.agents.llm.mock import MockLLMProvider
from app.agents.llm.model_registry import PROVIDERS, resolve_capability, supported_providers
from app.agents.llm.nvidia import NvidiaProvider
from app.agents.llm.opencode_zen import OpenCodeZenProvider
from app.agents.llm.openrouter import OpenRouterProvider


class TinySchema(BaseModel):
    answer: str


def _chat_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}], "usage": {"total_tokens": 7}},
    )


def _transport(handler):
    return httpx.MockTransport(handler)


# ------------------------------------------------------------- selection


def test_supported_providers_listed():
    providers = supported_providers()
    for name in ("opencode_zen", "openrouter", "nvidia", "mock"):
        assert name in providers


def test_factory_builds_named_providers():
    assert isinstance(_build("opencode_zen"), OpenCodeZenProvider)
    assert isinstance(_build("openrouter"), OpenRouterProvider)
    assert isinstance(_build("nvidia"), NvidiaProvider)
    assert isinstance(_build("mock"), MockLLMProvider)


def _build(name: str):
    from app.agents.llm.factory import _build_adapter

    return _build_adapter(name, "test-model")


def test_factory_unknown_provider_fails_clearly():
    from app.agents.llm.factory import _build_adapter

    with pytest.raises(ValueError, match="Unknown LLM provider"):
        _build_adapter("nonexistent", "x")


def test_agent_env_key_mapping():
    assert agent_env_key("Planning Agent") == "PLANNING_AGENT"
    assert agent_env_key("Product/UX & Prototype Agent") == "PRODUCT_UX_PROTOTYPE_AGENT"
    assert agent_env_key(None) == ""


def test_per_agent_env_override(monkeypatch):
    from types import SimpleNamespace

    fake = SimpleNamespace(
        llm_primary_provider="", llm_provider="mock", llm_model="m",
        llm_fallback_provider="", llm_fallback_model="",
    )
    monkeypatch.setattr(factory_module, "settings", fake)
    monkeypatch.setenv("LLM_PROVIDER_PLANNING_AGENT", "openrouter")
    monkeypatch.setenv("LLM_MODEL_PLANNING_AGENT", "some-model")
    provider = get_llm_provider(agent_name="Planning Agent")
    assert isinstance(provider, OpenRouterProvider)
    assert provider.model == "some-model"


# ------------------------------------------------------------- behavior


def test_openrouter_completes_with_usage():
    provider = OpenRouterProvider(api_key="k", model="m", transport=_transport(lambda req: _chat_response("hi")))
    assert provider.complete("sys", "user") == "hi"
    assert provider.last_usage["provider"] == "openrouter"
    assert provider.last_usage["tokens"] == 7


def test_openrouter_sends_gateway_headers():
    seen = {}

    def handler(req: httpx.Request):
        seen["referer"] = req.headers.get("HTTP-Referer")
        seen["title"] = req.headers.get("X-Title")
        return _chat_response("ok")

    OpenRouterProvider(api_key="k", model="m", transport=_transport(handler)).complete("s", "u")
    assert seen["referer"] and seen["title"] == "AgentForge"


def test_zen_missing_key_fails_clearly():
    provider = OpenCodeZenProvider(api_key="", model="deepseek-v4-flash")
    with pytest.raises(LLMAuthError, match="OPENCODE_ZEN_API_KEY"):
        provider.complete("s", "u")


def test_auth_error_not_retried():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(401, json={"error": "invalid key"})

    provider = NvidiaProvider(api_key="bad", model="m", transport=_transport(handler))
    with pytest.raises(LLMAuthError):
        provider.complete("s", "u")
    assert len(calls) == 1


def test_rate_limit_retried_then_succeeds():
    calls = []

    def handler(req):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, json={"error": "slow down"})
        return _chat_response("recovered")

    provider = OpenRouterProvider(api_key="k", model="m", transport=_transport(handler))
    assert provider.complete("s", "u") == "recovered"
    assert len(calls) == 2


def test_persistent_rate_limit_raises():
    provider = OpenCodeZenProvider(
        api_key="k", model="m", transport=_transport(lambda req: httpx.Response(429, json={}))
    )
    with pytest.raises(LLMRateLimitError):
        provider.complete("s", "u")


def test_timeout_normalized():
    def handler(req):
        raise httpx.ConnectTimeout("too slow")

    provider = NvidiaProvider(api_key="k", model="m", transport=_transport(handler))
    with pytest.raises(LLMTimeoutError):
        provider.complete("s", "u", timeout=1)


def test_malformed_response_is_api_error():
    provider = OpenRouterProvider(
        api_key="k", model="m", transport=_transport(lambda req: httpx.Response(200, json={"nope": True}))
    )
    with pytest.raises(LLMAPIError):
        provider.complete("s", "u")


def test_model_not_found_normalized():
    provider = OpenRouterProvider(
        api_key="k", model="ghost",
        transport=_transport(lambda req: httpx.Response(404, json={"error": "model not found"})),
    )
    from app.agents.llm.base import LLMModelNotFoundError

    with pytest.raises(LLMModelNotFoundError):
        provider.complete("s", "u")


def test_complete_json_validates_and_retries_correction():
    outputs = ['not json at all', '{"answer": 42}', '{"answer": "yes"}']
    provider = OpenRouterProvider(api_key="k", model="m", transport=_transport(lambda req: _chat_response(outputs.pop(0))))
    model, usage = provider.complete_json("sys", {"input": {}}, TinySchema, "test_task", max_retries=2)
    assert model.answer == "yes"
    assert usage["attempt"] == 3


def test_complete_json_gives_up_with_validation_error():
    provider = OpenRouterProvider(
        api_key="k", model="m", transport=_transport(lambda req: _chat_response("garbage"))
    )
    with pytest.raises(LLMValidationError):
        provider.complete_json("sys", {"input": {}}, TinySchema, "test_task", max_retries=1)


# ------------------------------------------------------------- fallback


def test_fallback_serves_on_transient_failure():
    primary = OpenRouterProvider(api_key="k", model="m", transport=_transport(lambda req: httpx.Response(500, json={})))
    fallback = MockLLMProvider()
    wrapped = FallbackLLMProvider(primary, fallback)
    assert "mock" in wrapped.complete("s", "u")
    assert wrapped.last_usage["provider"] == "mock"


def test_fallback_never_on_auth_failure():
    primary = OpenRouterProvider(api_key="k", model="m", transport=_transport(lambda req: httpx.Response(401, json={})))
    wrapped = FallbackLLMProvider(primary, MockLLMProvider())
    with pytest.raises(LLMAuthError):
        wrapped.complete("s", "u")


def test_no_fallback_configured_fails_clearly(monkeypatch):
    from types import SimpleNamespace

    fake = SimpleNamespace(
        llm_primary_provider="", llm_provider="openrouter", llm_model="m",
        llm_fallback_provider="", llm_fallback_model="",
    )
    monkeypatch.setattr(factory_module, "settings", fake)
    provider = get_llm_provider()
    assert isinstance(provider, OpenRouterProvider)
    assert not isinstance(provider, FallbackLLMProvider)


# ------------------------------------------------------------- registry


def test_registry_known_and_unknown_models():
    assert "opencode_zen" in PROVIDERS
    assert PROVIDERS["nvidia"].default_base_url == "https://integrate.api.nvidia.com/v1"
    assert PROVIDERS["opencode_zen"].default_base_url == "https://opencode.ai/zen/v1"
    known = resolve_capability("nvidia", "meta/llama-3.1-8b-instruct")
    assert known.context_limit == 128000
    unknown = resolve_capability("openrouter", "some/future-model")
    assert unknown.context_limit is None
    assert unknown.structured_output is False


def test_no_raw_error_leaks_provider_keys():
    err = LLMError("boom", provider="openrouter", model="m", details={"x": 1})
    assert "sk-" not in err.public_message()
    assert isinstance(err.public_message(), str)
