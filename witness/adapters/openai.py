"""OpenAI SDK adapter.

Patches `openai.resources.chat.completions.Completions.create` (and async) so every
call inside an @observe scope records a model_call decision and any tool_calls.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from witness.core.capture import current_trace
from witness.core.schema import DecisionType, Role

log = logging.getLogger(__name__)

_PATCHED = False
_ORIG_SYNC: Any = None
_ORIG_ASYNC: Any = None


def install() -> None:
    """Patch the OpenAI SDK. Raises ImportError if openai is not installed."""
    global _PATCHED, _ORIG_SYNC, _ORIG_ASYNC
    if _PATCHED:
        return

    from openai.resources.chat.completions import AsyncCompletions, Completions

    _ORIG_SYNC = Completions.create
    _ORIG_ASYNC = AsyncCompletions.create

    def _record_request(kwargs: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": kwargs.get("model"),
            "messages": kwargs.get("messages"),
            "tools": kwargs.get("tools"),
            "tool_choice": kwargs.get("tool_choice"),
            "max_tokens": kwargs.get("max_tokens") or kwargs.get("max_completion_tokens"),
            "temperature": kwargs.get("temperature"),
        }

    def _record_response(resp: Any) -> dict[str, Any]:
        try:
            choice = (resp.choices or [None])[0]
            msg = getattr(choice, "message", None) if choice else None
            return {
                "id": getattr(resp, "id", None),
                "model": getattr(resp, "model", None),
                "finish_reason": getattr(choice, "finish_reason", None) if choice else None,
                "message": _message_to_dict(msg) if msg else None,
                "usage": _usage_to_dict(getattr(resp, "usage", None)),
            }
        except Exception as e:  # pragma: no cover
            log.warning("openai adapter: failed to serialize response: %s", e)
            return {"_error": str(e)}

    def _on_call(kwargs: dict[str, Any], resp: Any, started_monotonic: float) -> None:
        trace = current_trace()
        if trace is None:
            return
        if trace.model is None:
            trace.model = kwargs.get("model")
        tools = kwargs.get("tools") or []
        if tools and not trace.tools_available:
            names = []
            for t in tools:
                if isinstance(t, dict):
                    fn = t.get("function") or {}
                    names.append(fn.get("name") or t.get("name") or "<unnamed>")
            trace.tools_available = names

        request_payload = _record_request(kwargs)
        response_payload = _record_response(resp)

        model_call = trace.add_decision(
            type=DecisionType.MODEL_CALL,
            input=request_payload,
            output=response_payload,
            duration_ms=int((time.monotonic() - started_monotonic) * 1000),
            metadata={"sdk": "openai"},
        )

        for m in (kwargs.get("messages") or []):
            if isinstance(m, dict):
                trace.add_message(
                    role=m.get("role", "user"),
                    content=m.get("content", ""),
                    tool_call_id=m.get("tool_call_id"),
                    parent_step_id=model_call.step_id,
                )

        msg = response_payload.get("message") or {}
        trace.add_message(
            role=Role.ASSISTANT,
            content=msg.get("content") or "",
            parent_step_id=model_call.step_id,
        )

        # Tool calls
        for tc in msg.get("tool_calls") or []:
            fn = (tc.get("function") if isinstance(tc, dict) else None) or {}
            trace.add_decision(
                type=DecisionType.TOOL_CALL,
                input={
                    "name": fn.get("name"),
                    "args": fn.get("arguments"),
                    "tool_use_id": tc.get("id") if isinstance(tc, dict) else None,
                },
                output={},
                parent_step_id=model_call.step_id,
                metadata={"sdk": "openai"},
            )

        if response_payload.get("finish_reason") == "stop" and msg.get("content"):
            trace.add_decision(
                type=DecisionType.FINAL_OUTPUT,
                input={},
                output={"text": msg.get("content")},
                parent_step_id=model_call.step_id,
                metadata={"sdk": "openai"},
            )

    def patched_create(self: Any, *args: Any, **kwargs: Any) -> Any:
        started = time.monotonic()
        resp = _ORIG_SYNC(self, *args, **kwargs)
        try:
            _on_call(kwargs, resp, started)
        except Exception as e:  # pragma: no cover
            log.warning("openai adapter: capture failed: %s", e)
        return resp

    async def patched_create_async(self: Any, *args: Any, **kwargs: Any) -> Any:
        started = time.monotonic()
        resp = await _ORIG_ASYNC(self, *args, **kwargs)
        try:
            _on_call(kwargs, resp, started)
        except Exception as e:  # pragma: no cover
            log.warning("openai adapter: capture failed: %s", e)
        return resp

    Completions.create = patched_create  # type: ignore[method-assign]
    AsyncCompletions.create = patched_create_async  # type: ignore[method-assign]
    _PATCHED = True


def uninstall() -> None:
    global _PATCHED
    if not _PATCHED:
        return
    from openai.resources.chat.completions import AsyncCompletions, Completions

    if _ORIG_SYNC is not None:
        Completions.create = _ORIG_SYNC  # type: ignore[method-assign]
    if _ORIG_ASYNC is not None:
        AsyncCompletions.create = _ORIG_ASYNC  # type: ignore[method-assign]
    _PATCHED = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _message_to_dict(msg: Any) -> dict[str, Any]:
    d = getattr(msg, "model_dump", None)
    if callable(d):
        return d()
    return {
        "role": getattr(msg, "role", "assistant"),
        "content": getattr(msg, "content", None),
        "tool_calls": getattr(msg, "tool_calls", None),
    }


def _usage_to_dict(usage: Any) -> dict[str, Any] | None:
    if usage is None:
        return None
    d = getattr(usage, "model_dump", None)
    if callable(d):
        return d()
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


__all__ = ["install", "uninstall"]
