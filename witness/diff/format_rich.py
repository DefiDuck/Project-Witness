"""Rich-powered terminal renderer for traces and diffs.

Imported lazily — base witness has no rich dependency. The CLI auto-detects
whether rich is importable and prefers this renderer; falls back to the plain
ANSI renderer in ``witness.diff.format`` otherwise.
"""
from __future__ import annotations

from typing import Any

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from witness.core.schema import Decision, DecisionType, Trace
from witness.diff.behavioral import DecisionChange, TraceDiff

# ---------------------------------------------------------------------------
# Color theme
# ---------------------------------------------------------------------------

COLOR_OK = "green"
COLOR_BAD = "red"
COLOR_WARN = "yellow"
COLOR_DIM = "grey50"
COLOR_ACCENT = "cyan"
COLOR_HEADER = "bold magenta"

KIND_STYLES: dict[str, str] = {
    "same": COLOR_DIM,
    "removed": COLOR_BAD,
    "added": COLOR_OK,
    "input_changed": COLOR_WARN,
    "output_changed": COLOR_WARN,
    "both_changed": COLOR_WARN,
    "type_changed": COLOR_WARN,
}

KIND_LABELS: dict[str, str] = {
    "same": "unchanged",
    "removed": "REMOVED",
    "added": "ADDED",
    "input_changed": "input changed",
    "output_changed": "output changed",
    "both_changed": "input + output changed",
    "type_changed": "type changed",
}


# ---------------------------------------------------------------------------
# Public renderers
# ---------------------------------------------------------------------------


def render_diff(d: TraceDiff, *, verbose: bool = False) -> Group:
    """Build a Group of renderables for a TraceDiff. Caller prints with a Console."""
    return Group(
        _diff_header(d),
        Text(""),
        _decision_timeline(d, verbose=verbose),
        Text(""),
        _tool_count_table(d),
        Text(""),
        _final_output_panel(d, verbose=verbose),
        Text(""),
        _wall_time_line(d),
    )


def render_fingerprint(fp) -> Group:
    """Build a Group for a Fingerprint."""
    return Group(
        _fp_header(fp),
        Text(""),
        _fp_stability_table(fp),
        Text(""),
        _fp_overall_panel(fp),
        Text(""),
        _fp_per_run_table(fp),
    )


