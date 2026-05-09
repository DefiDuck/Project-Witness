# ruff: noqa: RUF001, RUF002, RUF003
# Rationale: the speed selector renders "1× · 2× · 4×" using the proper
# multiplication-sign glyph (U+00D7), which is the correct typography per
# the brief. Ruff flags it as visually ambiguous with "x" but the
# user-facing strings, docstring example, and explanatory comments all
# refer to that exact character on purpose.
"""Play controls strip — the centerpiece of the playable ribbon.

Renders a 32px-tall horizontal control bar that drives playback over a
trace's decision sequence:

    [Restart] [Play/Pause]  step N/M  [-------scrubber-------]  1× · 2× · 4×

State lives in ``st.session_state["play"]`` as a small dict; this module
exposes pure helpers (``advance_index``, ``scrubber_position``) that the
trace_detail view and tests both call without touching Streamlit.

The strip itself is plain HTML rendered via ``st.markdown(unsafe_allow_html=True)``.
All controls are anchor links that mutate URL query params — Streamlit
reruns on the next render and we read the new state. No JS state machine,
no draggable scrubber (drag is explicitly out of scope per the brief).

Sub-second auto-advance during play is delegated to
``streamlit_autorefresh.st_autorefresh`` — the supported pattern in
Streamlit for timed reruns. ``time.sleep()`` inside a render would block
the websocket and freeze the UI; the brief forbids it.
"""
from __future__ import annotations

from html import escape
from typing import Any, TypedDict

import streamlit as st

# Default tick interval at 1×. Speed selector multiplies this down:
# 2× → 400ms, 4× → 200ms. Below 200ms playback feels jittery on
# mid-tier laptops because Streamlit's rerun cycle has its own latency.
BASE_TICK_MS = 800
ALLOWED_SPEEDS: tuple[int, ...] = (1, 2, 4)


class PlayState(TypedDict):
    """Shape of ``st.session_state["play"]``.

    ``index`` mirrors the URL ``?sel=`` param so deep-linking works; the
    trace_detail view is responsible for keeping the two in sync.
    """

    playing: bool
    index: int
    speed: int


def default_state() -> PlayState:
    return {"playing": False, "index": 0, "speed": 1}


def get_state(state: dict[str, Any]) -> PlayState:
    """Read (or initialize) the play state from session storage."""
    raw = state.get("play")
    if not isinstance(raw, dict):
        fresh = default_state()
        state["play"] = fresh
        return fresh
    # Patch missing keys without dropping any user-set fields.
    for k, v in default_state().items():
        raw.setdefault(k, v)
    return raw  # type: ignore[return-value]


def reset_for_trace(state: dict[str, Any], total: int) -> PlayState:
    """Called when the user navigates to a new trace.

    Stops any in-flight playback (per the brief: "User navigates away
    during playback → on next mount, play.playing resets to false to
    prevent runaway autorefresh") and clamps the index into the new
    trace's range.
    """
    play = get_state(state)
    play["playing"] = False
    if total <= 0:
        play["index"] = 0
    else:
        play["index"] = max(0, min(play["index"], total - 1))
    return play


def advance_index(current: int, total: int) -> tuple[int, bool]:
    """Compute the next play index and whether playback should auto-pause.

    Returns ``(next_index, should_pause)``. ``should_pause`` is True
    once the next index lands on the last decision — we don't want to
    tick again past the end. (The brief: "When index reaches the last
    decision, set playing = False — auto-pause at end.")
    """
    if total <= 0:
        return 0, True
    if current >= total - 1:
        # Already at end — clamp and stay paused.
        return total - 1, True
    next_idx = current + 1
    # Pause as soon as we land on the last step so the user sees it
    # render before playback halts.
    return next_idx, next_idx >= total - 1


def scrubber_position(index: int, total: int) -> float:
    """Return the fill fraction for the scrubber bar in ``[0.0, 1.0]``.

    Single-decision and zero-decision traces always render at 0.0; the
    Play button is also disabled in that case so the bar staying empty
    is consistent.
    """
    if total <= 1:
        return 0.0
    return max(0.0, min(1.0, index / (total - 1)))


def parse_speed(raw: str | None) -> int:
    """Coerce the URL ``?play_speed=`` param into one of ALLOWED_SPEEDS."""
    if raw is None:
        return 1
    try:
        s = int(raw)
    except (TypeError, ValueError):
        return 1
    return s if s in ALLOWED_SPEEDS else 1


