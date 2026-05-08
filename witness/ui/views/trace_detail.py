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

import json
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
    """Render the selected decision in the right pane.

    Two regions stacked top to bottom:

    1. Thin metadata strip — pipe-separated step_id · duration · timestamp.
    2. Typed content blocks — the actual prompt/response/tool args/etc,
       rendered in mono (or prose for final_output) so engineers can read
       what the agent actually did without expanding Raw JSON.

    Below both: the Raw JSON expander as an escape hatch.
    """
    duration = f"{d.duration_ms} ms" if d.duration_ms is not None else "—"
    meta = f"{d.step_id} · {duration} · {d.timestamp or '—'}"
    st.markdown(
        f'<div class="td-meta-strip">{escape(meta)}</div>',
        unsafe_allow_html=True,
    )

    st.markdown(_render_decision_content(d), unsafe_allow_html=True)

    with st.expander("Raw JSON", expanded=False):
        st.json(
            {
                "input": d.input or {},
                "output": d.output or {},
                "metadata": d.metadata or {},
            },
            expanded=False,
        )


# ---------------------------------------------------------------------------
# Typed content blocks — one renderer per decision type
# ---------------------------------------------------------------------------


def _render_block(
    label: str,
    body_html: str,
    *,
    mono: bool = True,
    chip: str | None = None,
    expand: bool = False,
) -> str:
    """Standard typed-content block: caps-label header (with optional
    right-aligned chip) and a body div with the right typography."""
    chip_html = (
        f'<span class="td-block-chip">{escape(chip)}</span>' if chip else ""
    )
    body_class = "td-block-body"
    if not mono:
        body_class += " prose"
    if expand:
        body_class += " expand"
    return (
        f'<div class="td-block">'
        f'<div class="td-block-head">'
        f'<span>{escape(label)}</span>{chip_html}'
        f'</div>'
        f'<div class="{body_class}">{body_html}</div>'
        f'</div>'
    )


def _empty_body() -> str:
    return '<span style="color: var(--fg-faint);">—</span>'


def _render_decision_content(d: Decision) -> str:
    if d.type == DecisionType.MODEL_CALL:
        return _render_model_call(d)
    if d.type == DecisionType.TOOL_CALL:
        return _render_tool_call(d)
    if d.type == DecisionType.TOOL_RESULT:
        return _render_tool_result(d)
    if d.type == DecisionType.FINAL_OUTPUT:
        return _render_final_output(d)
    if d.type == DecisionType.REASONING:
        return _render_reasoning(d)
    return _render_unknown(d)


def _render_model_call(d: Decision) -> str:
    parts: list[str] = []

    # PROMPT block (with model chip)
    prompt: Any = d.input.get("prompt")
    if not prompt and "messages" in d.input:
        prompt = _format_messages(d.input["messages"])
    prompt_body = escape(str(prompt)) if prompt else _empty_body()
    model = d.input.get("model")
    parts.append(
        _render_block("PROMPT", prompt_body, chip=str(model) if model else None)
    )

    # RESPONSE block
    response = d.output.get("text") or d.output.get("content")
    if isinstance(response, list):
        # Anthropic-style content blocks → flatten to text
        response = "\n\n".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in response
        )
    response_body = escape(str(response)) if response else _empty_body()
    parts.append(_render_block("RESPONSE", response_body))

    return "".join(parts)


def _render_tool_call(d: Decision) -> str:
    name = d.input.get("name") or d.input.get("tool") or "?"
    args = d.input.get("args")

    body_parts = [
        f'<div class="td-block-tool-name">{escape(str(name))}</div>'
    ]
    if isinstance(args, dict) and args:
        body_parts.append(_render_kv_args(args))
    elif args:
        body_parts.append(escape(json.dumps(args, indent=2, default=str)))
    return _render_block("TOOL CALL", "".join(body_parts))


def _render_tool_result(d: Decision) -> str:
    output = d.output or {}
    name = (d.input or {}).get("name") or (d.input or {}).get("tool")
    if not output:
        # Don't render an empty box — inline italic empty-state instead.
        chip = f"  · {name}" if name else ""
        return (
            f'<div class="td-block-empty">no result captured{escape(chip)}</div>'
        )
    body = escape(json.dumps(output, indent=2, default=str))
    return _render_block("RESULT", body, chip=str(name) if name else None)


def _render_final_output(d: Decision) -> str:
    text = (d.output or {}).get("text") or (d.output or {}).get("content")
    if isinstance(text, list):
        text = "\n\n".join(
            b.get("text", "") if isinstance(b, dict) else str(b) for b in text
        )
    body = escape(str(text)) if text else _empty_body()
    # Prose typography (sans), no max-height — final answers can be long.
    return _render_block("FINAL OUTPUT", body, mono=False, expand=True)


def _render_reasoning(d: Decision) -> str:
    text = (d.output or {}).get("text") or (d.output or {}).get("content")
    body = escape(str(text)) if text else _empty_body()
    return _render_block("REASONING", body)


def _render_unknown(d: Decision) -> str:
    label = d.type.value.upper()
    parts: list[str] = []
    if d.input:
        parts.append(
            '<div class="td-block-kv-key" style="font-size: 10.5px; '
            'text-transform: uppercase; letter-spacing: 0.06em; '
            'margin-bottom: 4px;">input</div>'
        )
        parts.append(escape(json.dumps(d.input, indent=2, default=str)))
    if d.output:
        if parts:
            parts.append(
                '<div class="td-block-kv-key" style="font-size: 10.5px; '
                'text-transform: uppercase; letter-spacing: 0.06em; '
                'margin: 8px 0 4px 0;">output</div>'
            )
        parts.append(escape(json.dumps(d.output, indent=2, default=str)))
    body = "".join(parts) if parts else _empty_body()
    return _render_block(label, body)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render_kv_args(args: dict[str, Any]) -> str:
    """Flat ``key: value`` rows for tool args. Falls back to JSON pretty-print
    when any value is a dict/list (because rendering nested dicts on one
    line gets unreadable fast)."""
    has_complex = any(isinstance(v, (dict, list)) for v in args.values())
    if has_complex:
        return escape(json.dumps(args, indent=2, default=str))
    rows: list[str] = []
    for k, v in args.items():
        v_str = v if isinstance(v, str) else json.dumps(v, default=str)
        rows.append(
            f'<div class="td-block-kv">'
            f'<span class="td-block-kv-key">{escape(str(k))}:</span> '
            f'{escape(v_str)}'
            f'</div>'
        )
    return "".join(rows)


def _format_messages(messages: Any) -> str:
    """Format an ``input.messages`` list (Anthropic / OpenAI shape) into a
    single readable string for the PROMPT block when no flat .prompt is set."""
    if not isinstance(messages, list):
        return str(messages)
    parts: list[str] = []
    for m in messages:
        if not isinstance(m, dict):
            parts.append(str(m))
            continue
        role = m.get("role", "?")
        content = m.get("content", "")
        if isinstance(content, list):
            content = "\n".join(
                block.get("text", str(block)) if isinstance(block, dict) else str(block)
                for block in content
            )
        parts.append(f"[{role}]\n{content}")
    return "\n\n".join(parts)


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
