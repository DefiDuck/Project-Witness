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

import difflib
import json
from html import escape
from typing import Any

import streamlit as st

from witness.core.schema import Decision, DecisionType
from witness.diff.behavioral import DecisionChange, TraceDiff
from witness.ui.components.flow import render_diff_ribbons

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
    """Render the full diff view.

    Two modes selected via ``?dv_view=ribbon|list`` (defaults to ribbon):

    - ribbon: stacked baseline + perturbed flow ribbons with diff annotations
              (added=green +, removed=red ghost, changed=amber ~) and
              connection lines between matched decisions. The hero view.
    - list:   the legacy gutter+minimap text diff. Kept as an escape hatch
              for engineers who want to grep the raw delta.
    """
    _render_diff_header(label_a, label_b, diff)
    view = _read_view_param()
    _render_view_toggle(view)
    if view == "list":
        body, minimap = st.columns([24, 1], gap="small")
        with body:
            _render_diff_body(diff)
        with minimap:
            _render_minimap(diff)
    else:
        expanded = _read_expand_param(diff.alignment.pairs)
        st.markdown(
            f'<div class="flow-ribbon-wrap">'
            f'{render_diff_ribbons(label_a, label_b, diff.alignment.pairs, expanded_slot=expanded)}'
            f'</div>',
            unsafe_allow_html=True,
        )
        if expanded is not None:
            _render_expansion_card(expanded, diff.alignment.pairs[expanded])


def _read_view_param() -> str:
    qp = st.query_params
    raw = qp.get("dv_view")
    val = raw[0] if isinstance(raw, list) and raw else raw
    return val if val in ("ribbon", "list") else "ribbon"


