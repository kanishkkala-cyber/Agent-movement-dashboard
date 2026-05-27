"""Daily Operations Overview — leadership command center (all employees, one day)."""

from __future__ import annotations

import html
from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from core import (
    clear_punch_data_cache,
    google_sheet_export_url,
    load_punch_data_cached,
    load_site_locations,
    punch_data_source_label,
    sites_data_dir,
)
from daily_overview_analytics import compute_daily_overview, enrich_metadata_columns
from responsive_ui import RESPONSIVE_DASHBOARD_CSS

OVERVIEW_CSS = """
<style>
.filter-glass {
  position: sticky;
  top: 0.35rem;
  z-index: 40;
  background: rgba(30,41,59,0.75);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border: 1px solid rgba(148,163,184,0.22);
  border-radius: 18px;
  padding: 0;
  margin-bottom: 0.5rem;
  box-shadow: 0 10px 40px rgba(0,0,0,0.35);
}
/* Visual panel around filter rows immediately after anchor */
div.filter-toolbar-anchor + div[data-testid="stVerticalBlock"] {
  background: rgba(30,41,59,0.75);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border: 1px solid rgba(148,163,184,0.22);
  border-radius: 18px;
  padding: 0.85rem 1rem 0.95rem 1rem;
  margin-bottom: 1rem;
  box-shadow: 0 10px 40px rgba(0,0,0,0.35);
}
.exec-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
  margin: 0.75rem 0 1.25rem 0;
}
.exec-kpi {
  background: linear-gradient(145deg, rgba(51,65,85,0.45) 0%, rgba(15,23,42,0.95) 100%);
  border: 1px solid rgba(148,163,184,0.14);
  border-radius: 14px;
  padding: 0.85rem 0.95rem;
  box-shadow: 0 0 24px rgba(56,189,248,0.06);
  transition: transform 0.15s ease, border-color 0.15s ease;
}
.exec-kpi:hover { transform: translateY(-2px); border-color: rgba(56,189,248,0.35); }
.exec-kpi .lbl { font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.12em; color: #94a3b8; font-weight: 600; }
.exec-kpi .val { font-size: 1.35rem; font-weight: 700; color: #f8fafc; margin-top: 0.25rem; }
.exec-kpi .sub { font-size: 0.72rem; color: #64748b; margin-top: 0.15rem; }
.section-h {
  font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.16em;
  color: #64748b; font-weight: 700; margin: 1.5rem 0 0.65rem 0;
}
.insight-card {
  background: rgba(30,41,59,0.65);
  border-left: 3px solid #38bdf8;
  border-radius: 0 10px 10px 0;
  padding: 0.65rem 0.9rem;
  margin-bottom: 0.45rem;
  color: #cbd5e1;
  font-size: 0.88rem;
}
.alert-center-panel {
  background: linear-gradient(160deg, rgba(15,23,42,0.92) 0%, rgba(30,41,59,0.55) 100%);
  border: 1px solid rgba(148,163,184,0.2);
  border-radius: 18px;
  padding: 1rem 1.15rem 1.1rem 1.15rem;
  margin: 0.5rem 0 1.5rem 0;
  box-shadow: 0 0 32px rgba(56,189,248,0.08);
}
.alert-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 8px;
  margin-bottom: 1rem;
}
.alert-sum-card {
  border-radius: 12px;
  padding: 0.65rem 0.75rem;
  border: 1px solid rgba(148,163,184,0.15);
  background: rgba(15,23,42,0.6);
}
.alert-sum-card .n { font-size: 1.4rem; font-weight: 700; color: #f8fafc; }
.alert-sum-card .l { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.1em; color: #94a3b8; }
.alert-card {
  border-radius: 12px;
  padding: 0.75rem 0.9rem;
  margin-bottom: 0.5rem;
  background: rgba(30,41,59,0.55);
  border-left: 4px solid #64748b;
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}
.alert-card:hover { transform: translateX(3px); box-shadow: 0 4px 20px rgba(0,0,0,0.25); }
.alert-card.sev-critical { border-left-color: #f87171; box-shadow: 0 0 18px rgba(248,113,113,0.12); }
.alert-card.sev-warning { border-left-color: #fb923c; box-shadow: 0 0 18px rgba(251,146,60,0.1); }
.alert-card.sev-mild { border-left-color: #facc15; }
.alert-card.sev-positive { border-left-color: #4ade80; box-shadow: 0 0 18px rgba(74,222,128,0.1); }
.alert-card .atitle { font-weight: 600; color: #f1f5f9; font-size: 0.9rem; }
.alert-card .amsg { color: #94a3b8; font-size: 0.8rem; margin-top: 0.2rem; }
.alert-card .ameta { font-size: 0.68rem; color: #64748b; margin-top: 0.35rem; text-transform: uppercase; letter-spacing: 0.06em; }
.alert-badge {
  display: inline-block; font-size: 0.62rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.08em; padding: 0.15rem 0.45rem; border-radius: 6px; margin-right: 0.35rem;
}
.alert-badge.critical { background: rgba(248,113,113,0.2); color: #fca5a5; }
.alert-badge.warning { background: rgba(251,146,60,0.2); color: #fdba74; }
.alert-badge.mild { background: rgba(250,204,21,0.15); color: #fde047; }
.alert-badge.positive { background: rgba(74,222,128,0.15); color: #86efac; }
.alert-badge.neutral { background: rgba(148,163,184,0.12); color: #94a3b8; border: 1px solid rgba(148,163,184,0.2); }
.alert-card.sev-neutral { border-left-color: #475569; opacity: 0.7; }
.alert-sum-card.neutral-card { border-color: rgba(148,163,184,0.12); }
.alert-insight {
  border-left: 2px solid #38bdf8;
  background: rgba(30,41,59,0.5);
  border-radius: 0 8px 8px 0;
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.35rem;
  font-size: 0.84rem;
  color: #cbd5e1;
}
.alert-trend-bar {
  font-size: 0.75rem;
  color: #94a3b8;
  margin-bottom: 0.75rem;
  padding: 0.45rem 0.65rem;
  border-radius: 10px;
  background: rgba(15,23,42,0.65);
  border: 1px solid rgba(148,163,184,0.12);
}
.alert-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 8px;
  background: rgba(51,65,85,0.6);
  margin-right: 0.5rem;
  font-size: 1rem;
}
</style>
"""