def render_trace_summary(t: Trace) -> Panel:
    """Pretty 'witness inspect' card for a single trace."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold")
    grid.add_column()
    grid.add_row("agent_name", t.agent_name)
    grid.add_row("run_id", t.run_id)
    grid.add_row("model", str(t.model))
    grid.add_row("tools_available", ", ".join(t.tools_available) or "—")
    grid.add_row("decisions", str(len(t.decisions)))
    grid.add_row("messages", str(len(t.messages)))
    grid.add_row("wall_time_ms", _fmt_ms(t.wall_time_ms))
    grid.add_row("entrypoint", str(t.entrypoint or "—"))
    if t.perturbation:
        grid.add_row(
            "perturbation",
            f"[bold yellow]{t.perturbation.type}[/]  {_fmt_params(t.perturbation.params)}",
        )
        grid.add_row("parent_run_id", str(t.parent_run_id))
    return Panel(
        grid,
        title=f"[{COLOR_HEADER}]witness trace[/]",
        border_style=COLOR_ACCENT,
        box=box.ROUNDED,
        padding=(1, 2),
    )


def make_console(*, no_color: bool = False, force_terminal: bool | None = None) -> Console:
    """Build a Rich Console with sensible defaults.

    ``force_terminal=True`` keeps colors even when piped — useful for
    `--color always` semantics.
    """
    return Console(
        no_color=no_color,
        force_terminal=force_terminal,
        highlight=False,
        soft_wrap=False,
        emoji=False,
    )


# ---------------------------------------------------------------------------
# Diff sections
# ---------------------------------------------------------------------------


def _diff_header(d: TraceDiff) -> Panel:
    base = d.baseline
    pert = d.perturbed

    perturbation_line = ""
    if pert.perturbation:
        params = _fmt_params(pert.perturbation.params)
        perturbation_line = (
            f"\n[{COLOR_DIM}]perturbation:[/] [bold]{pert.perturbation.type}[/]  "
            f"[{COLOR_DIM}]{params}[/]"
        )

    delta = len(pert.decisions) - len(base.decisions)
    delta_color = COLOR_BAD if delta < 0 else (COLOR_OK if delta > 0 else COLOR_WARN)
    delta_str = f"{delta:+d}" if delta != 0 else "0"

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold")
    grid.add_column()
    grid.add_column(style=COLOR_DIM)
    grid.add_row(
        "baseline",
        f"[bold]{base.agent_name}[/]",
        f"{len(base.decisions)} decisions, {_fmt_ms(base.wall_time_ms)}",
    )
    grid.add_row(
        "perturbed",
        f"[bold]{pert.agent_name}[/]",
        f"{len(pert.decisions)} decisions, {_fmt_ms(pert.wall_time_ms)}",
    )

    decisions_line = Text.from_markup(
        f"[bold]decisions[/]  {len(base.decisions)} -> {len(pert.decisions)}  "
        f"([{delta_color}]{delta_str}[/])"
    )

    body = Group(grid, Text.from_markup(perturbation_line) if perturbation_line else Text(""), decisions_line)

    return Panel(
        body,
        title=f"[{COLOR_HEADER}]witness diff[/]",
        border_style=COLOR_ACCENT,
        box=box.ROUNDED,
        padding=(1, 2),
    )


def _decision_timeline(d: TraceDiff, *, verbose: bool) -> Panel:
    table = Table(
        box=box.SIMPLE,
        expand=True,
        show_header=True,
        header_style="bold",
        pad_edge=False,
    )
    table.add_column("step", style=COLOR_DIM, no_wrap=True)
    table.add_column("kind", no_wrap=True)
    table.add_column("decision", overflow="ellipsis")

    interesting = [p for p in d.alignment.pairs if verbose or p.kind != "same"]
    if not interesting:
        return Panel(
            Text("(no decision-level changes)", style=COLOR_DIM, justify="center"),
            title="[bold]decision timeline[/]",
            border_style=COLOR_DIM,
            box=box.ROUNDED,
        )

    for ch in interesting:
        style = KIND_STYLES.get(ch.kind, "white")
        label = KIND_LABELS.get(ch.kind, ch.kind)
        d_obj = ch.baseline or ch.perturbed
        step = (d_obj.step_id if d_obj else "?")[:14]
        summary = _decision_summary(d_obj)
        kind_text = Text(label, style=style)
        table.add_row(step, kind_text, summary)

    return Panel(
        table,
        title="[bold]decision timeline[/]",
        border_style=COLOR_DIM,
        box=box.ROUNDED,
    )


def _tool_count_table(d: TraceDiff) -> Panel:
    base_counts = d.tool_counts_baseline
    pert_counts = d.tool_counts_perturbed
    if not base_counts and not pert_counts:
        return Panel(
            Text("(no tool calls)", style=COLOR_DIM, justify="center"),
            title="[bold]tool calls[/]",
            border_style=COLOR_DIM,
            box=box.ROUNDED,
        )

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold", expand=False)
    table.add_column("tool", style="bold")
    table.add_column("baseline", justify="right")
    table.add_column("perturbed", justify="right")
    table.add_column("Δ", justify="right")

    all_tools = sorted(set(base_counts) | set(pert_counts))
    for t in all_tools:
        b = base_counts.get(t, 0)
        p = pert_counts.get(t, 0)
        delta = p - b
        if delta == 0:
            delta_cell = Text("0", style=COLOR_DIM)
        else:
            color = COLOR_OK if delta > 0 else COLOR_BAD
            delta_cell = Text(f"{delta:+d}", style=color)
        table.add_row(t, str(b), str(p), delta_cell)

    return Panel(
        table,
        title="[bold]tool calls[/]",
        border_style=COLOR_DIM,
        box=box.ROUNDED,
    )


def _final_output_panel(d: TraceDiff, *, verbose: bool) -> Panel:
    if not d.final_output_changed:
        return Panel(
            Text("unchanged", style=COLOR_OK, justify="center"),
            title="[bold]final output[/]",
            border_style=COLOR_OK,
            box=box.ROUNDED,
        )

    base_str = _fmt_output(d.baseline.final_output, max_chars=10_000 if verbose else 400)
    pert_str = _fmt_output(d.perturbed.final_output, max_chars=10_000 if verbose else 400)

    body = Group(
        Text.from_markup(f"[{COLOR_BAD}][bold]CHANGED[/][/]", justify="center"),
        Text(""),
        Panel(
            Text(base_str, style=COLOR_BAD),
            title="[dim]baseline[/]",
            border_style=COLOR_BAD,
            box=box.ROUNDED,
            padding=(0, 1),
        ),
        Panel(
            Text(pert_str, style=COLOR_OK),
            title="[dim]perturbed[/]",
            border_style=COLOR_OK,
            box=box.ROUNDED,
            padding=(0, 1),
        ),
    )

    return Panel(
        body,
        title="[bold]final output[/]",
        border_style=COLOR_WARN,
        box=box.ROUNDED,
    )


def _wall_time_line(d: TraceDiff) -> Text:
    if d.wall_time_delta_ms is None:
        return Text("")
    sign = "+" if d.wall_time_delta_ms > 0 else ""
    return Text.from_markup(
        f"[{COLOR_DIM}]wall time[/]  {sign}{d.wall_time_delta_ms} ms"
    )


# ---------------------------------------------------------------------------
# Fingerprint sections
# ---------------------------------------------------------------------------


def _fp_header(fp) -> Panel:
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold")
    grid.add_column()
    grid.add_row("baseline", fp.baseline_run_id)
    grid.add_row("runs", str(len(fp.runs)))
    return Panel(
        grid,
        title=f"[{COLOR_HEADER}]witness fingerprint[/]",
        border_style=COLOR_ACCENT,
        box=box.ROUNDED,
        padding=(1, 2),
    )


def _fp_stability_table(fp) -> Panel:
    scores = fp.stability_by_decision_type()
    if not scores:
        return Panel(
            Text("(no decision types observed)", style=COLOR_DIM, justify="center"),
            title="[bold]stability by decision type[/]",
            border_style=COLOR_DIM,
            box=box.ROUNDED,
        )

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold", expand=True)
    table.add_column("decision type", style="bold", no_wrap=True)
    table.add_column("stability bar", justify="left")
    table.add_column("score", justify="right", no_wrap=True)

    for dtype, score in sorted(scores.items()):
        table.add_row(dtype, _stability_bar(score), _stability_label(score))

    return Panel(
        table,
        title="[bold]stability by decision type[/]",
        border_style=COLOR_DIM,
        box=box.ROUNDED,
    )


def _fp_overall_panel(fp) -> Panel:
    fout = fp.final_output_stability()
    overall = fp.overall_stability()
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold")
    grid.add_column()
    grid.add_column(justify="right", style="bold", no_wrap=True)
    grid.add_row("final output stability", _stability_bar(fout), _stability_label(fout))
    grid.add_row("overall stability", _stability_bar(overall), _stability_label(overall))
    return Panel(
        grid,
        title="[bold]aggregate scores[/]",
        border_style=_score_color(overall),
        box=box.ROUNDED,
        padding=(1, 2),
    )


def _fp_per_run_table(fp) -> Panel:
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold", expand=False)
    table.add_column("perturbation", style="bold")
    table.add_column("params", style=COLOR_DIM)
    table.add_column("Δ decisions", justify="right")
    table.add_column("final", justify="center")
    for r in fp.runs:
        params = _fmt_params(r.perturbation_params)
        delta = len(r.diff.perturbed.decisions) - len(r.diff.baseline.decisions)
        delta_color = COLOR_BAD if delta < 0 else (COLOR_OK if delta > 0 else COLOR_DIM)
        delta_cell = Text(f"{delta:+d}" if delta != 0 else "0", style=delta_color)
        if r.diff.final_output_changed:
            final_cell = Text("CHANGED", style=COLOR_BAD)
        else:
            final_cell = Text("same", style=COLOR_OK)
        table.add_row(r.perturbation_type, params, delta_cell, final_cell)
    return Panel(
        table,
        title="[bold]per-run summary[/]",
        border_style=COLOR_DIM,
        box=box.ROUNDED,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decision_summary(d: Decision | None) -> str:
    if d is None:
        return "[dim]<missing>[/dim]"
    if d.type == DecisionType.TOOL_CALL:
        name = d.input.get("name") or d.input.get("tool") or "?"
        return f"tool_call [bold cyan]{name}[/]"
    if d.type == DecisionType.MODEL_CALL:
        model = d.input.get("model") or ""
        return f"model_call [italic]{model}[/]" if model else "model_call"
    return d.type.value


def _stability_bar(score: float, width: int = 24) -> Text:
    filled = max(0, min(width, int(round(score * width))))
    color = _score_color(score)
    bar = Text()
    bar.append("█" * filled, style=color)
    bar.append("░" * (width - filled), style=COLOR_DIM)
    return bar


def _stability_label(score: float) -> Text:
    return Text(f"{score:.2f}", style=_score_color(score))


def _score_color(score: float) -> str:
    if score >= 0.66:
        return COLOR_OK
    if score >= 0.33:
        return COLOR_WARN
    return COLOR_BAD


def _fmt_ms(ms: int | None) -> str:
    if ms is None:
        return "?ms"
    if ms < 1000:
        return f"{ms}ms"
    return f"{ms / 1000:.2f}s"


def _fmt_params(params: dict[str, Any]) -> str:
    if not params:
        return ""
    return " ".join(f"{k}={v}" for k, v in params.items())


def _fmt_output(value: Any, *, max_chars: int = 400) -> str:
    if value is None:
        return "<none>"
    if isinstance(value, str):
        s = value
    else:
        try:
            import json as _json

            s = _json.dumps(value, indent=2, default=str)
        except (TypeError, ValueError):
            s = repr(value)
    if len(s) > max_chars:
        return s[:max_chars] + "…"
    return s


__all__ = [
    "render_diff",
    "render_fingerprint",
    "render_trace_summary",
    "make_console",
]
