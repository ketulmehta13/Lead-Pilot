"""Provider adapters: request/response translation (no network)."""

import json

import httpx
import pytest

from genai import llm

pytestmark = pytest.mark.django_db

TOOLS = [
    {
        "name": "search_leads",
        "description": "Find leads",
        "parameters": {"type": "object", "properties": {"label": {"type": "string"}}},
    }
]


def test_provider_auto_detection(monkeypatch):
    for key in ("LLM_PROVIDER", "GROQ_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    assert llm.provider_name() == "mock" and not llm.is_configured()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert llm.provider_name() == "anthropic"
    assert llm.model_name("anthropic") == "claude-opus-5-5"
    monkeypatch.setenv("GROQ_API_KEY", "x")
    assert llm.provider_name() == "groq"
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    assert llm.provider_name() == "openai"


def test_groq_adapter_translates_tools_and_tool_calls(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    sent = {}

    def fake_post(url, json, headers, timeout):
        sent.update(url=url, body=json, headers=headers)
        return httpx.Response(
            200,
            json={
                "model": "llama-3.3-70b-versatile",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": "search_leads",
                                                 "arguments": '{"label": "hot"}'},  # fmt: skip
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 120, "completion_tokens": 9},
            },
        )

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    history = [
        {"role": "system", "content": "be helpful"},
        {"role": "user", "content": "find hot leads"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c0", "name": "search_leads", "arguments": {"label": "warm"}}]},
        {"role": "tool", "tool_call_id": "c0", "content": "[]"},
    ]  # fmt: skip
    result = llm._ADAPTERS["groq"](history, TOOLS, None, "llama-3.3-70b-versatile", 500)
    assert sent["url"].startswith("https://api.groq.com/")
    assert sent["headers"]["Authorization"] == "Bearer test-key"
    assert sent["body"]["tools"][0]["function"]["name"] == "search_leads"
    assert sent["body"]["messages"][2]["tool_calls"][0]["function"]["arguments"] == json.dumps(
        {"label": "warm"}
    )
    assert sent["body"]["messages"][3] == {"role": "tool", "tool_call_id": "c0", "content": "[]"}
    assert result.tool_calls[0].arguments == {"label": "hot"}
    assert (result.prompt_tokens, result.completion_tokens) == (120, 9)


def test_groq_429_is_retryable_and_400_is_not(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setattr(
        llm.httpx, "post", lambda *a, **k: httpx.Response(429, headers={"retry-after": "3"})
    )
    with pytest.raises(llm._Retryable) as err:
        llm._ADAPTERS["groq"]([{"role": "user", "content": "x"}], None, None, "m", 10)
    assert err.value.retry_after == 3.0
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: httpx.Response(400, text="bad"))
    with pytest.raises(llm.LLMError) as err:
        llm._ADAPTERS["groq"]([{"role": "user", "content": "x"}], None, None, "m", 10)
    assert not isinstance(err.value, llm._Retryable)


def test_json_mode_adds_schema_instruction(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    sent = {}

    def fake_post(url, json, headers, timeout):
        sent.update(json)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    llm._ADAPTERS["groq"]([{"role": "user", "content": "x"}], None, schema, "m", 10)
    assert sent["response_format"] == {"type": "json_object"}
    assert "JSON schema" in sent["messages"][-1]["content"]


def test_anthropic_message_conversion_groups_tool_results():
    system, messages = llm._anthropic_messages(
        [
            {"role": "system", "content": "rules"},
            {"role": "user", "content": "go"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "a", "name": "t", "arguments": {}},
                {"id": "b", "name": "t", "arguments": {}}]},
            {"role": "tool", "tool_call_id": "a", "content": "1"},
            {"role": "tool", "tool_call_id": "b", "content": "2", "is_error": True},
        ]
    )  # fmt: skip
    assert system == "rules"
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    results = messages[2]["content"]
    assert [r["tool_use_id"] for r in results] == ["a", "b"] and results[1]["is_error"] is True


def test_anthropic_replays_raw_blocks_unchanged():
    raw = [{"type": "thinking", "thinking": "", "signature": "sig"},
           {"type": "tool_use", "id": "x", "name": "t", "input": {}}]  # fmt: skip
    _, messages = llm._anthropic_messages(
        [{"role": "user", "content": "go"},
         {"role": "assistant", "content": "", "provider_raw": raw}]  # fmt: skip
    )
    assert messages[1]["content"] is raw


def test_strict_schema_closes_objects():
    schema = {"type": "object", "properties": {"x": {"type": "object", "properties": {}}}}
    strict = llm._strict_schema(schema)
    assert strict["additionalProperties"] is False
    assert strict["properties"]["x"]["additionalProperties"] is False
    assert "additionalProperties" not in schema  # input untouched
