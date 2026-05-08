"""Witness UI theme — design tokens, typography, and component CSS.

Lifted from the Witness design handoff (dark-first, mono-heavy, restrained).

CRITICAL DESIGN RULE: do NOT use `font-family: ... !important` on broad
selectors (especially anything matching ``[class*="st-"]`` or ``span``).
Streamlit renders chevrons and icons as ligatures inside spans whose inline
``font-family: 'Material Symbols Outlined'`` will be silently overridden,
causing icon names ("arrow_right", "expand_more") to leak through as text.

The CSS below sets typography on the content elements only and leaves
inline-styled icon spans alone.
"""
from __future__ import annotations

THEME_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" />

<style>
:root {
    /* Linear / Vercel / Anthropic dark — one accent, restrained scale.
       Token names follow the redesign brief. Legacy aliases kept below
       so existing rules don't break in this commit; commit 5 -> commit 6
       will sweep references onto the new names. */

    /* Surfaces */
    --bg-page:     #08090A;
    --bg-surface:  #0E0F11;
    --bg-raised:   #15171A;

    /* Borders */
    --border:        rgba(255, 255, 255, 0.08);
    --border-hover:  rgba(255, 255, 255, 0.12);

    /* Foreground ramp */
    --fg:          #E6E6E6;
    --fg-muted:    #9A9A9A;
    --fg-faint:    #6B6B6B;
    --fg-disabled: #4A4A4A;

    /* Accent — one only, used sparingly */
    --accent:    #D97757;     /* Anthropic clay */
    --accent-fg: #0A0A0A;

    /* Status */
    --ok:    #3FB950;
    --err:   #F85149;
    --warn:  #D29922;
    --info:  #58A6FF;

    /* --- Legacy aliases (will be removed once all selectors migrate) --- */
    --bg:           var(--bg-page);
    --bg-1:         var(--bg-surface);
    --bg-2:         var(--bg-raised);
    --bg-3:         #1f2125;
    --border-2:     var(--border-hover);
    --fg-dim:       var(--fg-muted);
    --fg-faintest:  var(--fg-disabled);
    --accent-ink:   var(--accent-fg);
    --add:          var(--ok);
    --del:          var(--err);
    --add-bg:       rgba(63, 185, 80, 0.10);
    --del-bg:       rgba(248, 81, 73, 0.10);
    --hover:        rgba(255, 255, 255, 0.025);
    --selected:     rgba(255, 255, 255, 0.04);

    /* Typography */
    --sans: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
    --mono: 'JetBrains Mono', 'Geist Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;

    /* Radii — 6px inputs/buttons, 8px surfaces, 0 for list rows */
    --radius:    6px;
    --radius-lg: 8px;
}

/* ---- Streamlit page chrome ---------------------------------------- */

html, body, .stApp { background: var(--bg); }
.stApp { color: var(--fg); }

/* Body typography. NB: no !important — Streamlit's icon spans must keep
   their inline Material Symbols font-family. */
body, .stApp, .main, .block-container { font-family: var(--sans); font-size: 13px; }
.stMarkdown, .stMarkdown p, .stMarkdown span, .stMarkdown div,
.stHeading, .stCaption {
    font-family: var(--sans);
}

/* Tight content padding — Linear/Vercel density target */
.block-container {
    padding-top: 0.5rem !important;
    padding-bottom: 0.5rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    max-width: none !important;
}
.main .block-container { gap: 0.5rem; }

/* Hide Streamlit's top chrome */
header[data-testid="stHeader"] { height: 0 !important; min-height: 0 !important; background: transparent !important; }
[data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }

/* Tighten the gap between vertically stacked Streamlit blocks */
[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] {
    gap: 0.4rem;
}
[data-testid="stVerticalBlock"] { gap: 0.4rem; }

/* ---- Sidebar ------------------------------------------------------ */

