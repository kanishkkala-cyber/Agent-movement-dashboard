"""Operations map + analytics — premium control tower UI."""

from __future__ import annotations

import calendar as pym_cal
import html
import re
from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from analytics import (
    compute_movement_analytics,
    format_duration,
    pct_delta,
    slice_employee_window,
    timeline_chart_data,
)
from field_ops_analytics import compute_field_intelligence
from core import (
    ALL_AGENTS_LABEL,
    REQUIRED_COLUMNS,
    TRACKING_PAGE_CSS,
    build_map,
    clear_punch_data_cache,
    google_sheet_export_url,
    load_punch_data_cached,
    load_site_locations,
    punch_data_source_label,
    sites_data_dir,
)
from responsive_ui import RESPONSIVE_DASHBOARD_CSS

DASH_EXTRA_CSS = """
<style>
/* system fonts only — avoids blocking network fetch on first paint */
html, body, [class*="css"]  { font-family: system-ui, "Segoe UI", sans-serif !important; }
[data-testid="stAppViewContainer"] {
  background: linear-gradient(165deg, #0f172a 0%, #1e293b 42%, #0f172a 100%) !important;
}
[data-testid="stHeader"] {
  background: rgba(15,23,42,0.88) !important;
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(148,163,184,0.12);
}
[data-testid="stMain"] { color: #e2e8f0; }
[data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3 { color: #f8fafc !important; }
[data-testid="stMain"] .stMarkdown p, [data-testid="stMain"] .stMarkdown li { color: #cbd5e1; }
section[data-testid="stSidebar"] {
  background: rgba(15,23,42,0.96) !important;
  border-right: 1px solid rgba(148,163,184,0.1);
}
.filter-glass {
  display: block;
  height: 0;
  margin: 0;
  padding: 0;
  overflow: hidden;
  border: none;
}
div.filter-toolbar-anchor + div[data-testid="stVerticalBlock"] {
  position: sticky;
  top: 0.35rem;
  z-index: 40;
  background: rgba(30,41,59,0.75);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border: 1px solid rgba(148,163,184,0.22);
  border-radius: 18px;
  padding: 0.85rem 1rem 0.95rem 1rem;
  margin-bottom: 1.25rem;
  box-shadow: 0 10px 40px rgba(0,0,0,0.35);
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
}
div.filter-toolbar-anchor + div[data-testid="stVerticalBlock"]:hover {
  border-color: rgba(56,189,248,0.35);
  box-shadow: 0 14px 48px rgba(0,0,0,0.45);
}
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(188px, 1fr)); gap: 12px; margin-bottom: 0.5rem; }
.kpi-card {
  background: linear-gradient(150deg, rgba(51,65,85,0.5) 0%, rgba(30,41,59,0.92) 100%);
  border: 1px solid rgba(148,163,184,0.16);
  border-radius: 14px;
  padding: 0.95rem 1rem;
  transition: transform 0.15s ease, border-color 0.15s ease;
}
.kpi-card:hover { transform: translateY(-2px); border-color: rgba(56,189,248,0.35); }
.kpi-label { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.1em; color: #94a3b8; font-weight: 600; }
.kpi-value { font-size: 1.45rem; font-weight: 700; color: #f8fafc; margin: 0.3rem 0 0.1rem 0; }
.kpi-sub { font-size: 0.76rem; color: #64748b; }
.kpi-delta-pos { color: #4ade80; font-size: 0.78rem; font-weight: 600; margin-top: 0.25rem; }
.kpi-delta-neg { color: #fb7185; font-size: 0.78rem; font-weight: 600; margin-top: 0.25rem; }
.section-title {
  font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.14em;
  color: #64748b; font-weight: 700; margin: 1.35rem 0 0.65rem 0;
}
iframe[title*="st_folium"], iframe[title*="folium"] {
  border-radius: 14px !important;
  border: 1px solid rgba(148,163,184,0.18) !important;
  min-height: 400px !important;
  max-height: 70vh !important;
}
.date-pop-legend {
  display: flex; flex-wrap: wrap; gap: 0.5rem 0.85rem;
  margin-top: 0.5rem; font-size: 0.68rem; color: #94a3b8;
}
.date-pop-legend span { display: inline-flex; align-items: center; gap: 0.3rem; }
.date-pop-dot { width: 8px; height: 8px; border-radius: 999px; }
div[class*="st-key-cal_pick_"] button {
  min-height: 1.85rem !important; padding: 0.15rem !important;
  font-weight: 600 !important; border-radius: 999px !important;
  transition: transform 0.12s ease, box-shadow 0.12s ease !important;
}
div[class*="st-key-cal_pick_"] button:hover {
  transform: scale(1.06); box-shadow: 0 0 12px rgba(56,189,248,0.35);
}
</style>
"""


