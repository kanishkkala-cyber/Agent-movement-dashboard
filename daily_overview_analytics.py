"""Leadership daily overview — all employees for one calendar day."""

from __future__ import annotations

from datetime import date, time
from typing import Any

import numpy as np
import pandas as pd

from analytics import compute_movement_analytics, slice_employee_window
from core import REQUIRED_COLUMNS, SITE_TYPE_MFC, SITE_TYPE_SERVICE, SITE_TYPE_STORE
from field_ops_analytics import compute_field_intelligence
from operations_alerts import build_operations_alerts, enrich_with_previous_day

DAY_START = time(0, 0)
DAY_END = time(23, 59, 59)

TEAM_COL_CANDIDATES = ("Team", "Department", "Dept", "Business Unit")
REGION_COL_CANDIDATES = ("Region", "Territory", "Zone", "State", "Area")


def _pick_col(df: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def enrich_metadata_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Attach _team / _region from export columns when present."""
    out = df.copy()
    tc = _pick_col(df, TEAM_COL_CANDIDATES)
    rc = _pick_col(df, REGION_COL_CANDIDATES)
    out["_team"] = (
        df[tc].astype(str).str.strip().replace({"nan": "Unassigned"})
        if tc
        else "Unassigned"
    )
    out["_region"] = (
        df[rc].astype(str).str.strip().replace({"nan": "Unassigned"})
        if rc
        else "Unassigned"
    )
    return out


def _efficiency_score(row: dict[str, Any]) -> float:
    p = float(row.get("productive_time_pct") or 0)
    te = float(row.get("transit_efficiency") or 0)
    v = float(row.get("operational_visits") or 0)
    return round(min(100.0, p * 0.45 + min(te / 2.5, 1.0) * 30 + min(v / 8, 1.0) * 25), 1)


def _perf_tier(score: float) -> str:
    if score >= 65:
        return "high"
    if score >= 38:
        return "medium"
    return "low"


def compute_employee_day_row(
    full_df: pd.DataFrame,
    employee: str,
    day: date,
    sites_df: pd.DataFrame | None,
) -> dict[str, Any]:
    name_col = REQUIRED_COLUMNS["employee_name"]
    w = slice_employee_window(full_df, employee, day, DAY_START, DAY_END)
    team = "Unassigned"
    region = "Unassigned"
    if not w.empty and "_team" in w.columns:
        team = str(w["_team"].iloc[0])
    if not w.empty and "_region" in w.columns:
        region = str(w["_region"].iloc[0])
    if w.empty:
        return {
            "employee": employee,
            "team": team,
            "region": region,
            "distance_km": 0.0,
            "productive_time_pct": 0.0,
            "operational_visits": 0,
            "active_hours": 0.0,
            "transit_time_s": 0.0,
            "productive_time_s": 0.0,
            "avg_visit_duration_s": 0.0,
            "unique_locations": 0,
            "gps_pings": 0,
            "transit_efficiency": 0.0,
            "efficiency_score": 0.0,
            "performance_tier": "low",
            "has_activity": False,
        }
    mov = compute_movement_analytics(w, sites_df)
    intel = compute_field_intelligence(w, sites_df)
    row = {
        "employee": employee,
        "team": team,
        "region": region,
        "distance_km": mov.total_distance_km,
        "productive_time_pct": intel["productive_time_pct"],
        "operational_visits": intel["operational_visits"],
        "active_hours": intel["totals"]["active_hours"],
        "transit_time_s": intel["transit_time_s"],
        "productive_time_s": intel["productive_time_s"],
        "avg_visit_duration_s": intel["avg_visit_duration_s"],
        "unique_locations": mov.unique_locations,
        "gps_pings": intel["totals"]["gps_pings"],
        "transit_efficiency": intel["transit_efficiency"],
        "has_activity": intel["totals"]["gps_pings"] > 0,
    }
    row["efficiency_score"] = _efficiency_score(row)
    row["performance_tier"] = _perf_tier(row["efficiency_score"])
    return row


def _prior_data_day(full_df: pd.DataFrame, day: date) -> date | None:
    if full_df.empty:
        return None
    dates = sorted(pd.to_datetime(full_df["_ts"]).dt.date.dropna().unique())
    prior = [d for d in dates if d < day]
    return prior[-1] if prior else None


def compute_daily_overview(
    full_df: pd.DataFrame,
    day: date,
    sites_df: pd.DataFrame | None,
    *,
    teams: list[str] | None = None,
    regions: list[str] | None = None,
    location_types: list[str] | None = None,
    employee_search: str = "",
    include_prev_trends: bool = True,
) -> dict[str, Any]:
    """
    Full leadership payload for one day across all employees.
    location_types: yard | service | store (filters employees with time in those categories).
    """
    if full_df.empty:
        return _empty_payload(day)

    df = enrich_metadata_columns(full_df)
    name_col = REQUIRED_COLUMNS["employee_name"]
    start = pd.Timestamp.combine(day, DAY_START)
    end = pd.Timestamp.combine(day, DAY_END)
    day_df = df[(df["_ts"] >= start) & (df["_ts"] <= end)]
    if day_df.empty:
        return _empty_payload(day)

    employees = sorted(day_df[name_col].dropna().astype(str).unique().tolist())
    if employee_search.strip():
        q = employee_search.strip().lower()
        employees = [e for e in employees if q in e.lower()]

    rows: list[dict[str, Any]] = []
    for emp in employees:
        r = compute_employee_day_row(df, emp, day, sites_df)
        if teams and r["team"] not in teams:
            continue
        if regions and r["region"] not in regions:
            continue
        rows.append(r)

    if location_types and sites_df is not None and not sites_df.empty:
        type_map = {
            "yard": SITE_TYPE_MFC,
            "service": SITE_TYPE_SERVICE,
            "store": SITE_TYPE_STORE,
        }
        wanted = {type_map.get(t.lower(), t) for t in location_types}
        filtered: list[dict[str, Any]] = []
        for r in rows:
            w = slice_employee_window(df, r["employee"], day, DAY_START, DAY_END)
            intel = compute_field_intelligence(w, sites_df)
            ts = intel["time_split_s"]
            has = False
            if "yard" in location_types or SITE_TYPE_MFC in wanted:
                has = has or ts.get("yard_time_s", 0) > 60
            if "service" in location_types or SITE_TYPE_SERVICE in wanted:
                has = has or ts.get("service_time_s", 0) > 60
            if "store" in location_types or SITE_TYPE_STORE in wanted:
                has = has or ts.get("store_time_s", 0) > 60
            if has:
                filtered.append(r)
        rows = filtered

    if not rows:
        return _empty_payload(day)

    rows.sort(key=lambda x: -x["efficiency_score"])
    for i, r in enumerate(rows, start=1):
        r["rank"] = i

    active = [r for r in rows if r["has_activity"]]
    n_active = len(active)
    total_dist = sum(r["distance_km"] for r in active)
    total_visits = sum(r["operational_visits"] for r in active)
    total_pings = sum(r["gps_pings"] for r in active)
    avg_prod = float(np.mean([r["productive_time_pct"] for r in active])) if active else 0.0
    avg_transit_h = (
        float(np.mean([r["transit_time_s"] for r in active]) / 3600.0) if active else 0.0
    )
    avg_active_h = float(np.mean([r["active_hours"] for r in active])) if active else 0.0
    avg_visit = float(np.mean([r["avg_visit_duration_s"] for r in active])) if active else 0.0

    best = max(active, key=lambda x: x["efficiency_score"]) if active else rows[0]
    worst = min(active, key=lambda x: x["active_hours"]) if active else rows[-1]

    high = sum(1 for r in active if r["productive_time_pct"] >= 55)
    med = sum(1 for r in active if 30 <= r["productive_time_pct"] < 55)
    low = sum(1 for r in active if r["productive_time_pct"] < 30)

    hourly = [{"hour": h, "pings": 0, "operational_s": 0.0, "movement_km": 0.0} for h in range(24)]
    for r in active:
        w = slice_employee_window(df, r["employee"], day, DAY_START, DAY_END)
        intel = compute_field_intelligence(w, sites_df)
        for h in intel["hourly_utilization"]:
            hr = int(h["hour"])
            hourly[hr]["pings"] += int(
                w[pd.to_datetime(w["_ts"]).dt.hour == hr].shape[0]
            )
            hourly[hr]["operational_s"] += float(h["operational_s"])
            hourly[hr]["movement_km"] += float(h["movement_km"])

    loc_split = {
        "yard_s": 0.0,
        "service_s": 0.0,
        "store_s": 0.0,
        "transit_s": 0.0,
        "unknown_s": 0.0,
    }
    for r in active:
        w = slice_employee_window(df, r["employee"], day, DAY_START, DAY_END)
        intel = compute_field_intelligence(w, sites_df)
        ts = intel["time_split_s"]
        loc_split["yard_s"] += ts.get("yard_time_s", 0)
        loc_split["service_s"] += ts.get("service_time_s", 0)
        loc_split["store_s"] += ts.get("store_time_s", 0)
        loc_split["transit_s"] += ts.get("transit_time_s", 0)
        loc_split["unknown_s"] += ts.get("unknown_time_s", 0)

    movement_bins = {"low": 0, "moderate": 0, "heavy": 0}
    for r in active:
        d = r["distance_km"]
        if d < 5:
            movement_bins["low"] += 1
        elif d <= 20:
            movement_bins["moderate"] += 1
        else:
            movement_bins["heavy"] += 1

    team_stats: dict[str, dict[str, Any]] = {}
    for r in active:
        t = r["team"]
        if t not in team_stats:
            team_stats[t] = {
                "team": t,
                "employees": 0,
                "distance_km": 0.0,
                "visits": 0,
                "productive_pct_sum": 0.0,
                "active_hours_sum": 0.0,
            }
        team_stats[t]["employees"] += 1
        team_stats[t]["distance_km"] += r["distance_km"]
        team_stats[t]["visits"] += r["operational_visits"]
        team_stats[t]["productive_pct_sum"] += r["productive_time_pct"]
        team_stats[t]["active_hours_sum"] += r["active_hours"]

    team_comparison = []
    for t, s in team_stats.items():
        n = max(s["employees"], 1)
        team_comparison.append(
            {
                "team": t,
                "employees": s["employees"],
                "distance_km": round(s["distance_km"], 1),
                "visits": s["visits"],
                "avg_productive_pct": round(s["productive_pct_sum"] / n, 1),
                "avg_active_hours": round(s["active_hours_sum"] / n, 2),
            }
        )
    team_comparison.sort(key=lambda x: -x["avg_productive_pct"])

    region_stats: list[dict[str, Any]] = []
    by_region: dict[str, list[dict]] = {}
    for r in active:
        by_region.setdefault(r["region"], []).append(r)
    for reg, rs in by_region.items():
        region_stats.append(
            {
                "region": reg,
                "employees": len(rs),
                "distance_km": round(sum(x["distance_km"] for x in rs), 1),
                "avg_productive_pct": round(
                    float(np.mean([x["productive_time_pct"] for x in rs])), 1
                ),
                "visits": sum(x["operational_visits"] for x in rs),
            }
        )
    region_stats.sort(key=lambda x: -x["employees"])

    insights = _build_insights(
        active,
        high,
        med,
        low,
        total_visits,
        loc_split,
        team_comparison,
        avg_active_h,
    )

    top5 = sorted(active, key=lambda x: -x["efficiency_score"])[:5]
    bottom5 = sorted(active, key=lambda x: (x["active_hours"], x["distance_km"]))[:5]

    filter_options = {
        "teams": sorted(df["_team"].dropna().unique().tolist()),
        "regions": sorted(df["_region"].dropna().unique().tolist()),
    }

    alert_center = build_operations_alerts(
        df,
        day,
        sites_df,
        rows,
        team_comparison=team_comparison,
        region_stats=region_stats,
    )

    if include_prev_trends:
        prev_day = _prior_data_day(df, day)
        if prev_day is not None:
            prev_payload = compute_daily_overview(
                full_df,
                prev_day,
                sites_df,
                teams=teams,
                regions=regions,
                location_types=location_types,
                employee_search=employee_search,
                include_prev_trends=False,
            )
            alert_center = enrich_with_previous_day(
                alert_center,
                {**prev_payload["alert_center"], "day": prev_payload["day"]},
            )

    return {
        "day": str(day),
        "filter_options": filter_options,
        "executive_kpis": {
            "active_employees": n_active,
            "total_employees": len(rows),
            "total_distance_km": round(total_dist, 1),
            "total_operational_visits": int(total_visits),
            "avg_productive_time_pct": round(avg_prod, 1),
            "avg_transit_hours": round(avg_transit_h, 2),
            "avg_active_hours": round(avg_active_h, 2),
            "total_gps_pings": int(total_pings),
            "avg_visit_duration_s": round(avg_visit, 1),
            "top_performer": best["employee"],
            "top_performer_score": best["efficiency_score"],
            "lowest_activity": worst["employee"],
            "lowest_activity_hours": worst["active_hours"],
        },
        "leaderboard": rows,
        "productivity_distribution": {
            "high": high,
            "medium": med,
            "low": low,
        },
        "top_performers": top5,
        "bottom_performers": bottom5,
        "team_comparison": team_comparison,
        "hourly_operations": hourly,
        "location_breakdown_s": loc_split,
        "movement_distribution": movement_bins,
        "region_analytics": region_stats,
        "insights": insights,
        "alert_center": alert_center,
    }


def _build_insights(
    active: list[dict],
    high: int,
    med: int,
    low: int,
    total_visits: int,
    loc_split: dict[str, float],
    team_comparison: list[dict],
    avg_active_h: float,
) -> list[str]:
    n = len(active)
    if n == 0:
        return ["No operational activity recorded for the selected filters."]
    notes: list[str] = []
    long_day = sum(1 for r in active if r["active_hours"] >= 6)
    pct_long = round(100.0 * long_day / n, 0)
    notes.append(
        f"{pct_long:.0f}% of active employees logged more than 6 hours of field time today."
    )
    best_loc = max(
        [
            ("yards", loc_split["yard_s"]),
            ("service centres", loc_split["service_s"]),
            ("stores", loc_split["store_s"]),
        ],
        key=lambda x: x[1],
    )
    if best_loc[1] > 0:
        notes.append(f"Highest on-site engagement was at {best_loc[0]} locations.")
    if high > low:
        notes.append(
            f"{high} employees show high productive time vs {low} with low productive time."
        )
    if team_comparison:
        top_t = team_comparison[0]
        notes.append(
            f"Team **{top_t['team']}** leads average productive time at {top_t['avg_productive_pct']:.0f}%."
        )
    top_visits = sorted(active, key=lambda x: -x["operational_visits"])[:10]
    if top_visits and total_visits > 0:
        share = round(
            100.0
            * sum(r["operational_visits"] for r in top_visits)
            / max(total_visits, 1),
            0,
        )
        notes.append(
            f"Top 10 employees by visits accounted for {share:.0f}% of operational visits."
        )
    heavy = sum(1 for r in active if r["distance_km"] > 20)
    if heavy > n * 0.25:
        notes.append("Transit-heavy patterns observed — several agents exceeded 20 km today.")
    if avg_active_h < 4:
        notes.append("Overall field active hours are below typical full-day coverage.")
    if not notes:
        notes.append("Balanced field operations across the active workforce today.")
    return notes[:8]


def _empty_payload(day: date) -> dict[str, Any]:
    return {
        "day": str(day),
        "filter_options": {"teams": [], "regions": []},
        "executive_kpis": {
            "active_employees": 0,
            "total_employees": 0,
            "total_distance_km": 0.0,
            "total_operational_visits": 0,
            "avg_productive_time_pct": 0.0,
            "avg_transit_hours": 0.0,
            "avg_active_hours": 0.0,
            "total_gps_pings": 0,
            "avg_visit_duration_s": 0.0,
            "top_performer": "—",
            "top_performer_score": 0.0,
            "lowest_activity": "—",
            "lowest_activity_hours": 0.0,
        },
        "leaderboard": [],
        "productivity_distribution": {"high": 0, "medium": 0, "low": 0},
        "top_performers": [],
        "bottom_performers": [],
        "team_comparison": [],
        "hourly_operations": [{"hour": h, "pings": 0, "operational_s": 0.0, "movement_km": 0.0} for h in range(24)],
        "location_breakdown_s": {},
        "movement_distribution": {"low": 0, "moderate": 0, "heavy": 0},
        "region_analytics": [],
        "insights": ["No GPS data for this date and filter combination."],
        "alert_center": {
            "alerts": [],
            "summary": {"total": 0, "critical": 0, "warning": 0, "mild": 0, "positive": 0},
            "smart_insights": ["No GPS data for this date and filter combination."],
            "alert_types": [],
            "thresholds": {},
            "trends": None,
        },
    }