[data-testid="stSidebar"] {
    background: var(--bg-surface);
    border-right: 1px solid var(--border);
    /* Locked at 220px (Linear's sidebar width) — no collapse. */
    width: 220px !important;
    min-width: 220px !important;
    max-width: 220px !important;
    transform: translateX(0) !important;
    visibility: visible !important;
}
/* Hide the collapse button (design's sidebar is permanent) */
[data-testid="stSidebarCollapseButton"] { display: none !important; }
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
[data-testid="stSidebar"] button[kind="header"],
[data-testid="stSidebar"] button[kind="headerNoPadding"] {
    display: none !important;
}
/* Push main content over by sidebar width */
.stApp > [data-testid="stAppViewContainer"] > .main {
    margin-left: 0 !important;
}
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
    padding: 14px 14px 12px 16px;
}
[data-testid="stSidebar"] hr { border-color: var(--border); margin: 12px 0; }

/* Sidebar nav radio: make labels look like nav buttons. We DO NOT touch the
   font-family of the radio's inner icon span — the dot circle is part of
   Streamlit's BaseUI radio and uses its own font. */
[data-testid="stSidebar"] [role="radiogroup"] { gap: 2px; }
[data-testid="stSidebar"] [role="radiogroup"] > label {
    height: 28px;
    padding: 0 8px;
    border-radius: var(--radius);
    color: var(--fg-dim);
    cursor: pointer;
    transition: background 80ms linear;
}
[data-testid="stSidebar"] [role="radiogroup"] > label:hover { background: var(--hover); }
[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) {
    color: var(--fg) !important;
    background: var(--selected) !important;
}
[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) p {
    color: var(--fg) !important;
    font-weight: 500;
}
/* hide the radio's circle indicator */
[data-testid="stSidebar"] [role="radiogroup"] > label > div:first-child { display: none; }
[data-testid="stSidebar"] [role="radiogroup"] > label p { font-size: 12.5px; margin: 0; }

/* ---- Buttons ------------------------------------------------------ */

.stButton > button, .stDownloadButton > button {
    height: 28px;
    min-height: 28px;
    padding: 0 12px;
    border: 1px solid var(--border-2);
    background: var(--bg-2);
    border-radius: var(--radius);
    color: var(--fg);
    font-size: 12px;
    font-weight: 500;
    transition: background 80ms linear, border-color 80ms linear;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    background: var(--bg-3);
    border-color: var(--fg-faintest);
    color: var(--fg);
}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
    background: var(--accent);
    color: var(--accent-ink);
    border-color: var(--accent);
    font-weight: 600;
}
.stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {
    background: var(--accent);
    border-color: var(--accent);
    filter: brightness(1.06);
}
.stButton > button p, .stDownloadButton > button p { margin: 0; font-size: 12px; }

/* ---- Inputs ------------------------------------------------------- */

.stTextInput input, .stTextArea textarea, .stNumberInput input {
    background: var(--bg-2);
    border: 1px solid var(--border);
    color: var(--fg);
    font-family: var(--mono);
    font-size: 12px;
    border-radius: var(--radius);
    height: 32px;
}
.stTextArea textarea { height: auto; }
.stTextInput input:focus, .stTextArea textarea:focus { border-color: var(--fg-faint); }
.stTextInput input::placeholder, .stTextArea textarea::placeholder {
    color: var(--fg-faint);
    font-family: var(--mono);
}

/* Selectbox: skin the BaseUI select wrapper */
.stSelectbox > div[data-baseweb="select"] > div {
    background: var(--bg-2);
    border-color: var(--border);
    border-radius: var(--radius);
    min-height: 32px;
}
.stSelectbox > div[data-baseweb="select"] > div > div {
    font-family: var(--mono);
    font-size: 12px;
    color: var(--fg);
}

/* Hide tooltip help icon space on labels */
.stSelectbox label, .stTextInput label, .stTextArea label, .stNumberInput label, .stSlider label, .stRadio label {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--fg-dim);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 500;
}

/* ---- Slider ------------------------------------------------------- */

.stSlider [data-baseweb="slider"] [role="slider"] {
    background: var(--accent);
    border-color: var(--accent);
}
.stSlider [data-baseweb="slider"] [aria-valuenow] { color: var(--fg); }
.stSlider [data-baseweb="slider"] > div > div > div { background: var(--accent); }