def _time_choices() -> list[str]:
    opts = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)]
    opts.append("23:59")
    return opts


def _parse_hhmm(s: str):
    from datetime import time as dtime

    m = re.match(r"^(\d{1,2}):(\d{2})$", str(s).strip())
    if not m:
        return dtime(0, 0)
    h, mi = int(m.group(1)), int(m.group(2))
    return dtime(min(23, h), min(59, mi))


def _defaults_for_employee(scoped: pd.DataFrame, employee: str) -> tuple[date, str, str]:
    name_col = REQUIRED_COLUMNS["employee_name"]
    sub = scoped if employee == ALL_AGENTS_LABEL else scoped[scoped[name_col] == employee]
    if sub.empty:
        return date.today(), "00:00", "23:59"
    tmax = sub["_ts"].max()
    d = tmax.date() if pd.notna(tmax) else date.today()
    return d, "00:00", "23:59"


def _default_committed(scoped: pd.DataFrame, employees: list[str]) -> dict:
    emp0 = employees[0]
    d, tf, tt = _defaults_for_employee(scoped, emp0)
    return {
        "employee": emp0,
        "date": d,
        "from": tf,
        "to": tt,
        "yards": True,
        "service": True,
        "stores": True,
    }


def _active_filter_date() -> date:
    """Single source of truth for the date driving KPIs, map, and calendar highlight."""
    return st.session_state.committed["date"]


def _commit_active_date(d: date) -> None:
    """Sync widget date + committed date so calendar, popover label, and analytics match."""
    st.session_state.flt_date = d
    c = dict(st.session_state.committed)
    c["date"] = d
    st.session_state.committed = c
    st.session_state.avail_cal_month = d.replace(day=1)


def _on_flt_date_change() -> None:
    _commit_active_date(st.session_state.flt_date)


def _sync_widgets_from_committed(c: dict) -> None:
    """Push committed filters into widget keys — call only before filter widgets render."""
    st.session_state.flt_employee = c["employee"]
    st.session_state.flt_date = c["date"]
    st.session_state.flt_from = c["from"]
    st.session_state.flt_to = c["to"]
    st.session_state.flt_yards = c["yards"]
    st.session_state.flt_service = c["service"]
    st.session_state.flt_stores = c["stores"]
    st.session_state.avail_cal_month = c["date"].replace(day=1)


def _snapshot_from_widgets() -> dict:
    return {
        "employee": st.session_state.flt_employee,
        "date": st.session_state.flt_date,
        "from": st.session_state.flt_from,
        "to": st.session_state.flt_to,
        "yards": st.session_state.flt_yards,
        "service": st.session_state.flt_service,
        "stores": st.session_state.flt_stores,
    }


def _kpi_card(label: str, value: str, sub: str = "", delta_html: str = "") -> str:
    label_e = html.escape(label)
    value_e = html.escape(value)
    sub_e = html.escape(sub)
    return f"""<div class="kpi-card"><div class="kpi-label">{label_e}</div>
<div class="kpi-value">{value_e}</div><div class="kpi-sub">{sub_e}</div>{delta_html}</div>"""


