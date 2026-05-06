"""Real Anthropic API call. Skipped unless RUN_INTEGRATION=1 is set.

Costs a few cents. Runs against the real `anthropic` SDK and verifies the
adapter records a real model_call decision with usage tokens populated.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import witness

pytestmark = pytest.mark.integration


def test_anthropic_real_call_records_model_call(tmp_path: Path) -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")
    pytest.importorskip("anthropic")

    from witness.adapters import install_all

    install_all()

    @witness.observe(name="echo", output_dir=str(tmp_path))
    def echo() -> str:
        import anthropic

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=32,
            messages=[{"role": "user", "content": "Reply with the single word: OK"}],
        )
        for b in resp.content:
            if getattr(b, "type", None) == "text":
                return getattr(b, "text", "")
        return ""

    out = echo()
    assert out, "expected non-empty model response"

    trace = echo.__witness_last_trace__
    assert trace is not None
    assert trace.model and trace.model.startswith("claude-")
    types_seen = [d.type.value for d in trace.decisions]
    assert "model_call" in types_seen
    # The adapter should have populated the response payload's usage block.
    mc = next(d for d in trace.decisions if d.type.value == "model_call")
    usage = mc.output.get("usage")
    assert usage is not None
    assert usage.get("input_tokens", 0) > 0
    assert usage.get("output_tokens", 0) > 0


def test_anthropic_real_call_with_truncate_replay(tmp_path: Path) -> None:
    """End-to-end: capture real run, perturb, diff. Useful sanity check that
    the entrypoint flow works when the agent is module-scoped."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")
    pytest.importorskip("anthropic")

    from witness.adapters import install_all

    install_all()

    DOC = (
        "Anthropic released the Claude family of language models. "
        "The smallest is Haiku and the largest is Opus. "
        "Sonnet sits in between in size and cost. "
        "Each generation introduces capability gains over the prior."
    )

    @witness.observe(name="describe", output_dir=str(tmp_path))
    def describe(doc: str) -> str:
        import anthropic

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=128,
            messages=[
                {
                    "role": "user",
                    "content": f"In one sentence, summarize this:\n\n{doc}",
                }
            ],
        )
        for b in resp.content:
            if getattr(b, "type", None) == "text":
                return getattr(b, "text", "")
        return ""

    describe(doc=DOC)
    baseline = describe.__witness_last_trace__
    assert baseline is not None

    perturbed = witness.replay(
        baseline,
        witness.Truncate(fraction=0.5),
        agent_fn=describe,
    )
    d = witness.diff(baseline, perturbed)
    # We make NO promises about what changed (LLMs are non-deterministic),
    # but the perturbation lineage should be present and the diff should run.
    assert perturbed.parent_run_id == baseline.run_id
    assert perturbed.perturbation is not None
    summary = d.summary()
    assert summary["baseline"]["run_id"] == baseline.run_id
