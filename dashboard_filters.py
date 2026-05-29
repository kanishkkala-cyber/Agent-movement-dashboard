"""Centralized filter state for Streamlit dashboard pages."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from core import ALL_AGENTS_LABEL, REQUIRED_COLUMNS

# --- Tracking (Repo Agent Tracking) ---

TRACKING_COMMITTED = "committed"
TRACKING_WIDGETS_READY = "flt_widgets_ready"
TRACKING_PRESERVE_DATE = "tracking_preserve_date_on_load"
TRACKING_LAST_COMMITTED = "_trk_last_committed"


def tracking_filter_defaults(
    *,
    employee: str,
    sel_date: date,
    time_from: str = "00:00",
    time_to: str = "23:59",
    yards: bool = True,
    service: bool = True,
    stores: bool = True,
) -> dict[str, Any]:
    return {
        "employee": employee,
        "date": sel_date,
        "from": time_from,
        "to": time_to,
        "yards": yards,
        "service": service,
        "stores": stores,
    }


def tracking_sync_widgets(committed: dict[str, Any]) -> None:
    """Push committed filters into widget keys (call before widgets render)."""
    st.session_state.flt_employee = committed["employee"]
    st.session_state.flt_date = committed["date"]
    st.session_state.flt_from = committed["from"]
    st.session_state.flt_to = committed["to"]
    st.session_state.flt_yards = committed["yards"]
    st.session_state.flt_service = committed["service"]
    st.session_state.flt_stores = committed["stores"]
    st.session_state.avail_cal_month = committed["date"].replace(day=1)


def tracking_snapshot_from_widgets() -> dict[str, Any]:
    return {
        "employee": st.session_state.flt_employee,
        "date": st.session_state.flt_date,
        "from": st.session_state.flt_from,
        "to": st.session_state.flt_to,
        "yards": st.session_state.flt_yards,
        "service": st.session_state.flt_service,
        "stores": st.session_state.flt_stores,
    }


def tracking_fingerprint(c: dict[str, Any]) -> str:
    d = c["date"]
    d_s = d.isoformat() if isinstance(d, date) else str(d)
    return (
        f"{c.get('employee', '')}|{d_s}|{c.get('from', '')}|{c.get('to', '')}|"
        f"{int(bool(c.get('yards')))}{int(bool(c.get('service')))}{int(bool(c.get('stores')))}"
    )


def tracking_dates_with_pings(scoped: pd.DataFrame, employee: str) -> set[date]:
    name_col = REQUIRED_COLUMNS["employee_name"]
    sub = scoped.loc[scoped[name_col].astype(str) == str(employee)]
    if sub.empty:
        return set()
    return set(pd.to_datetime(sub["_ts"], errors="coerce").dt.date.dropna().unique())


def tracking_resolve_filters(scoped: pd.DataFrame) -> dict[str, Any]:
    """
  Single source of truth after filter widgets render.
  Syncs widget → committed, optionally snaps date when employee changes.
  """
    c = tracking_snapshot_from_widgets()
    emp = str(c["employee"])

    preserve_date = st.session_state.pop(TRACKING_PRESERVE_DATE, False)
    prev = st.session_state.get(TRACKING_LAST_COMMITTED)

    if (
        not preserve_date
        and emp != ALL_AGENTS_LABEL
        and prev is not None
        and prev.get("employee") != emp
    ):
        dh = tracking_dates_with_pings(scoped, emp)
        if dh and c["date"] not in dh:
            c["date"] = max(dh)
            st.session_state.flt_date = c["date"]
            st.session_state.avail_cal_month = c["date"].replace(day=1)

    st.session_state[TRACKING_COMMITTED] = c
    st.session_state[TRACKING_LAST_COMMITTED] = dict(c)
    return c


def tracking_commit_date(d: date) -> None:
    st.session_state.flt_date = d
    c = dict(st.session_state.get(TRACKING_COMMITTED) or tracking_snapshot_from_widgets())
    c["date"] = d
    st.session_state[TRACKING_COMMITTED] = c
    st.session_state[TRACKING_LAST_COMMITTED] = dict(c)
    st.session_state.avail_cal_month = d.replace(day=1)


def tracking_commit_from_widgets() -> None:
    """Immediate commit on widget change (on_change callbacks)."""
    c = tracking_snapshot_from_widgets()
    st.session_state[TRACKING_COMMITTED] = c
    st.session_state[TRACKING_LAST_COMMITTED] = dict(c)


def _resolve_employee_name(name: str, employees: list[str]) -> str:
    name = str(name).strip()
    if name in employees:
        return name
    lower = name.lower()
    for e in employees:
        if e.lower() == lower:
            return e
    return name


def drill_to_tracking(employee: str, sel_date: date) -> None:
    """Navigate to Repo Agent Tracking with employee + date pre-selected."""
    from core import load_punch_data_cached, REQUIRED_COLUMNS

    df = load_punch_data_cached()
    employees: list[str] = []
    if not df.empty:
        col = REQUIRED_COLUMNS["employee_name"]
        employees = sorted(df[col].dropna().astype(str).unique().tolist())
    emp = _resolve_employee_name(employee, employees) if employees else str(employee).strip()

    st.session_state[TRACKING_COMMITTED] = tracking_filter_defaults(
        employee=emp,
        sel_date=sel_date,
    )
    st.session_state[TRACKING_PRESERVE_DATE] = True
    st.session_state[TRACKING_WIDGETS_READY] = False
    st.session_state.pop(TRACKING_LAST_COMMITTED, None)
    st.switch_page("tracking.py")


# --- Daily Operations Overview ---

OVERVIEW_COMMITTED = "do_committed"
OVERVIEW_FILTER_SYNCED = "do_filter_synced"


def overview_snapshot_from_widgets() -> dict[str, Any]:
    return {
        "date": st.session_state.do_date,
        "teams": list(st.session_state.do_teams),
        "regions": list(st.session_state.do_regions),
        "loc_types": list(st.session_state.do_loc_types),
        "search": st.session_state.do_search.strip(),
    }


def overview_sync_widgets(committed: dict[str, Any]) -> None:
    st.session_state.do_date = committed["date"]
    st.session_state.do_teams = list(committed["teams"])
    st.session_state.do_regions = list(committed["regions"])
    st.session_state.do_loc_types = list(committed["loc_types"])
    st.session_state.do_search = committed["search"]


def overview_resolve_filters() -> dict[str, Any]:
    c = overview_snapshot_from_widgets()
    st.session_state[OVERVIEW_COMMITTED] = c
    return c


def overview_on_filter_change() -> None:
    overview_resolve_filters()