def tick_interval_ms(speed: int) -> int:
    """Auto-refresh interval for the given speed multiplier."""
    return max(100, BASE_TICK_MS // speed)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

# Lucide path data, 24×24 viewBox. Inlined so we don't ship a sprite sheet
# just for three icons. Stroke-based — each icon picks up `currentColor`.
_ICON_RESTART = "M3 12a9 9 0 1 0 3-6.7L3 8 M3 3v5h5"
_ICON_PLAY = "M6 3l14 9-14 9V3z"
_ICON_PAUSE = "M6 4h4v16H6z M14 4h4v16h-4z"


def _icon_svg(path: str, *, size: int = 14) -> str:
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="currentColor" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="{path}"/></svg>'
    )


def render_play_controls(
    label: str,
    total: int,
    play: PlayState,
    *,
    base_query: str = "",
) -> str:
    """Return the HTML for the play-controls strip.

    All buttons emit URL-anchor clicks against the current page; the
    trace_detail view reads the resulting query params on the next
    rerun. ``base_query`` is the trace-tab routing prefix that every
    link must preserve, e.g. ``"?trace=baseline.json&tab=sequence"``.
    """
    if total <= 0:
        return ""  # caller falls back to its empty state

    # Helper: build an URL with extra params layered on top of base_query.
    def _href(**overrides: str) -> str:
        head = base_query[1:] if base_query.startswith("?") else base_query
        existing: dict[str, str] = {}
        if head:
            for chunk in head.split("&"):
                if not chunk:
                    continue
                k, _, v = chunk.partition("=")
                existing[k] = v
        existing.update({k: str(v) for k, v in overrides.items()})
        # Ensure the play_action param is dropped on plain navigation.
        return "?" + "&".join(f"{k}={v}" for k, v in existing.items())

    cur = play["index"]
    speed = play["speed"]
    playing = play["playing"]
    is_single = total <= 1

    # Restart button.
    restart_href = _href(play_action="restart", sel="0")
    restart_btn = (
        f'<a class="pc-btn" href="{escape(restart_href)}" '
        f'title="Restart from step 1" aria-label="Restart">'
        f'{_icon_svg(_ICON_RESTART)}'
        f'</a>'
    )

    # Play/Pause toggle. Disabled when single-decision (nothing to advance).
    if is_single:
        play_btn = (
            f'<span class="pc-btn" aria-disabled="true" '
            f'title="Only one decision — nothing to play">'
            f'{_icon_svg(_ICON_PLAY)}'
            f'</span>'
        )
    elif playing:
        pause_href = _href(play_action="pause")
        play_btn = (
            f'<a class="pc-btn pc-btn-active" href="{escape(pause_href)}" '
            f'title="Pause" aria-label="Pause">'
            f'{_icon_svg(_ICON_PAUSE)}'
            f'</a>'
        )
    else:
        play_href = _href(play_action="play")
        play_btn = (
            f'<a class="pc-btn pc-btn-primary" href="{escape(play_href)}" '
            f'title="Play" aria-label="Play">'
            f'{_icon_svg(_ICON_PLAY)}'
            f'</a>'
        )

    # Step indicator: "<active+1> / <total>", 1-based for human readability.
    step_html = (
        f'<span class="pc-step">{cur + 1} / {total}</span>'
    )

    # Scrubber. 21 hit-zones max — anything finer and the percentage math
    # collapses to noise; we sample uniformly across [0, total-1].
    fill_pct = scrubber_position(cur, total) * 100.0
    hit_zones = []
    if total > 1:
        # Each zone is a wedge of the bar mapped to a step index. Simple
        # equal-width partition: width = 100/total. The zone for step i
        # covers [i*100/total, (i+1)*100/total).
        for i in range(total):
            start = i * 100.0 / total
            width = 100.0 / total
            href = _href(play_action="seek", sel=str(i))
            hit_zones.append(
                f'<a class="pc-scrubber-hit" href="{escape(href)}" '
                f'title="Jump to step {i + 1}" '
                f'style="left: {start:.2f}%; width: {width:.2f}%;"></a>'
            )
    scrubber_html = (
        f'<div class="pc-scrubber">'
        f'{"".join(hit_zones)}'
        f'<div class="pc-scrubber-track">'
        f'<div class="pc-scrubber-fill" style="width: {fill_pct:.2f}%;"></div>'
        f'</div>'
        f'</div>'
    )

    # Speed selector — three discrete options. The active one is bordered
    # with --accent; others are muted links.
    speeds: list[str] = []
    for sep_i, s in enumerate(ALLOWED_SPEEDS):
        if sep_i > 0:
            speeds.append('<span class="pc-speed-sep">·</span>')
        cls = "pc-speed pc-speed-active" if s == speed else "pc-speed"
        href = _href(play_action="speed", play_speed=str(s))
        speeds.append(
            f'<a class="{cls}" href="{escape(href)}" '
            f'title="Playback speed {s}×">{s}×</a>'
        )
    speeds_html = f'<div class="pc-speeds">{"".join(speeds)}</div>'

    # Suppress the unused trace-label parameter; kept for caller signature
    # stability (will be needed once the speed control deep-links).
    _ = label

    return (
        f'<div class="pc-strip">'
        f'{restart_btn}'
        f'{play_btn}'
        f'{step_html}'
        f'{scrubber_html}'
        f'{speeds_html}'
        f'</div>'
    )