/* ---- Toggle (st.toggle) ------------------------------------------ */
/* Default off-state is a gray track. On-state should use the accent. */
[data-testid="stSidebar"] [data-baseweb="toggle"] [role="switch"] {
    background: var(--bg-3);
    border: 1px solid var(--border-2);
}
[data-testid="stSidebar"] [data-baseweb="toggle"] [role="switch"][aria-checked="true"] {
    background: var(--accent);
    border-color: var(--accent);
}
[data-testid="stSidebar"] [data-baseweb="toggle"] [role="switch"] > div {
    background: var(--fg);
}

/* ---- File uploader: replace internal hint text -------------------- */

[data-testid="stFileUploader"] { margin-bottom: 0.4rem; }
[data-testid="stFileUploader"] section {
    background: var(--bg-1);
    border: 1px dashed var(--border-2);
    border-radius: var(--radius-lg);
    padding: 14px 18px;
    min-height: 56px;
}
/* Hide Streamlit's default "Drag and drop file here / 200MB per file" copy
   — but keep the visible "Browse files" button. */
[data-testid="stFileUploader"] section [data-testid="stFileUploaderDropzoneInstructions"] > div > span {
    display: none;
}
[data-testid="stFileUploader"] section [data-testid="stFileUploaderDropzoneInstructions"] > div > small {
    display: none;
}
/* Inject our own copy via ::before on the instructions container */
[data-testid="stFileUploader"] section [data-testid="stFileUploaderDropzoneInstructions"] > div::before {
    content: "drop trace JSON files here";
    font-family: var(--mono);
    font-size: 11.5px;
    color: var(--fg-faint);
    text-transform: lowercase;
}
[data-testid="stFileUploader"] section button {
    background: var(--bg-2) !important;
    color: var(--fg) !important;
    border: 1px solid var(--border-2) !important;
    height: 28px !important;
    padding: 0 12px !important;
    font-size: 12px !important;
    font-weight: 500 !important;
}
[data-testid="stFileUploader"] section button:hover {
    background: var(--bg-3) !important;
    border-color: var(--fg-faintest) !important;
}

/* ---- Tabs --------------------------------------------------------- */

[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 0;
    border-bottom: 1px solid var(--border);
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    height: 36px;
    padding: 0 14px;
    background: transparent;
    color: var(--fg-dim);
    border-bottom: 2px solid transparent;
    font-family: var(--mono);
    font-size: 12px;
}
[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
    color: var(--fg);
    border-bottom-color: var(--accent);
}

/* ---- Expanders --------------------------------------------------- */
/* IMPORTANT: do NOT change font-family on the expander summary inner
   spans — Streamlit's chevron ("expand_more"/"chevron_right") is rendered
   as a Material Symbols ligature in a span. Override font-family there
   and you'll see the literal text "expand_more" in the UI. */

[data-testid="stExpander"] {
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
}
[data-testid="stExpander"] summary {
    padding: 8px 14px;
    background: var(--bg-1);
}
[data-testid="stExpander"] summary p {
    font-family: var(--mono);
    font-size: 12px;
    color: var(--fg);
    margin: 0;
}

/* ---- Status / Toast / Spinner ------------------------------------- */

[data-testid="stStatus"] {
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
}
[data-testid="stStatus"] details summary p {
    font-family: var(--mono);
    font-size: 12px;
}

[data-testid="stToast"] {
    background: var(--bg-2);
    color: var(--fg);
    border: 1px solid var(--border-2);
    font-family: var(--mono);
    font-size: 11.5px;
}

/* ---- Dataframe ---------------------------------------------------- */

[data-testid="stDataFrame"] {
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: var(--radius);
}

/* ---- Code / pre / json ------------------------------------------- */

.stMarkdown pre, .stMarkdown code, [data-testid="stCodeBlock"] {
    background: var(--bg-2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    font-family: var(--mono);
    font-size: 11.5px;
    color: var(--fg);
}
[data-testid="stJson"] {
    background: var(--bg-2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 8px 10px;
    font-family: var(--mono);
    font-size: 11px;
}

/* ---- Type ramp ---------------------------------------------------- */
/* Five sizes only: caps-label 11, metadata 12 mono, body 13, ui 14m, heading 18.
   Headings collapse onto the same 18px to enforce the constraint. */

.stMarkdown h1,
.stMarkdown h2,
.stMarkdown h3,
.stMarkdown h4 {
    font-size: 18px;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--fg);
    margin: 0 0 4px 0;
    line-height: 1.2;
}
.stMarkdown p,
.stMarkdown li {
    font-size: 13px;
    line-height: 1.5;
    color: var(--fg);
}

/* ---- Scrollbar / selection --------------------------------------- */

*::-webkit-scrollbar { width: 8px; height: 8px; }
*::-webkit-scrollbar-track { background: transparent; }
*::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 4px; }
*::-webkit-scrollbar-thumb:hover { background: var(--fg-faint); }

