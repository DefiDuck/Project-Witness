"""Side-by-side diff view with gutter markers and a Sentry-style minimap.

Header: two trace IDs as ``baseline → perturbed`` in mono, plus a 4-stat
summary strip (decisions changed / skipped / tool diffs / final output).

Body: two-column decision sequences (mono). Each row has a left gutter
marker:
    +  in --ok   for added decisions (only present in perturbed)
    -  in --err  for removed decisions (only present in baseline)
    ~  in --warn for changed decisions (input or output diff)
    ·  faint    for unchanged decisions

Click a changed row to expand it inline and show the input/output diff
character-by-character with red/green runs.

Right edge: a 12px-wide minimap, full-height of the diff body, with 2px
ticks marking the positions of changed decisions. Each tick is colored
by its kind (ok / err / warn). Click a tick to scroll the diff body to
that decision.
"""
from __future__ import annotations

from html import escape

import streamlit as st

from witness.core.schema import Decision, DecisionType
from witness.diff.behavioral import DecisionChange, TraceDiff

_GUTTER = {
    "added": ("+", "var(--ok)"),
    "removed": ("-", "var(--err)"),
    "input_changed": ("~", "var(--warn)"),
    "output_changed": ("~", "var(--warn)"),
    "both_changed": ("~", "var(--warn)"),
    "type_changed": ("~", "var(--warn)"),
    "same": ("·", "var(--fg-faint)"),
}


def render_diff_view(
    label_a: str,
    label_b: str,
    diff: TraceDiff,
) -> None:
    """Render the full diff view: header strip + body + minimap."""
    _render_diff_header(label_a, label_b, diff)
    body, minimap = st.columns([24, 1], gap="small")
    with body:
        _render_diff_body(diff)
    with minimap:
        _render_minimap(diff)


# ---------------------------------------------------------------------------
# Header strip
# ---------------------------------------------------------------------------


def _render_diff_header(label_a: str, label_b: str, diff: TraceDiff) -> None:
    base = diff.baseline
    changed = sum(
        1
        for ch in diff.alignment.pairs
        if ch.kind not in ("same", "removed", "added")
    )
    removed = sum(1 for ch in diff.alignment.pairs if ch.kind == "removed")
    added = sum(1 for ch in diff.alignment.pairs if ch.kind == "added")
    base_tools = sum(diff.tool_counts_baseline.values())
    pert_tools = sum(diff.tool_counts_perturbed.values())
    tool_diff = abs(pert_tools - base_tools) + sum(
        1
        for k in (set(diff.tool_counts_baseline) | set(diff.tool_counts_perturbed))
        if diff.tool_counts_baseline.get(k, 0) != diff.tool_counts_perturbed.get(k, 0)
    )

    title = (
        f'<div class="dv-title mono">'
        f'<span class="dv-title-label">{escape(label_a)}</span>'
        f'<span class="dv-title-arrow">→</span>'
        f'<span class="dv-title-label">{escape(label_b)}</span>'
        f'</div>'
    )

    stats_html = (
        f'<div class="dv-stats">'
        f'{_stat("changed", changed + added, len(diff.alignment.pairs))}'
        f'{_stat("skipped", removed, len(base.decisions), accent="err" if removed else None)}'
        f'{_stat("tool diffs", tool_diff, base_tools or 1)}'
        f'{_stat_text("final output", "CHANGED" if diff.final_output_changed else "unchanged", accent="err" if diff.final_output_changed else "ok")}'
        f'</div>'
    )

    st.markdown(title + stats_html, unsafe_allow_html=True)


def _stat(label: str, value: int, of: int, *, accent: str | None = None) -> str:
    color = "var(--err)" if accent == "err" else (
        "var(--ok)" if accent == "ok" else "var(--fg)"
    )
    return (
        f'<div class="dv-stat">'
        f'<div class="dv-stat-label">{escape(label)}</div>'
        f'<div class="dv-stat-value mono" style="color: {color};">{value}'
        f'<span class="dv-stat-of">/ {of}</span></div>'
        f'</div>'
    )


def _stat_text(label: str, value: str, *, accent: str | None = None) -> str:
    color = "var(--err)" if accent == "err" else (
        "var(--ok)" if accent == "ok" else "var(--fg)"
    )
    return (
        f'<div class="dv-stat">'
        f'<div class="dv-stat-label">{escape(label)}</div>'
        f'<div class="dv-stat-value mono" style="color: {color}; font-size: 14px;">'
        f'{escape(value)}</div>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Diff body
# ---------------------------------------------------------------------------


def _render_diff_body(diff: TraceDiff) -> None:
    rows: list[str] = []
    for idx, ch in enumerate(diff.alignment.pairs):
        rows.append(_render_diff_row(idx, ch))
    st.markdown(
        f'<div class="dv-body">{"".join(rows)}</div>',
        unsafe_allow_html=True,
    )


def _render_diff_row(idx: int, ch: DecisionChange) -> str:
    marker, color = _GUTTER.get(ch.kind, ("·", "var(--fg-faint)"))

    base = ch.baseline
    pert = ch.perturbed

    base_text = _decision_summary(base) if base else "—"
    pert_text = _decision_summary(pert) if pert else "—"

    # Background tint per side based on kind
    base_bg = "transparent"
    pert_bg = "transparent"
    if ch.kind in ("removed",):
        base_bg = "var(--del-bg)"
    elif ch.kind in ("added",):
        pert_bg = "var(--add-bg)"
    elif ch.kind in ("input_changed", "output_changed", "both_changed", "type_changed"):
        base_bg = "var(--del-bg)"
        pert_bg = "var(--add-bg)"

    return (
        f'<div class="dv-row" id="dv-row-{idx}">'
        f'<span class="dv-gutter mono" style="color: {color};">{escape(marker)}</span>'
        f'<span class="dv-cell mono" style="background: {base_bg};">{escape(base_text)}</span>'
        f'<span class="dv-cell mono" style="background: {pert_bg};">{escape(pert_text)}</span>'
        f'</div>'
    )


def _decision_summary(d: Decision) -> str:
    if d.type == DecisionType.TOOL_CALL:
        name = d.input.get("name") or d.input.get("tool") or "?"
        return f"{d.type.value}  {name}"
    if d.type == DecisionType.MODEL_CALL:
        m = d.input.get("model") or ""
        return f"{d.type.value}  {m}".rstrip()
    return d.type.value


# ---------------------------------------------------------------------------
# Minimap — Sentry-style breadcrumb strip on the right edge
# ---------------------------------------------------------------------------


def _render_minimap(diff: TraceDiff) -> None:
    """Compact full-height strip of 2px ticks per changed decision."""
    pairs = diff.alignment.pairs
    if not pairs:
        return
    ticks: list[str] = []
    n = len(pairs)
    for idx, ch in enumerate(pairs):
        if ch.kind == "same":
            continue
        _, color = _GUTTER.get(ch.kind, ("·", "var(--fg-faint)"))
        # vertical position as a percentage of the strip height
        pct = (idx / max(n - 1, 1)) * 100
        ticks.append(
            f'<a class="dv-mini-tick" href="#dv-row-{idx}" '
            f'style="top: {pct:.2f}%; background: {color};" '
            f'title="row {idx} · {ch.kind}"></a>'
        )
    st.markdown(
        f'<div class="dv-minimap">{"".join(ticks)}</div>',
        unsafe_allow_html=True,
    )


__all__ = ["render_diff_view"]
