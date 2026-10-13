"""Centralized model/provider capability registry.

Single source of truth for provider endpoints, default models and capabilities
(context limit, native structured-output support, streaming). Agents never scatter
model names through code — they resolve capabilities here through the factory.

Limits marked None are unknown (not fabricated); the pipeline treats unknown as
"proceed with prompt-size caution" and always validates structured output.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key_env: str
    base_url_env: str
    default_base_url: str
    default_model: str
    chat_path: str = "/chat/completions"
    structured_output: bool = False
    streaming: bool = True


@dataclass(frozen=True)
class ModelCapability:
    provider: str
    model: str
    context_limit: int | None
    structured_output: bool
    streaming: bool
    notes: str = ""


PROVIDERS: dict[str, ProviderConfig] = {
    "opencode_zen": ProviderConfig(
        name="opencode_zen",
        api_key_env="OPENCODE_ZEN_API_KEY",
        base_url_env="OPENCODE_ZEN_BASE_URL",
        default_base_url="https://opencode.ai/zen/v1",
        default_model="deepseek-v4-flash",
    ),
    "openrouter": ProviderConfig(
        name="openrouter",
        api_key_env="OPENROUTER_API_KEY",
        base_url_env="OPENROUTER_BASE_URL",
        default_base_url="https://openrouter.ai/api/v1",
        default_model="",
    ),
    "nvidia": ProviderConfig(
        name="nvidia",
        api_key_env="NVIDIA_API_KEY",
        base_url_env="NVIDIA_BASE_URL",
        default_base_url="https://integrate.api.nvidia.com/v1",
        default_model="meta/llama-3.1-8b-instruct",
    ),
    "openai": ProviderConfig(
        name="openai",
        api_key_env="LLM_API_KEY",
        base_url_env="LLM_BASE_URL",
        default_base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        structured_output=True,
    ),
    "gemini": ProviderConfig(
        name="gemini",
        api_key_env="LLM_API_KEY",
        base_url_env="LLM_BASE_URL",
        default_base_url="https://generativelanguage.googleapis.com",
        default_model="gemini-1.5-flash",
    ),
    "mock": ProviderConfig(
        name="mock",
        api_key_env="",
        base_url_env="",
        default_base_url="",
        default_model="mock",
    ),
}

# Known models (verified against public provider docs where possible; unknown models
# fall back to provider defaults with conservative capabilities).
MODEL_CATALOG: dict[tuple[str, str], ModelCapability] = {
    ("opencode_zen", "deepseek-v4-flash"): ModelCapability("opencode_zen", "deepseek-v4-flash", None, False, True, "Zen OpenAI-compatible endpoint"),
    ("opencode_zen", "deepseek-v4-pro"): ModelCapability("opencode_zen", "deepseek-v4-pro", None, False, True, "Zen OpenAI-compatible endpoint"),
    ("opencode_zen", "kimi-k3"): ModelCapability("opencode_zen", "kimi-k3", None, False, True, "Zen OpenAI-compatible endpoint"),
    ("opencode_zen", "minimax-m3"): ModelCapability("opencode_zen", "minimax-m3", None, False, True, "Zen OpenAI-compatible endpoint"),
    ("opencode_zen", "qwen3-coder"): ModelCapability("opencode_zen", "qwen3-coder", None, False, True, "Zen OpenAI-compatible endpoint"),
    ("opencode_zen", "grok-code"): ModelCapability("opencode_zen", "grok-code", None, False, True, "Zen OpenAI-compatible endpoint"),
    ("nvidia", "meta/llama-3.1-8b-instruct"): ModelCapability("nvidia", "meta/llama-3.1-8b-instruct", 128000, False, True, "NVIDIA NIM cloud endpoint"),
    ("nvidia", "meta/llama-3.1-70b-instruct"): ModelCapability("nvidia", "meta/llama-3.1-70b-instruct", 128000, False, True, "NVIDIA NIM cloud endpoint"),
    ("nvidia", "moonshotai/kimi-k2-instruct"): ModelCapability("nvidia", "moonshotai/kimi-k2-instruct", None, False, True, "NVIDIA NIM cloud endpoint"),
}


def resolve_capability(provider: str, model: str) -> ModelCapability:
    """Return capabilities for a provider+model; unknown models get conservative defaults."""
    key = (provider, model)
    if key in MODEL_CATALOG:
        return MODEL_CATALOG[key]
    cfg = PROVIDERS.get(provider)
    return ModelCapability(
        provider=provider,
        model=model,
        context_limit=None,
        structured_output=bool(cfg.structured_output) if cfg else False,
        streaming=bool(cfg.streaming) if cfg else False,
        notes="Unlisted model — conservative defaults; strict prompting + validation apply",
    )


def supported_providers() -> list[str]:
    return sorted(PROVIDERS.keys())
