"""Test helper: script the LLM's replies and inspect what was sent to it.

    with scripted_llm(['{"subject": "Hi", "body": "..."}']) as calls:
        ...
        assert "Acme" in calls[0]["messages"][0]["content"]

Each scripted reply is either a string (the content) or an LLMResponse (e.g. with tool calls)
or an Exception instance to raise.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from . import llm


@contextmanager
def scripted_llm(replies: list[Any]) -> Iterator[list[dict[str, Any]]]:
    queue = list(replies)
    calls: list[dict[str, Any]] = []

    def fake(messages, tools, json_schema, model, max_tokens):
        calls.append({"messages": messages, "tools": tools, "json_schema": json_schema})
        if not queue:
            raise AssertionError("scripted_llm: no reply left for this call")
        reply = queue.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, llm.LLMResponse):
            return reply
        return llm.LLMResponse(content=reply, prompt_tokens=10, completion_tokens=5, model=model)

    original_mock = llm._ADAPTERS["mock"]
    original_provider = llm.provider_name
    llm._ADAPTERS["mock"] = fake
    llm.provider_name = lambda: "mock"
    try:
        yield calls
    finally:
        llm._ADAPTERS["mock"] = original_mock
        llm.provider_name = original_provider
