"""Render a TraceDiff as terminal-readable text, optionally with ANSI color."""
from __future__ import annotations

import json
from typing import Any

from witness.core.schema import Decision, DecisionType
from witness.diff.behavioral import DecisionChange, TraceDiff

# ---------------------------------------------------------------------------
# ANSI color helpers (no external deps; click.style is fine but this avoids
# threading click into the core diff module).
# ---------------------------------------------------------------------------

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_BLUE = "\033[34m"
_MAGENTA = "\033[35m"
_CYAN = "\033[36m"


def _c(text: str, code: str, *, color: bool) -> str:
    return f"{code}{text}{_RESET}" if color else text


def _bold(text: str, *, color: bool) -> str:
    return _c(text, _BOLD, color=color)


def _dim(text: str, *, color: bool) -> str:
    return _c(text, _DIM, color=color)


def _red(text: str, *, color: bool) -> str:
    return _c(text, _RED, color=color)


def _green(text: str, *, color: bool) -> str:
    return _c(text, _GREEN, color=color)


def _yellow(text: str, *, color: bool) -> str:
    return _c(text, _YELLOW, color=color)


def _cyan(text: str, *, color: bool) -> str:
    return _c(text, _CYAN, color=color)


# ---------------------------------------------------------------------------
# Public formatter
# ---------------------------------------------------------------------------


def format_text(d: TraceDiff, *, color: bool = True, verbose: bool = False) -> str:
    lines: list[str] = []

    header = _bold("=== witness diff ===", color=color)
    lines.append(header)

    base_line = (
        f"baseline:  {d.baseline.agent_name}  "
        f"({len(d.baseline.decisions)} decisions, "
        f"{_fmt_ms(d.baseline.wall_time_ms)})"
    )
    pert_line = (
        f"perturbed: {d.perturbed.agent_name}  "
        f"({len(d.perturbed.decisions)} decisions, "
        f"{_fmt_ms(d.perturbed.wall_time_ms)})"
    )
    if d.perturbed.perturbation:
        pert_line += _dim(
            f"  perturbation={d.perturbed.perturbation.type} {_fmt_params(d.perturbed.perturbation.params)}",
            color=color,
        )
    lines.append(_dim(base_line, color=color))
    lines.append(_dim(pert_line, color=color))
    lines.append("")

    # Decision-count delta
    delta = len(d.perturbed.decisions) - len(d.baseline.decisions)
    delta_str = f"{delta:+d}" if delta != 0 else "0"
    delta_color = _yellow if delta == 0 else (_red if delta < 0 else _green)
    lines.append(
        f"decisions: {len(d.baseline.decisions)} -> {len(d.perturbed.decisions)}  "
        f"({delta_color(delta_str, color=color)})"
    )

    # Per-decision change list
    for ch in d.alignment.pairs:
        line = _format_change(ch, color=color, verbose=verbose)
        if line is not None:
            lines.append(line)

    # Tool counts
    if d.tool_counts_baseline or d.tool_counts_perturbed:
        lines.append("")
        lines.append(
            f"tool calls: {_fmt_counts(d.tool_counts_baseline)} "
            f"-> {_fmt_counts(d.tool_counts_perturbed)}"
        )
        # Per-tool deltas
        all_tools = set(d.tool_counts_baseline) | set(d.tool_counts_perturbed)
        for t in sorted(all_tools):
            b = d.tool_counts_baseline.get(t, 0)
            p = d.tool_counts_perturbed.get(t, 0)
            if b == p:
                continue
            arrow = _green("+", color=color) if p > b else _red("-", color=color)
            lines.append(f"  {arrow} {t}: {b} -> {p}")

    # Wall time
    if d.wall_time_delta_ms is not None:
        sign = "+" if d.wall_time_delta_ms > 0 else ""
        lines.append("")
        lines.append(_dim(f"wall time: {sign}{d.wall_time_delta_ms} ms", color=color))

    # Final output
    lines.append("")
    if d.final_output_changed:
        lines.append(_bold(_red("final output: CHANGED", color=color), color=color))
        if verbose or _short_enough(d.baseline.final_output, d.perturbed.final_output):
            lines.append(_red(f"  - {_fmt_output(d.baseline.final_output)}", color=color))
            lines.append(_green(f"  + {_fmt_output(d.perturbed.final_output)}", color=color))
    else:
        lines.append(_green("final output: unchanged", color=color))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-change formatting
# ---------------------------------------------------------------------------


def _format_change(ch: DecisionChange, *, color: bool, verbose: bool) -> str | None:
    if ch.kind == "same":
        if not verbose:
            return None
        d = ch.baseline
        return _dim(f"  [{_step_id(d)}] {_decision_summary(d)} unchanged", color=color)

    if ch.kind == "removed":
        d = ch.baseline
        return _red(f"  [{_step_id(d)}] {_decision_summary(d)} REMOVED", color=color)

    if ch.kind == "added":
        d = ch.perturbed
        return _green(f"  [{_step_id(d)}] {_decision_summary(d)} ADDED", color=color)

    if ch.kind == "type_changed":
        return _yellow(
            f"  [{_step_id(ch.baseline)}] type changed: "
            f"{_decision_summary(ch.baseline)} -> {_decision_summary(ch.perturbed)}",
            color=color,
        )

    label_map = {
        "input_changed": "input changed",
        "output_changed": "output changed",
        "both_changed": "input+output changed",
    }
    label = label_map.get(ch.kind, ch.kind)
    return _yellow(
        f"  [{_step_id(ch.baseline or ch.perturbed)}] {_decision_summary(ch.baseline or ch.perturbed)}: {label}",
        color=color,
    )


def _step_id(d: Decision | None) -> str:
    return d.step_id if d else "?"


def _decision_summary(d: Decision | None) -> str:
    if d is None:
        return "<missing>"
    if d.type == DecisionType.TOOL_CALL:
        name = d.input.get("name") or d.input.get("tool") or "<unknown>"
        return f"tool_call {name}"
    if d.type == DecisionType.MODEL_CALL:
        return f"model_call {d.input.get('model') or ''}".strip()
    return d.type.value


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------


def _fmt_ms(ms: int | None) -> str:
    if ms is None:
        return "?ms"
    if ms < 1000:
        return f"{ms}ms"
    return f"{ms / 1000:.2f}s"


def _fmt_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "{}"
    inner = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    return "{" + inner + "}"


def _fmt_params(params: dict[str, Any]) -> str:
    if not params:
        return ""
    return " ".join(f"{k}={v}" for k, v in params.items())


def _fmt_output(value: Any, *, max_chars: int = 200) -> str:
    if value is None:
        return "<none>"
    if isinstance(value, str):
        s = value
    else:
        try:
            s = json.dumps(value, default=str)
        except (TypeError, ValueError):
            s = repr(value)
    s = s.replace("\n", "\\n")
    if len(s) > max_chars:
        return s[:max_chars] + "…"
    return s


def _short_enough(*values: Any, max_total: int = 600) -> bool:
    total = 0
    for v in values:
        try:
            total += len(json.dumps(v, default=str))
        except (TypeError, ValueError):
            total += len(repr(v))
        if total > max_total:
            return False
    return True


__all__ = ["format_text"]
