"""Flow ribbon — Witness's signature trace visualization.

A horizontal ribbon of connected nodes, one per decision. Each node is a
clean rounded rectangle with one visual signal — a 2px colored accent bar
at the top, painted in the decision-type's color — and one textual signal
— the full type label, mono caps. No icons. No glyphs. No ornament.

Pure SVG, server-rendered, click via plain anchor href — no JS.

Two public renderers:

- ``render_flow_ribbon(label, decisions, *, selected, diff)``
    Single ribbon for the Sequence tab on a trace detail.

- ``render_diff_ribbons(label_a, label_b, pairs, *, selected_a, selected_b)``
    Two stacked ribbons with connection lines + diff annotations for the
    Diffs page hero view.
"""
from __future__ import annotations

import math
from html import escape
from itertools import pairwise

from witness.core.schema import Decision, DecisionType
from witness.diff.behavioral import DecisionChange

# Type → color mapping. Used by the accent bar and the active-state border.
# Defining here keeps the diff and detail views in lockstep on color.
TYPE_COLOR: dict[str, str] = {
    DecisionType.MODEL_CALL.value:   "var(--accent)",      # amber
    DecisionType.TOOL_CALL.value:    "#58A6FF",            # blue
    DecisionType.TOOL_RESULT.value:  "#3FB950",            # green
    DecisionType.REASONING.value:    "var(--fg-muted)",    # gray
    DecisionType.FINAL_OUTPUT.value: "#BC8CFF",            # purple
    DecisionType.CUSTOM.value:       "var(--fg-faint)",
}


# ---------------------------------------------------------------------------
# Layout constants — single source of truth so tests can assert on them
# ---------------------------------------------------------------------------

LEFT_PAD = 12
RIGHT_PAD = 12
NODE_HEIGHT = 28
NODE_GAP = 8
TOP_PAD = 14            # leaves headroom above the node for hover lift
RIBBON_HEIGHT = 96
DURATION_LABEL_OFFSET = 14   # below node baseline
NODE_RADIUS = 6
ACCENT_HEIGHT = 2

# Label width math. Mono at 11px is ~7.2px per char in JetBrains Mono /
# ui-monospace. The 24px padding (12px each side) is what gives the label
# breathing room inside the node.
LABEL_CHAR_PX = 7.2
LABEL_HORIZONTAL_PAD = 24
NODE_MIN_WIDTH = 56     # ghost stubs need room even when no label

# Animation timings — kept here so theme.py keyframes and Python delays
# stay in sync.
ENTER_STAGGER_MS = 40
ENTER_DURATION_MS = 200
EDGE_DELAY_MS = 100


def width_for_duration(duration_ms: int | None) -> float:
    """Log-scaled width hint for a single decision's duration.

    Returns the duration-only width (without the label-min). Callers use
    this as one half of ``_node_width`` for nodes that have a duration,
    and use 80px as the uniform fallback when no duration is available.
    The log scale surfaces slow decisions visually without letting a
    12-second LLM call hijack the entire viewport.
    """
    if duration_ms is None:
        return 80.0
    ms = max(1, int(duration_ms))
    return max(48.0, min(200.0, math.log(ms) * 16))


def _label_width(type_value: str) -> float:
    """Pixel width of the full uppercase type label at 11px mono."""
    return len(type_value.upper()) * LABEL_CHAR_PX + LABEL_HORIZONTAL_PAD


def _node_width(d: Decision | None, *, hide_duration: bool) -> float:
    """Auto-width: ``max(label_width, log_duration_width)``.

    The label-floor guarantees no truncation (FINAL_OUTPUT and TOOL_RESULT
    are the long ones at 12 and 11 chars). Above that floor, slow
    decisions get visually wider via the log curve.
    """
    if d is None:
        return NODE_MIN_WIDTH
    label_w = _label_width(d.type.value)
    if hide_duration:
        return max(label_w, NODE_MIN_WIDTH)
    return max(label_w, width_for_duration(d.duration_ms), NODE_MIN_WIDTH)


