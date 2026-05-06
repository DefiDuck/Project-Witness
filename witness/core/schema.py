"""Trace schema (trace_v1).

Pydantic models for the on-disk JSON format. Every other component in Witness reads
and writes these types.

Forward compatibility: every model has `extra="allow"` and a `metadata` dict so future
fields can be appended without breaking older readers. The schema_version on the Trace
is the canonical version marker.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    """Short, sortable, human-readable id."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Role(str, Enum):
    """Conversation roles. Matches Anthropic / OpenAI conventions."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class DecisionType(str, Enum):
    """The kinds of agent decisions Witness records.

    `model_call`     — the agent invoked an LLM
    `tool_call`      — the agent decided to call a tool (extracted from a model response)
    `tool_result`    — a tool returned (paired with a tool_call)
    `reasoning`      — extended-thinking / scratchpad step
    `final_output`   — the agent emitted its final answer
    `custom`         — user-recorded decision via `witness.record_decision(...)`
    """

    MODEL_CALL = "model_call"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    REASONING = "reasoning"
    FINAL_OUTPUT = "final_output"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


class Message(BaseModel):
    """One conversation turn. Content is either a string or a list of content blocks
    (Anthropic-style: text/tool_use/tool_result).
    """

    model_config = ConfigDict(extra="allow")

    role: Role
    content: Union[str, list[dict[str, Any]]]
    tool_call_id: Optional[str] = None
    parent_step_id: Optional[str] = Field(
        default=None,
        description="Decision step_id that produced this message.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


class Decision(BaseModel):
    """One observable choice point in the agent's run."""

    model_config = ConfigDict(extra="allow")

    step_id: str = Field(default_factory=lambda: _new_id("s"))
    timestamp: str = Field(default_factory=_now_iso)
    type: DecisionType
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    parent_step_id: Optional[str] = None
    duration_ms: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Perturbation record (set on a perturbed trace, not a baseline)
# ---------------------------------------------------------------------------


class PerturbationRecord(BaseModel):
    """Describes the perturbation applied to produce this trace."""

    model_config = ConfigDict(extra="allow")

    type: str
    params: dict[str, Any] = Field(default_factory=dict)
    summary: Optional[str] = None
    """One-line description of what was changed."""


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------


class Trace(BaseModel):
    """A captured agent run, plus all the metadata needed to replay or diff it.

    Stable fields are first-class. Anything novel goes into `metadata`. Bump
    `schema_version` only on breaking changes.
    """

    model_config = ConfigDict(extra="allow")

    schema_version: str = SCHEMA_VERSION
    run_id: str = Field(default_factory=lambda: _new_id("run"))
    agent_name: str
    model: Optional[str] = None
    tools_available: list[str] = Field(default_factory=list)

    messages: list[Message] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)

    final_output: Any = None

    started_at: str = Field(default_factory=_now_iso)
    ended_at: Optional[str] = None
    wall_time_ms: Optional[int] = None

    # Replay / lineage
    entrypoint: Optional[str] = Field(
        default=None,
        description="'module.path:function_name' for re-importing the agent during replay.",
    )
    parent_run_id: Optional[str] = Field(
        default=None,
        description="If this is a perturbed trace, the run_id of the baseline it was derived from.",
    )
    perturbation: Optional[PerturbationRecord] = None

    # Free-form
    inputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Captured arguments to the @observe-wrapped function.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def add_message(
        self,
        role: Role | str,
        content: Union[str, list[dict[str, Any]]],
        *,
        tool_call_id: Optional[str] = None,
        parent_step_id: Optional[str] = None,
    ) -> Message:
        msg = Message(
            role=Role(role) if isinstance(role, str) else role,
            content=content,
            tool_call_id=tool_call_id,
            parent_step_id=parent_step_id,
        )
        self.messages.append(msg)
        return msg

    def add_decision(
        self,
        type: DecisionType | str,
        *,
        input: Optional[dict[str, Any]] = None,
        output: Optional[dict[str, Any]] = None,
        parent_step_id: Optional[str] = None,
        duration_ms: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Decision:
        dec = Decision(
            type=DecisionType(type) if isinstance(type, str) else type,
            input=input or {},
            output=output or {},
            parent_step_id=parent_step_id,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )
        self.decisions.append(dec)
        return dec

    def finalize(self, final_output: Any = None, *, started_monotonic: float | None = None) -> None:
        """Stamp ended_at, wall_time_ms, and the final output."""
        self.ended_at = _now_iso()
        self.final_output = final_output
        if started_monotonic is not None:
            self.wall_time_ms = int((time.monotonic() - started_monotonic) * 1000)

    def tool_call_counts(self) -> dict[str, int]:
        """Map of tool_name -> number of times called in this trace."""
        counts: dict[str, int] = {}
        for d in self.decisions:
            if d.type == DecisionType.TOOL_CALL:
                name = d.input.get("name") or d.input.get("tool") or "<unknown>"
                counts[name] = counts.get(name, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# Type alias for clarity
# ---------------------------------------------------------------------------

# Used in adapters that emit dicts directly into Decision.input/output without
# going through pydantic — kept as a type alias so editor go-to-def works.
JsonLike = Union[None, bool, int, float, str, list[Any], dict[str, Any]]

__all__ = [
    "SCHEMA_VERSION",
    "Role",
    "DecisionType",
    "Message",
    "Decision",
    "PerturbationRecord",
    "Trace",
    "JsonLike",
]
