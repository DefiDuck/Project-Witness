"""Witness UI theme — design tokens, typography, and component CSS.

Mirrors the design handoff at design-pkg/project-witness/project/Witness.html.
Colors / spacing / type scale lifted directly from the prototype's :root vars.

The CSS is injected into the Streamlit page via ``st.markdown(unsafe_allow_html=True)``
in ``app.py``. Streamlit primitives that we can theme via .streamlit/config.toml
already match the palette; this module handles everything Streamlit doesn't expose
as a config knob (typography, custom component classes, layout overrides).
"""
from __future__ import annotations

THEME_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" />

<style>
:root {
    /* dark — default */
    --bg:        #0a0a0a;
    --bg-1:      #101010;
    --bg-2:      #161616;
    --bg-3:      #1c1c1c;
    --border:    #222;
    --border-2:  #2a2a2a;
    --fg:        #fafafa;
    --fg-dim:    #888;
    --fg-faint:  #555;
    --fg-faintest: #3a3a3a;
    --accent:    #e8a951;          /* desaturated amber */
    --accent-ink:#0a0a0a;
    --add:       #3ec286;
    --del:       #e36876;
    --add-bg:    rgba(62,194,134,0.10);
    --del-bg:    rgba(227,104,118,0.10);
    --hover:     rgba(255,255,255,0.025);
    --selected:  rgba(255,255,255,0.04);

    --sans: 'Inter', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif;
    --mono: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;

    --radius: 4px;
    --radius-lg: 6px;
    --row-h: 32px;
}

/* -- Streamlit globals --------------------------------------------------- */

html, body, [class*="st-"], .stApp, .main, .block-container, p, span, div, label {
    font-family: var(--sans) !important;
}
html, body, .stApp {
    background: var(--bg) !important;
    color: var(--fg) !important;
    font-size: 13px !important;
}
.block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 2rem !important;
    max-width: none !important;
}
header[data-testid="stHeader"] { background: transparent !important; height: 0 !important; }
[data-testid="stToolbar"] { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }

/* Sidebar — match the design's 240px bg-1 panel */
[data-testid="stSidebar"] {
    background: var(--bg-1) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
    padding: 14px 14px 12px 16px !important;
}
[data-testid="stSidebar"] hr { border-color: var(--border) !important; margin: 14px 0 !important; }
[data-testid="stSidebar"] h1 { font-weight: 600 !important; font-size: 15px !important; letter-spacing: -0.01em !important; margin: 0 !important; }

