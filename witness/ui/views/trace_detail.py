"""Trace detail view — opened from the Traces list when ?trace=<label> is set.

Three regions stacked top to bottom:

1. Header strip (~48px): filename + pipe-separated mono metadata strip,
   plus secondary "Diff…" and primary "Perturb…" buttons on the right.
2. Tab row: Sequence / Messages / Runs / Stability — 2px accent underline
   on the active tab, no background fills.
3. Content pane, scoped per tab.

Sequence tab — the signature layout: a 200px left rail with the numbered
decision list, and a flex-fill right pane showing the selected decision
as labelled fields with a collapsed Raw JSON disclosure at the bottom.
Active rail item gets a 2px --accent left-border and --bg-2 background.
"""
from __future__ import annotations

from collections.abc import Callable
from html import escape
from typing import Any

import streamlit as st

from witness.core.schema import Decision, DecisionType, Trace
from witness.ui.components import empty_state

_TYPE_COLOR = {
    DecisionType.MODEL_CALL.value: "var(--fg-dim)",
    DecisionType.TOOL_CALL.value: "var(--accent)",
    DecisionType.TOOL_RESULT.value: "var(--accent)",
    DecisionType.REASONING.value: "var(--fg-faint)",
    DecisionType.FINAL_OUTPUT.value: "var(--add)",
    DecisionType.CUSTOM.value: "var(--fg-dim)",
}


def render_trace_detail(
    label: str,
    trace: Trace,
    *,
    on_diff: Callable[[], None],
    on_perturb: Callable[[], None],
    state: dict[str, Any],
) -> None:
    """Render the trace detail view for ``label``."""
    _render_header_strip(label, trace, on_diff=on_diff, on_perturb=on_perturb)
    tab_id = _render_tab_row(label)
    _render_tab_content(label, trace, tab_id, state=state)


# ---------------------------------------------------------------------------
# Header strip
# ---------------------------------------------------------------------------


