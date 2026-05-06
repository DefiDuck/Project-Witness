"""End-to-end demo flow: capture -> perturb -> diff. Mirrors README success criteria."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import witness


@pytest.fixture
def big_doc() -> str:
    # Six distinct paragraphs so truncation actually changes which sentences
    # the mock summary reads.
    paragraphs = [
        "Alpha. The first idea concerns helpful behavior and human feedback loops.",
        "Beta. The second idea is harm avoidance through learned constitutional rules.",
        "Gamma. Honesty emerges when models critique their own outputs systematically.",
        "Delta. Reward hacking is mitigated by principle-grounded preference modeling.",
        "Epsilon. Scalable oversight reduces dependence on per-prompt human review.",
        "Zeta. Empirical results indicate the method generalizes across model sizes.",
    ]
    return "\n\n".join(paragraphs)


def test_capture_then_replay_then_diff_e2e(tmp_path: Path, big_doc: str) -> None:
    """The full programmatic flow:

       baseline = research(doc=...)
       perturbed = witness.replay(baseline, Truncate(0.75), agent_fn=research)
       diff = witness.diff(baseline, perturbed)

    With distinct-content paragraphs and a 75% truncation, the perturbed doc
    drops below 200 chars (skipping the read_document branch entirely) AND
    cuts off enough paragraphs that the final summary differs.
    """
    from examples import research_agent

    # Re-decorate research with output_path inside tmp_path.
    @witness.observe(name="research", output_path=str(tmp_path / "baseline.json"))
    def research(doc: str) -> str:
        return research_agent._mock_agent_loop(doc)

    research(doc=big_doc)
    baseline = research.__witness_last_trace__
    assert baseline is not None
    # Mock loop on a long doc emits 7 decisions.
    assert len(baseline.decisions) == 7

    perturbed = witness.replay(
        baseline,
        witness.Truncate(fraction=0.75),
        agent_fn=research,
        output_path=str(tmp_path / "perturbed.json"),
    )

    d = witness.diff(baseline, perturbed)
    assert d.final_output_changed is True

    # The perturbation lineage is recorded
    assert perturbed.parent_run_id == baseline.run_id
    assert perturbed.perturbation is not None
    assert perturbed.perturbation.type == "truncate"


def test_truncate_into_short_doc_drops_read_decision(tmp_path: Path) -> None:
    """When the truncated doc dips below 200 chars, the read_document tool_call vanishes."""
    from examples import research_agent

    @witness.observe(name="research", output_path=str(tmp_path / "baseline.json"))
    def research(doc: str) -> str:
        return research_agent._mock_agent_loop(doc)

    # Original is ~350 chars (over the 200-char threshold so baseline triggers
    # read_document); truncated 60% -> ~140 chars (under threshold so perturbed skips it).
    short_doc = (
        "First paragraph here with some additional content for length.\n\n"
        "Second paragraph also extends a bit further than usual to bulk it up.\n\n"
        "Third paragraph wraps things up with one more meaningful sentence here.\n\n"
        "Fourth paragraph adds one more line for measure."
    )
    assert len(short_doc) > 200
    research(doc=short_doc)
    baseline = research.__witness_last_trace__
    perturbed = witness.replay(baseline, witness.Truncate(fraction=0.6), agent_fn=research)

    # Baseline has the read_document branch; perturbed doesn't (doc too short after truncate).
    base_tool_names = [
        d.input.get("name") for d in baseline.decisions if d.type.value == "tool_call"
    ]
    pert_tool_names = [
        d.input.get("name") for d in perturbed.decisions if d.type.value == "tool_call"
    ]
    assert "read_document" in base_tool_names
    assert "read_document" not in pert_tool_names

    d = witness.diff(baseline, perturbed)
    assert len(perturbed.decisions) < len(baseline.decisions)
    # At least one tool_call REMOVED in the alignment
    removed_kinds = [p.kind for p in d.alignment.pairs]
    assert "removed" in removed_kinds


def test_cli_flow_end_to_end(tmp_path: Path, big_doc: str) -> None:
    """Run the actual CLI subprocess: produce baseline via example, perturb (no-rerun
    since the example writes to ./baseline.json), then diff.
    """
    from examples import research_agent

    base_path = tmp_path / "baseline.json"

    @witness.observe(name="research", output_path=str(base_path))
    def research(doc: str) -> str:
        return research_agent._mock_agent_loop(doc)

    research(doc=big_doc)
    assert base_path.exists()

    # `witness perturb baseline.json --type truncate --no-rerun -o perturbed_input.json`
    perturbed_input = tmp_path / "perturbed_input.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "witness",
            "perturb",
            str(base_path),
            "--type",
            "truncate",
            "--param",
            "fraction=0.5",
            "-o",
            str(perturbed_input),
            "--no-rerun",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert perturbed_input.exists()

    # Now do a real perturb+rerun. The example's @observe writes to baseline.json,
    # so we redirect cwd to tmp_path so the rerun trace doesn't clobber.
    perturbed_path = tmp_path / "perturbed.json"
    perturbed_trace = witness.replay(
        witness.load_trace(base_path),
        witness.Truncate(fraction=0.5),
        agent_fn=research,
        output_path=str(perturbed_path),
    )
    assert perturbed_path.exists()
    assert perturbed_trace.parent_run_id is not None

    # `witness diff baseline.json perturbed.json --plain --no-color`
    # --plain so the text shape is stable; encoding=utf-8 in case rich left
    # any utf-8 box chars in stderr or elsewhere.
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "witness",
            "diff",
            str(base_path),
            str(perturbed_path),
            "--plain",
            "--no-color",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stderr
    assert "witness diff" in result.stdout
    assert "decisions:" in result.stdout
    # The diff text should reference at least one of the change kinds
    assert any(kw in result.stdout for kw in ("REMOVED", "ADDED", "CHANGED", "input changed"))