def _fmt_dur(sec: float) -> str:
    if sec < 60:
        return f"{int(sec)}s"
    m, s = divmod(int(sec), 60)
    if m < 60:
        return f"{m}m"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


@st.cache_data(show_spinner=False)
def _filter_options() -> tuple[list[str], list[str]]:
    df = load_punch_data_cached()
    if df.empty:
        return [], []
    df = enrich_metadata_columns(df)
    return (
        sorted(df["_team"].dropna().astype(str).unique().tolist()),
        sorted(df["_region"].dropna().astype(str).unique().tolist()),
    )


@st.cache_data(show_spinner=False)
def _cached_overview(
    sites_folder: str,
    day_iso: str,
    teams: tuple[str, ...],
    regions: tuple[str, ...],
    loc_types: tuple[str, ...],
    search: str,
) -> dict:
    df = load_punch_data_cached()
    sites = load_site_locations(sites_folder)
    d = date.fromisoformat(day_iso)
    return compute_daily_overview(
        df,
        d,
        sites,
        teams=list(teams) if teams else None,
        regions=list(regions) if regions else None,
        location_types=list(loc_types) if loc_types else None,
        employee_search=search,
    )


def _drill_to_tracking(employee: str, sel_date: date) -> None:
    st.session_state.committed = {
        "employee": employee,
        "date": sel_date,
        "from": "00:00",
        "to": "23:59",
        "yards": True,
        "service": True,
        "stores": True,
    }
    st.session_state.flt_widgets_ready = False
    st.switch_page("tracking.py")


