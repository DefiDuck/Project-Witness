"""Trace-lineage SVG graph — the GitKraken-style branch view for traces.

Each loaded trace becomes one horizontal lane. Decisions render as colored
dots along the lane (color-coded by type). Perturbed traces visually branch
off from their parent baseline with a curved connector. Renders as inline
SVG via st.markdown — no external libraries.
"""
from __future__ import annotations

from html import escape
from typing import Optional

from witness.core.schema import DecisionType, Trace


# Palette — mirrors the witness/ui/theme.py CSS variables. Hardcoded as hex
# because CSS variables don't always inherit reliably into inline SVG fills.
_BG = "#101010"
_BORDER = "#222"
_BORDER_2 = "#2a2a2a"
_FG = "#fafafa"
_FG_DIM = "#888"
_FG_FAINT = "#555"
_ACCENT = "#e8a951"
_ADD = "#3ec286"
_DEL = "#e36876"


_DOT_COLOR = {
    DecisionType.MODEL_CALL.value: _FG_DIM,
    DecisionType.TOOL_CALL.value: _ACCENT,
    DecisionType.TOOL_RESULT.value: _ACCENT,
    DecisionType.REASONING.value: _FG_FAINT,
    DecisionType.FINAL_OUTPUT.value: _ADD,
    DecisionType.CUSTOM.value: _FG_DIM,
}


def render_lineage_svg(
    traces: dict[str, Trace],
    *,
    active_label: Optional[str] = None,
    width: int = 880,
    lane_height: int = 36,
) -> str:
    """Render a horizontal trace-lineage SVG. Returns ``""`` if no traces."""
    if not traces:
        return ""

    ordered = _order_lanes(traces)
    n_lanes = len(ordered)
    if n_lanes == 0:
        return ""

    # Layout
    label_w = 180
    duration_w = 70
    plot_pad = 18
    plot_x0 = label_w + plot_pad
    plot_x1 = width - duration_w - plot_pad
    plot_w = plot_x1 - plot_x0
    height = 24 + n_lanes * lane_height + 16

    # x-scale: equal spacing across the longest trace
    max_dec = max((len(t.decisions) for _, t, _ in ordered), default=1)
    if max_dec < 2:
        dx = 0.0
    else:
        dx = plot_w / (max_dec - 1)

    # Lane y position (centered in lane row)
    def lane_y(i: int) -> int:
        return 24 + i * lane_height + lane_height // 2

    parts: list[str] = []
    parts.append(
        f'<svg width="100%" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="trace lineage">'
    )
    # Background card
    parts.append(
        f'<rect x="0" y="0" width="{width}" height="{height}" '
        f'fill="{_BG}" stroke="{_BORDER}" rx="6"/>'
    )

    # Top-axis tick line (just a faint horizontal at the top of the plot)
    parts.append(
        f'<line x1="{plot_x0}" y1="14" x2="{plot_x1}" y2="14" '
        f'stroke="{_BORDER}" stroke-width="1" stroke-dasharray="2,3"/>'
    )
    parts.append(
        f'<text x="{plot_x0}" y="10" fill="{_FG_FAINT}" '
        f'font-family="ui-monospace, JetBrains Mono, monospace" font-size="9" '
        f'text-transform="uppercase" letter-spacing="0.06em">decision sequence</text>'
    )

    # Branch curves — drawn under the dots so they don't cover them
    label_to_idx = {label: i for i, (label, _, _) in enumerate(ordered)}
    for i, (label, trace, parent_label) in enumerate(ordered):
        if not parent_label:
            continue
        parent_i = label_to_idx.get(parent_label)
        if parent_i is None:
            continue
        py = lane_y(parent_i)
        cy = lane_y(i)
        # Curve from the very start of the parent lane to the very start of
        # this lane — looks like a branch pulling away from the trunk.
        cx_start = plot_x0 - 6
        cx_mid = plot_x0 - 16
        path = (
            f'M {cx_start} {py} '
            f'C {cx_mid} {py}, {cx_mid} {cy}, {cx_start} {cy}'
        )
        parts.append(
            f'<path d="{path}" stroke="{_ACCENT}" stroke-width="1.5" '
            f'fill="none" opacity="0.55"/>'
        )

    # Lanes
    for i, (label, trace, parent_label) in enumerate(ordered):
        y = lane_y(i)
        is_active = label == active_label

        # Active-lane background highlight (full row strip)
        if is_active:
            parts.append(
                f'<rect x="2" y="{y - lane_height // 2 + 2}" '
                f'width="{width - 4}" height="{lane_height - 4}" '
                f'fill="{_FG}" opacity="0.04" rx="3"/>'
            )

        # Trace label
        kind_chip = ""
        if parent_label is not None:
            kind_chip = (
                f'<tspan fill="{_ACCENT}" font-size="9" '
                f'dx="6">●</tspan>'
            )
        # Truncate long labels so they don't overrun the plot
        display = label[:24] + "…" if len(label) > 24 else label
        label_color = _FG if is_active else _FG_DIM
        parts.append(
            f'<text x="14" y="{y + 4}" fill="{label_color}" '
            f'font-family="ui-monospace, JetBrains Mono, monospace" '
            f'font-size="11.5" font-weight="{500 if is_active else 400}">'
            f'{escape(display)}{kind_chip}</text>'
        )

        # Sequence connector line (only if 2+ decisions)
        n_dec = len(trace.decisions)
        if n_dec >= 2:
            x_end = plot_x0 + dx * (n_dec - 1)
            parts.append(
                f'<line x1="{plot_x0}" y1="{y}" x2="{x_end:.1f}" y2="{y}" '
                f'stroke="{_BORDER_2}" stroke-width="1"/>'
            )

        # Decision dots
        for k, dec in enumerate(trace.decisions):
            cx = plot_x0 + dx * k
            color = _DOT_COLOR.get(dec.type.value, _FG_DIM)
            parts.append(
                f'<circle cx="{cx:.1f}" cy="{y}" r="4.5" fill="{color}" '
                f'stroke="{_BG}" stroke-width="1.5">'
                f'<title>#{k} {dec.type.value} · {_short_summary(dec)}</title>'
                f"</circle>"
            )

        # Right-side metadata: wall time + decision count
        wall = trace.wall_time_ms or 0
        wall_str = f"{wall} ms" if wall < 1000 else f"{wall / 1000:.2f}s"
        parts.append(
            f'<text x="{plot_x1 + 8}" y="{y - 2}" fill="{_FG_DIM}" '
            f'font-family="ui-monospace, JetBrains Mono, monospace" '
            f'font-size="10.5">{n_dec} dec</text>'
        )
        parts.append(
            f'<text x="{plot_x1 + 8}" y="{y + 11}" fill="{_FG_FAINT}" '
            f'font-family="ui-monospace, JetBrains Mono, monospace" '
            f'font-size="10">{escape(wall_str)}</text>'
        )

    # Legend at the very bottom
    legend_y = height - 6
    legend_items = [
        (_DOT_COLOR[DecisionType.MODEL_CALL.value], "model_call"),
        (_DOT_COLOR[DecisionType.TOOL_CALL.value], "tool_call"),
        (_DOT_COLOR[DecisionType.FINAL_OUTPUT.value], "final_output"),
    ]
    legend_x = plot_x0
    for color, name in legend_items:
        parts.append(
            f'<circle cx="{legend_x}" cy="{legend_y}" r="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{legend_x + 8}" y="{legend_y + 3}" fill="{_FG_FAINT}" '
            f'font-family="ui-monospace, JetBrains Mono, monospace" '
            f'font-size="9.5">{name}</text>'
        )
        legend_x += 110

    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Lane ordering