/* Sidebar nav: target the radio so it looks like nav buttons */
[data-testid="stSidebar"] [role="radiogroup"] { gap: 2px !important; }
[data-testid="stSidebar"] [role="radiogroup"] label {
    height: 28px !important;
    padding: 0 8px !important;
    border-radius: var(--radius) !important;
    color: var(--fg-dim) !important;
    background: transparent !important;
    cursor: pointer !important;
    transition: background 80ms linear !important;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover { background: var(--hover) !important; }
[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) {
    color: var(--fg) !important;
    background: var(--selected) !important;
}
[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child { display: none !important; }
[data-testid="stSidebar"] [role="radiogroup"] label > div { font-size: 12.5px !important; }

/* -- Buttons ------------------------------------------------------------- */

.stButton > button, .stDownloadButton > button {
    height: 28px !important;
    padding: 0 10px !important;
    border: 1px solid var(--border-2) !important;
    background: var(--bg-2) !important;
    border-radius: var(--radius) !important;
    color: var(--fg) !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    transition: background 80ms linear, border-color 80ms linear !important;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    background: var(--bg-3) !important;
    border-color: var(--fg-faintest) !important;
}
.stButton > button[kind="primary"], .stButton > button[data-testid="baseButton-primary"] {
    background: var(--accent) !important;
    color: var(--accent-ink) !important;
    border-color: var(--accent) !important;
    font-weight: 600 !important;
}

/* -- Inputs / selects / textareas --------------------------------------- */

.stTextInput input, .stTextArea textarea, .stNumberInput input, .stSelectbox > div[data-baseweb="select"] > div {
    background: var(--bg-2) !important;
    border: 1px solid var(--border) !important;
    color: var(--fg) !important;
    font-family: var(--mono) !important;
    font-size: 12px !important;
    border-radius: var(--radius) !important;
}
.stTextInput input:focus, .stTextArea textarea:focus { border-color: var(--fg-faint) !important; }
.stSelectbox label, .stTextInput label, .stTextArea label, .stNumberInput label, .stSlider label {
    font-family: var(--mono) !important;
    font-size: 10.5px !important;
    color: var(--fg-faint) !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    font-weight: 400 !important;
}

/* -- Slider ------------------------------------------------------------- */

.stSlider > div > div > div > div { background: var(--accent) !important; }
.stSlider [role="slider"] {
    background: var(--accent) !important;
    border-color: var(--accent) !important;
}

/* -- File uploader ------------------------------------------------------ */

[data-testid="stFileUploader"] section {
    background: var(--bg-1) !important;
    border: 1px dashed var(--border-2) !important;
    border-radius: var(--radius-lg) !important;
    padding: 24px !important;
}
[data-testid="stFileUploader"] section button {
    background: var(--bg-2) !important;
    color: var(--fg) !important;
    border: 1px solid var(--border-2) !important;
}

/* -- Tabs --------------------------------------------------------------- */

[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 0 !important;
    border-bottom: 1px solid var(--border) !important;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    height: 36px !important;
    padding: 0 14px !important;
    background: transparent !important;
    color: var(--fg-dim) !important;
    border-bottom: 2px solid transparent !important;
    font-size: 12px !important;
    font-family: var(--mono) !important;
}
[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
    color: var(--fg) !important;
    border-bottom-color: var(--accent) !important;
}

/* -- Expanders --------------------------------------------------------- */

[data-testid="stExpander"] {
    background: var(--bg-1) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
}
[data-testid="stExpander"] summary {
    font-family: var(--mono) !important;
    font-size: 12px !important;
    color: var(--fg) !important;
}

/* -- Status / Toast / Spinner -------------------------------------------- */

[data-testid="stStatus"] {
    background: var(--bg-1) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-lg) !important;
}

/* -- Dataframe --------------------------------------------------------- */

[data-testid="stDataFrame"] {
    background: var(--bg-1) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
}

/* -- Code / pre / json -------------------------------------------------- */

pre, code, .stCode {
    background: var(--bg-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    font-family: var(--mono) !important;
    font-size: 11.5px !important;
    color: var(--fg) !important;
}

/* -- Headers ------------------------------------------------------------ */

h1 { font-size: 22px !important; font-weight: 600 !important; letter-spacing: -0.01em !important; color: var(--fg) !important; }
h2 { font-size: 16px !important; font-weight: 500 !important; letter-spacing: -0.01em !important; color: var(--fg) !important; }
h3 { font-size: 14px !important; font-weight: 500 !important; letter-spacing: -0.005em !important; color: var(--fg) !important; }
h4 { font-size: 12.5px !important; font-weight: 500 !important; color: var(--fg) !important; }

/* -- Custom scrollbar -------------------------------------------------- */

*::-webkit-scrollbar { width: 8px; height: 8px; }
*::-webkit-scrollbar-track { background: transparent; }
*::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 4px; }
*::-webkit-scrollbar-thumb:hover { background: var(--fg-faint); }

::selection { background: var(--accent); color: var(--accent-ink); }

/* -- Witness component classes (used in custom HTML markup) ----------- */

.mono { font-family: var(--mono) !important; font-feature-settings: 'zero', 'cv01'; }
.dim  { color: var(--fg-dim) !important; }
.faint{ color: var(--fg-faint) !important; }
.dim2 { color: var(--fg-faintest) !important; }

.uppercase-label {
    font-family: var(--mono);
    font-size: 10.5px;
    color: var(--fg-faint);
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

/* status dots */
.dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; vertical-align: middle; }
.dot-accent { background: var(--accent); }
.dot-add    { background: var(--add); }
.dot-del    { background: var(--del); }
.dot-dim    { background: var(--fg-faint); }

/* chip — small pill-style label */
.chip {
    display: inline-flex; align-items: center; gap: 6px;
    height: 20px; padding: 0 8px;
    border: 1px solid var(--border);
    border-radius: 3px;
    font-family: var(--mono);
    font-size: 10.5px;
    color: var(--fg-dim);
    background: transparent;
    line-height: 1;
}
.chip-accent { border-color: var(--accent); color: var(--accent); }
.chip-add { border-color: var(--add); color: var(--add); }
.chip-del { border-color: var(--del); color: var(--del); }

/* witness-stat — large number stat block (used on Diff hero / Fingerprint headline) */
.witness-stat {
    padding: 14px 20px;
    border-right: 1px solid var(--border);
}
.witness-stat:last-child { border-right: 0; }
.witness-stat .label {
    font-family: var(--mono);
    font-size: 10.5px;
    color: var(--fg-faint);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 6px;
}
.witness-stat .value {
    font-family: var(--mono);
    font-size: 28px;
    font-weight: 500;
    color: var(--fg);
    letter-spacing: -0.02em;
    line-height: 1.1;
    display: inline-block;
}
.witness-stat .value.del { color: var(--del); }
.witness-stat .value.add { color: var(--add); }
.witness-stat .of {
    font-family: var(--mono);
    font-size: 12px;
    color: var(--fg-faint);
    margin-left: 4px;
}
.witness-stat .sub {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--fg-faint);
    margin-top: 4px;
}
.witness-stat .sub.del { color: var(--del); }
.witness-stat .sub.add { color: var(--add); }

