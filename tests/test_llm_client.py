from __future__ import annotations

from app.services.llm_client import (
    LLMConfig,
    chat_completions_url,
    chat_headers,
    chat_payload,
    load_llm_config,
)


def test_chat_completions_url_accepts_bailian_base_url() -> None:
    assert (
        chat_completions_url("https://dashscope.aliyuncs.com/compatible-mode/v1")
        == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    )


def test_chat_headers_use_bearer_token() -> None:
    config = LLMConfig(
        provider="bailian",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-plus",
        api_key="sk-test",
        timeout=30,
        enable_thinking=None,
    )

    assert chat_headers(config)["Authorization"] == "Bearer sk-test"


def test_chat_payload_is_openai_compatible() -> None:
    config = LLMConfig(
        provider="bailian",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-plus",
        api_key=None,
        timeout=30,
        enable_thinking=None,
    )

    payload = chat_payload(
        config=config,
        messages=[{"role": "user", "content": "hello"}],
        temperature=0.3,
        max_tokens=512,
    )

    assert payload == {
        "model": "qwen-plus",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": False,
        "temperature": 0.3,
        "max_tokens": 512,
    }


def test_load_llm_config_accepts_dashscope_api_key(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "bailian")
    monkeypatch.setenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("BAILIAN_API_KEY", raising=False)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL", "qwen-plus")

    config = load_llm_config()

    assert config.provider == "bailian"
    assert config.api_key == "sk-test"
    assert config.model == "qwen-plus"


def test_bailian_provider_defaults_do_not_use_ollama_model(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "bailian")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("BAILIAN_MODEL", raising=False)
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3-lora")

    config = load_llm_config()

    assert config.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert config.model == "qwen-plus"


def test_qwen3_bailian_disables_thinking_by_default(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "bailian")
    monkeypatch.setenv("LLM_MODEL", "qwen3.5-flash")

    config = load_llm_config()
    payload = chat_payload(
        config=config,
        messages=[{"role": "user", "content": "hello"}],
        temperature=0.3,
        max_tokens=256,
    )

    assert config.enable_thinking is False
    assert payload["enable_thinking"] is False
