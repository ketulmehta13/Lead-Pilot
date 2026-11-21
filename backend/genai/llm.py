"""Provider-neutral LLM wrapper. Every LLM call in LeadPilot goes through `chat()`.

    chat(messages, tools=None, json_schema=None, *, purpose, user=None) -> LLMResponse

Messages use a neutral, OpenAI-style shape:
    {"role": "system" | "user" | "assistant" | "tool", "content": str,
     "tool_calls": [{"id", "name", "arguments": dict}],   # assistant only
     "tool_call_id": str,                                    # tool only
     "provider_raw": ...}                                    # assistant only, see below
Tools: [{"name", "description", "parameters": <JSON schema>}].

Providers (env LLM_PROVIDER, default: groq if GROQ_API_KEY, else anthropic if
ANTHROPIC_API_KEY, else mock):
    groq       Groq's OpenAI-compatible REST API (default model openai/gpt-oss-120b)
    openai     OpenAI's REST API (same adapter, different base URL)
    anthropic  Claude via the official `anthropic` SDK (default model claude-opus-5-5)
    mock       deterministic offline output: tests, and running without any API key

Assistant turns carry `provider_raw` (Claude's content blocks, thinking included) so an agent
loop can send them back unchanged, as the Claude API requires.

API keys are read from env vars only. Every call has a timeout, retries with backoff on 429 /
5xx / network errors, and is logged to genai.LLMCall with token counts and latency.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_MODELS = {
    "groq": "openai/gpt-oss-120b",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-opus-5-5",
    "mock": "mock-1",
}
OPENAI_COMPATIBLE_URLS = {
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
}
KEY_ENV = {"groq": "GROQ_API_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}


class LLMError(Exception):
    """The provider failed (network, auth, rate limit after retries, bad request)."""


class LLMRefusal(LLMError):
    """The model declined the request."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    provider: str = ""
    stop_reason: str = ""
    provider_raw: Any = None

    def as_message(self) -> dict[str, Any]:
        """This reply as a neutral assistant message, ready to append to the conversation."""
        message: dict[str, Any] = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            message["tool_calls"] = [
                {"id": c.id, "name": c.name, "arguments": c.arguments} for c in self.tool_calls
            ]
        if self.provider_raw is not None:
            message["provider_raw"] = self.provider_raw
        return message


# --- configuration --------------------------------------------------------------------------


def provider_name() -> str:
    configured = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if configured:
        return configured
    for name in ("groq", "anthropic", "openai"):
        if os.environ.get(KEY_ENV[name]):
            return name
    return "mock"


def model_name(provider: str) -> str:
    return os.environ.get("LLM_MODEL", "").strip() or DEFAULT_MODELS[provider]


def is_configured() -> bool:
    """True when a real provider (not the offline mock) will answer."""
    return provider_name() != "mock"


def _timeout() -> float:
    return float(os.environ.get("LLM_TIMEOUT_SECONDS", "45"))


def _max_retries() -> int:
    return int(os.environ.get("LLM_MAX_RETRIES", "2"))


# --- public entry point ---------------------------------------------------------------------


def chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    json_schema: dict[str, Any] | None = None,
    *,
    purpose: str = "general",
    user=None,
    max_tokens: int = 4000,
) -> LLMResponse:
    """Send a conversation to the configured provider and return a normalized response.

    `json_schema` asks for a JSON object matching the schema (validate it yourself; see
    genai.services.structured_chat). `tools` enables function calling.
    """
    provider = provider_name()
    model = model_name(provider)
    adapter = _ADAPTERS.get(provider)
    if adapter is None:
        raise LLMError(f"Unknown LLM_PROVIDER '{provider}'.")

    started = time.monotonic()
    attempts = 0
    try:
        response, attempts = _with_retries(
            lambda: adapter(messages, tools, json_schema, model, max_tokens)
        )
    except LLMRefusal as exc:
        _log(user, purpose, provider, model, started, attempts or 1, "refused", str(exc))
        raise
    except LLMError as exc:
        _log(user, purpose, provider, model, started, attempts or 1, "error", str(exc))
        raise
    response.provider, response.model = provider, response.model or model
    _log(user, purpose, provider, response.model, started, attempts, "ok", "", response)
    return response


class _Retryable(LLMError):
    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def _with_retries(call) -> tuple[LLMResponse, int]:
    retries = _max_retries()
    for attempt in range(retries + 1):
        try:
            return call(), attempt + 1
        except _Retryable as exc:
            if attempt == retries:
                raise LLMError(f"{exc} (gave up after {retries + 1} attempts)") from exc
            delay = exc.retry_after or min(2**attempt + random.uniform(0, 0.5), 20)
            logger.warning("LLM call failed (%s); retrying in %.1fs", exc, delay)
            time.sleep(delay)
    raise AssertionError("unreachable")