/* witness-stat-row — horizontal grid of stats (used on Diff and Fingerprint) */
.witness-stat-row {
    display: grid;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    background: var(--bg);
}

/* witness-kv — dashed-bottom KV row (used in inspector panels) */
.witness-kv {
    display: flex; justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px dashed var(--border);
}
.witness-kv .k {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--fg-faint);
}
.witness-kv .v {
    font-family: var(--mono);
    font-size: 11.5px;
    color: var(--fg);
}
.witness-kv .v.accent { color: var(--accent); }

/* witness-section — numbered section header (01/02/03 on Perturb) */
.witness-section {
    display: flex; align-items: baseline; gap: 10px;
    margin-bottom: 12px;
}
.witness-section .n {
    font-family: var(--mono);
    font-size: 10.5px;
    color: var(--fg-faint);
}
.witness-section .title {
    font-size: 12.5px;
    font-weight: 500;
    color: var(--fg);
}

/* witness-bar — horizontal stability bar */
.witness-bar-row {
    display: grid;
    grid-template-columns: 220px 1fr 70px 90px;
    gap: 16px;
    padding: 12px 18px;
    align-items: center;
    border-bottom: 1px solid var(--border);
}
.witness-bar-row:last-child { border-bottom: 0; }
.witness-bar-row .name {
    font-family: var(--mono);
    font-size: 11.5px;
    color: var(--fg);
}
.witness-bar-row .pct {
    font-family: var(--mono);
    font-size: 13px;
    font-weight: 500;
    text-align: right;
    color: var(--fg);
}
.witness-bar-row .delta {
    font-family: var(--mono);
    font-size: 11px;
    text-align: right;
    color: var(--fg-faint);
}
.witness-bar-row .delta.del { color: var(--del); }
.witness-bar-row .delta.add { color: var(--add); }

