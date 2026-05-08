"""Reusable UI components — composable building blocks for views."""

from witness.ui.components.empty_state import empty_state
from witness.ui.components.widgets import (
    StatusPanel,
    confirm_button,
    decision_expander,
    decision_list,
    filter_rows,
    markdown_download,
    search_input,
)

# Re-export the private helper used by the legacy components test. Marked
# private with an underscore so it doesn't clutter the public surface.
from witness.ui.components.widgets import _decision_summary  # noqa: F401

__all__ = [
    "empty_state",
    "StatusPanel",
    "confirm_button",
    "decision_expander",
    "decision_list",
    "filter_rows",
    "markdown_download",
    "search_input",
]