# ---------------------------------------------------------------------------
# Single ribbon
# ---------------------------------------------------------------------------


def render_flow_ribbon(
    label: str,
    decisions: list[Decision],
    *,
    selected: int = 0,
    diff: dict[int, str] | None = None,
    play_index: int | None = None,
    inline_click: bool = False,
) -> str:
    """Render the trace's decision sequence as a horizontal flow ribbon.

    Returns an SVG string ready to inject via ``st.markdown(unsafe_allow_html=True)``.
    Pure function — no Streamlit calls. Empty decisions → empty string;
    callers should render the canonical empty state instead.

    Parameters
    ----------
    selected:
        Index of the manually-selected node (gets the ring + halo).
    diff:
        Maps decision index → ``"added" | "removed" | "changed"`` for
        overlay annotations. Only used when comparing two traces; the
        trace detail Sequence tab passes ``None``.
    play_index:
        When playback is active, the node at this index gets an
        additional ``flow-node-play-active`` class so CSS can layer an
        amber outer glow on top of the normal selection ring. Pass
        ``None`` to disable the playback overlay.
    inline_click:
        When ``True`` (the diff page), node anchors emit
        ``?expand=<i>`` so the click stays on the diff page and triggers
        the inline expansion card. When ``False`` (the trace detail
        page), node anchors emit
        ``?trace=<label>&tab=sequence&sel=<i>`` so the click navigates
        within the trace.
    """
    if not decisions:
        return ""

    diff = diff or {}
    all_none = all(d.duration_ms is None for d in decisions)

    # Compute x positions.
    x = float(LEFT_PAD)
    positions: list[tuple[float, float]] = []
    for d in decisions:
        w = _node_width(d, hide_duration=all_none)
        positions.append((x, w))
        x += w + NODE_GAP
    total_width = max(int(x + RIGHT_PAD), 320)

    parts: list[str] = []
    parts.append(_svg_open(total_width, RIBBON_HEIGHT, classes="flow-ribbon"))
    parts.append(_defs())
    parts.extend(
        _render_edges(positions, len(decisions), y=TOP_PAD + NODE_HEIGHT / 2)
    )
    for i, d in enumerate(decisions):
        parts.append(
            _render_node(
                d,
                i,
                positions[i],
                label=label,
                selected=(i == selected),
                diff_kind=diff.get(i),
                hide_duration=all_none,
                play_active=(play_index is not None and i == play_index),
                inline_click=inline_click,
            )
        )
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Stacked diff ribbons (baseline + perturbed)
# ---------------------------------------------------------------------------