.witness-bar {
    position: relative;
    height: 18px;
}
.witness-bar .track {
    position: absolute;
    left: 0; top: 50%;
    transform: translateY(-50%);
    height: 8px; width: 100%;
    background: var(--bg-3);
    border-radius: 1px;
}
.witness-bar .fill {
    position: absolute;
    left: 0; top: 50%;
    transform: translateY(-50%);
    height: 8px;
    border-radius: 1px;
    transition: width 240ms ease;
}
.witness-bar .fill.low  { background: var(--del); }
.witness-bar .fill.mid  { background: var(--accent); }
.witness-bar .fill.high { background: var(--add); }

/* container / panel utility */
.witness-panel {
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 0;
    overflow: hidden;
}

/* witness-empty — designed empty-state card */
.witness-empty {
    text-align: center;
    padding: 64px 24px;
    background: var(--bg-1);
    border: 1px dashed var(--border-2);
    border-radius: var(--radius-lg);
    margin: 24px 0;
}
.witness-empty .title {
    font-size: 14px;
    font-weight: 500;
    color: var(--fg);
    margin-bottom: 8px;
}
.witness-empty .desc {
    font-family: var(--mono);
    font-size: 11.5px;
    color: var(--fg-faint);
}

/* -- Animations --------------------------------------------------------- */

@keyframes fadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
.fade-in { animation: fadeIn 160ms ease-out; }

@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.pulse { animation: pulse 1.4s ease-in-out infinite; }

@keyframes blink { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0; } }
.caret { animation: blink 1s steps(1) infinite; }

/* -- File-browser style row layout (used on Load page) ------------------ */

