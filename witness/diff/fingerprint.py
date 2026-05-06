"""Behavioral fingerprint: a stability vector across N perturbations.

A fingerprint is "what fraction of decisions of each type survived a perturbation
unchanged?", aggregated over a list of perturbed traces. Higher = more stable.

Used to answer: "is my agent more brittle to truncation or to prompt injection?
which decision type is the weak link?"
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from witness.core.schema import DecisionType, Trace
from witness.diff.behavioral import TraceDiff, diff


@dataclass
class PerturbationResult:
    perturbation_type: str
    perturbation_params: dict[str, Any]
    diff: TraceDiff


@dataclass
class Fingerprint:
    """Aggregated stability across N perturbed runs of one baseline."""

    baseline_run_id: str
    runs: list[PerturbationResult]

    def stability_by_decision_type(self) -> dict[str, float]:
        """For each decision type seen in the baseline, the fraction of runs
        where every decision of that type survived unchanged.

        1.0 = always stable. 0.0 = always changed.
        """
        baseline_types: set[str] = set()
        for r in self.runs:
            for d in r.diff.baseline.decisions:
                baseline_types.add(d.type.value)

        scores: dict[str, float] = {}
        if not self.runs:
            return scores

        for t in baseline_types:
            stable_runs = 0
            for r in self.runs:
                if _decisions_of_type_unchanged(r.diff, t):
                    stable_runs += 1
            scores[t] = stable_runs / len(self.runs)
        return scores

    def final_output_stability(self) -> float:
        """Fraction of runs whose final output matched the baseline."""
        if not self.runs:
            return 1.0
        unchanged = sum(1 for r in self.runs if not r.diff.final_output_changed)
        return unchanged / len(self.runs)

    def overall_stability(self) -> float:
        """Geometric mean of per-decision-type stability and final-output stability.

        Penalizes weak spots more than a simple mean would.
        """
        scores = list(self.stability_by_decision_type().values())
        scores.append(self.final_output_stability())
        if not scores:
            return 1.0
        # Avoid log(0): use a tiny epsilon for fully-unstable buckets so the
        # geometric mean doesn't collapse to 0 unless EVERY bucket failed.
        eps = 1e-6
        import math

        log_sum = sum(math.log(max(s, eps)) for s in scores)
        return math.exp(log_sum / len(scores))

    def summary(self) -> dict[str, Any]:
        return {
            "baseline_run_id": self.baseline_run_id,
            "n_runs": len(self.runs),
            "stability_by_decision_type": self.stability_by_decision_type(),
            "final_output_stability": self.final_output_stability(),
            "overall_stability": self.overall_stability(),
            "runs": [
                {
                    "perturbation": r.perturbation_type,
                    "params": r.perturbation_params,
                    "decisions_baseline": len(r.diff.baseline.decisions),
                    "decisions_perturbed": len(r.diff.perturbed.decisions),
                    "final_output_changed": r.diff.final_output_changed,
                }
                for r in self.runs
            ],
        }


def fingerprint(baseline: Trace, perturbed_traces: list[Trace]) -> Fingerprint:
    """Build a Fingerprint from a baseline and N perturbed traces."""
    runs = []
    for p in perturbed_traces:
        d = diff(baseline, p)
        ptype = p.perturbation.type if p.perturbation else "unknown"
        params = p.perturbation.params if p.perturbation else {}
        runs.append(PerturbationResult(perturbation_type=ptype, perturbation_params=params, diff=d))
    return Fingerprint(baseline_run_id=baseline.run_id, runs=runs)


def _decisions_of_type_unchanged(d: TraceDiff, decision_type: str) -> bool:
    """Are all decisions of the given type in either trace unchanged in the alignment?"""
    for pair in d.alignment.pairs:
        # Look at whichever side of the pair has a decision.
        for side in (pair.baseline, pair.perturbed):
            if side is not None and side.type.value == decision_type:
                if pair.kind != "same":
                    return False
                break
    return True


__all__ = ["fingerprint", "Fingerprint", "PerturbationResult"]
