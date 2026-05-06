"""Schema round-trip and forward-compat tests."""
from __future__ import annotations

import json

import pytest

from witness.core.schema import (
    SCHEMA_VERSION,
    Decision,
    DecisionType,
    Message,
    PerturbationRecord,
    Role,
    Trace,
)


def test_trace_default_run_id_is_unique() -> None:
    a = Trace(agent_name="a")
    b = Trace(agent_name="a")
    assert a.run_id != b.run_id
    assert a.run_id.startswith("run_")


def test_trace_round_trip_via_json() -> None:
    t = Trace(agent_name="r", model="claude-x", tools_available=["search"])
    t.add_message(role="user", content="hello")
    d = t.add_decision(
        type="model_call",
        input={"prompt": "hi"},
        output={"text": "hi back"},
        duration_ms=50,
    )
    t.add_message(role=Role.ASSISTANT, content="hi back", parent_step_id=d.step_id)
    t.finalize(final_output="hi back")

    raw = t.model_dump_json()
    parsed = Trace.model_validate_json(raw)

    assert parsed.agent_name == "r"
    assert parsed.model == "claude-x"
    assert parsed.tools_available == ["search"]
    assert parsed.final_output == "hi back"
    assert parsed.schema_version == SCHEMA_VERSION
    assert len(parsed.decisions) == 1
    assert parsed.decisions[0].type == DecisionType.MODEL_CALL


def test_trace_forward_compat_extra_fields_preserved() -> None:
    """Future fields appended at the top level shouldn't crash older readers."""
    raw = {
        "agent_name": "x",
        "schema_version": "1.0",
        "messages": [],
        "decisions": [],
        "novel_field_42": {"future": True},
    }
    t = Trace.model_validate(raw)
    # extra='allow' means it should be accessible via __pydantic_extra__
    extras = t.model_dump()
    assert extras.get("novel_field_42") == {"future": True}


def test_decision_step_id_unique_and_prefixed() -> None:
    a = Decision(type=DecisionType.MODEL_CALL)
    b = Decision(type=DecisionType.MODEL_CALL)
    assert a.step_id != b.step_id
    assert a.step_id.startswith("s_")


def test_perturbation_record_round_trip() -> None:
    rec = PerturbationRecord(type="truncate", params={"fraction": 0.5})
    raw = rec.model_dump_json()
    parsed = PerturbationRecord.model_validate_json(raw)
    assert parsed.type == "truncate"
    assert parsed.params == {"fraction": 0.5}


def test_tool_call_counts() -> None:
    t = Trace(agent_name="r")
    t.add_decision(type="tool_call", input={"name": "search"})
    t.add_decision(type="tool_call", input={"name": "search"})
    t.add_decision(type="tool_call", input={"name": "read"})
    t.add_decision(type="model_call", input={})  # not a tool call
    counts = t.tool_call_counts()
    assert counts == {"search": 2, "read": 1}


def test_role_enum_accepts_strings() -> None:
    m = Message(role="user", content="hi")
    assert m.role == Role.USER


def test_decision_with_invalid_type_rejected() -> None:
    with pytest.raises(ValueError):
        Decision(type="bogus_type")  # type: ignore[arg-type]


def test_finalize_sets_wall_time() -> None:
    import time

    t = Trace(agent_name="r")
    started = time.monotonic()
    time.sleep(0.005)
    t.finalize(final_output="done", started_monotonic=started)
    assert t.wall_time_ms is not None and t.wall_time_ms >= 0
    assert t.ended_at is not None


def test_message_content_can_be_blocks() -> None:
    blocks = [{"type": "text", "text": "hi"}, {"type": "tool_use", "name": "search"}]
    m = Message(role=Role.ASSISTANT, content=blocks)
    raw = m.model_dump_json()
    parsed = Message.model_validate_json(raw)
    assert parsed.content == blocks


def test_trace_full_json_dump_contains_all_top_level_fields() -> None:
    t = Trace(agent_name="r")
    dumped = json.loads(t.model_dump_json())
    expected_keys = {
        "schema_version",
        "run_id",
        "agent_name",
        "model",
        "tools_available",
        "messages",
        "decisions",
        "final_output",
        "started_at",
        "ended_at",
        "wall_time_ms",
        "entrypoint",
        "parent_run_id",
        "perturbation",
        "inputs",
        "metadata",
    }
    assert expected_keys.issubset(dumped.keys())