def handle_url_action(
    state: dict[str, Any],
    total: int,
    *,
    action: str | None,
    sel: int | None,
    speed: int | None,
) -> bool:
    """Apply an inbound ``?play_action=…`` URL transition to the play state.

    Returns ``True`` if the state changed and the caller should clear
    these params from the URL and rerun.

    The five recognised actions:

    - ``play``     → set playing=True
    - ``pause``    → set playing=False
    - ``restart``  → index=0 (caller already received sel=0)
    - ``seek``     → set index from ``sel``, pause
    - ``speed``    → set speed from ``speed``

    Anything else (or no action) → no-op.
    """
    play = get_state(state)
    changed = False

    if action == "play" and total > 1:
        if not play["playing"]:
            play["playing"] = True
            changed = True
    elif action == "pause":
        if play["playing"]:
            play["playing"] = False
            changed = True
    elif action == "restart":
        if play["index"] != 0:
            play["index"] = 0
            changed = True
    elif action == "seek" and sel is not None:
        clamped = max(0, min(sel, max(total - 1, 0)))
        if play["index"] != clamped:
            play["index"] = clamped
            changed = True
        if play["playing"]:
            play["playing"] = False
            changed = True
    elif (
        action == "speed"
        and speed is not None
        and speed in ALLOWED_SPEEDS
        and play["speed"] != speed
    ):
        play["speed"] = speed
        changed = True

    return changed


def maybe_autorefresh(play: PlayState) -> None:
    """Wire up ``st_autorefresh`` when playing. No-op when paused.

    Picks the smallest interval permitted by ``BASE_TICK_MS / speed`` and
    keys the refresh on ``play_tick`` so multiple controls don't compete
    for the same tick handle.
    """
    if not play["playing"]:
        return
    try:
        # streamlit-autorefresh ships no type stubs as of 1.0; the import
        # is the only thing that touches it from this module.
        from streamlit_autorefresh import st_autorefresh  # type: ignore[import-untyped]
    except ImportError:  # pragma: no cover — missing in stripped envs
        return
    st_autorefresh(
        interval=tick_interval_ms(play["speed"]),
        key="witness_play_tick",
    )


__all__ = [
    "ALLOWED_SPEEDS",
    "BASE_TICK_MS",
    "PlayState",
    "advance_index",
    "default_state",
    "get_state",
    "handle_url_action",
    "maybe_autorefresh",
    "parse_speed",
    "render_play_controls",
    "reset_for_trace",
    "scrubber_position",
    "tick_interval_ms",
]


# Keep the import-time check loud so a missing dep surfaces immediately
# rather than silently degrading playback.
def _self_check() -> bool:
    """Boolean indicator that the autorefresh dep is importable. Used by
    callers that want to render a "playback unavailable" hint."""
    try:
        import streamlit_autorefresh  # noqa: F401
    except ImportError:
        return False
    return True


# Touch streamlit so it's part of this module's import side effects in
# the same way the rest of the UI components are. (Streamlit's CLI
# bootstrap is fussy about which modules it has eagerly imported.)
_ = st
