"""Reusable Streamlit UI building blocks.

These wrap idiomatic Streamlit primitives in slightly higher-level helpers so
``app.py`` reads as a sequence of intent rather than markup. ClaudeDesign owns
the visual treatment (CSS, theme); this module owns the structural HTML and
behavior.
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable, Optional

import streamlit as st

from witness.core.schema import Decision, DecisionType, Trace


# ---------------------------------------------------------------------------
# Empty states
# ---------------------------------------------------------------------------


def empty_state(
    title: str,
    description: str = "",
    *,
    cta_label: Optional[str] = None,
    cta_target_page: Optional[str] = None,
    on_cta: Optional[Callable[[], None]] = None,
    key_prefix: str = "empty",
) -> None:
    """Render a centered empty-state card.

    `cta_target_page` is the value to write into ``st.session_state.nav_target``
    so the sidebar's radio picks it up on the next rerun. (See ``app.py``'s nav
    handler.)
    """
    st.markdown(
        f"""
        <div class="empty-state">
          <div class="empty-state-title">{title}</div>
          <div class="empty-state-desc">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if cta_label:
        col_l, col_c, col_r = st.columns([1, 1, 1])
        with col_c:
            if st.button(cta_label, key=f"{key_prefix}_cta", use_container_width=True):
                if on_cta is not None:
                    on_cta()
                if cta_target_page is not None:
                    st.session_state["nav_target"] = cta_target_page
                    st.rerun()


# ---------------------------------------------------------------------------
# Confirmation pattern (two-click destructive action)
# ---------------------------------------------------------------------------


def confirm_button(
    label: str,
    confirm_label: str = "Yes",
    *,
    key: str,
    on_confirm: Callable[[], None],
    type: str = "secondary",
    timeout_seconds: float = 4.0,
) -> None:
    """Two-click destructive action.

    First click reveals a Yes/No pair; auto-resets after ``timeout_seconds``.
    Default labels are deliberately short (``Yes`` / ``No``) so the pair
    renders cleanly even when this widget lives inside a narrow column —
    the original ``Confirm`` / ``Cancel`` labels wrapped to multiple lines
    and rendered as ``Confi rm`` / ``Canc el`` in the trace-list row layout.

    Caller passes ``on_confirm`` which actually mutates state. After confirm
    we call ``st.rerun()`` so the UI reflects the mutation.
    """
    pending_key = f"_confirm_pending::{key}"
    pending_at_key = f"_confirm_at::{key}"

    pending = st.session_state.get(pending_key, False)
    pending_at = st.session_state.get(pending_at_key, 0.0)

    # Auto-reset stale pending
    if pending and (time.monotonic() - pending_at) > timeout_seconds:
        pending = False
        st.session_state[pending_key] = False

    if not pending:
        if st.button(label, key=f"_btn::{key}", type=type, use_container_width=True):
            st.session_state[pending_key] = True
            st.session_state[pending_at_key] = time.monotonic()
            st.rerun()
    else:
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button(
                confirm_label,
                key=f"_yes::{key}",
                type="primary",
                use_container_width=True,
            ):
                st.session_state[pending_key] = False
                on_confirm()
                st.rerun()
        with col_b:
            if st.button(
                "No",
                key=f"_no::{key}",
                type="secondary",
                use_container_width=True,
            ):
                st.session_state[pending_key] = False
                st.rerun()


# ---------------------------------------------------------------------------
# Search / filter input
# ---------------------------------------------------------------------------


def search_input(
    *,
    key: str,
    placeholder: str = "Search…",
    label: str = "search",
) -> str:
    """A consistent search input. Returns the current query (lowercased,
    stripped). Empty string when nothing entered.
    """
    q = st.text_input(
        label,
        key=key,
        placeholder=placeholder,
        label_visibility="collapsed",
    )
    return (q or "").strip().lower()