def render_diff_ribbons(
    label_a: str,
    label_b: str,
    pairs: list[DecisionChange],
    *,
    selected_a: int = -1,
    selected_b: int = -1,
    expanded_slot: int | None = None,
    inline_click: bool = True,
) -> str:
    """Render baseline and perturbed flow ribbons stacked, with connection
    lines for matched pairs and ghost stubs for added/removed.

    ``pairs`` is the alignment list from ``TraceDiff.alignment.pairs``. We
    walk it in order so the two ribbons stay visually aligned: matched
    pairs occupy the same horizontal slot in both ribbons; added/removed
    leave a gap on the corresponding side.
    """
    if not pairs:
        return ""

    # Collect per-side decisions and their alignment-slot index, plus
    # diff-kind annotations keyed by side+index.
    a_decisions: list[Decision | None] = []
    b_decisions: list[Decision | None] = []
    a_kinds: dict[int, str] = {}
    b_kinds: dict[int, str] = {}

    for slot, ch in enumerate(pairs):
        a_decisions.append(ch.baseline)
        b_decisions.append(ch.perturbed)
        if ch.kind == "removed" and ch.baseline is not None:
            a_kinds[slot] = "removed"
        elif ch.kind == "added" and ch.perturbed is not None:
            b_kinds[slot] = "added"
        elif ch.kind in ("input_changed", "output_changed", "both_changed", "type_changed"):
            if ch.baseline is not None:
                a_kinds[slot] = "changed"
            if ch.perturbed is not None:
                b_kinds[slot] = "changed"
        # 'same' → no annotation

    # Compute per-slot widths: max of the two sides at that slot so the
    # ribbons stay column-aligned. If a side has no decision, use the
    # other side's width.
    use_uniform = all(
        (d is None) or d.duration_ms is None
        for d in (*a_decisions, *b_decisions)
    )
    slot_widths: list[float] = []
    for a_d, b_d in zip(a_decisions, b_decisions, strict=True):
        wa = _node_width(a_d, hide_duration=use_uniform) if a_d else 0.0
        wb = _node_width(b_d, hide_duration=use_uniform) if b_d else 0.0
        slot_widths.append(max(wa, wb, NODE_MIN_WIDTH))

    # Compute slot x positions (shared across both ribbons).
    x = float(LEFT_PAD)
    slot_positions: list[float] = []
    for w in slot_widths:
        slot_positions.append(x)
        x += w + NODE_GAP
    total_width = max(int(x + RIGHT_PAD), 320)

    # Layout: 2 ribbons + connection band between them.
    a_y = 0
    band_h = 30
    b_y = RIBBON_HEIGHT + band_h
    height = b_y + RIBBON_HEIGHT

    parts: list[str] = []
    parts.append(_svg_open(total_width, height, classes="flow-diff-ribbons"))
    parts.append(_defs())

    # Side labels (left margin).
    parts.append(
        f'<text x="{LEFT_PAD}" y="10" font-family="ui-monospace, monospace" '
        f'font-size="9" font-weight="600" fill="var(--fg-faint)" '
        f'letter-spacing="0.06em">BASELINE</text>'
    )
    parts.append(
        f'<text x="{LEFT_PAD}" y="{b_y + 10}" font-family="ui-monospace, monospace" '
        f'font-size="9" font-weight="600" fill="var(--fg-faint)" '
        f'letter-spacing="0.06em">PERTURBED</text>'
    )

    # Connection lines + ghost stubs.
    parts.append('<g class="flow-conns">')
    for slot, ch in enumerate(pairs):
        ax = slot_positions[slot] + slot_widths[slot] / 2
        ay = a_y + TOP_PAD + NODE_HEIGHT  # bottom of baseline node
        by = b_y + TOP_PAD                # top of perturbed node
        if ch.baseline is not None and ch.perturbed is not None:
            # Matched (same or changed) → faint vertical line.
            stroke = "var(--warn)" if ch.kind != "same" else "var(--border)"
            opacity = "0.6" if ch.kind != "same" else "0.4"
            parts.append(
                f'<line x1="{ax}" y1="{ay}" x2="{ax}" y2="{by}" '
                f'stroke="{stroke}" stroke-width="1" opacity="{opacity}" '
                f'stroke-dasharray="{"4 3" if ch.kind != "same" else ""}"/>'
            )
        elif ch.baseline is not None and ch.perturbed is None:
            # Removed: dashed stub from baseline going down to a ghost dot.
            ghost_y = b_y + TOP_PAD + NODE_HEIGHT / 2
            parts.append(
                f'<line x1="{ax}" y1="{ay}" x2="{ax}" y2="{ghost_y}" '
                f'stroke="var(--err)" stroke-width="1" opacity="0.4" '
                f'stroke-dasharray="3 3"/>'
            )
            parts.append(
                f'<circle cx="{ax}" cy="{ghost_y}" r="2.5" '
                f'fill="none" stroke="var(--err)" stroke-width="1" '
                f'opacity="0.6"/>'
            )
        elif ch.baseline is None and ch.perturbed is not None:
            # Added: dashed stub up from perturbed to a ghost dot in the
            # baseline lane.
            ghost_y = a_y + TOP_PAD + NODE_HEIGHT / 2
            parts.append(
                f'<line x1="{ax}" y1="{ghost_y}" x2="{ax}" y2="{by}" '
                f'stroke="var(--ok)" stroke-width="1" opacity="0.4" '
                f'stroke-dasharray="3 3"/>'
            )
            parts.append(
                f'<circle cx="{ax}" cy="{ghost_y}" r="2.5" '
                f'fill="none" stroke="var(--ok)" stroke-width="1" '
                f'opacity="0.6"/>'
            )
    parts.append('</g>')

    # Per-side edges (arrow chains) — only between adjacent existing nodes.
    parts.append('<g class="flow-edges">')
    parts.extend(
        _render_aligned_edges(
            a_decisions, slot_positions, slot_widths,
            y=a_y + TOP_PAD + NODE_HEIGHT / 2,
        )
    )
    parts.extend(
        _render_aligned_edges(
            b_decisions, slot_positions, slot_widths,
            y=b_y + TOP_PAD + NODE_HEIGHT / 2,
        )
    )
    parts.append('</g>')

    # When a slot is expanded on the diff view, both the baseline and
    # perturbed nodes at that slot get the selection ring so the user
    # sees the pair that the expansion card is showing.
    sel_a_effective = (
        expanded_slot if expanded_slot is not None else selected_a
    )
    sel_b_effective = (
        expanded_slot if expanded_slot is not None else selected_b
    )

    # Baseline ribbon nodes.
    for slot, d_a in enumerate(a_decisions):
        if d_a is None:
            continue
        x_pos = slot_positions[slot]
        w = _node_width(d_a, hide_duration=use_uniform)
        parts.append(
            _render_node(
                d_a,
                slot,
                (x_pos, w),
                label=label_a,
                selected=(slot == sel_a_effective),
                diff_kind=a_kinds.get(slot),
                hide_duration=use_uniform,
                y_offset=a_y,
                href_tab="diffs",
                inline_click=inline_click,
            )
        )

    # Perturbed ribbon nodes.
    for slot, d_b in enumerate(b_decisions):
        if d_b is None:
            continue
        x_pos = slot_positions[slot]
        w = _node_width(d_b, hide_duration=use_uniform)
        parts.append(
            _render_node(
                d_b,
                slot,
                (x_pos, w),
                label=label_b,
                selected=(slot == sel_b_effective),
                diff_kind=b_kinds.get(slot),
                hide_duration=use_uniform,
                y_offset=b_y,
                href_tab="diffs",
                inline_click=inline_click,
            )
        )

    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Internal SVG helpers
