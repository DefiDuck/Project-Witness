"""Trace JSON store: save_trace, load_trace, round-trip."""
from __future__ import annotations

import json
from pathlib import Path

from witness.core.schema import Trace
from witness.core.store import load_trace, load_trace_dict, save_trace


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    t = Trace(agent_name="r")
    t.add_message(role="user", content="hi")
    t.add_decision(type="model_call", input={"x": 1}, output={"y": 2})
    t.finalize(final_output="done")

    path = tmp_path / "trace.json"
    saved = save_trace(t, path)
    assert saved.exists()

    loaded = load_trace(path)
    assert loaded.run_id == t.run_id
    assert loaded.agent_name == "r"
    assert loaded.final_output == "done"
    assert len(loaded.decisions) == 1
    assert loaded.decisions[0].input == {"x": 1}


def test_save_creates_parent_dirs(tmp_path: Path) -> None:
    t = Trace(agent_name="r")
    nested = tmp_path / "deep" / "in" / "the" / "tree.json"
    save_trace(t, nested)
    assert nested.exists()


def test_load_trace_dict_returns_raw(tmp_path: Path) -> None:
    t = Trace(agent_name="r")
    path = tmp_path / "t.json"
    save_trace(t, path)
    raw = load_trace_dict(path)
    assert raw["agent_name"] == "r"


def test_save_indent_argument(tmp_path: Path) -> None:
    t = Trace(agent_name="r")
    path = tmp_path / "t.json"
    save_trace(t, path, indent=4)
    text = path.read_text(encoding="utf-8")
    # 4-space indented JSON should have lines starting with "    "
    assert "    " in text
    # Still valid JSON
    json.loads(text)