def _log(user, purpose, provider, model, started, attempts, status, error, response=None):
    from .models import LLMCall  # local: keep this module importable without Django apps

    try:
        LLMCall.objects.create(
            user=user if getattr(user, "pk", None) else None,
            purpose=purpose[:40],
            provider=provider,
            model=model[:80],
            prompt_tokens=getattr(response, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(response, "completion_tokens", 0) or 0,
            latency_ms=int((time.monotonic() - started) * 1000),
            attempts=attempts,
            status=status,
            error=error[:2000],
        )
    except Exception:  # noqa: BLE001 - logging must never break the feature
        logger.exception("Could not log LLM call")


# --- OpenAI-compatible (Groq, OpenAI) -------------------------------------------------------


def _openai_messages(messages: list[dict[str, Any]], json_schema) -> list[dict[str, Any]]:
    out = []
    for m in messages:
        role = m["role"]
        if role == "assistant" and m.get("tool_calls"):
            out.append(
                {
                    "role": "assistant",
                    "content": m.get("content") or None,
                    "tool_calls": [
                        {
                            "id": c["id"],
                            "type": "function",
                            "function": {
                                "name": c["name"],
                                "arguments": json.dumps(c["arguments"]),
                            },
                        }
                        for c in m["tool_calls"]
                    ],
                }
            )
        elif role == "tool":
            out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
        else:
            out.append({"role": role, "content": m["content"]})
    if json_schema is not None:
        # json_object mode needs the word "JSON" and the shape in the prompt.
        out.append(
            {
                "role": "system",
                "content": "Respond with a single JSON object only, matching this JSON schema:\n"
                + json.dumps(json_schema),
            }
        )
    return out


def _openai_compatible(name: str):
    def call(messages, tools, json_schema, model, max_tokens) -> LLMResponse:
        key = os.environ.get(KEY_ENV[name], "")
        if not key:
            raise LLMError(f"{KEY_ENV[name]} is not set.")
        body: dict[str, Any] = {
            "model": model,
            "messages": _openai_messages(messages, json_schema),
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }
        if model.startswith("openai/gpt-oss"):
            # Reasoning model: keep thinking short (latency, and it shares max_tokens).
            body["reasoning_effort"] = os.environ.get("LLM_REASONING_EFFORT", "low")
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["parameters"],
                    },
                }
                for t in tools
            ]
        if json_schema is not None and not tools:
            body["response_format"] = {"type": "json_object"}
        try:
            r = httpx.post(
                OPENAI_COMPATIBLE_URLS[name],
                json=body,
                headers={"Authorization": f"Bearer {key}"},
                timeout=_timeout(),
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise _Retryable(f"{name} network error: {exc}") from exc
        if r.status_code == 429 or r.status_code >= 500:
            retry_after = r.headers.get("retry-after")
            raise _Retryable(
                f"{name} HTTP {r.status_code}",
                float(retry_after) if retry_after and retry_after.isdigit() else None,
            )
        if r.status_code >= 400:
            raise LLMError(f"{name} HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        choice = data["choices"][0]
        msg = choice["message"]
        calls = []
        for c in msg.get("tool_calls") or []:
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {"_raw": c["function"].get("arguments")}
            calls.append(ToolCall(id=c["id"], name=c["function"]["name"], arguments=args))
        usage = data.get("usage") or {}
        return LLMResponse(
            content=msg.get("content") or "",
            tool_calls=calls,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            model=data.get("model", model),
            stop_reason=choice.get("finish_reason") or "",
        )

    return call


# --- Claude (official anthropic SDK) -------------------------------------------------------


def _strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Structured outputs need additionalProperties: false on every object."""
    schema = json.loads(json.dumps(schema))

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                node.setdefault("additionalProperties", False)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)
    return schema


def _anthropic_messages(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    system_parts, out = [], []
    for m in messages:
        role = m["role"]
        if role == "system":
            system_parts.append(m["content"])
        elif role == "assistant":
            if m.get("provider_raw") is not None:
                content = m["provider_raw"]  # pass Claude's blocks back unchanged
            else:
                content = [{"type": "text", "text": m["content"]}] if m.get("content") else []
                content += [
                    {"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["arguments"]}
                    for c in m.get("tool_calls") or []
                ]
            out.append({"role": "assistant", "content": content})
        elif role == "tool":
            block = {
                "type": "tool_result",
                "tool_use_id": m["tool_call_id"],
                "content": m["content"],
            }
            if m.get("is_error"):
                block["is_error"] = True
            # All results for one assistant turn go back in a single user message.
            if (
                out
                and out[-1]["role"] == "user"
                and isinstance(out[-1]["content"], list)
                and all(b.get("type") == "tool_result" for b in out[-1]["content"])
            ):
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
        else:
            out.append({"role": "user", "content": m["content"]})
    return "\n\n".join(system_parts), out


def _anthropic(messages, tools, json_schema, model, max_tokens) -> LLMResponse:
    import anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise LLMError("ANTHROPIC_API_KEY is not set.")
    client = anthropic.Anthropic(timeout=_timeout(), max_retries=0)  # retries handled above
    system, converted = _anthropic_messages(messages)
    params: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": converted,
        # Thinking is always on for claude-opus-5-5; effort is the depth control.
        "output_config": {"effort": os.environ.get("LLM_EFFORT", "low")},
    }
    if system:
        params["system"] = system
    if tools:
        params["tools"] = [
            {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
            for t in tools
        ]
    if json_schema is not None and not tools:
        params["output_config"]["format"] = {
            "type": "json_schema",
            "schema": _strict_schema(json_schema),
        }
    if model in {"claude-opus-5-5", "claude-fable-5-2", "claude-sonnet-5-5"}:
        # Server-side refusal fallback: a declined request is re-run on a fallback model.
        params["betas"] = ["server-side-fallback-2026-07-01"]
        params["fallbacks"] = "default"
        create = client.beta.messages.create
    else:
        create = client.messages.create

    try:
        response = create(**params)
    except anthropic.RateLimitError as exc:
        retry_after = exc.response.headers.get("retry-after")
        delay = float(retry_after) if retry_after else None
        raise _Retryable("anthropic rate limited", delay) from exc
    except anthropic.APIStatusError as exc:
        if exc.status_code >= 500:
            raise _Retryable(f"anthropic HTTP {exc.status_code}") from exc
        raise LLMError(f"anthropic HTTP {exc.status_code}: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:  # includes timeouts
        raise _Retryable(f"anthropic network error: {exc}") from exc

    if response.stop_reason == "refusal":
        category = getattr(getattr(response, "stop_details", None), "category", None)
        raise LLMRefusal(f"Claude declined the request ({category or 'no category'}).")
    text = "".join(b.text for b in response.content if b.type == "text")
    calls = [
        ToolCall(id=b.id, name=b.name, arguments=dict(b.input))
        for b in response.content
        if b.type == "tool_use"
    ]
    return LLMResponse(
        content=text,
        tool_calls=calls,
        prompt_tokens=response.usage.input_tokens,
        completion_tokens=response.usage.output_tokens,
        model=response.model,
        stop_reason=response.stop_reason or "",
        provider_raw=[b.to_dict() for b in response.content],
    )


# --- Mock (offline / tests) -----------------------------------------------------------------


def _fill(schema: dict[str, Any], key: str = "") -> Any:
    """A placeholder value for a JSON schema (offline mode)."""
    if "enum" in schema:
        return schema["enum"][0]
    t = schema.get("type")
    if t == "object":
        return {k: _fill(v, k) for k, v in (schema.get("properties") or {}).items()}
    if t == "array":
        return [_fill(schema.get("items", {}), key)]
    if t in ("integer", "number"):
        return 1
    if t == "boolean":
        return False
    return f"[offline draft: set GROQ_API_KEY for real {key or 'text'}]"


def _mock(messages, tools, json_schema, model, max_tokens) -> LLMResponse:
    """Deterministic stand-in. Tests replace it with scripted responses (genai.testing)."""
    if json_schema is not None:
        content = json.dumps(_fill(json_schema))
    else:
        content = (
            "[offline mode] No LLM is configured, so this is a placeholder answer. "
            "Set GROQ_API_KEY (or ANTHROPIC_API_KEY) in .env to get real responses."
        )
    prompt = sum(len(str(m.get("content", ""))) for m in messages) // 4
    return LLMResponse(content=content, prompt_tokens=prompt, completion_tokens=len(content) // 4,
                       model=model, stop_reason="stop")  # fmt: skip


_ADAPTERS = {
    "groq": _openai_compatible("groq"),
    "openai": _openai_compatible("openai"),
    "anthropic": _anthropic,
    "mock": _mock,
}
