"""Shared responsive CSS for laptop / split-screen desktop widths (not mobile)."""

RESPONSIVE_DASHBOARD_CSS = """
<style>
/* Anchor markers for scoped filter-toolbar rules (zero-height) */
.filter-toolbar-anchor,
.ac-filter-anchor {
  display: block;
  height: 0;
  margin: 0;
  padding: 0;
  overflow: hidden;
  border: none;
}

/* ── Main content width ───────────────────────────────────────── */
[data-testid="stAppViewContainer"] .main .block-container {
  max-width: 100% !important;
  padding-left: clamp(0.75rem, 2vw, 2rem) !important;
  padding-right: clamp(0.75rem, 2vw, 2rem) !important;
}

/* ── Prevent label letter-stacking ────────────────────────────── */
[data-testid="stMain"] [data-testid="stWidgetLabel"],
[data-testid="stMain"] [data-testid="stWidgetLabel"] p,
[data-testid="stMain"] label[data-testid="stWidgetLabel"] {
  white-space: nowrap !important;
  word-break: keep-all !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  min-width: 0 !important;
}

/* ── Inputs & selects: usable minimum widths ─────────────────── */
[data-testid="stMain"] [data-testid="stSelectbox"] > div,
[data-testid="stMain"] [data-testid="stDateInput"] > div,
[data-testid="stMain"] [data-testid="stTextInput"] > div,
[data-testid="stMain"] [data-testid="stMultiSelect"] > div {
  min-width: 7.5rem !important;
}

[data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"],
[data-testid="stMain"] [data-testid="stDateInput"] input {
  min-width: 6.5rem !important;
}

/* ── Buttons: don't crush ─────────────────────────────────────── */
[data-testid="stMain"] [data-testid="stBaseButton"] button,
[data-testid="stMain"] [data-testid="stPopover"] button {
  white-space: nowrap !important;
  min-width: 5.25rem !important;
  padding-left: 0.65rem !important;
  padding-right: 0.65rem !important;
}

[data-testid="stMain"] [data-testid="stBaseButton"][data-testid="stBaseButton-primary"] button {
  min-width: 5.75rem !important;
}

/* Date popover trigger */
[data-testid="stMain"] [data-testid="stPopover"] > button {
  min-width: 7.5rem !important;
  width: 100% !important;
}

/* ── Checkboxes: horizontal label alignment ─────────────────── */
[data-testid="stMain"] [data-testid="stCheckbox"] {
  min-width: 4.75rem !important;
}
[data-testid="stMain"] [data-testid="stCheckbox"] label,
[data-testid="stMain"] [data-testid="stCheckbox"] label p {
  white-space: nowrap !important;
  word-break: keep-all !important;
}

/* ── Filter toolbar rows (marked via adjacent marker div) ───── */
div.filter-toolbar-anchor + div[data-testid="stVerticalBlock"] [data-testid="stHorizontalBlock"],
div.filter-toolbar-anchor ~ div[data-testid="stVerticalBlock"] [data-testid="stHorizontalBlock"] {
  flex-wrap: wrap !important;
  row-gap: 0.6rem !important;
  column-gap: 0.5rem !important;
  align-items: flex-end !important;
}

div.filter-toolbar-anchor + div[data-testid="stVerticalBlock"] [data-testid="column"],
div.filter-toolbar-anchor ~ div[data-testid="stVerticalBlock"] [data-testid="column"] {
  flex: 1 1 10.5rem !important;
  min-width: 10.5rem !important;
  width: auto !important;
  max-width: 100% !important;
}

/* Wider columns for employee / search */
div.filter-toolbar-anchor + div[data-testid="stVerticalBlock"] [data-testid="column"]:nth-child(1),
div.filter-toolbar-anchor ~ div[data-testid="stVerticalBlock"] [data-testid="column"]:nth-child(1) {
  flex: 2 1 14rem !important;
  min-width: 14rem !important;
}

/* Alert-center filter rows */
div.ac-filter-anchor + div[data-testid="stVerticalBlock"] [data-testid="stHorizontalBlock"],
div.ac-filter-anchor ~ div[data-testid="stVerticalBlock"] [data-testid="stHorizontalBlock"] {
  flex-wrap: wrap !important;
  row-gap: 0.55rem !important;
  column-gap: 0.45rem !important;
  align-items: flex-end !important;
}

div.ac-filter-anchor + div[data-testid="stVerticalBlock"] [data-testid="column"],
div.ac-filter-anchor ~ div[data-testid="stVerticalBlock"] [data-testid="column"] {
  flex: 1 1 9.5rem !important;
  min-width: 9.5rem !important;
  width: auto !important;
}

/* ── KPI / exec grids already use auto-fit ───────────────────── */

/* ── Dataframe / chart overflow ──────────────────────────────── */
[data-testid="stMain"] [data-testid="stDataFrame"],
[data-testid="stMain"] [data-testid="stDataFrame"] > div {
  overflow-x: auto !important;
  max-width: 100% !important;
}

/* ── Laptop breakpoints ───────────────────────────────────────── */
@media (max-width: 1600px) {
  div.filter-toolbar-anchor + div[data-testid="stVerticalBlock"] [data-testid="column"],
  div.filter-toolbar-anchor ~ div[data-testid="stVerticalBlock"] [data-testid="column"] {
    flex: 1 1 9.5rem !important;
    min-width: 9.5rem !important;
  }
}

@media (max-width: 1366px) {
  [data-testid="stMain"] [data-testid="stBaseButton"] button {
    min-width: 4.75rem !important;
    font-size: 0.82rem !important;
  }
  div.filter-toolbar-anchor + div[data-testid="stVerticalBlock"] [data-testid="column"],
  div.filter-toolbar-anchor ~ div[data-testid="stVerticalBlock"] [data-testid="column"] {
    flex: 1 1 8.75rem !important;
    min-width: 8.75rem !important;
  }
  .exec-kpi-grid {
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)) !important;
  }
  .kpi-grid {
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)) !important;
  }
}

@media (max-width: 1200px) {
  div.filter-toolbar-anchor + div[data-testid="stVerticalBlock"] [data-testid="column"]:nth-child(1),
  div.filter-toolbar-anchor ~ div[data-testid="stVerticalBlock"] [data-testid="column"]:nth-child(1) {
    flex: 1 1 100% !important;
    min-width: 100% !important;
  }
}
</style>
"""