.witness-table-header {
    display: grid;
    grid-template-columns: 1fr 140px 90px 160px 90px 110px;
    gap: 16px;
    padding: 8px 20px;
    border-bottom: 1px solid var(--border);
    font-family: var(--mono);
    font-size: 10.5px;
    color: var(--fg-faint);
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.witness-table-row {
    display: grid;
    grid-template-columns: 1fr 140px 90px 160px 90px 110px;
    gap: 16px;
    padding: 0 20px;
    height: 36px;
    align-items: center;
    border-left: 2px solid transparent;
    border-bottom: 1px solid var(--bg-1);
}
.witness-table-row.selected { border-left-color: var(--accent); background: var(--selected); }
.witness-table-row .filename { font-family: var(--mono); font-size: 12px; color: var(--fg); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.witness-table-row .agent { font-size: 12px; color: var(--fg-dim); }
.witness-table-row .num { font-family: var(--mono); font-size: 11.5px; color: var(--fg-dim); text-align: right; }
.witness-table-row .meta { font-family: var(--mono); font-size: 11.5px; color: var(--fg-faint); text-align: right; }

/* -- Diff-specific: side-by-side timeline rows -------------------------- */

.witness-diff-row {
    height: 32px;
    padding: 0 16px;
    display: grid;
    grid-template-columns: 8px 60px 90px 1fr;
    gap: 10px;
    align-items: center;
    border-bottom: 1px solid var(--bg-1);
}
.witness-diff-row.changed.baseline-side { background: var(--del-bg); }
.witness-diff-row.changed.perturbed-side { background: var(--add-bg); }
.witness-diff-row .t { font-family: var(--mono); font-size: 10.5px; color: var(--fg-faint); }
.witness-diff-row .type { font-family: var(--mono); font-size: 10.5px; color: var(--fg-dim); }
.witness-diff-row .summary { font-family: var(--mono); font-size: 11.5px; color: var(--fg); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.witness-diff-placeholder {
    height: 32px;
    padding: 0 16px;
    display: flex; align-items: center;
    background: repeating-linear-gradient(45deg, transparent, transparent 6px, var(--bg-1) 6px, var(--bg-1) 7px);
    border-bottom: 1px solid var(--bg-1);
    font-family: var(--mono);
    font-size: 10.5px;
    color: var(--fg-faint);
}

/* -- Inspect-specific: vertical sequence line + decision rows ----------- */

.witness-sequence {
    position: relative;
    padding-left: 32px;
}
.witness-sequence::before {
    content: '';
    position: absolute;
    left: 30px; top: 18px; bottom: 18px;
    width: 1px;
    background: var(--border-2);
}
.witness-sequence-row {
    display: grid;
    grid-template-columns: 70px 110px 1fr 60px;
    gap: 14px;
    padding: 0 20px 0 0;
    height: 32px;
    align-items: center;
    border-left: 2px solid transparent;
    margin-left: -2px;
}
.witness-sequence-row.open { border-left-color: var(--accent); }
.witness-sequence-row .t { font-family: var(--mono); font-size: 10.5px; color: var(--fg-faint); margin-left: 14px; position: relative; }
.witness-sequence-row .node {
    position: absolute; left: -3px; top: 50%; transform: translateY(-50%);
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--bg);
    border: 1px solid var(--fg-faint);
}
.witness-sequence-row.open .node { background: var(--accent); border-color: var(--accent); }
.witness-sequence-row .type { font-family: var(--mono); font-size: 11px; }
.witness-sequence-row .type.tool { color: var(--accent); }
.witness-sequence-row .type.output { color: var(--add); }
.witness-sequence-row .type.other { color: var(--fg-dim); }
.witness-sequence-row .summary { font-size: 12.5px; color: var(--fg); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.witness-sequence-row .tokens { font-family: var(--mono); font-size: 10.5px; color: var(--fg-faint); text-align: right; }

/* -- Headline KvBig (Fingerprint) -------------------------------------- */

.witness-headline {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0;
    margin-bottom: 32px;
    max-width: 720px;
}
.witness-headline > div {
    border-right: 1px solid var(--border);
    padding: 0 18px 0 0;
    margin-right: 18px;
}
.witness-headline > div:last-child { border-right: 0; padding-right: 0; margin-right: 0; }
.witness-headline .label {
    font-family: var(--mono);
    font-size: 10.5px;
    color: var(--fg-faint);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 8px;
}
.witness-headline .value {
    font-size: 24px;
    font-weight: 500;
    color: var(--fg);
    letter-spacing: -0.02em;
    margin-bottom: 4px;
}
.witness-headline .value.mono { font-family: var(--mono); }
.witness-headline .sub { font-family: var(--mono); font-size: 11px; color: var(--fg-faint); }
.witness-headline .sub.del { color: var(--del); }
.witness-headline .sub.add { color: var(--add); }

/* -- Comparison table --------------------------------------------------- */

.witness-cmp-row {
    display: grid;
    grid-template-columns: 1fr 100px 100px 100px;
    gap: 16px;
    padding: 10px 18px;
    border-bottom: 1px solid var(--border);
}
.witness-cmp-row:last-child { border-bottom: 0; }
.witness-cmp-row.head .cell { font-family: var(--mono); font-size: 10.5px; color: var(--fg-faint); text-transform: uppercase; letter-spacing: 0.04em; }
.witness-cmp-row .cell { font-size: 12px; color: var(--fg); }
.witness-cmp-row .cell.right { text-align: right; }
.witness-cmp-row .cell.mono { font-family: var(--mono); font-size: 11.5px; color: var(--fg); }
.witness-cmp-row .cell.dim { color: var(--fg-dim); }
.witness-cmp-row .cell.del { color: var(--del); }
.witness-cmp-row .cell.add { color: var(--add); }

/* -- Section divider with space --------------------------------------- */

.witness-divider {
    height: 1px;
    background: var(--border);
    border: 0;
    margin: 18px 0;
}

/* keyboard shortcut hint */
kbd {
    font-family: var(--mono);
    font-size: 10px;
    color: var(--fg-dim);
    background: var(--bg-3);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 1px 5px;
    line-height: 1;
}
</style>
"""


__all__ = ["THEME_CSS"]
