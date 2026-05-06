"""Behavioral fingerprint."""
from __future__ import annotations

from pathlib import Path

import witness
from witness.diff.fingerprint import fingerprint


def test_fingerprint_one_baseline_two_runs(tmp_traces: Path) -> None:
    from examples import research_agent

    @witness.observe(name="research", output_dir=str(tmp_traces))
    def research(doc: str) -> str:
        return research_agent._mock_agent_loop(doc)

    long_doc = (
        "Para A is about helpful behavior and human feedback loops here.\n\n"
        "Para B is about harm avoidance through learned constitutional rules.\n\n"
        "Para C is about honesty emerging when models critique their own outputs.\n\n"
        "Para D is about reward hacking mitigation via principle-grounded models.\n\n"
        "Para E is about scalable oversight reducing dependence on humans.\n\n"
        "Para F is about empirical results indicating method generalization."
    )
    research(doc=long_doc)
    baseline = research.__witness_last_trace__
    assert baseline is not None

    p1 = witness.replay(baseline, witness.Truncate(fraction=0.25), agent_fn=research)
    p2 = witness.replay(baseline, witness.Truncate(fraction=0.75), agent_fn=research)

    fp = fingerprint(baseline, [p1, p2])
    assert len(fp.runs) == 2
    summary = fp.summary()
    assert summary["n_runs"] == 2
    assert "stability_by_decision_type" in summary
    # Final output stability is between 0 and 1
    assert 0.0 <= summary["final_output_stability"] <= 1.0
    assert 0.0 <= summary["overall_stability"] <= 1.0


def test_fingerprint_identical_perturbed_is_perfectly_stable(tmp_traces: Path) -> None:
    """If 'perturbed' traces are actually identical to baseline, stability == 1."""
    @witness.observe(name="r", output_dir=str(tmp_traces))
    def agent() -> str:
        witness.record_decision(
            witness.DecisionType.MODEL_CALL,
            input={"prompt": "hi"},
            output={"text": "hi back"},
        )
        return "hi back"

    agent()
    base = agent.__witness_last_trace__
    # Use the same trace for "perturbed" entries — identical, so stability == 1.
    fp = fingerprint(base, [base, base])
    assert fp.final_output_stability() == 1.0
    assert all(s == 1.0 for s in fp.stability_by_decision_type().values())
    assert fp.overall_stability() == 1.0


def test_fingerprint_no_runs_returns_neutral() -> None:
    base = witness.Trace(agent_name="x")
    fp = fingerprint(base, [])
    # No runs -> default to perfectly stable (nothing to compare)
    assert fp.final_output_stability() == 1.0
    assert fp.overall_stability() == 1.0
