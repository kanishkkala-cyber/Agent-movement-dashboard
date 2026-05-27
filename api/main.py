"""FastAPI service for the Field Operations Dashboard (React). GPS remains source of truth."""

from __future__ import annotations

import os
import sys
from datetime import date, time

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# Project root (parent of api/)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from field_ops_analytics import (  # noqa: E402
    build_route_geometry,
    compute_field_intelligence,
    compute_leaderboard_rows,
)
from core import (  # noqa: E402
    REQUIRED_COLUMNS,
    load_folder_raw,
    load_site_locations_raw,
    punch_data_dir,
    sites_data_dir,
)
from analytics import slice_employee_window  # noqa: E402
from daily_overview_analytics import compute_daily_overview, enrich_metadata_columns  # noqa: E402

app = FastAPI(title="Field Operations API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _parse_hhmm(s: str) -> time:
    parts = s.strip().split(":")
    if len(parts) < 2:
        raise ValueError("expected HH:MM")
    h, m = int(parts[0]), int(parts[1])
    if h == 23 and m == 59:
        return time(23, 59, 59)
    return time(h, m, 0)


def _sites_payload(sites_df: pd.DataFrame) -> list[dict]:
    if sites_df is None or sites_df.empty:
        return []
    out = []
    for _, r in sites_df.iterrows():
        out.append(
            {
                "lat": float(r["latitude"]),
                "lon": float(r["longitude"]),
                "name": str(r.get("name", ""))[:120],
                "site_type": str(r.get("site_type", "")),
            }
        )
    return out


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/meta")
def meta(day: date = Query(..., description="Calendar day (YYYY-MM-DD)")):
    folder = str(punch_data_dir())
    df = load_folder_raw(folder)
    if df.empty:
        return {"dates": [], "employees": [], "day": str(day)}
    ts = pd.to_datetime(df["_ts"])
    name_col = REQUIRED_COLUMNS["employee_name"]
    m = ts.dt.date == day
    sub = df.loc[m, name_col].dropna().astype(str).unique().tolist()
    dates = sorted(ts.dt.date.dropna().unique().tolist(), reverse=True)[:60]
    return {
        "day": str(day),
        "dates": [str(d) for d in dates],
        "employees": sorted(set(sub)),
    }


@app.get("/api/field-dashboard")
def field_dashboard(
    day: date = Query(...),
    time_from: str = Query("00:00", alias="from"),
    time_to: str = Query("23:59", alias="to"),
    employee: str = Query(..., description="Employee name or __all__"),
):
    try:
        t_from = _parse_hhmm(time_from)
        t_to = _parse_hhmm(time_to)
    except Exception as e:
        raise HTTPException(400, f"Invalid time: {e}") from e

    folder = str(punch_data_dir())
    sites_folder = str(sites_data_dir())
    full_df = load_folder_raw(folder)
    sites_df = load_site_locations_raw(sites_folder)
    if full_df.empty:
        raise HTTPException(404, "No punch data in Data-day-wise/")

    leaderboard = compute_leaderboard_rows(full_df, day, t_from, t_to, sites_df)

    if employee == "__all__":
        return {
            "day": str(day),
            "time_from": time_from,
            "time_to": time_to,
            "employee": "__all__",
            "intelligence": None,
            "route": None,
            "route_note": "Select a single agent to load route replay, movement intelligence, and hourly analytics.",
            "sites": _sites_payload(sites_df),
            "leaderboard": {
                "by_productive_pct": sorted(
                    leaderboard, key=lambda r: r["productive_time_pct"], reverse=True
                )[:15],
                "by_operational_visits": sorted(
                    leaderboard, key=lambda r: r["operational_visits"], reverse=True
                )[:15],
                "by_transit_efficiency": sorted(
                    leaderboard, key=lambda r: r["transit_efficiency"], reverse=True
                )[:15],
                "low_activity": sorted(leaderboard, key=lambda r: r["active_hours"])[:10],
            },
        }

    window = slice_employee_window(full_df, employee, day, t_from, t_to)
    if window.empty:
        raise HTTPException(404, "No data for employee in this window")
    intel = compute_field_intelligence(window, sites_df)
    route = build_route_geometry(window)

    lb_prod = sorted(leaderboard, key=lambda r: r["productive_time_pct"], reverse=True)
    lb_visits = sorted(leaderboard, key=lambda r: r["operational_visits"], reverse=True)
    lb_eff = sorted(leaderboard, key=lambda r: r["transit_efficiency"], reverse=True)

    return {
        "day": str(day),
        "time_from": time_from,
        "time_to": time_to,
        "employee": employee,
        "intelligence": intel,
        "route": route,
        "route_note": None,
        "sites": _sites_payload(sites_df),
        "leaderboard": {
            "by_productive_pct": lb_prod[:15],
            "by_operational_visits": lb_visits[:15],
            "by_transit_efficiency": lb_eff[:15],
            "low_activity": sorted(leaderboard, key=lambda r: r["active_hours"])[:10],
        },
    }


@app.get("/api/daily-overview")
def daily_overview(
    day: date = Query(...),
    teams: str = Query("", description="Comma-separated teams"),
    regions: str = Query("", description="Comma-separated regions"),
    location_types: str = Query("", description="Comma-separated: yard,service,store"),
    search: str = Query("", description="Employee name search"),
):
    folder = str(punch_data_dir())
    sites_folder = str(sites_data_dir())
    full_df = load_folder_raw(folder)
    if full_df.empty:
        raise HTTPException(404, "No punch data in Data-day-wise/")
    sites_df = load_site_locations_raw(sites_folder)
    team_list = [t.strip() for t in teams.split(",") if t.strip()]
    region_list = [r.strip() for r in regions.split(",") if r.strip()]
    loc_list = [x.strip() for x in location_types.split(",") if x.strip()]
    payload = compute_daily_overview(
        full_df,
        day,
        sites_df,
        teams=team_list or None,
        regions=region_list or None,
        location_types=loc_list or None,
        employee_search=search,
    )
    df = enrich_metadata_columns(full_df)
    payload["filter_options"] = {
        "teams": sorted(df["_team"].dropna().astype(str).unique().tolist()),
        "regions": sorted(df["_region"].dropna().astype(str).unique().tolist()),
        "dates": [
            str(d)
            for d in sorted(pd.to_datetime(df["_ts"]).dt.date.dropna().unique(), reverse=True)[:90]
        ],
    }
    return payload
