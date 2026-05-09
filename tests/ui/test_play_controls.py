
# ruff: noqa: RUF003
"""Tests for ``witness.ui.components.play_controls``.

The play controls strip is mostly pure HTML + a small state machine. We
test the state machine (advance_index / scrubber_position / handle_url_action)
directly and the strip's HTML by inspecting the returned string. Streamlit
itself isn't booted — the helpers don't touch ``st.session_state`` outside
the dict the tests pass in.
"""
from __future__ import annotations

import pytest

from witness.ui.components.play_controls import (
    ALLOWED_SPEEDS,
    advance_index,
    default_state,
    get_state,
    handle_url_action,
    parse_speed,
    render_play_controls,
    reset_for_trace,
    scrubber_position,
    tick_interval_ms,
)

# ---------------------------------------------------------------------------
# advance_index — the single-step transition
# ---------------------------------------------------------------------------


def test_advance_index_normal() -> None:
    assert advance_index(0, 5) == (1, False)
    assert advance_index(3, 5) == (4, True)  # last step → auto-pause
    assert advance_index(4, 5) == (4, True)  # already at end


def test_advance_index_zero_total_pauses() -> None:
    assert advance_index(0, 0) == (0, True)


def test_advance_index_single_step_pauses_immediately() -> None:
    # total=1: nothing to advance to, must auto-pause
    assert advance_index(0, 1) == (0, True)


# ---------------------------------------------------------------------------
# scrubber_position — fill fraction in [0, 1]
# ---------------------------------------------------------------------------


def test_scrubber_position_endpoints() -> None:
    assert scrubber_position(0, 5) == 0.0
    assert scrubber_position(4, 5) == 1.0


def test_scrubber_position_midpoint() -> None:
    # 5 steps: index 2 → 2/4 = 0.5
    assert scrubber_position(2, 5) == 0.5


def test_scrubber_position_single_step_traces() -> None:
    # No progress to show on a 1-step trace; bar stays empty.
    assert scrubber_position(0, 1) == 0.0
    assert scrubber_position(0, 0) == 0.0


def test_scrubber_position_clamps_out_of_range() -> None:
    # Defensive: out-of-range index doesn't go negative or above 1.0.
    assert scrubber_position(-3, 5) == 0.0
    assert scrubber_position(99, 5) == 1.0


# ---------------------------------------------------------------------------
# parse_speed + tick_interval_ms
# ---------------------------------------------------------------------------


def test_parse_speed_known_values() -> None:
    assert parse_speed("1") == 1
    assert parse_speed("2") == 2
    assert parse_speed("4") == 4


def test_parse_speed_unknown_falls_back() -> None:
    assert parse_speed(None) == 1
    assert parse_speed("") == 1
    assert parse_speed("abc") == 1
    assert parse_speed("3") == 1  # not in ALLOWED_SPEEDS
    assert parse_speed("8") == 1


def test_tick_interval_halves_per_doubling() -> None:
    assert tick_interval_ms(1) == 800
    assert tick_interval_ms(2) == 400
    assert tick_interval_ms(4) == 200


def test_allowed_speeds_constant() -> None:
    # Guard against silent expansion of the speed selector — the brief
    # explicitly limits it to 1×/2×/4×.
    assert ALLOWED_SPEEDS == (1, 2, 4)


# ---------------------------------------------------------------------------
# get_state / default_state / reset_for_trace
# ---------------------------------------------------------------------------


def test_get_state_initializes_when_missing() -> None:
    state: dict[str, object] = {}
    play = get_state(state)
    assert play == default_state()
    # And the dict is mutable / shared with session.
    play["index"] = 3
    assert state["play"]["index"] == 3


def test_get_state_patches_missing_keys() -> None:
    state: dict[str, object] = {"play": {"playing": True}}
    play = get_state(state)
    assert play["playing"] is True  # preserved
    assert play["index"] == 0       # patched
    assert play["speed"] == 1       # patched


def test_reset_for_trace_clamps_and_pauses() -> None:
    state: dict[str, object] = {"play": {"playing": True, "index": 99, "speed": 2}}
    play = reset_for_trace(state, total=5)
    assert play["playing"] is False  # navigation kills runaway autorefresh
    assert play["index"] == 4         # clamped to total-1
    assert play["speed"] == 2         # speed preserved across navigation


def test_reset_for_trace_zero_total_zeros_index() -> None:
    state: dict[str, object] = {"play": {"playing": True, "index": 5, "speed": 1}}
    play = reset_for_trace(state, total=0)
    assert play["playing"] is False
    assert play["index"] == 0


# ---------------------------------------------------------------------------
# handle_url_action — the URL-action transitions
# ---------------------------------------------------------------------------


def test_handle_play_starts() -> None:
    state: dict[str, object] = {}
    changed = handle_url_action(state, total=5, action="play", sel=None, speed=None)
    assert changed is True
    assert get_state(state)["playing"] is True


def test_handle_play_noop_when_already_playing() -> None:
    state: dict[str, object] = {"play": {"playing": True, "index": 0, "speed": 1}}
    changed = handle_url_action(state, total=5, action="play", sel=None, speed=None)
    assert changed is False


def test_handle_play_blocked_on_single_decision() -> None:
    """Single-decision traces have no playback — the brief: Play button
    disabled, state ``1 / 1``. handle_url_action must respect that."""
    state: dict[str, object] = {}
    changed = handle_url_action(state, total=1, action="play", sel=None, speed=None)
    assert changed is False
    assert get_state(state)["playing"] is False


