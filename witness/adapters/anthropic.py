"""Anthropic SDK adapter.

Patches `anthropic.resources.messages.Messages.create` (and the async variant) so
every call inside an @observe scope records:

  - one `model_call` decision with the input request and the raw response
  - one `tool_call` decision per `tool_use` content block in the response
  - one user-role message capturing what was sent
  - one assistant-role message capturing the response

The adapter is idempotent: calling `install()` twice is safe.
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
    """Patch the Anthropic SDK. Raises ImportError if anthropic is not installed."""
    global _PATCHED, _ORIG_SYNC, _ORIG_ASYNC
    if _PATCHED:
        return

    # Imports here so we fail with ImportError only when actually installing.
    from anthropic.resources.messages import AsyncMessages, Messages

    _ORIG_SYNC = Messages.create
    _ORIG_ASYNC = AsyncMessages.create

    def _record_request(kwargs: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": kwargs.get("model"),
            "system": kwargs.get("system"),
            "messages": kwargs.get("messages"),
            "tools": kwargs.get("tools"),
            "tool_choice": kwargs.get("tool_choice"),
            "max_tokens": kwargs.get("max_tokens"),
            "temperature": kwargs.get("temperature"),
        }

    def _record_response(resp: Any) -> dict[str, Any]:
        # `resp` is an anthropic.types.Message — has .content (list of blocks),
        # .stop_reason, .usage, .id, .role.
        try:
            return {
                "id": getattr(resp, "id", None),
                "role": getattr(resp, "role", "assistant"),
                "stop_reason": getattr(resp, "stop_reason", None),
                "content": _content_blocks_to_dict(getattr(resp, "content", [])),
                "usage": _usage_to_dict(getattr(resp, "usage", None)),
                "model": getattr(resp, "model", None),
            }
        except Exception as e:  # pragma: no cover
            log.warning("anthropic adapter: failed to serialize response: %s", e)
            return {"_error": str(e)}

    def _on_call(kwargs: dict[str, Any], resp: Any, started_monotonic: float) -> None:
        trace = current_trace()
        if trace is None:
            return
        # Track the model on the trace if it isn't set yet.
        if trace.model is None:
            trace.model = kwargs.get("model")
        # Track tools_available the first time we see them.
        tools = kwargs.get("tools") or []
        if tools and not trace.tools_available:
            trace.tools_available = [t.get("name", "<unnamed>") for t in tools if isinstance(t, dict)]

        request_payload = _record_request(kwargs)
        response_payload = _record_response(resp)

        # Record the model_call decision.
        model_call = trace.add_decision(
            type=DecisionType.MODEL_CALL,
            input=request_payload,
            output=response_payload,
            duration_ms=int((time.monotonic() - started_monotonic) * 1000),
            metadata={"sdk": "anthropic"},
        )

        # Echo the user-side messages onto the trace's conversation log
        # (only the *new* tail — we don't know what was already logged, so we
        # always append the latest user/system snapshot once per call).
        for m in (kwargs.get("messages") or []):
            if isinstance(m, dict):
                role = m.get("role", "user")
                content = m.get("content", "")
                trace.add_message(role=role, content=content, parent_step_id=model_call.step_id)

        # Append the assistant response as a message.
        trace.add_message(
            role=Role.ASSISTANT,
            content=response_payload.get("content") or "",
            parent_step_id=model_call.step_id,
        )

        # Decompose tool_use content blocks into their own tool_call decisions.
        for block in response_payload.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                trace.add_decision(
                    type=DecisionType.TOOL_CALL,
                    input={
                        "name": block.get("name"),
                        "args": block.get("input"),
                        "tool_use_id": block.get("id"),
                    },
                    output={},  # filled in when the tool returns (user records via record_decision)
                    parent_step_id=model_call.step_id,
                    metadata={"sdk": "anthropic"},
                )

        # If stop_reason is "end_turn" and there's a final text block, record final_output.
        if response_payload.get("stop_reason") == "end_turn":
            text = _first_text_block(response_payload.get("content") or [])
            if text is not None:
                trace.add_decision(
                    type=DecisionType.FINAL_OUTPUT,
                    input={},
                    output={"text": text},
                    parent_step_id=model_call.step_id,
                    metadata={"sdk": "anthropic"},
                )

    def patched_create(self: Any, *args: Any, **kwargs: Any) -> Any:
        started = time.monotonic()
        resp = _ORIG_SYNC(self, *args, **kwargs)
        try:
            _on_call(kwargs, resp, started)
        except Exception as e:  # pragma: no cover
            log.warning("anthropic adapter: capture failed: %s", e)
        return resp

    async def patched_create_async(self: Any, *args: Any, **kwargs: Any) -> Any:
        started = time.monotonic()
        resp = await _ORIG_ASYNC(self, *args, **kwargs)
        try:
            _on_call(kwargs, resp, started)
        except Exception as e:  # pragma: no cover
            log.warning("anthropic adapter: capture failed: %s", e)
        return resp

    Messages.create = patched_create  # type: ignore[method-assign]
    AsyncMessages.create = patched_create_async  # type: ignore[method-assign]
    _PATCHED = True


def uninstall() -> None:
    """Restore the original SDK methods. Mostly used in tests."""
    global _PATCHED
    if not _PATCHED:
        return
    from anthropic.resources.messages import AsyncMessages, Messages

    if _ORIG_SYNC is not None:
        Messages.create = _ORIG_SYNC  # type: ignore[method-assign]
    if _ORIG_ASYNC is not None:
        AsyncMessages.create = _ORIG_ASYNC  # type: ignore[method-assign]
    _PATCHED = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _content_blocks_to_dict(blocks: Any) -> list[dict[str, Any]]:
    """Anthropic returns content blocks as pydantic models. JSON-ify them."""
    out: list[dict[str, Any]] = []
    for b in blocks or []:
        if isinstance(b, dict):
            out.append(b)
            continue
        d = getattr(b, "model_dump", None)
        if callable(d):
            out.append(d())
            continue
        # Last-ditch: copy known fields manually.
        out.append(
            {
                "type": getattr(b, "type", None),
                "text": getattr(b, "text", None),
                "id": getattr(b, "id", None),
                "name": getattr(b, "name", None),
                "input": getattr(b, "input", None),
            }
        )
    return out


def _usage_to_dict(usage: Any) -> dict[str, Any] | None:
    if usage is None:
        return None
    d = getattr(usage, "model_dump", None)
    if callable(d):
        return d()
    return {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }


def _first_text_block(blocks: list[dict[str, Any]]) -> str | None:
    for b in blocks:
        if b.get("type") == "text":
            return b.get("text")
    return None


__all__ = ["install", "uninstall"]