def _render_view_toggle(active: str) -> None:
    """Pill toggle (ribbon / list) rendered top-right of the diff view."""
    pills = []
    for v, label in (("ribbon", "Ribbon"), ("list", "List")):
        cls = "wt-pill wt-pill-active" if v == active else "wt-pill"
        pills.append(f'<a class="{cls}" href="?dv_view={v}">{label}</a>')
    st.markdown(
        f'<div style="display: flex; justify-content: flex-end; margin: 4px 0 12px;">'
        f'<div class="wt-pill-group">{"".join(pills)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


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


# ---------------------------------------------------------------------------
# Inline expansion card (?expand=<i>) — the killer view of the diff page
# ---------------------------------------------------------------------------


def _read_expand_param(pairs: list[DecisionChange]) -> int | None:
    """Read and bounds-check the ``?expand=`` query param.

    Returns the slot index (0-based) when valid, else ``None``. Out-of-range
    values silently fall back to no expansion rather than erroring — the
    user might have an old deep-link after the underlying alignment shrank.
    """
    qp = st.query_params
    raw = qp.get("expand")
    val = raw[0] if isinstance(raw, list) and raw else raw
    if val is None:
        return None
    try:
        idx = int(val)
    except (TypeError, ValueError):
        return None
    if 0 <= idx < len(pairs):
        return idx
    return None


_KIND_LABEL = {
    "same": "unchanged",
    "input_changed": "input changed",
    "output_changed": "output changed",
    "both_changed": "both changed",
    "type_changed": "type changed",
    "added": "added",
    "removed": "removed",
}


def _render_expansion_card(slot: int, ch: DecisionChange) -> None:
    """Render the inline two-column expansion card below the ribbons.

    Left column: the baseline decision at this slot. Right column: the
    perturbed decision. If one side is missing (added or removed), that
    column shows a single italic empty-state line per the brief.

    Diffs in field values get character-level highlights via
    ``_diff_text``; long fields fall back to line-level diff implicitly
    because ndiff handles both.
    """
    a, b = ch.baseline, ch.perturbed
    kind_text = _KIND_LABEL.get(ch.kind, ch.kind)
    type_text = (a.type.value if a is not None else b.type.value if b is not None else "—")
    fields = _changed_fields(a, b)
    fields_html = (
        f'<span class="dv-expand-meta-fields">changed: {escape(", ".join(fields))}</span>'
        if fields
        else ""
    )

    # Close link clears just the expand param; the rest of the URL state
    # (dv_view, etc.) survives by virtue of being preserved in the page.
    close_href = "?dv_view=ribbon"

    st.markdown(
        f'<div class="dv-expand-wrap">'
        f'<div class="dv-expand-card">'
        f'<div class="dv-expand-meta">'
        f'<span>step {slot + 1} · {escape(type_text)} · {escape(kind_text)}</span>'
        f'<a class="dv-expand-close" href="{close_href}">× Close</a>'  # noqa: RUF001
        f'</div>'
        f'{fields_html}'
        f'<div class="dv-expand-grid">'
        f'<div class="dv-expand-col">'
        f'<div class="dv-expand-col-head">Baseline · step {slot + 1}</div>'
        f'{_render_expansion_side(a, b, side="baseline")}'
        f'</div>'
        f'<div class="dv-expand-col">'
        f'<div class="dv-expand-col-head">Perturbed · step {slot + 1}</div>'
        f'{_render_expansion_side(b, a, side="perturbed")}'
        f'</div>'
        f'</div></div></div>',
        unsafe_allow_html=True,
    )


def _changed_fields(a: Decision | None, b: Decision | None) -> list[str]:
    """Names of fields that differ between two decisions, for the
    ``changed: input, output`` chip in the metadata strip."""
    out: list[str] = []
    if a is None or b is None:
        return out
    if a.type != b.type:
        out.append("type")
    if (a.input or {}) != (b.input or {}):
        out.append("input")
    if (a.output or {}) != (b.output or {}):
        out.append("output")
    return out


def _render_expansion_side(
    self_d: Decision | None,
    other_d: Decision | None,
    *,
    side: str,
) -> str:
    """Render one column of the expansion card.

    When ``self_d`` is None, render the empty-state line (added on the
    baseline side, removed on the perturbed side). Otherwise render typed
    content blocks with character-level diff fragments highlighting any
    field that changed between sides.
    """
    if self_d is None:
        msg = (
            "not in baseline" if side == "baseline" else "not in perturbed"
        )
        return f'<div class="dv-expand-col-empty">{escape(msg)}</div>'

    blocks: list[str] = []

    # Type block — show as a small caps-label so the expanded view echoes
    # the ribbon node's primary signal.
    blocks.append(
        _diff_block("TYPE", self_d.type.value, other_d.type.value if other_d else None)
    )

    # Input + output get JSON-formatted then character-diffed against the
    # other side. For the trivial 'same' case there's nothing to highlight,
    # which _diff_text handles by returning escaped plain text.
    self_in = _stringify_field(self_d.input or {})
    other_in = _stringify_field(other_d.input or {}) if other_d else None
    blocks.append(_diff_block("INPUT", self_in, other_in))

    self_out = _stringify_field(self_d.output or {})
    other_out = _stringify_field(other_d.output or {}) if other_d else None
    blocks.append(_diff_block("OUTPUT", self_out, other_out))

    return "".join(blocks)


def _stringify_field(v: Any) -> str:
    """Compact pretty-print a JSON-ish value so ndiff can chew it
    line-by-line. We deliberately use indent=2 so multi-line values get
    aligned and difflib can produce clean line-level highlights."""
    if isinstance(v, str):
        return v
    try:
        return json.dumps(v, indent=2, default=str, sort_keys=True)
    except (TypeError, ValueError):
        return str(v)


def _diff_block(label: str, self_text: str, other_text: str | None) -> str:
    """Wrap a ``label + body`` pair in the same caps-header block the
    trace detail uses, but the body's text gets ndiff highlights."""
    body = _diff_text(self_text, other_text)
    return (
        f'<div class="td-block">'
        f'<div class="td-block-head"><span>{escape(label)}</span></div>'
        f'<div class="td-block-body">{body}</div>'
        f'</div>'
    )


def _diff_text(self_text: str, other_text: str | None) -> str:
    """Render ``self_text`` with green/red span fragments for the parts
    that differ from ``other_text``.

    For short single-line values we use ``ndiff`` at character granularity;
    for long multi-line values we use ``unified_diff``-style line-level
    chunks. ``ndiff`` itself produces both — we just inspect the leading
    marker on each chunk.
    """
    if other_text is None:
        # Other side is missing — entire body is treated as an addition
        # on this side (or a removal, depending on orientation; the
        # caller dictates by passing self / other).
        return f'<span class="dv-frag-add">{escape(self_text)}</span>'

    if self_text == other_text:
        return escape(self_text)

    # Pick char vs line granularity based on length. ``128`` keeps short
    # tool args char-level (so single-token swaps highlight cleanly) and
    # long prompts line-level (so the diff stays scannable).
    if len(self_text) <= 128 and len(other_text) <= 128 and "\n" not in self_text:
        return _diff_chars(self_text, other_text)
    return _diff_lines(self_text, other_text)


def _diff_chars(self_text: str, other_text: str) -> str:
    """Character-level diff via ``ndiff``. Each chunk is one character."""
    parts: list[str] = []
    for chunk in difflib.ndiff(other_text, self_text):
        # ndiff produces "  c" / "+ c" / "- c" / "? …"; the trailing line is
        # a hint, skipped here. We only emit the SELF side: " " and "+".
        if not chunk:
            continue
        marker = chunk[:1]
        ch = chunk[2:] if len(chunk) >= 2 else ""
        if marker == " ":
            parts.append(escape(ch))
        elif marker == "+":
            parts.append(f'<span class="dv-frag-add">{escape(ch)}</span>')
        # marker '-' is the OTHER side; we don't render it on this column.
        # marker '?' is the hint line; skip.
    return "".join(parts)


def _diff_lines(self_text: str, other_text: str) -> str:
    """Line-level diff for long values. Same strategy as
    ``_diff_chars`` but operating on splitlines()."""
    self_lines = self_text.splitlines(keepends=False)
    other_lines = other_text.splitlines(keepends=False)
    out: list[str] = []
    for chunk in difflib.ndiff(other_lines, self_lines):
        if not chunk:
            continue
        marker = chunk[:1]
        line = chunk[2:] if len(chunk) >= 2 else ""
        if marker == " ":
            out.append(escape(line))
        elif marker == "+":
            out.append(f'<span class="dv-frag-add">{escape(line)}</span>')
        # again, skip '-' (other side) and '?' (hint).
    return "\n".join(out)


__all__ = ["render_diff_view"]