def _dates_with_pings(scoped: pd.DataFrame, employee: str, name_col: str) -> set[date]:
    sub = scoped.loc[scoped[name_col].astype(str) == str(employee)]
    if sub.empty:
        return set()
    return set(pd.to_datetime(sub["_ts"], errors="coerce").dt.date.dropna().unique())


def _day_status(
    d: date,
    *,
    view_month: date,
    dates_have: set[date],
    selected: date,
    d_lo: date,
    d_hi: date,
    today: date,
) -> str:
    y, m = view_month.year, view_month.month
    in_m = d.month == m and d.year == y
    if not in_m:
        return "pad"
    if d > today:
        return "future"
    if d < d_lo or d > d_hi:
        return "out"
    if d == selected:
        return "selected"
    if d in dates_have:
        return "data"
    return "empty"


def _clamp_view_month(m: date, d_lo: date, d_hi: date) -> date:
    m0 = d_lo.replace(day=1)
    m1 = d_hi.replace(day=1)
    if (m.year, m.month) < (m0.year, m0.month):
        return m0
    if (m.year, m.month) > (m1.year, m1.month):
        return m1
    return m


def _shift_view_month(m: date, delta: int) -> date:
    return (pd.Timestamp(m) + pd.DateOffset(months=delta)).date().replace(day=1)


def _inject_calendar_day_styles(weeks: list[list[date]], view_month: date, **kw) -> None:
    rules: list[str] = []
    for week in weeks:
        for d in week:
            st_key = f"cal_pick_{d.strftime('%Y%m%d')}"
            status = _day_status(d, view_month=view_month, **kw)
            if status == "pad":
                rules.append(
                    f'div.st-key-{st_key} button {{ visibility: hidden !important; pointer-events: none !important; }}'
                )
            elif status == "selected":
                rules.append(
                    f'div.st-key-{st_key} button {{ background: #0284c7 !important; color: #fff !important; '
                    f'border: 2px solid #7dd3fc !important; box-shadow: 0 0 14px rgba(56,189,248,0.55) !important; }}'
                )
            elif status == "data":
                rules.append(
                    f"div.st-key-{st_key} button {{ background: #16a34a !important; color: #fff !important; }}"
                )
            elif status == "empty":
                rules.append(
                    f"div.st-key-{st_key} button {{ background: #dc2626 !important; color: #fff !important; }}"
                )
            else:
                rules.append(
                    f"div.st-key-{st_key} button {{ background: #334155 !important; color: #94a3b8 !important; opacity: 0.55 !important; }}"
                )
    st.markdown(f"<style>{chr(10).join(rules)}</style>", unsafe_allow_html=True)


def _render_date_availability_picker(
    *,
    dates_have: set[date],
    d_lo: date,
    d_hi: date,
) -> None:
    """Colored month grid inside the Date popover (green = data, red = none, blue = selected)."""
    today = date.today()
    vm = _clamp_view_month(st.session_state.avail_cal_month, d_lo, d_hi)
    st.session_state.avail_cal_month = vm
    selected = _active_filter_date()
    y, m = vm.year, vm.month
    weeks = pym_cal.Calendar(firstweekday=0).monthdatescalendar(y, m)

    nav_l, nav_c, nav_r = st.columns([0.35, 4.0, 0.35])
    with nav_l:
        if st.button("◀", key="date_pop_prev", help="Previous month"):
            st.session_state.avail_cal_month = _clamp_view_month(
                _shift_view_month(vm, -1), d_lo, d_hi
            )
            st.rerun()
    with nav_c:
        st.markdown(
            f"<div style='text-align:center;font-weight:600;color:#e2e8f0;font-size:0.9rem'>{vm:%B %Y}</div>",
            unsafe_allow_html=True,
        )
    with nav_r:
        if st.button("▶", key="date_pop_next", help="Next month"):
            st.session_state.avail_cal_month = _clamp_view_month(
                _shift_view_month(vm, 1), d_lo, d_hi
            )
            st.rerun()

    kw = dict(
        dates_have=dates_have,
        selected=selected,
        d_lo=d_lo,
        d_hi=d_hi,
        today=today,
    )
    _inject_calendar_day_styles(weeks, vm, **kw)

    hdr = st.columns(7)
    for col, wd in zip(hdr, ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]):
        with col:
            st.caption(wd)

    for week in weeks:
        cols = st.columns(7)
        for col, d in zip(cols, week):
            with col:
                status = _day_status(d, view_month=vm, **kw)
                if status == "pad":
                    st.write("")
                    continue
                tip = {
                    "data": "GPS data available",
                    "empty": "No GPS data",
                    "selected": "Selected day",
                    "future": "Future date",
                    "out": "Outside loaded exports",
                }.get(status, "")
                if st.button(
                    str(d.day),
                    key=f"cal_pick_{d.strftime('%Y%m%d')}",
                    use_container_width=True,
                    help=tip,
                    disabled=status in ("future", "out"),
                ):
                    _commit_active_date(d)
                    st.rerun()

    st.markdown(
        '<div class="date-pop-legend">'
        '<span><span class="date-pop-dot" style="background:#16a34a"></span>Has data</span>'
        '<span><span class="date-pop-dot" style="background:#dc2626"></span>No data</span>'
        '<span><span class="date-pop-dot" style="background:#0284c7"></span>Selected</span>'
        '<span><span class="date-pop-dot" style="background:#334155"></span>Muted</span>'
        "</div>",
        unsafe_allow_html=True,
    )