# ---------------------------------------------------------------------------


def _order_lanes(traces: dict[str, Trace]):
    """Order: each baseline followed by its perturbed children, then orphans.

    Returns list of (label, trace, parent_label_or_None).
    """
    items = list(traces.items())
    by_run_id = {t.run_id: lbl for lbl, t in items}

    baselines = [(lbl, t) for lbl, t in items if not t.perturbation]
    perturbed = [(lbl, t) for lbl, t in items if t.perturbation]

    ordered: list[tuple[str, Trace, Optional[str]]] = []
    used: set[str] = set()
    for blbl, btr in baselines:
        ordered.append((blbl, btr, None))
        used.add(blbl)
        for plbl, ptr in perturbed:
            if ptr.parent_run_id == btr.run_id and plbl not in used:
                ordered.append((plbl, ptr, blbl))
                used.add(plbl)

    # Orphan perturbed traces (parent not loaded) — show them separately
    for plbl, ptr in perturbed:
        if plbl in used:
            continue
        parent_lbl = (
            by_run_id.get(ptr.parent_run_id) if ptr.parent_run_id else None
        )
        ordered.append((plbl, ptr, parent_lbl))
        used.add(plbl)

    return ordered


def _short_summary(d) -> str:
    if d.type == DecisionType.TOOL_CALL:
        name = d.input.get("name") or d.input.get("tool") or "?"
        return f"tool_call · {name}"
    if d.type == DecisionType.MODEL_CALL:
        m = d.input.get("model") or ""
        return f"model_call · {m}".rstrip(" ·")
    return d.type.value


__all__ = ["render_lineage_svg"]
