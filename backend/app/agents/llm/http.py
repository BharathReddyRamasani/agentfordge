"""Shared HTTP transport for OpenAI-compatible providers.

Timeouts, bounded retries with exponential backoff + jitter on 429/5xx/network
errors, and normalized errors. An httpx client (or transport) can be injected for
tests — production paths always use real network I/O with a timeout.
"""

import random
import time

import httpx

from app.agents.llm.base import LLMAPIError, LLMTimeoutError, normalize_http_error


def post_json(
    url: str,
    *,
    headers: dict,
    payload: dict,
    timeout: float,
    max_retries: int,
    provider: str,
    model: str,
    client: httpx.Client | None = None,
) -> dict:
    """POST JSON and return the decoded body. Raises normalized LLMError on failure."""
    own_client = client is None
    client = client or httpx.Client(timeout=timeout)
    try:
        attempt = 0
        while True:
            try:
                resp = client.post(url, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                err: Exception = LLMTimeoutError(
                    f"{provider}: request timed out after {timeout}s",
                    provider=provider, model=model, details={"error": type(exc).__name__},
                )
            except httpx.HTTPError as exc:
                err = LLMAPIError(
                    f"{provider}: network error: {type(exc).__name__}",
                    provider=provider, model=model, details={"error": str(exc)[:200]},
                )
            else:
                if resp.status_code < 400:
                    try:
                        return resp.json()
                    except ValueError as exc:
                        err = LLMAPIError(
                            f"{provider}: invalid JSON response",
                            provider=provider, model=model, details={"error": str(exc)[:200]},
                        )
                else:
                    err = normalize_http_error(resp.status_code, resp.text, provider=provider, model=model)
            retryable = getattr(err, "retryable", False) is True
            if not retryable or attempt >= max_retries:
                raise err
            delay = min(2**attempt + random.uniform(0, 0.5), 30.0)
            time.sleep(delay)
            attempt += 1
    finally:
        if own_client:
            client.close()


def chat_completion(
    base_url: str,
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    timeout: float,
    max_retries: int,
    provider: str,
    extra_headers: dict | None = None,
    use_json_mode: bool = False,
    client: httpx.Client | None = None,
) -> tuple[str, dict]:
    """Call an OpenAI-compatible /chat/completions endpoint. Returns (text, usage)."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    body: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if use_json_mode:
        body["response_format"] = {"type": "json_object"}
    data = post_json(
        base_url.rstrip("/") + "/chat/completions",
        headers=headers, payload=body, timeout=timeout, max_retries=max_retries,
        provider=provider, model=model, client=client,
    )
    try:
        message = data["choices"][0]["message"]
        content = message.get("content") or ""
        if isinstance(content, list):  # content-part arrays
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        usage = data.get("usage", {}) or {}
        usage_info = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "tokens": usage.get("total_tokens", 0),
        }
        return str(content), usage_info
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMAPIError(
            f"{provider}: malformed chat-completion response",
            provider=provider, model=model, details={"error": str(exc)[:200]},
        ) from exc
