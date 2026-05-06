"""replay() — counterfactual rerun."""
from __future__ import annotations

from pathlib import Path

import pytest

import witness
from witness.core.schema import DecisionType
from witness.perturbations.truncate import Truncate


def test_replay_truncates_input_and_produces_lineage(tmp_traces: Path) -> None:
    @witness.observe(name="agent", output_dir=str(tmp_traces))
    def agent(doc: str) -> int:
        witness.record_decision(
            DecisionType.MODEL_CALL,
            input={"len_in": len(doc)},
            output={"len_in": len(doc)},
        )
        return len(doc)

    doc = "x" * 1000
    agent(doc)
    baseline = agent.__witness_last_trace__
    assert baseline is not None
    assert baseline.final_output == 1000

    perturbed = witness.replay(baseline, Truncate(fraction=0.5), agent_fn=agent)
    assert perturbed.parent_run_id == baseline.run_id
    assert perturbed.perturbation is not None
    assert perturbed.perturbation.type == "truncate"
    assert perturbed.final_output == 500  # half the doc was passed in


def test_replay_diff_shows_input_change(tmp_traces: Path) -> None:
    @witness.observe(name="a", output_dir=str(tmp_traces))
    def agent(doc: str) -> str:
        witness.record_decision(
            DecisionType.MODEL_CALL,
            input={"doc_len": len(doc)},
            output={"summary": doc[:20]},
        )
        return doc[:20]

    doc = "first sentence here. second sentence here. third sentence here. " * 10
    agent(doc)
    baseline = agent.__witness_last_trace__
    perturbed = witness.replay(baseline, Truncate(fraction=0.5), agent_fn=agent)
    d = witness.diff(baseline, perturbed)
    # Same shape, but inputs/outputs differ.
    assert len(baseline.decisions) == len(perturbed.decisions)
    changed = [p for p in d.alignment.pairs if p.kind in ("input_changed", "both_changed")]
    assert len(changed) >= 1


def test_replay_without_agent_fn_falls_back_to_entrypoint() -> None:
    """If no agent_fn given and entrypoint isn't importable, raise."""
    # Create a fake trace with an unresolvable entrypoint.
    from witness.core.schema import Trace

    t = Trace(agent_name="x", entrypoint="this.module.does.not:exist")
    with pytest.raises(ValueError, match="entrypoint"):
        witness.replay(t, Truncate(fraction=0.5))


def test_replay_writes_output_path(tmp_path: Path, tmp_traces: Path) -> None:
    @witness.observe(name="a", output_dir=str(tmp_traces))
    def agent(doc: str) -> str:
        return doc[: len(doc) // 2]

    agent("lorem ipsum dolor sit amet " * 20)
    baseline = agent.__witness_last_trace__
    out = tmp_path / "perturbed.json"
    witness.replay(baseline, Truncate(fraction=0.5), agent_fn=agent, output_path=str(out))
    assert out.exists()
    loaded = witness.load_trace(out)
    assert loaded.parent_run_id == baseline.run_id