::selection { background: var(--accent); color: var(--accent-ink); }

/* ---- Witness component classes (rendered via st.markdown HTML) --- */

.mono { font-family: var(--mono); font-feature-settings: 'zero', 'cv01'; }
.dim  { color: var(--fg-dim); }
.faint{ color: var(--fg-faint); }

.uppercase-label {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--fg-dim);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 500;
}

/* dots */
.dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; vertical-align: middle; }
.dot-accent { background: var(--accent); }
.dot-add    { background: var(--add); }
.dot-del    { background: var(--del); }
.dot-dim    { background: var(--fg-faint); }

/* chip */
.chip {
    display: inline-flex; align-items: center; gap: 6px;
    height: 20px; padding: 0 8px;
    border: 1px solid var(--border);
    border-radius: 3px;
    font-family: var(--mono);
    font-size: 10.5px;
    color: var(--fg-dim);
    line-height: 1;
}
.chip-accent { border-color: var(--accent); color: var(--accent); }
.chip-add { border-color: var(--add); color: var(--add); }
.chip-del { border-color: var(--del); color: var(--del); }

/* ---- Hero stat row (Diff page) ----------------------------------- */

.witness-stat-row {
    display: grid;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    background: var(--bg);
    margin: 8px 0;
}
.witness-stat {
    padding: 14px 20px;
    border-right: 1px solid var(--border);
}
.witness-stat:last-child { border-right: 0; }
.witness-stat .label {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--fg-dim);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 500;
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

/* ---- KV pair (inspector panels) ---------------------------------- */

.witness-kv {
    display: flex; justify-content: space-between;
    padding: 5px 0;
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
    text-align: right;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 60%;
}
.witness-kv .v.accent { color: var(--accent); }

/* ---- Numbered section header (Perturb page) --------------------- */

