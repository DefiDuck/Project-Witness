"""Reusable UI components — composable building blocks for views."""

from witness.ui.components.empty_state import empty_state
from witness.ui.components.play_controls import (
    PlayState,
    advance_index,
    handle_url_action,
    maybe_autorefresh,
    render_play_controls,
    reset_for_trace,
    scrubber_position,
)

# Re-export the private helper used by the legacy components test. Marked
# private with an underscore so it doesn't clutter the public surface.
from witness.ui.components.widgets import (
    StatusPanel,
    _decision_summary,  # noqa: F401
    confirm_button,
    decision_expander,
    decision_list,
    filter_rows,
    markdown_download,
    search_input,
)

__all__ = [
    "PlayState",
    "StatusPanel",
    "advance_index",
    "confirm_button",
    "decision_expander",
    "decision_list",
    "empty_state",
    "filter_rows",
    "handle_url_action",
    "markdown_download",
    "maybe_autorefresh",
    "render_play_controls",
    "reset_for_trace",
    "scrubber_position",
    "search_input",
]
