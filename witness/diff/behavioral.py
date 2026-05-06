"""Behavioral diff between two traces.

The diff is *mechanical*, not semantic — we compare structure (decision counts,
tool-call sequences, output equality), not meaning. LLM-as-judge is explicitly
out of scope for v0.

Algorithm
---------
1. Pair the two decision sequences using a longest-common-subsequence (LCS)
   alignment over the `(type, tool_name)` key. This survives small reorderings
   and clearly classifies inserts/deletes.

2. For each aligned pair, classify as ``same`` / ``input_changed`` /
   ``output_changed`` / ``both_changed`` by comparing input and output dicts.

3. Surface high-level summary stats: total decisions, tool counts, final-output
   equality.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from witness.core.schema import Decision, DecisionType, Trace


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DecisionChange:
    """Describes how an aligned pair of decisions differs."""

    kind: str
    """One of: 'same', 'input_changed', 'output_changed', 'both_changed',
    'added', 'removed', 'type_changed'."""

    baseline: Optional[Decision] = None
    perturbed: Optional[Decision] = None

    @property
    def changed(self) -> bool:
        return self.kind != "same"


@dataclass
class DecisionAlignment:
    """Per-position alignment of the two decision sequences."""

    pairs: list[DecisionChange] = field(default_factory=list)

    def count(self, kind: str) -> int:
        return sum(1 for p in self.pairs if p.kind == kind)


@dataclass
class TraceDiff:
    """Result of comparing two traces."""

    baseline: Trace
    perturbed: Trace
    alignment: DecisionAlignment
    tool_counts_baseline: dict[str, int]
    tool_counts_perturbed: dict[str, int]
    final_output_changed: bool
    wall_time_delta_ms: Optional[int]

    # Quick aggregate accessors -------------------------------------------------

    @property
    def decisions_added(self) -> list[Decision]:
        return [p.perturbed for p in self.alignment.pairs if p.kind == "added" and p.perturbed]

    @property
    def decisions_removed(self) -> list[Decision]:
        return [p.baseline for p in self.alignment.pairs if p.kind == "removed" and p.baseline]

    @property
    def decisions_changed(self) -> list[DecisionChange]:
        return [
            p
            for p in self.alignment.pairs
            if p.kind in ("input_changed", "output_changed", "both_changed", "type_changed")
        ]

    @property
    def decisions_same(self) -> list[DecisionChange]:
        return [p for p in self.alignment.pairs if p.kind == "same"]

    def summary(self) -> dict[str, Any]:
        """Compact dict suitable for JSON output."""
        return {
            "baseline": {
                "run_id": self.baseline.run_id,
                "agent_name": self.baseline.agent_name,
                "decisions": len(self.baseline.decisions),
                "wall_time_ms": self.baseline.wall_time_ms,
            },
            "perturbed": {
                "run_id": self.perturbed.run_id,
                "agent_name": self.perturbed.agent_name,
                "decisions": len(self.perturbed.decisions),
                "wall_time_ms": self.perturbed.wall_time_ms,
                "perturbation": self.perturbed.perturbation.model_dump()
                if self.perturbed.perturbation
                else None,
            },
            "decisions_delta": len(self.perturbed.decisions) - len(self.baseline.decisions),
            "decisions_added": len(self.decisions_added),
            "decisions_removed": len(self.decisions_removed),
            "decisions_changed": len(self.decisions_changed),
            "decisions_same": len(self.decisions_same),
            "tool_counts_baseline": self.tool_counts_baseline,
            "tool_counts_perturbed": self.tool_counts_perturbed,
            "final_output_changed": self.final_output_changed,
            "wall_time_delta_ms": self.wall_time_delta_ms,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.summary(), indent=indent, default=str)

    def __str__(self) -> str:
        # Lazy import to keep the diff module dependency-light.
        from witness.diff.format import format_text

        return format_text(self, color=False)


# ---------------------------------------------------------------------------
# Diff algorithm
# ---------------------------------------------------------------------------


def diff(baseline: Trace, perturbed: Trace) -> TraceDiff:
    """Compute the behavioral diff between two traces."""
    alignment = _align_decisions(baseline.decisions, perturbed.decisions)

    final_changed = _final_output_changed(baseline.final_output, perturbed.final_output)
    wall_delta: Optional[int] = None
    if baseline.wall_time_ms is not None and perturbed.wall_time_ms is not None:
        wall_delta = perturbed.wall_time_ms - baseline.wall_time_ms

    return TraceDiff(
        baseline=baseline,
        perturbed=perturbed,
        alignment=alignment,
        tool_counts_baseline=baseline.tool_call_counts(),
        tool_counts_perturbed=perturbed.tool_call_counts(),
        final_output_changed=final_changed,
        wall_time_delta_ms=wall_delta,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _decision_key(d: Decision) -> tuple[str, str]:
    """LCS alignment key — type plus, for tool calls, the tool name."""
    if d.type == DecisionType.TOOL_CALL:
        name = d.input.get("name") or d.input.get("tool") or "<unknown>"
        return (d.type.value, str(name))
    return (d.type.value, "")


def _align_decisions(a: list[Decision], b: list[Decision]) -> DecisionAlignment:
    """Standard LCS table over the alignment keys, then walk back to produce
    add/remove/match labels.
    """
    n, m = len(a), len(b)
    keys_a = [_decision_key(x) for x in a]
    keys_b = [_decision_key(x) for x in b]

    # dp[i][j] = LCS length of a[:i], b[:j]
    dp: list[list[int]] = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if keys_a[i - 1] == keys_b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    # Walk backwards
    pairs_rev: list[DecisionChange] = []
    i, j = n, m
    while i > 0 and j > 0:
        if keys_a[i - 1] == keys_b[j - 1]:
            pairs_rev.append(_classify_pair(a[i - 1], b[j - 1]))
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            pairs_rev.append(DecisionChange(kind="removed", baseline=a[i - 1], perturbed=None))
            i -= 1
        else:
            pairs_rev.append(DecisionChange(kind="added", baseline=None, perturbed=b[j - 1]))
            j -= 1
    while i > 0:
        pairs_rev.append(DecisionChange(kind="removed", baseline=a[i - 1], perturbed=None))
        i -= 1
    while j > 0:
        pairs_rev.append(DecisionChange(kind="added", baseline=None, perturbed=b[j - 1]))
        j -= 1

    return DecisionAlignment(pairs=list(reversed(pairs_rev)))


def _classify_pair(a: Decision, b: Decision) -> DecisionChange:
    if a.type != b.type:
        return DecisionChange(kind="type_changed", baseline=a, perturbed=b)
    in_changed = not _equal(a.input, b.input)
    out_changed = not _equal(a.output, b.output)
    if in_changed and out_changed:
        kind = "both_changed"
    elif in_changed:
        kind = "input_changed"
    elif out_changed:
        kind = "output_changed"
    else:
        kind = "same"
    return DecisionChange(kind=kind, baseline=a, perturbed=b)


def _equal(x: Any, y: Any) -> bool:
    """Robust equality. Falls back to JSON-canonical comparison so that small
    pydantic vs dict differences don't cause spurious mismatches.
    """
    if x is y:
        return True
    try:
        return json.dumps(x, sort_keys=True, default=str) == json.dumps(
            y, sort_keys=True, default=str
        )
    except (TypeError, ValueError):
        return x == y


def _final_output_changed(a: Any, b: Any) -> bool:
    return not _equal(a, b)


__all__ = ["diff", "TraceDiff", "DecisionAlignment", "DecisionChange"]