.witness-section {
    display: flex; align-items: baseline; gap: 10px;
    margin: 14px 0 10px 0;
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

/* ---- Stability bar (Fingerprint page) ---------------------------- */

.witness-bar-row {
    display: grid;
    grid-template-columns: 200px 1fr 60px 90px;
    gap: 16px;
    padding: 10px 18px;
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

.witness-bar { position: relative; height: 18px; }
.witness-bar .track {
    position: absolute; left: 0; top: 50%;
    transform: translateY(-50%);
    height: 8px; width: 100%;
    background: var(--bg-3);
    border-radius: 1px;
}
.witness-bar .fill {
    position: absolute; left: 0; top: 50%;
    transform: translateY(-50%);
    height: 8px;
    border-radius: 1px;
    transition: width 240ms ease;
}
.witness-bar .fill.low  { background: var(--del); }
.witness-bar .fill.mid  { background: var(--accent); }
.witness-bar .fill.high { background: var(--add); }

/* ---- Witness panel & empty card --------------------------------- */

.witness-panel {
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    overflow: hidden;
}

.witness-empty {
    text-align: center;
    padding: 28px 18px;
    background: var(--bg-1);
    border: 1px dashed var(--border-2);
    border-radius: var(--radius-lg);
    margin: 8px 0;
}
.witness-empty .title {
    font-size: 13.5px;
    font-weight: 500;
    color: var(--fg);
    margin-bottom: 6px;
}
.witness-empty .desc {
    font-family: var(--mono);
    font-size: 11.5px;
    color: var(--fg-faint);
}

/* ---- Animations -------------------------------------------------- */

@keyframes fadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
.fade-in { animation: fadeIn 160ms ease-out; }

@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.pulse { animation: pulse 1.4s ease-in-out infinite; }

@keyframes blink { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0; } }
.caret { animation: blink 1s steps(1) infinite; }

/* ---- Load-page file-browser table ------------------------------- */

.witness-table-header {
    display: grid;
    grid-template-columns: 1.5fr 1fr 0.6fr 1fr 0.7fr 0.8fr;
    gap: 16px;
    padding: 8px 16px;
    border-bottom: 1px solid var(--border);
    font-family: var(--mono);
    font-size: 11px;
    color: var(--fg-dim);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 500;
}
.witness-table-header span { white-space: nowrap; }
.witness-table-row {
    display: grid;
    grid-template-columns: 1.5fr 1fr 0.6fr 1fr 0.7fr 0.8fr;
    gap: 16px;
    padding: 0 16px;
    height: 34px;
    align-items: center;
    border-left: 2px solid transparent;
    border-bottom: 1px solid var(--bg-1);
}
.witness-table-row.selected { border-left-color: var(--accent); background: var(--selected); }
.witness-table-row .filename { font-family: var(--mono); font-size: 12px; color: var(--fg); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.witness-table-row .agent { font-size: 12px; color: var(--fg-dim); }
.witness-table-row .num   { font-family: var(--mono); font-size: 11.5px; color: var(--fg-dim); }
.witness-table-row .meta  { font-family: var(--mono); font-size: 11px; color: var(--fg-faint); }
.witness-table-row .right { text-align: right; }

/* ---- Diff side-by-side rows ------------------------------------ */

.witness-diff-row {
    height: 30px;
    padding: 0 14px;
    display: grid;
    grid-template-columns: 8px 60px 90px 1fr;
    gap: 10px;
    align-items: center;
    border-bottom: 1px solid var(--bg-1);
}
.witness-diff-row.changed.baseline-side { background: var(--del-bg); }
.witness-diff-row.changed.perturbed-side { background: var(--add-bg); }
.witness-diff-row .t       { font-family: var(--mono); font-size: 10.5px; color: var(--fg-faint); }
.witness-diff-row .type    { font-family: var(--mono); font-size: 10.5px; }
.witness-diff-row .summary { font-family: var(--mono); font-size: 11.5px; color: var(--fg); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.witness-diff-placeholder {
    height: 30px;
    padding: 0 14px;
    display: flex; align-items: center;
    background: repeating-linear-gradient(45deg, transparent, transparent 6px, var(--bg-1) 6px, var(--bg-1) 7px);
    border-bottom: 1px solid var(--bg-1);
    font-family: var(--mono);
    font-size: 10.5px;
    color: var(--fg-faint);
}

/* ---- Inspect: vertical sequence + decision rows ---------------- */

.witness-sequence {
    position: relative;
    padding-left: 28px;
}
.witness-sequence::before {
    content: '';
    position: absolute;
    left: 26px; top: 18px; bottom: 18px;
    width: 1px;
    background: var(--border-2);
}
.witness-sequence-row {
    display: grid;
    grid-template-columns: 60px 110px 1fr 60px;
    gap: 14px;
    padding: 0 16px 0 0;
    height: 30px;
    align-items: center;
    border-left: 2px solid transparent;
    margin-left: -2px;
    position: relative;
}
.witness-sequence-row::before {
    content: '';
    position: absolute;
    left: -3px; top: 50%; transform: translateY(-50%);
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--bg);
    border: 1px solid var(--fg-faint);
}
.witness-sequence-row.open { border-left-color: var(--accent); }
.witness-sequence-row.open::before { background: var(--accent); border-color: var(--accent); }
.witness-sequence-row .t    { font-family: var(--mono); font-size: 10.5px; color: var(--fg-faint); margin-left: 14px; }
.witness-sequence-row .type { font-family: var(--mono); font-size: 11px; }
.witness-sequence-row .type.tool   { color: var(--accent); }
.witness-sequence-row .type.output { color: var(--add); }
.witness-sequence-row .type.other  { color: var(--fg-dim); }
.witness-sequence-row .summary { font-size: 12.5px; color: var(--fg); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.witness-sequence-row .tokens  { font-family: var(--mono); font-size: 10.5px; color: var(--fg-faint); text-align: right; }

/* ---- Fingerprint headline (3 KvBig blocks) --------------------- */

.witness-headline {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0;
    margin: 8px 0 22px 0;
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
    font-size: 11px;
    color: var(--fg-dim);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 500;
    margin-bottom: 8px;
}
.witness-headline .value {
    font-size: 22px;
    font-weight: 500;
    color: var(--fg);
    letter-spacing: -0.02em;
    margin-bottom: 4px;
}
.witness-headline .value.mono { font-family: var(--mono); }
.witness-headline .sub { font-family: var(--mono); font-size: 11px; color: var(--fg-faint); }
.witness-headline .sub.del { color: var(--del); }
.witness-headline .sub.add { color: var(--add); }

/* ---- Per-run comparison table ---------------------------------- */

.witness-cmp-row {
    display: grid;
    grid-template-columns: 1.4fr 1fr 0.6fr 0.6fr;
    gap: 16px;
    padding: 9px 16px;
    border-bottom: 1px solid var(--border);
}
.witness-cmp-row:last-child { border-bottom: 0; }
.witness-cmp-row.head .cell {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--fg-dim);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 500;
}
.witness-cmp-row .cell { font-size: 12px; color: var(--fg); }
.witness-cmp-row .cell.right { text-align: right; }
.witness-cmp-row .cell.mono  { font-family: var(--mono); font-size: 11.5px; color: var(--fg); }
.witness-cmp-row .cell.dim   { color: var(--fg-dim); }
.witness-cmp-row .cell.del   { color: var(--del); }
.witness-cmp-row .cell.add   { color: var(--add); }

/* ---- Filter pill group (Load page tabs all/baseline/perturbed) -- */

/* Style horizontal st.radio to look like the design's connected pill group.
   Hide the circles, flatten labels into pill buttons, share borders. */
.stRadio[data-testid="stRadio"] [role="radiogroup"][aria-orientation="horizontal"] {
    display: inline-flex !important;
    gap: 0 !important;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    flex-wrap: nowrap !important;
    margin: 0 !important;
}
.stRadio[data-testid="stRadio"] [role="radiogroup"][aria-orientation="horizontal"] > label {
    height: 28px;
    padding: 0 12px !important;
    margin: 0 !important;
    background: transparent;
    color: var(--fg-dim);
    border-right: 1px solid var(--border);
    border-radius: 0 !important;
    cursor: pointer;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: background 80ms linear;
}
.stRadio[data-testid="stRadio"] [role="radiogroup"][aria-orientation="horizontal"] > label:last-child {
    border-right: 0;
}
.stRadio[data-testid="stRadio"] [role="radiogroup"][aria-orientation="horizontal"] > label:hover {
    background: var(--hover);
}
.stRadio[data-testid="stRadio"] [role="radiogroup"][aria-orientation="horizontal"] > label:has(input:checked) {
    background: var(--bg-3);
    color: var(--fg) !important;
}
/* hide the radio circle indicator inside pill labels */
.stRadio[data-testid="stRadio"] [role="radiogroup"][aria-orientation="horizontal"] > label > div:first-child {
    display: none !important;
}
/* Use text-transform: none !important — Streamlit's BaseUI radio applies
   text-transform: uppercase via its own stylesheet (winning over our
   cascade), which is why filter chips were rendering as MODEL_CALL (2)
   instead of model_call (2). Forcing none means we get exactly the
   casing the Python code passed in. */
.stRadio[data-testid="stRadio"] [role="radiogroup"][aria-orientation="horizontal"] > label p,
.stRadio[data-testid="stRadio"] [role="radiogroup"][aria-orientation="horizontal"] > label span,
.stRadio[data-testid="stRadio"] [role="radiogroup"][aria-orientation="horizontal"] > label div {
    font-family: var(--mono) !important;
    font-size: 11.5px !important;
    margin: 0 !important;
    text-transform: none !important;
    color: inherit !important;
    letter-spacing: 0 !important;
}

/* ---- Top-bar style header (page title + subtitle line) --------- */

.witness-topbar {
    display: flex; align-items: baseline; gap: 12px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 14px;
}
.witness-topbar .title {
    font-size: 14px;
    font-weight: 500;
    color: var(--fg);
}
.witness-topbar .subtitle {
    font-family: var(--mono);
    font-size: 11.5px;
    color: var(--fg-dim);
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

/* hide the streamlit "manage app" footer */
[data-testid="stStatusWidget"] { display: none !important; }

/* ---- Dense traces table (commit 2) ------------------------------ */

.wt-table-head {
    display: grid;
    grid-template-columns: 16px 2fr 1.4fr 1.4fr 0.8fr 0.9fr 0.9fr 96px;
    gap: 12px;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    font-family: var(--mono);
    font-size: 11px;
    color: var(--fg-faint);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 500;
    user-select: none;
}
.wt-table-head .wt-col-head {
    color: var(--fg-faint);
    text-decoration: none;
    transition: color 80ms linear;
}
.wt-table-head .wt-col-head:hover { color: var(--fg); }

.wt-row {
    position: relative;
    display: grid;
    grid-template-columns: 16px 2fr 1.4fr 1.4fr 0.8fr 0.9fr 0.9fr 96px;
    gap: 12px;
    align-items: center;
    height: 32px;
    padding: 0 12px;
    border-bottom: 1px solid var(--border);
    transition: background 80ms linear;
    cursor: pointer;
}
.wt-row:hover { background: var(--bg-2); }
.wt-row.active {
    background: var(--bg-2);
    box-shadow: inset 2px 0 0 0 var(--accent);
}
.wt-row .wt-dot { justify-self: center; }
.wt-row .wt-cell {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 12.5px;
}
.wt-row .wt-filename { font-family: var(--mono); color: var(--fg); }
.wt-row .wt-agent { color: var(--fg-dim); }
.wt-row .wt-model { color: var(--fg-faint); font-size: 11.5px; }
.wt-row .wt-decisions { color: var(--fg-dim); font-size: 11.5px; text-align: right; }
.wt-row .wt-stability { font-size: 11.5px; text-align: right; }
.wt-row .wt-captured { color: var(--fg-faint); font-size: 11px; text-align: right; }

/* Whole-row click overlay — sits beneath the icon actions via z-index */
.wt-row-overlay {
    position: absolute;
    inset: 0;
    z-index: 1;
    text-decoration: none;
    color: inherit;
}

.wt-actions {
    grid-column: 8 / 9;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 2px;
    z-index: 2;
    opacity: 0;
    transition: opacity 100ms ease;
    pointer-events: none;
}
.wt-row:hover .wt-actions {
    opacity: 1;
    pointer-events: auto;
}
.wt-action {
    width: 26px;
    height: 26px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    color: var(--fg-faint);
    text-decoration: none;
    transition: background 80ms linear, color 80ms linear;
}
.wt-action:hover { background: var(--bg-3); color: var(--fg); }
.wt-action-danger:hover { color: var(--del); background: var(--del-bg); }
.wt-action svg { display: block; }

/* ---- Trace detail (commit 4) ----------------------------------- */

.td-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    padding: 12px 0 8px 0;
}
.td-header-text { display: flex; flex-direction: column; gap: 2px; }
.td-filename {
    font-family: var(--sans);
    font-size: 14px;
    font-weight: 500;
    color: var(--fg);
    letter-spacing: -0.005em;
}
.td-meta {
    font-family: var(--mono);
    font-size: 12px;
    color: var(--fg-dim);
}
.td-hr {
    border: 0;
    height: 1px;
    background: var(--border);
    margin: 4px 0 8px 0;
}

.td-tab-row {
    display: flex;
    gap: 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 14px;
}
.td-tab {
    height: 32px;
    padding: 0 14px;
    display: inline-flex;
    align-items: center;
    font-family: var(--sans);
    font-size: 14px;
    font-weight: 500;
    color: var(--fg-dim);
    text-decoration: none;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    transition: color 80ms linear;
}
.td-tab:hover { color: var(--fg); }
.td-tab-active {
    color: var(--fg);
    border-bottom-color: var(--accent);
}

/* Sequence rail + main pane */
.td-seq-rail {
    display: flex;
    flex-direction: column;
    gap: 0;
    padding: 0;
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
}
.td-seq-item {
    display: grid;
    grid-template-columns: 32px 1fr;
    gap: 8px;
    align-items: center;
    height: 28px;
    padding: 0 10px;
    border-left: 2px solid transparent;
    border-bottom: 1px solid var(--border);
    color: inherit;
    text-decoration: none;
    transition: background 80ms linear;
}
.td-seq-item:last-child { border-bottom: 0; }
.td-seq-item:hover { background: var(--bg-2); }
.td-seq-active {
    border-left-color: var(--accent);
    background: var(--bg-2);
}
.td-seq-idx {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--fg-faint);
}
.td-seq-type {
    font-family: var(--mono);
    font-size: 12px;
}

/* Decision detail fields */
.td-fields {
    display: flex;
    flex-direction: column;
    gap: 0;
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
}
.td-field-row {
    display: grid;
    grid-template-columns: 100px 1fr;
    gap: 12px;
    padding: 8px 14px;
    border-bottom: 1px solid var(--border);
}
.td-field-row:last-child { border-bottom: 0; }
.td-field-label {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--fg-faint);
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.td-field-value {
    font-size: 13px;
    color: var(--fg);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* Empty inline (Sequence/Messages/Runs/Stability when no content) */
.td-empty-inline {
    padding: 32px 8px;
    text-align: center;
    font-family: var(--mono);
    font-size: 12px;
    color: var(--fg-faint);
}

/* Messages list */
.td-msg-row {
    display: grid;
    grid-template-columns: 32px 80px 1fr;
    gap: 12px;
    align-items: center;
    height: 32px;
    padding: 0 12px;
    border-bottom: 1px solid var(--border);
    font-size: 12.5px;
}
.td-msg-idx { font-family: var(--mono); color: var(--fg-faint); }
.td-msg-role { font-family: var(--mono); color: var(--fg-dim); font-size: 11.5px; }
.td-msg-content {
    color: var(--fg);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* Runs list (perturbed children) */
.td-run-row {
    display: grid;
    grid-template-columns: 1.5fr 1fr 80px;
    gap: 12px;
    align-items: center;
    height: 32px;
    padding: 0 12px;
    border-bottom: 1px solid var(--border);
    color: inherit;
    text-decoration: none;
    transition: background 80ms linear;
}
.td-run-row:hover { background: var(--bg-2); }
.td-run-label { color: var(--fg); font-size: 12.5px; }
.td-run-type { color: var(--fg-dim); font-size: 12px; }
.td-run-decisions { color: var(--fg-faint); font-size: 11.5px; text-align: right; }

/* ---- Empty state (commit 6) ----------------------------------- */

.es-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 64px 24px;
    gap: 8px;
}
.es-icon {
    color: var(--fg-faint);
    margin-bottom: 4px;
    line-height: 0;
}
.es-icon svg { display: block; }
.es-message {
    font-family: var(--sans);
    font-size: 13px;
    color: var(--fg-muted);
    line-height: 1.5;
}
.es-hint {
    font-family: var(--mono);
    font-size: 12px;
    color: var(--fg-faint);
    line-height: 1.5;
}
.es-hint kbd { margin: 0 2px; }

/* Stability headline */
.td-stability-headline {
    display: flex;
    align-items: baseline;
    gap: 12px;
    padding: 18px 0 8px 0;
}
.td-stability-value {
    font-family: var(--mono);
    font-size: 28px;
    font-weight: 500;
    color: var(--fg);
    letter-spacing: -0.02em;
}
.td-stability-label {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--fg-faint);
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

/* ---- Bordered containers (st.container(border=True)) ----------- */
/* Used to group each Load-page trace row with its action buttons,  */
/* and to tile the 3 onboarding sub-cards on the welcome panel.     */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: var(--border) !important;
    border-radius: var(--radius) !important;
    background: var(--bg-1);
    transition: border-color 80ms linear, background 80ms linear;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: var(--border-2) !important;
}
[data-testid="stVerticalBlockBorderWrapper"] > div {
    padding: 6px 8px !important;
}
/* Tighten the inner vertical-block gap inside cards */
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"] {
    gap: 6px !important;
}
/* Equalize heights of bordered cards living inside st.columns — keeps the
   3 onboarding sub-cards aligned across the row even when one is taller. */
[data-testid="stColumn"] [data-testid="stVerticalBlockBorderWrapper"] {
    height: 100%;
}
</style>
"""


__all__ = ["THEME_CSS"]
