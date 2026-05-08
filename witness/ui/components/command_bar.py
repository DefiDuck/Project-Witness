"""⌘K command bar — fixed-position overlay with fuzzy command picker.

V1 commands (intentionally tight scope per brief):
- Open trace…       (fuzzy filename search; enter opens detail)
- Perturb current trace…   (only enabled when a trace is active)
- Diff…             (pick two traces)
- Go to settings

Streamlit doesn't ship a real command bar primitive. This component renders
a fixed-position overlay using raw HTML + a small Streamlit text input for
the query. Up/down navigation and Enter-to-execute are wired by mapping
the rendered results to anchor links (`?cmd=<id>&...`) — Streamlit reruns
on URL change and the page handles the action.

Triggering ⌘K itself requires JavaScript that Streamlit doesn't expose
natively. We register a hidden text-input wired to st.session_state via
the streamlit-shortcuts package (an opt-in dep). If unavailable, the bar
is reachable via the bottom-right hint button instead.
"""
from __future__ import annotations

from html import escape
from typing import Any, TypedDict

import streamlit as st


class _Command(TypedDict):
    id: str
    label: str
    hint: str  # right-aligned shortcut hint inside the row
    icon: str
    target_url: str  # where Enter / click should route to (relative URL)
    enabled: bool


# Lucide icons used inside the command rows
_ICONS: dict[str, str] = {
    "file-text": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
        '<polyline points="14 2 14 8 20 8"/></svg>'
    ),
    "git-compare": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="5" cy="6" r="3"/><path d="M12 6h5a2 2 0 0 1 2 2v7"/>'
        '<polyline points="15 9 19 5 23 9"/>'
        '<circle cx="19" cy="18" r="3"/><path d="M12 18H7a2 2 0 0 1-2-2V9"/>'
        '<polyline points="9 15 5 19 1 15"/></svg>'
    ),
    "split": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M8 3 4 7l4 4M4 7h16M16 21l4-4-4-4M20 17H4"/></svg>'
    ),
    "settings": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>'
        '</svg>'
    ),
}


def _all_commands(state: dict[str, Any]) -> list[_Command]:
    loaded = list((state.get("loaded_traces") or {}).keys())
    active = state.get("active_label")
    cmds: list[_Command] = []

    for label in loaded:
        cmds.append(
            {
                "id": f"open:{label}",
                "label": f"Open trace · {label}",
                "hint": "↵",
                "icon": "file-text",
                "target_url": f"?trace={label}",
                "enabled": True,
            }
        )

    cmds.append(
        {
            "id": "perturb",
            "label": "Perturb current trace…",
            "hint": "P",
            "icon": "git-compare",
            "target_url": (
                f"?trace={active}&action=perturb" if active else "#"
            ),
            "enabled": active is not None,
        }
    )
    cmds.append(
        {
            "id": "diff",
            "label": "Diff…",
            "hint": "D",
            "icon": "split",
            "target_url": "?nav=Diffs",
            "enabled": len(loaded) >= 2,
        }
    )
    cmds.append(
        {
            "id": "settings",
            "label": "Go to settings",
            "hint": ",",
            "icon": "settings",
            "target_url": "?nav=Settings",
            "enabled": True,
        }
    )

    return cmds


def _filter_commands(commands: list[_Command], q: str) -> list[_Command]:
    if not q:
        return commands[:8]  # max-8 rows per brief
    needle = q.lower()
    out: list[_Command] = []
    for c in commands:
        if needle in c["label"].lower() or needle in c["id"].lower():
            out.append(c)
        if len(out) >= 8:
            break
    return out


def render_command_bar(state: dict[str, Any]) -> None:
    """Render the ⌘K overlay if state['cmd_bar_open'] is True."""
    if not state.get("cmd_bar_open"):
        return

    q = st.session_state.get("cmd_bar_query", "") or ""
    commands = _filter_commands(_all_commands(state), q)

    # Render the overlay container (positioning is in CSS)
    rows_html = []
    for c in commands:
        opacity = "1" if c["enabled"] else "0.4"
        href = c["target_url"] if c["enabled"] else "#"
        rows_html.append(
            f'<a class="cb-row" href="{href}" style="opacity: {opacity};">'
            f'<span class="cb-row-icon">{_ICONS.get(c["icon"], "")}</span>'
            f'<span class="cb-row-label">{escape(c["label"])}</span>'
            f'<kbd class="cb-row-hint">{escape(c["hint"])}</kbd>'
            f'</a>'
        )
    if not rows_html:
        rows_html.append(
            '<div class="cb-empty">no matches</div>'
        )

    st.markdown(
        f'<div class="cb-overlay">'
        f'<div class="cb-panel">'
        f'<div class="cb-input-wrap">'
        # The actual input is rendered via st.text_input below; this <div>
        # is a placeholder for visual chrome. The input gets pulled into
        # the panel via CSS positioning trick below.
        f'</div>'
        f'<div class="cb-results">{"".join(rows_html)}</div>'
        f'</div>'
        f'<a class="cb-backdrop" href="?cmd_close=1" aria-label="Close"></a>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # The actual text-input. Renders elsewhere on the page but is visually
    # repositioned into the panel via CSS (.cb-floating-input).
    st.text_input(
        "Type a command…",
        placeholder="Type a command…",
        key="cmd_bar_query",
        label_visibility="collapsed",
    )


def open_command_bar(state: dict[str, Any]) -> None:
    state["cmd_bar_open"] = True


def close_command_bar(state: dict[str, Any]) -> None:
    state["cmd_bar_open"] = False
    st.session_state["cmd_bar_query"] = ""


__all__ = [
    "close_command_bar",
    "open_command_bar",
    "render_command_bar",
]
