"""Single empty-state pattern, used everywhere.

Vertical+horizontal centered: 16px lucide icon (--fg-faint), 13px message
(--fg-muted), 12px mono hint with an inline kbd-styled shortcut (--fg-faint).
No card, no border, no button — drag-and-drop and keyboard shortcuts
are the implicit recovery paths.

Usage:
    from witness.ui.components import empty_state
    empty_state(
        icon="inbox",
        message="No traces yet.",
        hint="Drop a .jsonl file or press ⌘O.",
    )
"""
from __future__ import annotations

from html import escape

import streamlit as st


# ---------------------------------------------------------------------------
# Lucide SVG icon set (16px, stroke-width 1.5, currentColor) used in empty
# states. Add icons here as new empty states need them; do not inline SVG
# at the call site.
# ---------------------------------------------------------------------------

_ICONS: dict[str, str] = {
    "inbox": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/>'
        '<path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11Z"/>'
        '</svg>'
    ),
    "git-compare": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="5" cy="6" r="3"/><path d="M12 6h5a2 2 0 0 1 2 2v7"/>'
        '<polyline points="15 9 19 5 23 9"/>'
        '<circle cx="19" cy="18" r="3"/><path d="M12 18H7a2 2 0 0 1-2-2V9"/>'
        '<polyline points="9 15 5 19 1 15"/>'
        '</svg>'
    ),
    "list-tree": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M21 12h-8M21 6H8M21 18h-8M3 6v12a2 2 0 0 0 2 2h3"/>'
        '<path d="M3 6h0M3 12h5"/>'
        '</svg>'
    ),
    "activity": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>'
        '</svg>'
    ),
    "message-square": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>'
        '</svg>'
    ),
}


def empty_state(icon: str, message: str, hint: str) -> None:
    """Render the canonical empty state.

    Parameters
    ----------
    icon:
        Lucide icon name. Must be one of the keys in ``_ICONS`` — extending
        the set is intentional, so adding an icon is a deliberate edit here.
    message:
        Single sentence, no period stripping — write it like a sentence:
        ``"No traces yet."``.
    hint:
        Recovery hint with a keyboard shortcut wrapped in ``<kbd>``.
        e.g. ``"Drop a .jsonl file or press <kbd>⌘O</kbd>."``
        Renderer trusts this string — caller is responsible for the kbd.
    """
    svg = _ICONS.get(icon)
    if svg is None:
        # Fail loudly; we'd rather see this in dev than render a broken UI.
        raise KeyError(f"empty_state: unknown icon {icon!r} (have: {sorted(_ICONS)})")

    st.markdown(
        f'<div class="es-wrap">'
        f'<div class="es-icon">{svg}</div>'
        f'<div class="es-message">{escape(message)}</div>'
        f'<div class="es-hint">{hint}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


__all__ = ["empty_state"]