# ---------------------------------------------------------------------------


def _svg_open(width: int, height: int, *, classes: str) -> str:
    return (
        f'<svg class="{classes}" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink">'
    )


def _defs() -> str:
    """Just the arrow marker — no icon symbols. Premium dev tools don't put
    pictographic content inside data primitives."""
    return (
        '<defs>'
        '<marker id="flow-arrow" viewBox="0 0 10 10" refX="8" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto">'
        '<path d="M 0 1 L 8 5 L 0 9" fill="none" stroke="var(--border)" '
        'stroke-width="1" stroke-linecap="round"/>'
        '</marker>'
        '</defs>'
    )


def _render_edges(
    positions: list[tuple[float, float]], n: int, *, y: float
) -> list[str]:
    parts: list[str] = []
    for i, (cur, nxt) in enumerate(pairwise(positions)):
        x_end = cur[0] + cur[1]
        x_next = nxt[0]
        delay = i * ENTER_STAGGER_MS + ENTER_DURATION_MS + EDGE_DELAY_MS
        length = x_next - x_end
        parts.append(
            f'<line class="flow-edge" x1="{x_end}" y1="{y}" '
            f'x2="{x_next}" y2="{y}" '
            f'stroke="var(--border)" stroke-width="1" '
            f'marker-end="url(#flow-arrow)" '
            f'stroke-dasharray="{length:.2f}" '
            f'stroke-dashoffset="{length:.2f}" '
            f'style="animation-delay: {delay}ms"/>'
        )
    # Silence the unused n parameter (kept for caller signature stability).
    _ = n
    return parts


