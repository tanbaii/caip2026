from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11545"
DEFAULT_OLLAMA_MODEL = "qwen3-lora"
DEFAULT_BAILIAN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_BAILIAN_MODEL = "qwen-plus"


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    base_url: str
    model: str
    api_key: str | None
    timeout: float
    enable_thinking: bool | None


def load_llm_config(
    *,
    base_url: str | None = None,
    model: str | None = None,
    timeout: float | None = None,
    timeout_env: str = "LLM_TIMEOUT",
) -> LLMConfig:
    provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    env_base_url = os.getenv("LLM_BASE_URL") or os.getenv("BAILIAN_BASE_URL")
    if not env_base_url and provider == "bailian":
        env_base_url = DEFAULT_BAILIAN_BASE_URL
    env_base_url = env_base_url or os.getenv("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL
    configured_base_url = (base_url or env_base_url).rstrip("/")

    if not provider:
        if "dashscope.aliyuncs.com" in configured_base_url:
            provider = "bailian"
        elif os.getenv("LLM_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or os.getenv("BAILIAN_API_KEY"):
            provider = "openai-compatible"
        else:
            provider = "ollama"

    if model:
        configured_model = model
    elif provider == "bailian":
        configured_model = os.getenv("LLM_MODEL") or os.getenv("BAILIAN_MODEL") or DEFAULT_BAILIAN_MODEL
    else:
        configured_model = os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
    api_key = os.getenv("LLM_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or os.getenv("BAILIAN_API_KEY")
    configured_timeout = timeout if timeout is not None else float(os.getenv(timeout_env, os.getenv("LLM_TIMEOUT", "30")))
    configured_enable_thinking = _optional_bool(os.getenv("LLM_ENABLE_THINKING"))
    if configured_enable_thinking is None and provider == "bailian" and configured_model.lower().startswith("qwen3"):
        configured_enable_thinking = False

    return LLMConfig(
        provider=provider,
        base_url=configured_base_url,
        model=configured_model,
        api_key=api_key,
        timeout=configured_timeout,
        enable_thinking=configured_enable_thinking,
    )


def chat_completions_url(base_url: str) -> str:
    clean = base_url.rstrip("/")
    if clean.endswith("/chat/completions"):
        return clean
    if clean.endswith("/v1"):
        return f"{clean}/chat/completions"
    return f"{clean}/v1/chat/completions"


def chat_headers(config: LLMConfig) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    return headers


def chat_payload(
    *,
    config: LLMConfig,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    payload = {
        "model": config.model,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if config.enable_thinking is not None:
        payload["enable_thinking"] = config.enable_thinking
    return payload


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def post_chat_completion(config: LLMConfig, payload: dict[str, Any]) -> dict[str, Any]:
    import httpx

    with httpx.Client(timeout=config.timeout) as client:
        response = client.post(
            chat_completions_url(config.base_url),
            json=payload,
            headers=chat_headers(config),
        )
        response.raise_for_status()
        return response.json()


async def apost_chat_completion(config: LLMConfig, payload: dict[str, Any]) -> dict[str, Any]:
    import httpx

    async with httpx.AsyncClient(timeout=config.timeout) as client:
        response = await client.post(
            chat_completions_url(config.base_url),
            json=payload,
            headers=chat_headers(config),
        )
        response.raise_for_status()
        return response.json()


def first_choice_text(data: dict[str, Any]) -> str:
    return (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )


def _optional_bool(value: str | None) -> bool | None:
    if value is None or not value.strip():
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}