def filter_rows(rows: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Case-insensitive filter: keep rows where ANY value contains `query`."""
    if not query:
        return rows
    q = query.lower()
    out = []
    for row in rows:
        for v in row.values():
            try:
                if q in str(v).lower():
                    out.append(row)
                    break
            except Exception:
                continue
    return out


# ---------------------------------------------------------------------------
# Decision expander — single decision rendered as a click-to-open block
# ---------------------------------------------------------------------------


def decision_expander(
    d: Decision,
    *,
    index: Optional[int] = None,
    open: bool = False,
    related_messages: Optional[list[Any]] = None,
) -> None:
    """One decision rendered as an expander with full input/output."""
    summary = _decision_summary(d)
    duration = f"{d.duration_ms} ms" if d.duration_ms is not None else "—"
    prefix = f"#{index} · " if index is not None else ""
    label = f"{prefix}{summary}  ·  {duration}"
    with st.expander(label, expanded=open):
        cols = st.columns(2)
        with cols[0]:
            st.markdown("**input**")
            st.json(d.input or {}, expanded=False)
        with cols[1]:
            st.markdown("**output**")
            st.json(d.output or {}, expanded=False)
        meta = {
            "step_id": d.step_id,
            "timestamp": d.timestamp,
            "parent_step_id": d.parent_step_id,
            "type": d.type.value,
        }
        if d.metadata:
            meta["metadata"] = d.metadata
        st.markdown("**metadata**")
        st.json(meta, expanded=False)
        if related_messages:
            st.markdown("**related messages**")
            for m in related_messages:
                st.markdown(f"- `{getattr(m, 'role', '?').value if hasattr(m, 'role') else '?'}`")


def decision_list(
    decisions: list[Decision],
    *,
    query: str = "",
    title: Optional[str] = None,
    show_index: bool = True,
    expand_first: bool = False,
) -> int:
    """Render a list of decisions as expanders. Returns the count rendered after
    filtering."""
    if title:
        st.markdown(f"#### {title}")
    if not decisions:
        st.caption("(no decisions)")
        return 0

    filtered = []
    for i, d in enumerate(decisions):
        if query:
            blob = json.dumps(
                {"step_id": d.step_id, "type": d.type.value, "input": d.input, "output": d.output},
                default=str,
            ).lower()
            if query not in blob:
                continue
        filtered.append((i, d))

    if not filtered:
        st.caption("(no decisions match the search)")
        return 0

    for ord_, (i, d) in enumerate(filtered):
        decision_expander(
            d,
            index=i if show_index else None,
            open=(ord_ == 0 and expand_first),
        )
    return len(filtered)


# ---------------------------------------------------------------------------
# Markdown export action — paired preview + download
# ---------------------------------------------------------------------------


def markdown_download(
    markdown: str,
    *,
    filename: str = "witness-export.md",
    label: str = "Download as markdown",
    key: str = "md_download",
    show_preview: bool = True,
) -> None:
    """Render a download button + optional code preview for a markdown blob."""
    st.download_button(
        label,
        data=markdown,
        file_name=filename,
        mime="text/markdown",
        key=key,
    )
    if show_preview:
        with st.expander("preview", expanded=False):
            st.code(markdown, language="markdown")


# ---------------------------------------------------------------------------
# Status panel for long-running ops
# ---------------------------------------------------------------------------


class StatusPanel:
    """Thin wrapper around ``st.status`` with sensible defaults.

    Use as a context manager::

        with StatusPanel("Running truncate(0.5)...") as status:
            status.write("step 1/3")
            ...
            status.complete("run finished — 4 decisions captured")
    """

    def __init__(self, label: str, *, expanded: bool = True) -> None:
        self._initial_label = label
        self._expanded = expanded
        self._status = None  # type: Optional[Any]

    def __enter__(self) -> "StatusPanel":
        self._status = st.status(self._initial_label, expanded=self._expanded)
        self._status.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None and self._status is not None:
            self._status.update(label=f"failed: {exc}", state="error")
        elif self._status is not None and not getattr(self, "_completed", False):
            # Auto-complete if caller forgot to.
            self._status.update(state="complete")
        if self._status is not None:
            self._status.__exit__(exc_type, exc, tb)

    def write(self, *args: Any, **kwargs: Any) -> None:
        if self._status is None:
            return
        self._status.write(*args, **kwargs)

    def update(self, *, label: Optional[str] = None, state: Optional[str] = None) -> None:
        if self._status is None:
            return
        kwargs: dict[str, Any] = {}
        if label is not None:
            kwargs["label"] = label
        if state is not None:
            kwargs["state"] = state
        self._status.update(**kwargs)

    def complete(self, label: Optional[str] = None) -> None:
        self._completed = True
        self.update(label=label, state="complete")

    def error(self, label: str) -> None:
        self._completed = True
        self.update(label=label, state="error")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decision_summary(d: Decision) -> str:
    if d.type == DecisionType.TOOL_CALL:
        name = d.input.get("name") or d.input.get("tool") or "?"
        return f"tool_call · {name}"
    if d.type == DecisionType.MODEL_CALL:
        m = d.input.get("model") or ""
        return f"model_call · {m}".rstrip(" ·")
    return d.type.value


__all__ = [
    "empty_state",
    "confirm_button",
    "search_input",
    "filter_rows",
    "decision_expander",
    "decision_list",
    "markdown_download",
    "StatusPanel",
]