def _render_aligned_edges(
    decisions: list[Decision | None],
    slot_positions: list[float],
    slot_widths: list[float],
    *,
    y: float,
) -> list[str]:
    """Edges between consecutive existing decisions on the same row,
    skipping over slots where the decision is None on this side."""
    parts: list[str] = []
    prev_idx: int | None = None
    edge_i = 0
    for i, d in enumerate(decisions):
        if d is None:
            continue
        if prev_idx is not None:
            x_end = slot_positions[prev_idx] + slot_widths[prev_idx]
            x_next = slot_positions[i]
            length = x_next - x_end
            delay = edge_i * ENTER_STAGGER_MS + ENTER_DURATION_MS + EDGE_DELAY_MS
            parts.append(
                f'<line class="flow-edge" x1="{x_end}" y1="{y}" '
                f'x2="{x_next}" y2="{y}" '
                f'stroke="var(--border)" stroke-width="1" '
                f'marker-end="url(#flow-arrow)" '
                f'stroke-dasharray="{length:.2f}" '
                f'stroke-dashoffset="{length:.2f}" '
                f'style="animation-delay: {delay}ms"/>'
            )
            edge_i += 1
        prev_idx = i
    return parts


def _accent_path(x: float, y: float, w: float, color: str) -> str:
    """A 2px-tall colored bar at the top of a rounded node, conforming to
    the parent's rx=6 corner curves.

    Geometry: the parent's top-left corner is a quarter-circle of radius
    ``NODE_RADIUS`` centered at ``(x+rx, y+rx)``. The accent's bottom-left
    corner sits where that circle crosses ``y = ACCENT_HEIGHT`` — namely
    ``x = rx - sqrt(rx² - (rx - h)²)``. The path then arcs along the
    parent's corner up to the top edge, runs across, and arcs down the
    right corner. This way the accent fills exactly the strip of the
    parent rect at ``y in [0, h]`` with no overflow.
    """
    rx = NODE_RADIUS
    h = ACCENT_HEIGHT
    inset = rx - math.sqrt(rx * rx - (rx - h) * (rx - h))
    return (
        f'<path class="flow-accent" d="'
        f'M {x + inset:.2f},{y + h:.2f} '
        f'A {rx},{rx} 0 0 1 {x + rx:.2f},{y:.2f} '
        f'L {x + w - rx:.2f},{y:.2f} '
        f'A {rx},{rx} 0 0 1 {x + w - inset:.2f},{y + h:.2f} '
        f'Z" fill="{color}"/>'
    )