def run() -> None:
    st.markdown(TRACKING_PAGE_CSS, unsafe_allow_html=True)
    st.markdown(DASH_EXTRA_CSS, unsafe_allow_html=True)
    st.markdown(RESPONSIVE_DASHBOARD_CSS, unsafe_allow_html=True)

    st.markdown("### Repo Agent Tracking")

    src = punch_data_source_label()
    c_src, c_ref = st.columns([4, 1])
    with c_src:
        if src != "local folder (Data-day-wise/)":
            st.caption(f"Data source: **{src}**")
    with c_ref:
        if st.button("Refresh data", key="trk_refresh", use_container_width=True):
            clear_punch_data_cache()
            st.rerun()

    df = load_punch_data_cached()
    sites_df = load_site_locations(str(sites_data_dir()))

    if df.empty:
        if google_sheet_export_url():
            st.warning("No rows from Google Sheet. Check `.env` URL and sheet column headers.")
        else:
            st.warning(
                "No GPS data. Set `GOOGLE_SHEET_URL` in `.env` or add Excel to `Data-day-wise/`."
            )
        return

    name_col = REQUIRED_COLUMNS["employee_name"]
    scoped = df.copy()
    employees = sorted(scoped[name_col].dropna().unique().tolist())
    if not employees:
        st.warning("No employees in the loaded data.")
        return

    emp_options = [ALL_AGENTS_LABEL] + employees
    tchoices = _time_choices()

    if "committed" not in st.session_state:
        st.session_state.committed = _default_committed(scoped, employees)
    if "flt_widgets_ready" not in st.session_state:
        _sync_widgets_from_committed(st.session_state.committed)
        st.session_state.flt_widgets_ready = True
    if "avail_cal_month" not in st.session_state:
        st.session_state.avail_cal_month = st.session_state.committed["date"].replace(day=1)

    # Keep date widget in sync with committed before rendering filters.
    active_d = _active_filter_date()
    if st.session_state.get("flt_date") != active_d:
        st.session_state.flt_date = active_d
        st.session_state.avail_cal_month = active_d.replace(day=1)

    d_lo = scoped["_ts"].min().date()
    d_hi = scoped["_ts"].max().date()

    st.markdown('<div class="filter-glass filter-toolbar-anchor"></div>', unsafe_allow_html=True)

    def _on_employee_change_calendar() -> None:
        em = st.session_state.flt_employee
        if em == ALL_AGENTS_LABEL:
            return
        dh = _dates_with_pings(scoped, em, name_col)
        if dh:
            st.session_state.avail_cal_month = max(dh).replace(day=1)
        else:
            st.session_state.avail_cal_month = date.today().replace(day=1)

    r1 = st.columns([2.4, 1.2, 1.0, 1.0])
    with r1[0]:
        st.selectbox(
            "Employee",
            options=emp_options,
            key="flt_employee",
            placeholder="Search or select",
            filter_mode="fuzzy",
            on_change=_on_employee_change_calendar,
        )
    with r1[1]:
        emp_pick = st.session_state.flt_employee
        sel_d = _active_filter_date()
        if emp_pick == ALL_AGENTS_LABEL:
            st.date_input(
                "Date",
                min_value=d_lo,
                max_value=d_hi,
                key="flt_date",
                on_change=_on_flt_date_change,
            )
        else:
            dates_have = _dates_with_pings(scoped, emp_pick, name_col)
            with st.popover(f"{sel_d:%Y/%m/%d}", use_container_width=True):
                st.caption("Green = GPS data · Red = no data · Blue = selected")
                _render_date_availability_picker(
                    dates_have=dates_have,
                    d_lo=d_lo,
                    d_hi=d_hi,
                )
    with r1[2]:
        st.selectbox("From time", options=tchoices, key="flt_from")
    with r1[3]:
        st.selectbox("To time", options=tchoices, key="flt_to")

    r2 = st.columns([0.75, 0.75, 0.75, 2.2, 1.1, 1.1])
    with r2[0]:
        st.checkbox("Yards", key="flt_yards")
    with r2[1]:
        st.checkbox("Service", key="flt_service")
    with r2[2]:
        st.checkbox("Stores", key="flt_stores")
    with r2[4]:
        if st.button("Reset filters", use_container_width=True):
            st.session_state.committed = _default_committed(scoped, employees)
            st.session_state.flt_widgets_ready = False
            st.rerun()
    with r2[5]:
        if st.button("Apply filters", type="primary", use_container_width=True):
            st.session_state.committed = _snapshot_from_widgets()
            st.rerun()

    c = st.session_state.committed
    emp = c["employee"]
    sel_date: date = c["date"]
    t_from = _parse_hhmm(c["from"])
    t_to = _parse_hhmm(c["to"])
    show_y, show_sc, show_st = c["yards"], c["service"], c["stores"]

    start_dt = pd.Timestamp.combine(sel_date, t_from)
    end_dt = pd.Timestamp.combine(sel_date, t_to)
    if end_dt < start_dt:
        st.error("End time must be on or after start time.")
        return

    all_mode = emp == ALL_AGENTS_LABEL
    mask = (scoped["_ts"] >= start_dt) & (scoped["_ts"] <= end_dt)
    if all_mode:
        path_df = scoped.loc[mask].copy()
    else:
        path_df = scoped.loc[mask & (scoped[name_col] == emp)].copy()
    path_df = path_df.sort_values([name_col, "_ts"] if all_mode else ["_ts"]).reset_index(drop=True)

    if not all_mode and not path_df.empty:
        cur = compute_movement_analytics(path_df, sites_df)
        prev_day = sel_date - timedelta(days=1)
        prev_df = slice_employee_window(scoped, emp, prev_day, t_from, t_to)
        prev = compute_movement_analytics(prev_df, sites_df)

        st.markdown('<div class="section-title">Primary KPIs</div>', unsafe_allow_html=True)
        d_pct = pct_delta(cur.total_distance_km, prev.total_distance_km)
        d_html = ""
        if d_pct is not None:
            cls = "kpi-delta-pos" if d_pct >= 0 else "kpi-delta-neg"
            d_html = f'<div class="{cls}">vs previous day: {d_pct:+.1f}%</div>'

        grid = "".join(
            [
                _kpi_card("Total distance", f"{cur.total_distance_km:.1f} km", "GPS route length", d_html),
                _kpi_card("Travel time", format_duration(cur.travel_time_seconds), "Time moving"),
                _kpi_card("Stationary / idle", format_duration(cur.stationary_time_seconds), "Low movement"),
                _kpi_card("Stops", str(cur.num_stops), "Dwells ≥ 3 min"),
                _kpi_card("GPS pings", str(cur.gps_pings), "Location captures"),
                _kpi_card("Active hours", f"{cur.active_hours:.2f} h", "First → last ping"),
            ]
        )
        st.markdown(f'<div class="kpi-grid">{grid}</div>', unsafe_allow_html=True)

        st.markdown('<div class="section-title">Operational KPIs</div>', unsafe_allow_html=True)
        ogrid = "".join(
            [
                _kpi_card("Longest stop", format_duration(cur.longest_stop_seconds), "Peak dwell"),
                _kpi_card(
                    "Most visited type",
                    str(cur.most_visited_location_type)[:28],
                    "Within ~350–550 m of site",
                ),
                _kpi_card(
                    "Avg stop duration",
                    format_duration(cur.avg_stop_seconds) if cur.num_stops else "—",
                    "Across stops",
                ),
                _kpi_card("Unique locations", str(cur.unique_locations), "~110 m cells"),
                _kpi_card(
                    "Off-site pings",
                    str(cur.geofence_violations),
                    "> 2.5 km from nearest Y/SC/T",
                ),
            ]
        )
        st.markdown(f'<div class="kpi-grid">{ogrid}</div>', unsafe_allow_html=True)

        # Field operations intelligence (same GPS + site logic as field_ops_analytics — no API).
        fo = compute_field_intelligence(path_df, sites_df)
        prev_fo = compute_field_intelligence(prev_df, sites_df)
        fo_d_pct = pct_delta(fo["productive_time_pct"], prev_fo["productive_time_pct"])
        fo_d_html = ""
        if fo_d_pct is not None:
            cls = "kpi-delta-pos" if fo_d_pct >= 0 else "kpi-delta-neg"
            fo_d_html = f'<div class="{cls}">vs previous day: {fo_d_pct:+.1f}%</div>'

        st.markdown(
            '<div class="section-title">Field operations intelligence</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "On-site vs transit from GPS segments at MFC yards, service centres, and Turno stores."
        )
        sd = fo["stop_distribution"]
        fgrid1 = "".join(
            [
                _kpi_card(
                    "Productive time",
                    f"{fo['productive_time_pct']:.1f} %",
                    "At operational locations ÷ active time",
                    fo_d_html,
                ),
                _kpi_card(
                    "On-site time",
                    format_duration(fo["productive_time_s"]),
                    "Yard / service centre / store",
                ),
                _kpi_card(
                    "Transit time",
                    format_duration(fo["transit_time_s"]),
                    fo["transit_vs_work"]["ratio_label"][:40],
                ),
                _kpi_card(
                    "Operational visits",
                    str(fo["operational_visits"]),
                    "Entries within ~350–550 m of a fixed site",
                ),
                _kpi_card(
                    "Avg visit duration",
                    format_duration(fo["avg_visit_duration_s"]),
                    "On-site time ÷ visits",
                ),
                _kpi_card(
                    "Transit efficiency",
                    f"{fo['transit_efficiency']:.2f}",
                    "Visits ÷ km · " + str(fo["transit_efficiency_label"])[:42],
                ),
            ]
        )
        st.markdown(f'<div class="kpi-grid">{fgrid1}</div>', unsafe_allow_html=True)

        fgrid2 = "".join(
            [
                _kpi_card("Stops under 5 min", str(sd["short"]), "Brief dwells"),
                _kpi_card("Stops 5–20 min", str(sd["medium"]), "Medium dwells"),
                _kpi_card("Stops over 20 min", str(sd["long"]), "Long dwells"),
                _kpi_card(
                    "Unknown / idle (off-site)",
                    format_duration(fo["time_split_s"]["unknown_time_s"]),
                    "Low movement, not at a fixed site",
                ),
            ]
        )
        st.markdown(f'<div class="kpi-grid">{fgrid2}</div>', unsafe_allow_html=True)

        if fo["insights"]:
            st.markdown("**Field operations insights**")
            for line in fo["insights"]:
                st.markdown(f"- {html.escape(str(line))}")

        with st.expander("Time split by location category (minutes)", expanded=False):
            ts = fo["time_split_s"]
            split_rows = [
                {"Category": "Yard", "Minutes": round(ts.get("yard_time_s", 0) / 60, 1)},
                {"Category": "Service", "Minutes": round(ts.get("service_time_s", 0) / 60, 1)},
                {"Category": "Store", "Minutes": round(ts.get("store_time_s", 0) / 60, 1)},
                {"Category": "Transit", "Minutes": round(ts.get("transit_time_s", 0) / 60, 1)},
                {"Category": "Unknown", "Minutes": round(ts.get("unknown_time_s", 0) / 60, 1)},
            ]
            st.dataframe(pd.DataFrame(split_rows), use_container_width=True, hide_index=True)

        rev = fo["revisit_analytics"]["locations"]
        if rev:
            with st.expander("Repeat visits (same fixed site)", expanded=False):
                st.dataframe(
                    pd.DataFrame(rev),
                    use_container_width=True,
                    hide_index=True,
                )

        with st.expander("Hourly utilization (km / seconds)", expanded=False):
            st.dataframe(
                pd.DataFrame(fo["hourly_utilization"]),
                use_container_width=True,
                hide_index=True,
            )

        ic1, ic2 = st.columns(2)
        with ic1:
            st.markdown("**Productivity insights**")
            for line in cur.productivity_notes:
                st.markdown(f"- {html.escape(line)}")
        with ic2:
            st.markdown("**Location visits (pings within ~350–550 m)**")
            vt = pd.DataFrame(
                [{"Site type": k, "Pings": v} for k, v in cur.visit_by_type.items()]
            )
            st.dataframe(vt, use_container_width=True, hide_index=True)

        st.markdown('<div class="section-title">Movement timeline</div>', unsafe_allow_html=True)
        tl = timeline_chart_data(path_df)
        if not tl.empty and len(tl) > 1:
            chart = (
                alt.Chart(tl)
                .mark_line(strokeWidth=2.5, color="#38bdf8")
                .encode(
                    alt.X(
                        "ts:T",
                        title="Time of day",
                        axis=alt.Axis(
                            format="%I:%M %p",
                            labelOverlap=True,
                        ),
                    ),
                    alt.Y("cum_km:Q", title="Cumulative distance (km)"),
                    tooltip=[
                        alt.Tooltip("ts:T", format="%I:%M:%S %p", title="Time"),
                        alt.Tooltip("cum_km:Q", format=".2f", title="km"),
                    ],
                )
                .properties(height=240, background="transparent")
                .configure_axis(
                    labelColor="#94a3b8",
                    titleColor="#cbd5e1",
                    gridColor="#334155",
                    domainColor="#475569",
                )
                .configure_view(strokeWidth=0)
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.caption("Not enough points for a timeline.")

    elif all_mode:
        st.info(
            "Select **one employee** and click **Apply filters** to unlock KPIs, timeline, and productivity analytics. "
            "Map below shows **all agents** for the selected date & time."
        )
    else:
        st.warning("No GPS data for this employee, date, and time window.")

    st.markdown('<div class="section-title">Route map</div>', unsafe_allow_html=True)
    if path_df.empty:
        st.caption("Adjust filters and click **Apply filters**.")
        return

    fmap = build_map(
        path_df,
        all_agents=all_mode,
        sites_df=sites_df,
        show_mfc=show_y,
        show_service=show_sc,
        show_stores=show_st,
    )
    try:
        # returned_objects=[]: do not sync zoom/pan/clicks back to Streamlit — avoids a full
        # script rerun on every map interaction (see streamlit_folium st_folium docs).
        st_folium(
            fmap,
            use_container_width=True,
            height=520,
            key="tracking_map",
            returned_objects=[],
        )
    except Exception as e:
        st.error(f"Map could not be displayed: {e}")


run()