def _render_alert_center(ac: dict, sel_date: date) -> None:
    alerts = ac.get("alerts") or []
    summary = ac.get("summary") or {}
    insights = ac.get("smart_insights") or []
    trends = ac.get("trends")
    st.markdown('<div class="section-h">Operations Alert Center</div>', unsafe_allow_html=True)
    st.markdown('<div class="alert-center-panel">', unsafe_allow_html=True)

    n_insuff = summary.get("insufficient_data", 0)
    insuff_cell = (
        f'<div class="alert-sum-card neutral-card">'
        f'<div class="n" style="color:#64748b">{n_insuff}</div>'
        f'<div class="l">Insufficient data</div></div>'
    ) if n_insuff > 0 else ""
    sum_html = f"""
    <div class="alert-summary-grid">
      <div class="alert-sum-card"><div class="n">{summary.get('total', 0)}</div><div class="l">Actionable alerts</div></div>
      <div class="alert-sum-card"><div class="n" style="color:#f87171">{summary.get('critical', 0)}</div><div class="l">Critical</div></div>
      <div class="alert-sum-card"><div class="n" style="color:#fb923c">{summary.get('warning', 0)}</div><div class="l">Warning</div></div>
      <div class="alert-sum-card"><div class="n" style="color:#fde047">{summary.get('mild', 0)}</div><div class="l">Mild</div></div>
      <div class="alert-sum-card"><div class="n" style="color:#86efac">{summary.get('positive', 0)}</div><div class="l">Positive</div></div>
      {insuff_cell}
    </div>
    """
    st.markdown(sum_html, unsafe_allow_html=True)

    if trends:
        td = trends
        st.markdown(
            f'<div class="alert-trend-bar">vs {html.escape(str(td.get("previous_day", "")))}: '
            f'Critical <strong>{td.get("critical_delta", 0):+d}</strong> · '
            f'Warning <strong>{td.get("warning_delta", 0):+d}</strong> · '
            f'Positive <strong>{td.get("positive_delta", 0):+d}</strong> · '
            f'Total <strong>{td.get("total_delta", 0):+d}</strong></div>',
            unsafe_allow_html=True,
        )

    for line in insights:
        st.markdown(f'<div class="alert-insight">{html.escape(line)}</div>', unsafe_allow_html=True)

    if not alerts:
        st.caption("No operational alerts for this date and filter set.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    teams_in = sorted({a.get("team") or "Unassigned" for a in alerts if a.get("employee")})
    regions_in = sorted({a.get("region") or "Unassigned" for a in alerts if a.get("employee")})
    types_in = ac.get("alert_types") or sorted({a["type"] for a in alerts})

    st.markdown('<div class="ac-filter-anchor"></div>', unsafe_allow_html=True)
    af1 = st.columns([1.2, 1.3, 1.4])
    with af1[0]:
        sev_f = st.multiselect(
            "Severity",
            options=["critical", "warning", "mild", "positive", "neutral"],
            default=["critical", "warning", "mild", "positive"],
            key="ac_severity",
        )
    with af1[1]:
        type_f = st.multiselect("Alert type", options=types_in, default=[], key="ac_type", placeholder="All types")
    with af1[2]:
        team_f = st.multiselect("Team", options=teams_in, default=[], key="ac_team", placeholder="All teams")
    af2 = st.columns([1.4, 1.0])
    with af2[0]:
        region_f = st.multiselect("Region", options=regions_in, default=[], key="ac_region", placeholder="All regions")
    with af2[1]:
        sort_f = st.selectbox(
            "Sort by",
            options=["severity", "impact", "employee", "timestamp"],
            key="ac_sort",
        )

    filtered = alerts
    if sev_f:
        filtered = [a for a in filtered if a["severity"] in sev_f]
    if type_f:
        filtered = [a for a in filtered if a["type"] in type_f]
    if team_f:
        filtered = [a for a in filtered if a.get("team") in team_f or not a.get("employee")]
    if region_f:
        filtered = [a for a in filtered if a.get("region") in region_f or not a.get("employee")]

    if sort_f == "impact":
        filtered = sorted(filtered, key=lambda a: -a.get("impact_score", 0))
    elif sort_f == "employee":
        filtered = sorted(filtered, key=lambda a: (a.get("employee") or "zzz", -a.get("severity_rank", 0)))
    elif sort_f == "timestamp":
        filtered = sorted(
            filtered,
            key=lambda a: (a.get("timestamp", ""), -a.get("severity_rank", 0)),
            reverse=True,
        )
    else:
        filtered = sorted(filtered, key=lambda a: (-a.get("severity_rank", 0), -a.get("impact_score", 0)))

    st.caption(f"Showing {len(filtered)} of {len(alerts)} alerts")

    if "ac_expanded" not in st.session_state:
        st.session_state.ac_expanded = None

    for a in filtered[:40]:
        sev = a["severity"]
        emp = a.get("employee") or "Fleet insight"
        icon = html.escape(a.get("icon", "◆"))
        badge = f'<span class="alert-badge {sev}">{html.escape(a.get("severity_label", sev))}</span>'
        trend = a.get("trend", "")
        trend_b = ""
        if trend and trend not in ("recurring",):
            trend_b = f' <span class="alert-badge mild">{html.escape(trend)}</span>'
        metrics_s = ", ".join(
            f"{k}: {round(v, 1) if isinstance(v, float) else v}"
            for k, v in (a.get("metrics") or {}).items()
        )
        details_html = ""
        if st.session_state.ac_expanded == a["id"]:
            for d in a.get("details") or []:
                details_html += f'<div class="amsg" style="margin-left:1rem">› {html.escape(d)}</div>'
        st.markdown(
            f'<div class="alert-card sev-{sev}">'
            f'<span class="alert-icon">{icon}</span>{badge}{trend_b}'
            f'<span class="atitle">{html.escape(a.get("title", ""))}</span>'
            f'<div class="amsg"><strong>{html.escape(emp)}</strong> — {html.escape(a.get("message", ""))}</div>'
            f'<div class="ameta">{html.escape(a.get("type_label", a.get("type", "")))}'
            f'{(" · " + html.escape(metrics_s)) if metrics_s else ""}'
            f' · impact {a.get("impact_score", 0):.0f}</div>{details_html}</div>',
            unsafe_allow_html=True,
        )
        c_exp, c_drill = st.columns([1, 1])
        with c_exp:
            if st.button("Details", key=f"ac_exp_{a['id']}", use_container_width=True):
                st.session_state.ac_expanded = (
                    None if st.session_state.ac_expanded == a["id"] else a["id"]
                )
                st.rerun()
        with c_drill:
            if a.get("employee"):
                if st.button(
                    f"Open {a['employee'][:22]}",
                    key=f"ac_drill_{a['id']}",
                    use_container_width=True,
                ):
                    _drill_to_tracking(a["employee"], sel_date)

    if len(filtered) > 40:
        st.caption(f"… and {len(filtered) - 40} more alerts (narrow filters to see all).")

    st.markdown("</div>", unsafe_allow_html=True)


def _default_day(df: pd.DataFrame) -> date:
    if df.empty:
        return date.today()
    return pd.to_datetime(df["_ts"]).max().date()


def run() -> None:
    st.markdown(OVERVIEW_CSS, unsafe_allow_html=True)
    st.markdown(RESPONSIVE_DASHBOARD_CSS, unsafe_allow_html=True)
    st.markdown("### Daily Operations Overview")

    sites_folder = str(sites_data_dir())
    src = punch_data_source_label()
    sheet_url = google_sheet_export_url()

    hdr_l, hdr_r = st.columns([4, 1])
    with hdr_l:
        if sheet_url:
            st.caption(f"Data source: **{src}** · Update your sheet anytime, then click Refresh.")
    with hdr_r:
        if st.button("Refresh data", use_container_width=True):
            clear_punch_data_cache()
            _filter_options.clear()
            _cached_overview.clear()
            st.rerun()

    raw = load_punch_data_cached()
    if raw.empty:
        if sheet_url:
            st.warning(
                "No rows loaded from Google Sheet. Check GOOGLE_SHEET_URL in `.env`, "
                "sheet sharing (Anyone with link → Viewer), and column headers "
                "(Employee Name, Time Stamp, Latitude, Longitude)."
            )
        else:
            st.warning(
                "No GPS data found. Set `GOOGLE_SHEET_URL` in `.env` to your published sheet, "
                "or place Excel files in `Data-day-wise/`."
            )
        return

    d_lo = raw["_ts"].min().date()
    d_hi = raw["_ts"].max().date()
    team_opts, region_opts = _filter_options()

    if "do_committed" not in st.session_state:
        st.session_state.do_committed = {
            "date": _default_day(raw),
            "teams": [],
            "regions": [],
            "loc_types": [],
            "search": "",
        }

    if "do_filter_synced" not in st.session_state:
        st.session_state.do_date = st.session_state.do_committed["date"]
        st.session_state.do_filter_synced = True

    def _on_do_date_change() -> None:
        dc = dict(st.session_state.do_committed)
        dc["date"] = st.session_state.do_date
        st.session_state.do_committed = dc
        _filter_options.clear()
        _cached_overview.clear()

    st.markdown('<div class="filter-glass filter-toolbar-anchor"></div>', unsafe_allow_html=True)
    fc1 = st.columns([1.1, 1.35, 1.35, 1.5])
    with fc1[0]:
        st.date_input(
            "Date",
            min_value=d_lo,
            max_value=d_hi,
            key="do_date",
            on_change=_on_do_date_change,
        )
    with fc1[1]:
        st.multiselect("Team", options=team_opts, key="do_teams", placeholder="All teams")
    with fc1[2]:
        st.multiselect("Region", options=region_opts, key="do_regions", placeholder="All regions")
    with fc1[3]:
        st.multiselect(
            "Location type",
            options=["yard", "service", "store"],
            key="do_loc_types",
            placeholder="All types",
        )
    fc2 = st.columns([3.2, 0.85, 0.85])
    with fc2[0]:
        st.text_input("Employee search", key="do_search", placeholder="Name contains…")
    with fc2[1]:
        if st.button("Reset", use_container_width=True):
            st.session_state.do_committed = {
                "date": _default_day(raw),
                "teams": [],
                "regions": [],
                "loc_types": [],
                "search": "",
            }
            st.session_state.do_date = st.session_state.do_committed["date"]
            st.session_state.do_teams = []
            st.session_state.do_regions = []
            st.session_state.do_loc_types = []
            st.session_state.do_search = ""
            _filter_options.clear()
            _cached_overview.clear()
            st.rerun()
    with fc2[2]:
        if st.button("Apply", type="primary", use_container_width=True):
            st.session_state.do_committed = {
                "date": st.session_state.do_date,
                "teams": list(st.session_state.do_teams),
                "regions": list(st.session_state.do_regions),
                "loc_types": list(st.session_state.do_loc_types),
                "search": st.session_state.do_search.strip(),
            }
            st.rerun()

    dc = st.session_state.do_committed
    payload = _cached_overview(
        sites_folder,
        dc["date"].isoformat(),
        tuple(dc["teams"]),
        tuple(dc["regions"]),
        tuple(dc["loc_types"]),
        dc["search"],
    )

    k = payload["executive_kpis"]
    cards = [
        ("Active employees", str(k["active_employees"]), f"of {k['total_employees']} in view"),
        ("Total distance", f"{k['total_distance_km']:.1f} km", "Fleet movement"),
        ("Operational visits", str(k["total_operational_visits"]), "Fixed-site entries"),
        ("Avg productive %", f"{k['avg_productive_time_pct']:.1f}%", "On-site vs active"),
        ("Avg transit", f"{k['avg_transit_hours']:.2f} h", "Between pings"),
        ("Avg active hours", f"{k['avg_active_hours']:.2f} h", "First → last ping"),
        ("GPS pings", str(k["total_gps_pings"]), "Location captures"),
        ("Avg visit", _fmt_dur(k["avg_visit_duration_s"]), "Per operational visit"),
        ("Top performer", str(k["top_performer"])[:22], f"Score {k['top_performer_score']:.0f}"),
        ("Lowest activity", str(k["lowest_activity"])[:22], f"{k['lowest_activity_hours']:.2f} h active"),
    ]
    grid = "".join(
        f'<div class="exec-kpi"><div class="lbl">{html.escape(a)}</div>'
        f'<div class="val">{html.escape(b)}</div><div class="sub">{html.escape(c)}</div></div>'
        for a, b, c in cards
    )
    st.markdown(f'<div class="exec-kpi-grid">{grid}</div>', unsafe_allow_html=True)

    _render_alert_center(payload.get("alert_center") or {}, dc["date"])

    st.markdown('<div class="section-h">Employee leaderboard</div>', unsafe_allow_html=True)
    lb = payload["leaderboard"]
    if not lb:
        st.info("No rows for this date / filters.")
    else:
        df_lb = pd.DataFrame(lb)
        show_cols = [
            "rank",
            "employee",
            "team",
            "region",
            "distance_km",
            "productive_time_pct",
            "operational_visits",
            "active_hours",
            "transit_time_s",
            "avg_visit_duration_s",
            "unique_locations",
            "efficiency_score",
            "performance_tier",
        ]
        df_show = df_lb[[c for c in show_cols if c in df_lb.columns]].copy()
        df_show["transit_time_s"] = df_show["transit_time_s"].apply(_fmt_dur)
        df_show["avg_visit_duration_s"] = df_show["avg_visit_duration_s"].apply(_fmt_dur)

        ev = st.dataframe(
            df_show,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="do_leaderboard",
        )

        sel_rows = []
        if hasattr(ev, "selection") and ev.selection is not None:
            sel_rows = ev.selection.get("rows", []) if hasattr(ev.selection, "get") else []

        a1, a2, a3 = st.columns([1.2, 1.2, 2])
        with a1:
            drill = st.button("Open employee detail view", type="primary", use_container_width=True)
        with a2:
            csv = df_show.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download leaderboard CSV",
                data=csv,
                file_name=f"leaderboard_{payload['day']}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        if drill and sel_rows:
            idx = sel_rows[0]
            emp = df_lb.iloc[idx]["employee"]
            _drill_to_tracking(emp, dc["date"])

    col_l, col_r = st.columns(2)
    pdist = payload["productivity_distribution"]
    with col_l:
        st.markdown('<div class="section-h">Productivity distribution</div>', unsafe_allow_html=True)
        pie_df = pd.DataFrame(
            [
                {"band": "High", "n": pdist["high"]},
                {"band": "Medium", "n": pdist["medium"]},
                {"band": "Low", "n": pdist["low"]},
            ]
        )
        if pie_df["n"].sum() > 0:
            ch = (
                alt.Chart(pie_df)
                .mark_arc(innerRadius=50)
                .encode(
                    theta="n:Q",
                    color=alt.Color("band:N", scale=alt.Scale(range=["#4ade80", "#fbbf24", "#f87171"])),
                    tooltip=["band", "n"],
                )
                .properties(height=220)
            )
            st.altair_chart(ch, use_container_width=True)

    with col_r:
        st.markdown('<div class="section-h">Movement distance bands</div>', unsafe_allow_html=True)
        md = payload["movement_distribution"]
        mdf = pd.DataFrame(
            [{"band": k, "n": v} for k, v in md.items()]
        )
        if mdf["n"].sum() > 0:
            ch2 = (
                alt.Chart(mdf)
                .mark_bar(cornerRadiusEnd=6)
                .encode(
                    x=alt.X("band:N", title=""),
                    y=alt.Y("n:Q", title="Employees"),
                    color=alt.value("#38bdf8"),
                )
                .properties(height=220)
            )
            st.altair_chart(ch2, use_container_width=True)

    t1, t2 = st.columns(2)
    with t1:
        st.markdown('<div class="section-h">Top performers</div>', unsafe_allow_html=True)
        for r in payload["top_performers"]:
            st.markdown(
                f"**{html.escape(r['employee'])}** — {r['productive_time_pct']:.0f}% productive · "
                f"{r['operational_visits']} visits · {r['distance_km']:.1f} km"
            )
    with t2:
        st.markdown('<div class="section-h">Lowest activity</div>', unsafe_allow_html=True)
        for r in payload["bottom_performers"]:
            st.markdown(
                f"**{html.escape(r['employee'])}** — {r['active_hours']:.2f} h active · "
                f"{r['distance_km']:.1f} km · {r['productive_time_pct']:.0f}% productive"
            )

    st.markdown('<div class="section-h">Team comparison</div>', unsafe_allow_html=True)
    tc = payload["team_comparison"]
    if tc:
        tdf = pd.DataFrame(tc)
        ch3 = (
            alt.Chart(tdf)
            .mark_bar()
            .encode(
                y=alt.Y("team:N", sort="-x"),
                x=alt.X("avg_productive_pct:Q", title="Avg productive %"),
                color=alt.Color("avg_productive_pct:Q", scale=alt.Scale(scheme="blues")),
                tooltip=["team", "employees", "distance_km", "visits", "avg_productive_pct"],
            )
            .properties(height=max(180, len(tc) * 28))
        )
        st.altair_chart(ch3, use_container_width=True)

    st.markdown('<div class="section-h">Hourly operations heatmap</div>', unsafe_allow_html=True)
    hourly = pd.DataFrame(payload["hourly_operations"])
    if not hourly.empty:
        hm = hourly.melt(id_vars=["hour"], var_name="metric", value_name="value")
        ch4 = (
            alt.Chart(hm)
            .mark_rect()
            .encode(
                x=alt.X("hour:O", title="Hour"),
                y=alt.Y("metric:N", title=""),
                color=alt.Color("value:Q", scale=alt.Scale(scheme="blues")),
                tooltip=["hour", "metric", "value"],
            )
            .properties(height=120)
        )
        st.altair_chart(ch4, use_container_width=True)

    st.markdown('<div class="section-h">Location time breakdown (fleet total)</div>', unsafe_allow_html=True)
    loc = payload["location_breakdown_s"]
    if loc:
        ldf = pd.DataFrame(
            [
                {"type": "Yard", "minutes": loc.get("yard_s", 0) / 60},
                {"type": "Service", "minutes": loc.get("service_s", 0) / 60},
                {"type": "Store", "minutes": loc.get("store_s", 0) / 60},
                {"type": "Transit", "minutes": loc.get("transit_s", 0) / 60},
                {"type": "Unknown", "minutes": loc.get("unknown_s", 0) / 60},
            ]
        )
        ch5 = (
            alt.Chart(ldf)
            .mark_bar()
            .encode(
                x=alt.X("type:N", sort="-y"),
                y=alt.Y("minutes:Q"),
                color=alt.Color("type:N", legend=None),
            )
            .properties(height=200)
        )
        st.altair_chart(ch5, use_container_width=True)

    if payload["region_analytics"]:
        st.markdown('<div class="section-h">Region / territory</div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(payload["region_analytics"]), use_container_width=True, hide_index=True)

    st.markdown('<div class="section-h">Daily operational insights</div>', unsafe_allow_html=True)
    for line in payload["insights"]:
        st.markdown(f'<div class="insight-card">{html.escape(line)}</div>', unsafe_allow_html=True)


run()
