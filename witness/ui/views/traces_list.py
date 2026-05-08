"""Dense trace list — single-table view, hairline separators, hover actions.

Layout (left to right): status dot · filename · agent · model · decisions ·
stability · captured. 32px row height, 1px hairline between rows. On hover
the row's background lightens and three icon buttons (open / diff / remove)
fade in at the right edge. The whole row is a click target via an absolute-
positioned overlay anchor; icons sit above the overlay with higher z-index.

Status dots:
    ok    — fingerprint computed and stable (>= 0.66)
    warn  — fingerprint mixed (0.33-0.66)
    err   — fingerprint fragile (< 0.33)
    dim   — no fingerprint yet

Sorting: column headers are clickable. The active sort column gets a faint
↑/↓ arrow appended. Default: captured desc (newest first).

Filtering: the search input matches against filename + agent. The pill row
(all / baseline / perturbed) narrows by trace kind.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

import streamlit as st

from witness.core.schema import Trace

# ---------------------------------------------------------------------------
# Lucide icons (16px, stroke-width 1.5, currentColor)
# ---------------------------------------------------------------------------

_ICON_ARROW_RIGHT = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M5 12h14M12 5l7 7-7 7"/></svg>'
)
_ICON_SPLIT = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M8 3 4 7l4 4M4 7h16M16 21l4-4-4-4M20 17H4"/></svg>'
)
_ICON_X = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M18 6 6 18M6 6l12 12"/></svg>'
)


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


def render_traces_list(
    state: dict[str, Any],
    *,
    add_trace: Callable[[str, Trace], str],
    on_empty: Callable[[], None],
) -> None:
    """Render the dense trace list. ``state`` is the session-state dict;
    ``add_trace`` and ``on_empty`` are wired by the caller (app.py)."""

    # ---- Search + filter pill row -----------------------------------
    # The pill group is a row of anchor links, not st.radio — Streamlit's
    # horizontal radio leaves the BaseUI circle indicators visible no
    # matter how aggressively we try to hide them, and the labels render
    # uppercase from the BaseUI stylesheet. Anchors give us total control.
    cols = st.columns([5, 3])
    with cols[0]:
        q_raw = st.text_input(
            "Search traces…",
            placeholder="Search traces…",
            key="traces_search",
            label_visibility="collapsed",
        )
        q = (q_raw or "").strip().lower()
    kind = state.get("traces_kind", "all")
    with cols[1]:
        st.markdown(_render_kind_pills(kind), unsafe_allow_html=True)

    loaded: dict[str, Trace] = state.get("loaded_traces", {})

    # ---- Drag-and-drop file uploader (always visible) --------------
    uploaded = st.file_uploader(
        "drop trace JSON files",
        type=["json"],
        accept_multiple_files=True,
        key="traces_uploader",
        label_visibility="collapsed",
    )
    if uploaded:
        for f in uploaded:
            try:
                text = f.read().decode("utf-8")
                t = Trace.model_validate_json(text)
            except Exception as e:
                st.error(f"failed to parse `{f.name}`: {e}")
                continue
            actual = add_trace(Path(f.name).stem, t)
            st.toast(f"loaded {actual} · {len(t.decisions)} decisions")
        st.session_state["traces_uploader"] = None
        st.rerun()

    # ---- Empty state -----------------------------------------------
    if not loaded:
        on_empty()
        return

    # ---- Sort state -------------------------------------------------
    sort_key = state.get("traces_sort_key", "captured")
    sort_dir = state.get("traces_sort_dir", "desc")

    # ---- Filter + sort the rows ------------------------------------
    rows_filtered = _filter_rows(loaded, q, kind)
    rows_filtered = _sort_rows(rows_filtered, sort_key, sort_dir)

    # ---- Column header (click to sort) -----------------------------
    st.markdown(_render_header(sort_key, sort_dir), unsafe_allow_html=True)

    # Header click handling — use a query param the page reads on rerun
    qp = st.query_params
    new_sort = qp.get("sort")
    if isinstance(new_sort, list):
        new_sort = new_sort[0] if new_sort else None
    if new_sort and new_sort != sort_key:
        state["traces_sort_key"] = new_sort
        state["traces_sort_dir"] = "asc"
        st.query_params.clear()
        st.rerun()
    elif new_sort and new_sort == sort_key:
        # Same column re-clicked: flip direction
        state["traces_sort_dir"] = "asc" if sort_dir == "desc" else "desc"
        st.query_params.clear()
        st.rerun()

    # ---- Rows -------------------------------------------------------
    active_label = state.get("active_label")
    rows_html = "".join(
        _render_row(label, t, is_active=(label == active_label))
        for label, t in rows_filtered
    )
    if not rows_html:
        st.markdown(
            '<div style="padding: 18px 8px; text-align: center; '
            'font-family: var(--mono); font-size: 12px; color: var(--fg-faint);">'
            "no traces match the current filter"
            "</div>",
            unsafe_allow_html=True,
        )
        return
    st.markdown(rows_html, unsafe_allow_html=True)

    # ---- Footer: hint about click + key actions --------------------
    st.markdown(
        '<div style="padding: 14px 8px 4px 8px; '
        'font-family: var(--mono); font-size: 11px; color: var(--fg-faint);">'
        "click any row to open · "
        "<kbd>↑</kbd>/<kbd>↓</kbd> to navigate · "
        "<kbd>Enter</kbd> to open · "
        "<kbd>P</kbd> to perturb"
        "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Filtering and sorting
# ---------------------------------------------------------------------------


def _filter_rows(
    loaded: dict[str, Trace], q: str, kind: str
) -> list[tuple[str, Trace]]:
    out: list[tuple[str, Trace]] = []
    for label, t in loaded.items():
        if kind == "baseline" and t.perturbation:
            continue
        if kind == "perturbed" and not t.perturbation:
            continue
        if q:
            if q in label.lower() or q in t.agent_name.lower():
                out.append((label, t))
        else:
            out.append((label, t))
    return out


_SORT_KEYS = {
    "filename": lambda label, t: label.lower(),
    "agent": lambda label, t: t.agent_name.lower(),
    "model": lambda label, t: (t.model or "").lower(),
    "decisions": lambda label, t: len(t.decisions),
    "stability": lambda label, t: _stability_score(t),
    "captured": lambda label, t: t.started_at or "",
}


def _sort_rows(
    rows: list[tuple[str, Trace]], sort_key: str, sort_dir: str
) -> list[tuple[str, Trace]]:
    keyfn = _SORT_KEYS.get(sort_key, _SORT_KEYS["captured"])
    return sorted(rows, key=lambda r: keyfn(r[0], r[1]), reverse=(sort_dir == "desc"))


# ---------------------------------------------------------------------------
# Per-row rendering
# ---------------------------------------------------------------------------


def _render_kind_pills(active: str) -> str:
    """Connected pill group: all / baseline / perturbed. Anchor links to
    ?kind=<value>; URL is processed in view_traces()."""
    pills = []
    for k in ("all", "baseline", "perturbed"):
        cls = "wt-pill wt-pill-active" if k == active else "wt-pill"
        pills.append(f'<a class="{cls}" href="?kind={k}">{k}</a>')
    return f'<div class="wt-pill-group">{"".join(pills)}</div>'


def _render_header(sort_key: str, sort_dir: str) -> str:
    arrow = " ↓" if sort_dir == "desc" else " ↑"

    def col(key: str, label: str, *, right: bool = False) -> str:
        is_active = key == sort_key
        suffix = arrow if is_active else ""
        align = "text-align: right;" if right else ""
        active_color = (
            "color: var(--fg);" if is_active else "color: var(--fg-muted);"
        )
        return (
            f'<a class="wt-col-head" href="?sort={key}" '
            f'style="{align} {active_color}">'
            f'{escape(label)}{suffix}</a>'
        )

    return (
        '<div class="wt-table-head">'
        f'<span></span>'
        f"{col('filename', 'filename')}"
        f"{col('agent', 'agent')}"
        f"{col('model', 'model')}"
        f"{col('decisions', 'decisions', right=True)}"
        f"{col('stability', 'stability', right=True)}"
        f"{col('captured', 'captured', right=True)}"
        '<span></span>'
        '</div>'
    )


def _render_row(label: str, t: Trace, *, is_active: bool) -> str:
    # Status dot color from cached fingerprint (if any). For now we use the
    # decision count as a proxy heuristic; commit 4 wires real fingerprint.
    score = _stability_score(t)
    dot_class = _stability_dot_class(score)
    stability_str = _stability_label(score) if score is not None else "—"
    stability_color = _stability_color(score)

    captured = _relative_time(t.started_at)
    filename = _truncate_middle(label, 36)
    agent = _truncate_middle(t.agent_name, 24)
    model = _truncate_middle(t.model or "—", 22)

    active_class = " active" if is_active else ""

    # Three hover-revealed icon links. Each mutates the URL; the page
    # reads the action on the next rerun.
    actions_html = (
        '<div class="wt-actions">'
        f'<a class="wt-action" href="?action=open&trace={escape(label)}" '
        f'title="Open">{_ICON_ARROW_RIGHT}</a>'
        f'<a class="wt-action" href="?action=diff&trace={escape(label)}" '
        f'title="Diff against…">{_ICON_SPLIT}</a>'
        f'<a class="wt-action wt-action-danger" '
        f'href="?action=remove&trace={escape(label)}" '
        f'title="Remove">{_ICON_X}</a>'
        '</div>'
    )

    # Whole-row clickable overlay (sits below icons via z-index).
    overlay = (
        f'<a class="wt-row-overlay" href="?trace={escape(label)}" '
        f'aria-label="Open {escape(label)}"></a>'
    )

    return (
        f'<div class="wt-row{active_class}">'
        f'<span class="wt-dot dot dot-{dot_class}"></span>'
        f'<span class="wt-cell wt-filename" title="{escape(label)}">'
        f'{escape(filename)}</span>'
        f'<span class="wt-cell wt-agent">{escape(agent)}</span>'
        f'<span class="wt-cell wt-model mono">{escape(model)}</span>'
        f'<span class="wt-cell wt-decisions mono">{len(t.decisions)}</span>'
        f'<span class="wt-cell wt-stability mono" '
        f'style="color: {stability_color};">{escape(stability_str)}</span>'
        f'<span class="wt-cell wt-captured mono">{escape(captured)}</span>'
        f'{actions_html}'
        f'{overlay}'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truncate_middle(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    head = (n - 1) // 2
    tail = n - 1 - head
    return s[:head] + "…" + s[-tail:]


def _relative_time(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        ts = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso[:10] or "—"
    now = datetime.now(tz=UTC)
    delta = now - ts
    seconds = delta.total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    if seconds < 604800:
        return f"{int(seconds // 86400)}d ago"
    return iso[:10]


def _stability_score(t: Trace) -> float | None:
    """Return the cached stability score for a trace, or None if not yet
    computed. We don't run a full fingerprint here — too expensive on render.
    """
    cached = (t.metadata or {}).get("_cached_stability")
    if isinstance(cached, (int, float)):
        return float(cached)
    return None


def _stability_dot_class(score: float | None) -> str:
    if score is None:
        return "dim"
    if score >= 0.66:
        return "add"
    if score < 0.33:
        return "del"
    return "accent"


def _stability_label(score: float | None) -> str:
    if score is None:
        return "—"
    return f"{int(score * 100)}%"


def _stability_color(score: float | None) -> str:
    if score is None:
        return "var(--fg-faint)"
    if score >= 0.66:
        return "var(--add)"
    if score < 0.33:
        return "var(--del)"
    return "var(--accent)"


__all__ = ["render_traces_list"]