def _render_node(
    d: Decision,
    i: int,
    pos: tuple[float, float],
    *,
    label: str,
    selected: bool,
    diff_kind: str | None,
    hide_duration: bool,
    y_offset: float = 0.0,
    href_tab: str = "sequence",
    play_active: bool = False,
    inline_click: bool = False,
) -> str:
    x_n, w_n = pos
    color = TYPE_COLOR.get(d.type.value, "var(--fg-muted)")

    # Border treatment. Default 1px var(--border); 1px type-color when
    # active (the brief explicitly calls for 1px, not 2 — the active
    # signal is the colored ring + the halo, not weight). Diff overlays
    # take precedence over the selected color: in the diff view the
    # add/remove/change status is the primary signal, the selected halo
    # is supplementary.
    border_color = "var(--border)"
    border_width = "1"
    opacity = "1"
    glyph = ""

    # Selected wins over default border, but diff overlays win over selected.
    if selected:
        border_color = color  # 1px ring in the type's color

    if diff_kind == "removed":
        border_color = "var(--err)"
        opacity = "0.5"
    elif diff_kind == "added":
        border_color = "var(--ok)"
        glyph = (
            f'<text x="{x_n + w_n - 6}" y="{y_offset + TOP_PAD + 11}" '
            f'font-family="ui-monospace, monospace" font-size="10" '
            f'font-weight="700" fill="var(--ok)" text-anchor="end" '
            f'class="flow-diff-glyph">+</text>'
        )
    elif diff_kind == "changed":
        border_color = "var(--warn)"
        glyph = (
            f'<text x="{x_n + w_n - 6}" y="{y_offset + TOP_PAD + 11}" '
            f'font-family="ui-monospace, monospace" font-size="10" '
            f'font-weight="700" fill="var(--warn)" text-anchor="end" '
            f'class="flow-diff-glyph">~</text>'
        )

    # Glow halo for active node — sits behind the rect.
    halo = ""
    if selected:
        halo = (
            f'<rect class="flow-halo" '
            f'x="{x_n - 3}" y="{y_offset + TOP_PAD - 5}" '
            f'width="{w_n + 6}" height="{NODE_HEIGHT + 6}" rx="9" '
            f'fill="{color}" opacity="0.15"/>'
        )

    node_y = y_offset + TOP_PAD - (2 if selected else 0)

    # Full type label, centered. No truncation — width was sized to fit.
    label_text = d.type.value.upper()
    text_x = x_n + w_n / 2
    text_y = node_y + NODE_HEIGHT / 2 + 4

    # URL contract:
    # - inline_click=False (trace detail Sequence tab): clicking navigates
    #   to that decision via ?trace=<label>&tab=sequence&sel=<i>.
    # - inline_click=True (diff page): clicking opens the inline expansion
    #   card via ?expand=<i>; we deliberately do NOT navigate to a trace.
    href = (
        f"?expand={i}"
        if inline_click
        else f"?trace={escape(label)}&tab={href_tab}&sel={i}"
    )
    duration_text = ""
    if not hide_duration:
        dur = _format_duration(d.duration_ms)
        duration_text = (
            f'<text x="{x_n + w_n / 2}" '
            f'y="{y_offset + TOP_PAD + NODE_HEIGHT + DURATION_LABEL_OFFSET}" '
            f'font-family="ui-monospace, monospace" font-size="10" '
            f'fill="var(--fg-faint)" text-anchor="middle">{escape(dur)}</text>'
        )

    delay = i * ENTER_STAGGER_MS

    accent_y = node_y
    accent = _accent_path(x_n, accent_y, w_n, color)

    classes = ["flow-node"]
    if selected:
        classes.append("flow-node-active")
    if play_active:
        classes.append("flow-node-play-active")

    return (
        f'<a href="{href}" xlink:href="{href}" id="node-{i}" '
        f'class="flow-node-link">'
        f'<g class="{" ".join(classes)}" '
        f'opacity="{opacity}" '
        f'style="animation-delay: {delay}ms">'
        f'{halo}'
        f'<rect class="flow-node-body" '
        f'x="{x_n}" y="{node_y}" width="{w_n}" height="{NODE_HEIGHT}" '
        f'rx="{NODE_RADIUS}" fill="var(--bg-raised)" '
        f'stroke="{border_color}" stroke-width="{border_width}"/>'
        f'{accent}'
        f'<text x="{text_x}" y="{text_y}" '
        f'font-family="ui-monospace, JetBrains Mono, monospace" '
        f'font-size="11" font-weight="600" fill="var(--fg)" '
        f'letter-spacing="0.06em" text-anchor="middle">{escape(label_text)}</text>'
        f'{glyph}'
        f'</g></a>'
        f'{duration_text}'
    )


def _format_duration(ms: int | None) -> str:
    if ms is None:
        return "—"
    if ms < 1000:
        return f"{ms}ms"
    return f"{ms / 1000:.1f}s"


__all__ = [
    "NODE_HEIGHT",
    "RIBBON_HEIGHT",
    "TYPE_COLOR",
    "render_diff_ribbons",
    "render_flow_ribbon",
    "width_for_duration",
]
