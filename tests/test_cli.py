"""CLI smoke tests via Click's CliRunner."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from witness.cli import cli
from witness.core.schema import DecisionType, Trace
from witness.core.store import save_trace


def _make_simple_trace(agent_name: str = "a", final: str = "ok") -> Trace:
    t = Trace(agent_name=agent_name, model="m")
    t.add_decision(type=DecisionType.MODEL_CALL, input={"prompt": "hi"}, output={"text": final})
    t.add_decision(type=DecisionType.TOOL_CALL, input={"name": "search"}, output={})
    t.add_decision(type=DecisionType.FINAL_OUTPUT, input={}, output={"text": final})
    t.final_output = final
    t.wall_time_ms = 100
    return t


def test_cli_diff_runs_and_prints(tmp_path: Path) -> None:
    a = _make_simple_trace(final="alpha")
    b = _make_simple_trace(final="beta")
    pa = tmp_path / "a.json"
    pb = tmp_path / "b.json"
    save_trace(a, pa)
    save_trace(b, pb)

    runner = CliRunner()
    # --plain bypasses rich so the text shape is stable for assertions.
    result = runner.invoke(cli, ["diff", str(pa), str(pb), "--plain", "--no-color"])
    assert result.exit_code == 0, result.output
    assert "witness diff" in result.output
    assert "final output: CHANGED" in result.output


def test_cli_diff_json_output(tmp_path: Path) -> None:
    a = _make_simple_trace()
    b = _make_simple_trace()
    pa = tmp_path / "a.json"
    pb = tmp_path / "b.json"
    save_trace(a, pa)
    save_trace(b, pb)

    runner = CliRunner()
    result = runner.invoke(cli, ["diff", str(pa), str(pb), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "decisions_delta" in data
    assert "tool_counts_baseline" in data


def test_cli_perturb_no_rerun_writes_snapshot(tmp_path: Path) -> None:
    t = _make_simple_trace()
    t.inputs = {"doc": "x" * 1000}
    base_path = tmp_path / "baseline.json"
    save_trace(t, base_path)

    out = tmp_path / "perturbed.json"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "perturb",
            str(base_path),
            "--type",
            "truncate",
            "--param",
            "fraction=0.5",
            "-o",
            str(out),
            "--no-rerun",
        ],
    )
    assert result.exit_code == 0, result.output
    snap = json.loads(out.read_text(encoding="utf-8"))
    assert snap["perturbation"]["type"] == "truncate"
    assert len(snap["inputs"]["doc"]) == 500


def test_cli_perturbations_lists_truncate() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["perturbations"])
    assert result.exit_code == 0
    assert "truncate" in result.output


def test_cli_inspect_prints_summary(tmp_path: Path) -> None:
    t = _make_simple_trace(agent_name="inspect_me")
    p = tmp_path / "t.json"
    save_trace(t, p)
    runner = CliRunner()
    result = runner.invoke(cli, ["inspect", str(p), "--plain"])
    assert result.exit_code == 0
    assert "agent_name:" in result.output
    assert "inspect_me" in result.output


def test_cli_inspect_with_decisions_flag(tmp_path: Path) -> None:
    t = _make_simple_trace()
    p = tmp_path / "t.json"
    save_trace(t, p)
    runner = CliRunner()
    result = runner.invoke(cli, ["inspect", str(p), "--decisions", "--plain"])
    assert result.exit_code == 0
    assert "decisions" in result.output
    assert "model_call" in result.output


def test_cli_perturb_unknown_type_errors(tmp_path: Path) -> None:
    t = _make_simple_trace()
    base_path = tmp_path / "baseline.json"
    save_trace(t, base_path)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["perturb", str(base_path), "--type", "nonexistent", "--no-rerun"]
    )
    assert result.exit_code != 0


def test_cli_diff_verbose_includes_unchanged(tmp_path: Path) -> None:
    a = _make_simple_trace()
    b = _make_simple_trace()
    pa = tmp_path / "a.json"
    pb = tmp_path / "b.json"
    save_trace(a, pa)
    save_trace(b, pb)
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", str(pa), str(pb), "--no-color", "-v"])
    assert result.exit_code == 0
    assert "unchanged" in result.output