def test_handle_pause_stops() -> None:
    state: dict[str, object] = {"play": {"playing": True, "index": 2, "speed": 1}}
    changed = handle_url_action(state, total=5, action="pause", sel=None, speed=None)
    assert changed is True
    assert get_state(state)["playing"] is False


def test_handle_seek_jumps_and_pauses() -> None:
    """Mid-playback click on the scrubber jumps + pauses."""
    state: dict[str, object] = {"play": {"playing": True, "index": 0, "speed": 1}}
    changed = handle_url_action(state, total=10, action="seek", sel=4, speed=None)
    assert changed is True
    play = get_state(state)
    assert play["index"] == 4
    assert play["playing"] is False


def test_handle_seek_clamps_oob_index() -> None:
    state: dict[str, object] = {}
    handle_url_action(state, total=5, action="seek", sel=99, speed=None)
    assert get_state(state)["index"] == 4
    handle_url_action(state, total=5, action="seek", sel=-3, speed=None)
    assert get_state(state)["index"] == 0


def test_handle_restart_resets_index_only() -> None:
    """Restart goes to step 0 but doesn't change playing/paused state."""
    state: dict[str, object] = {"play": {"playing": True, "index": 7, "speed": 1}}
    changed = handle_url_action(state, total=10, action="restart", sel=None, speed=None)
    assert changed is True
    play = get_state(state)
    assert play["index"] == 0
    assert play["playing"] is True  # preserved


def test_handle_speed_updates() -> None:
    state: dict[str, object] = {}
    changed = handle_url_action(state, total=5, action="speed", sel=None, speed=2)
    assert changed is True
    assert get_state(state)["speed"] == 2


def test_handle_speed_rejects_unknown_value() -> None:
    state: dict[str, object] = {}
    handle_url_action(state, total=5, action="speed", sel=None, speed=3)
    assert get_state(state)["speed"] == 1  # unchanged from default


def test_handle_unknown_action_is_noop() -> None:
    state: dict[str, object] = {}
    assert handle_url_action(state, 5, action="hyperdrive", sel=None, speed=None) is False
    assert handle_url_action(state, 5, action=None, sel=None, speed=None) is False


# ---------------------------------------------------------------------------
# render_play_controls — HTML invariants
# ---------------------------------------------------------------------------


def test_render_returns_empty_for_zero_decisions() -> None:
    """Zero-decision traces fall back to the empty state — the strip
    must not render at all."""
    play = default_state()
    assert render_play_controls("base", 0, play) == ""


def test_render_strip_has_all_controls() -> None:
    play = {"playing": False, "index": 0, "speed": 1}
    html = render_play_controls("base", 5, play, base_query="?trace=base&tab=sequence")
    # Restart, Play, Step indicator, Scrubber, Speed pills
    assert "pc-strip" in html
    assert "pc-btn" in html
    assert "play_action=restart" in html
    assert "play_action=play" in html
    assert "1 / 5" in html
    assert "pc-scrubber" in html
    assert "pc-speeds" in html
    # Speed selector all three values present
    assert "play_speed=1" in html
    assert "play_speed=2" in html
    assert "play_speed=4" in html


def test_render_play_button_swaps_to_pause_when_playing() -> None:
    play = {"playing": True, "index": 1, "speed": 1}
    html = render_play_controls("base", 5, play)
    # When playing the Play button becomes Pause and uses the active class.
    assert "play_action=pause" in html
    assert "pc-btn-active" in html
    assert "play_action=play" not in html


def test_render_step_indicator_is_one_based() -> None:
    """``index=2`` → ``3 / 5``, not ``2 / 5`` — humans count from 1."""
    play = {"playing": False, "index": 2, "speed": 1}
    html = render_play_controls("base", 5, play)
    assert "3 / 5" in html


def test_render_active_speed_has_active_class() -> None:
    play = {"playing": False, "index": 0, "speed": 2}
    html = render_play_controls("base", 5, play)
    # Hrefs are HTML-escaped in the rendered string; ``&`` becomes ``&amp;``.
    assert (
        'class="pc-speed pc-speed-active" '
        'href="?play_action=speed&amp;play_speed=2"' in html
    )
    # And 1× / 4× are NOT active.
    assert (
        'class="pc-speed" href="?play_action=speed&amp;play_speed=1"' in html
    )
    assert (
        'class="pc-speed" href="?play_action=speed&amp;play_speed=4"' in html
    )


def test_render_single_decision_disables_play() -> None:
    play = default_state()
    html = render_play_controls("base", 1, play)
    assert 'aria-disabled="true"' in html
    assert "1 / 1" in html


def test_render_scrubber_fill_matches_scrubber_position() -> None:
    """Visual scrubber width must match scrubber_position(index, total) * 100."""
    play = {"playing": False, "index": 2, "speed": 1}
    html = render_play_controls("base", 5, play)
    # 2/4 = 50%
    assert 'width: 50.00%;' in html


def test_render_scrubber_emits_one_hit_per_step() -> None:
    """Click-to-jump zones should partition the bar evenly."""
    play = default_state()
    html = render_play_controls("base", 5, play)
    assert html.count('class="pc-scrubber-hit"') == 5


def test_render_preserves_base_query() -> None:
    """Buttons must navigate within the same trace+tab — not bounce the
    user back to the trace list."""
    play = default_state()
    html = render_play_controls(
        "base.json", 3, play, base_query="?trace=base.json&tab=sequence"
    )
    assert "trace=base.json" in html
    assert "tab=sequence" in html


# ---------------------------------------------------------------------------
# parse-speed property: every URL value round-trips cleanly
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("speed", [1, 2, 4])
def test_speed_round_trip(speed: int) -> None:
    assert parse_speed(str(speed)) == speed
    assert tick_interval_ms(speed) > 0