def _render_header_strip(
    label: str,
    trace: Trace,
    *,
    on_diff: Callable[[], None],
    on_perturb: Callable[[], None],
) -> None:
    meta = " · ".join(
        [
            escape(trace.agent_name),
            escape(trace.model or "—"),
            f"{len(trace.decisions)} decisions",
            _captured_str(trace.started_at),
        ]
    )
    st.markdown(
        f'<div class="td-header">'
        f'<div class="td-header-text">'
        f'<div class="td-filename">{escape(label)}</div>'
        f'<div class="td-meta">{meta}</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Action buttons render via Streamlit so callbacks fire — they sit
    # immediately under the HTML strip but visually we'll align them right
    # with a small column trick.
    cols = st.columns([6, 1, 1])
    with cols[1]:
        if st.button("Diff…", key=f"td_diff_{label}", use_container_width=True):
            on_diff()
    with cols[2]:
        if st.button(
            "Perturb…",
            key=f"td_perturb_{label}",
            type="primary",
            use_container_width=True,
        ):
            on_perturb()

    st.markdown('<hr class="td-hr"/>', unsafe_allow_html=True)


def _captured_str(iso: str | None) -> str:
    if not iso:
        return "—"
    return f"captured {iso[:10]}"


# ---------------------------------------------------------------------------
# Tab row
# ---------------------------------------------------------------------------


_TAB_IDS = ["sequence", "messages", "runs", "stability"]
_TAB_LABELS = {
    "sequence": "Sequence",
    "messages": "Messages",
    "runs": "Runs",
    "stability": "Stability",
}


def _render_tab_row(label: str) -> str:
    """Render the tab row as anchor links to ?trace=<label>&tab=<id>.

    Returns the active tab id (read from query params).
    """
    qp = st.query_params
    active_raw = qp.get("tab")
    active = active_raw[0] if isinstance(active_raw, list) and active_raw else active_raw
    if active not in _TAB_IDS:
        active = "sequence"

    tabs_html = ['<div class="td-tab-row">']
    for tid in _TAB_IDS:
        href = f"?trace={escape(label)}&tab={tid}"
        cls = "td-tab td-tab-active" if tid == active else "td-tab"
        tabs_html.append(
            f'<a class="{cls}" href="{href}">{_TAB_LABELS[tid]}</a>'
        )
    tabs_html.append("</div>")
    st.markdown("".join(tabs_html), unsafe_allow_html=True)
    return active


# ---------------------------------------------------------------------------
# Tab content
# ---------------------------------------------------------------------------


def _render_tab_content(
    label: str, trace: Trace, tab_id: str, *, state: dict[str, Any]
) -> None:
    if tab_id == "sequence":
        _render_sequence(label, trace, state=state)
    elif tab_id == "messages":
        _render_messages(trace)
    elif tab_id == "runs":
        _render_runs(label, trace, state=state)
    elif tab_id == "stability":
        _render_stability(label, trace, state=state)


# ---------------------------------------------------------------------------
# Sequence tab — 200px left rail + main pane
# ---------------------------------------------------------------------------


def _render_sequence(
    label: str, trace: Trace, *, state: dict[str, Any]
) -> None:
    if not trace.decisions:
        empty_state(
            icon="activity",
            message="No decisions captured.",
            hint="The trace ended without recording any agent steps.",
        )
        return

    # Selected decision index (per-trace, kept in session state)
    sel_key = f"td_sel_{label}"
    selected: int = state.get(sel_key, 0)
    if selected >= len(trace.decisions):
        selected = 0

    # Allow selection via ?sel=<i>
    qp = st.query_params
    sel_raw = qp.get("sel")
    sel_param = sel_raw[0] if isinstance(sel_raw, list) and sel_raw else sel_raw
    if sel_param is not None:
        try:
            new_sel = int(sel_param)
        except ValueError:
            new_sel = selected
        if 0 <= new_sel < len(trace.decisions) and new_sel != selected:
            state[sel_key] = new_sel
            selected = new_sel

    rail, pane = st.columns([1, 3], gap="medium")
    with rail:
        rail_html = ['<div class="td-seq-rail">']
        for i, d in enumerate(trace.decisions):
            href = f"?trace={escape(label)}&tab=sequence&sel={i}"
            cls = "td-seq-item td-seq-active" if i == selected else "td-seq-item"
            color = _TYPE_COLOR.get(d.type.value, "var(--fg-dim)")
            rail_html.append(
                f'<a class="{cls}" href="{href}">'
                f'<span class="td-seq-idx">{i:02d}</span>'
                f'<span class="td-seq-type" style="color: {color};">'
                f'{escape(d.type.value)}</span>'
                f'</a>'
            )
        rail_html.append("</div>")
        st.markdown("".join(rail_html), unsafe_allow_html=True)

    with pane:
        d = trace.decisions[selected]
        _render_decision_fields(d)


def _render_decision_fields(d: Decision) -> None:
    """Selected decision rendered as labeled fields, with Raw JSON disclosure."""
    color = _TYPE_COLOR.get(d.type.value, "var(--fg-dim)")
    summary = _decision_summary(d)
    duration = f"{d.duration_ms} ms" if d.duration_ms is not None else "—"

    fields_html = (
        f'<div class="td-fields">'
        f'<div class="td-field-row">'
        f'<span class="td-field-label">type</span>'
        f'<span class="td-field-value mono" style="color: {color};">'
        f'{escape(d.type.value)}</span>'
        f'</div>'
        f'<div class="td-field-row">'
        f'<span class="td-field-label">summary</span>'
        f'<span class="td-field-value">{escape(summary)}</span>'
        f'</div>'
        f'<div class="td-field-row">'
        f'<span class="td-field-label">step_id</span>'
        f'<span class="td-field-value mono">{escape(d.step_id)}</span>'
        f'</div>'
        f'<div class="td-field-row">'
        f'<span class="td-field-label">duration</span>'
        f'<span class="td-field-value mono">{escape(duration)}</span>'
        f'</div>'
        f'<div class="td-field-row">'
        f'<span class="td-field-label">timestamp</span>'
        f'<span class="td-field-value mono">{escape(d.timestamp or "—")}</span>'
        f'</div>'
        f'</div>'
    )
    st.markdown(fields_html, unsafe_allow_html=True)

    with st.expander("Raw JSON", expanded=False):
        st.json(
            {
                "input": d.input or {},
                "output": d.output or {},
                "metadata": d.metadata or {},
            },
            expanded=False,
        )


def _decision_summary(d: Decision) -> str:
    if d.type == DecisionType.TOOL_CALL:
        name = d.input.get("name") or d.input.get("tool") or "?"
        return f"tool_call · {name}"
    if d.type == DecisionType.MODEL_CALL:
        m = d.input.get("model") or ""
        return f"model_call · {m}".rstrip(" ·")
    return d.type.value


# ---------------------------------------------------------------------------
# Messages tab — empty-state-aware list
# ---------------------------------------------------------------------------


def _render_messages(trace: Trace) -> None:
    if not trace.messages:
        empty_state(
            icon="message-square",
            message="No messages captured.",
            hint="Adapter didn't record conversation turns for this run.",
        )
        return
    rows = []
    for i, m in enumerate(trace.messages):
        content = (
            m.content
            if isinstance(m.content, str)
            else str(m.content)
        )
        if len(content) > 200:
            content = content[:200] + "…"
        rows.append(
            f'<div class="td-msg-row">'
            f'<span class="td-msg-idx">{i:02d}</span>'
            f'<span class="td-msg-role">{escape(m.role.value)}</span>'
            f'<span class="td-msg-content">{escape(content)}</span>'
            f'</div>'
        )
    st.markdown("".join(rows), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Runs tab — placeholder; commit 7 wires perturb-from-detail
# ---------------------------------------------------------------------------


def _render_runs(
    label: str, trace: Trace, *, state: dict[str, Any]
) -> None:
    # List perturbed children of this trace (those whose parent_run_id == trace.run_id)
    children = [
        (lbl, t)
        for lbl, t in state.get("loaded_traces", {}).items()
        if t.parent_run_id == trace.run_id
    ]
    if not children:
        empty_state(
            icon="git-compare",
            message="No runs yet.",
            hint="Open a trace and press <kbd>P</kbd> to perturb.",
        )
        return
    rows = []
    for lbl, t in children:
        ptype = t.perturbation.type if t.perturbation else "—"
        rows.append(
            f'<a class="td-run-row" href="?trace={escape(lbl)}">'
            f'<span class="td-run-label mono">{escape(lbl)}</span>'
            f'<span class="td-run-type">{escape(ptype)}</span>'
            f'<span class="td-run-decisions mono">{len(t.decisions)} dec</span>'
            f'</a>'
        )
    st.markdown("".join(rows), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Stability tab — fingerprint when computed; empty-state when not
# ---------------------------------------------------------------------------


def _render_stability(
    label: str, trace: Trace, *, state: dict[str, Any]
) -> None:
    cached = (trace.metadata or {}).get("_cached_stability")
    if cached is None:
        empty_state(
            icon="activity",
            message="No stability score yet.",
            hint="Run a fingerprint to compute.",
        )
        return
    pct = int(float(cached) * 100)
    st.markdown(
        f'<div class="td-stability-headline">'
        f'<span class="td-stability-value">{pct}%</span>'
        f'<span class="td-stability-label">overall stability</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


__all__ = ["render_trace_detail"]
