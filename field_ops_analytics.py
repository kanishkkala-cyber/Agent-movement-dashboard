"""
Field Operations Intelligence — operational metrics from GPS (source of truth).

No fraud/spoof/trust scoring. Used by FastAPI for the React Field Operations Dashboard.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time
from typing import Any

import numpy as np
import pandas as pd

from analytics import (
    NEAR_SITE_KM,
    STATIONARY_SEGMENT_KM,
    detect_stops,
    haversine_km,
    site_nearest_with_index,
    slice_employee_window,
)
from core import (
    REQUIRED_COLUMNS,
    SITE_TYPE_MFC,
    SITE_TYPE_SERVICE,
    SITE_TYPE_STORE,
)

OPERATIONAL_TYPES: frozenset[str] = frozenset(
    {
        SITE_TYPE_MFC,
        SITE_TYPE_SERVICE,
        SITE_TYPE_STORE,
    }
)

TIME_SPLIT_KEYS = (
    "yard_time_s",
    "service_time_s",
    "store_time_s",
    "transit_time_s",
    "unknown_time_s",
)

TYPE_TO_SPLIT: dict[str, str] = {
    SITE_TYPE_MFC: "yard_time_s",
    SITE_TYPE_SERVICE: "service_time_s",
    SITE_TYPE_STORE: "store_time_s",
}


def _prep_day_df(day_df: pd.DataFrame) -> pd.DataFrame:
    if day_df.empty:
        return day_df
    ts0 = pd.to_datetime(day_df["_ts"])
    if ts0.is_monotonic_increasing:
        return day_df.reset_index(drop=True)
    return day_df.sort_values("_ts").reset_index(drop=True)


def _df_for_stops(df: pd.DataFrame, max_rows: int = 3500) -> pd.DataFrame:
    if len(df) <= max_rows:
        return df
    ix = np.unique(np.linspace(0, len(df) - 1, num=max_rows, dtype=np.int64))
    return df.iloc[ix].sort_values("_ts").reset_index(drop=True)


def _segment_category(
    d_min: float,
    site_type: str | None,
    d_seg_km: float,
) -> str:
    """Classify segment starting at ping i (d_min / type at i)."""
    if site_type is not None and d_min <= NEAR_SITE_KM and site_type in OPERATIONAL_TYPES:
        return TYPE_TO_SPLIT.get(site_type, "unknown_time_s")
    if d_seg_km >= STATIONARY_SEGMENT_KM:
        return "transit_time_s"
    return "unknown_time_s"


def _compute_visits(
    near: np.ndarray,
    site_idx: np.ndarray,
    stypes: np.ndarray,
    ts: pd.Series,
) -> tuple[int, dict[str, int], list[dict[str, Any]]]:
    """Operational visits: contiguous runs inside NEAR_SITE_KM at same site index."""
    n = len(near)
    visits: list[tuple[int, str, float, datetime, datetime]] = []
    if n == 0:
        return 0, {"yard": 0, "service": 0, "store": 0}, []

    i = 0
    while i < n:
        if not near[i]:
            i += 1
            continue
        j0 = int(site_idx[i])
        t0 = ts.iloc[i]
        k = i + 1
        while k < n and near[k] and int(site_idx[k]) == j0:
            k += 1
        t1 = ts.iloc[k - 1]
        dur = (t1 - t0).total_seconds()
        st = str(stypes[i])
        visits.append((j0, st, dur, t0.to_pydatetime(), t1.to_pydatetime()))
        i = k

    by_type = defaultdict(int)
    for _j, st, _d, _a, _b in visits:
        key = TYPE_TO_SPLIT.get(st)
        if key and key in TIME_SPLIT_KEYS:
            by_type[key.replace("_time_s", "")] += 1  # count only op categories

    # normalize keys expected by API
    visit_counts = {
        "yard": int(by_type.get("yard", 0)),
        "service": int(by_type.get("service", 0)),
        "store": int(by_type.get("store", 0)),
    }
    return len(visits), visit_counts, [
        {
            "site_index": int(v[0]),
            "site_type": v[1],
            "duration_s": round(v[2], 1),
            "start": v[3].isoformat(),
            "end": v[4].isoformat(),
        }
        for v in visits
    ]


def compute_field_intelligence(
    day_df: pd.DataFrame,
    sites_df: pd.DataFrame | None,
) -> dict[str, Any]:
    """Full intelligence payload for one employee time window."""
    lat_col = REQUIRED_COLUMNS["latitude"]
    lon_col = REQUIRED_COLUMNS["longitude"]
    empty_time = {k: 0.0 for k in TIME_SPLIT_KEYS}
    base: dict[str, Any] = {
        "productive_time_pct": 0.0,
        "productive_time_s": 0.0,
        "active_time_s": 0.0,
        "transit_time_s": 0.0,
        "operational_time_s": 0.0,
        "time_split_s": empty_time.copy(),
        "transit_vs_work": {"transit_s": 0.0, "operational_s": 0.0, "ratio_label": "—"},
        "operational_visits": 0,
        "visit_counts_by_category": {},
        "avg_visit_duration_s": 0.0,
        "avg_visit_by_category_s": {},
        "transit_efficiency": 0.0,
        "transit_efficiency_label": "—",
        "stop_distribution": {"short": 0, "medium": 0, "long": 0},
        "movement_intensity": [],
        "revisit_analytics": {"locations": [], "summary": {}},
        "hourly_utilization": [],
        "insights": [],
        "totals": {
            "distance_km": 0.0,
            "gps_pings": 0,
            "active_hours": 0.0,
            "num_stops": 0,
        },
    }

    df = _prep_day_df(day_df)
    if df.empty:
        base["insights"] = ["No GPS data in this window."]
        return base

    lat = df[lat_col].astype(float).values
    lon = df[lon_col].astype(float).values
    ts = pd.to_datetime(df["_ts"])
    n = len(df)
    first_ts = ts.iloc[0].to_pydatetime()
    last_ts = ts.iloc[-1].to_pydatetime()
    active_s = max(0.0, (last_ts - first_ts).total_seconds())

    split_s = empty_time.copy()
    total_distance_km = 0.0
    d_km = np.array([])
    dt_s = np.array([])
    d_min = np.array([])
    site_idx = np.array([], dtype=np.int64)
    stypes = np.array([])
    near = np.array([], dtype=bool)
    stype_at: list[str] = []

    if n >= 2:
        d_km = haversine_km(lat[:-1], lon[:-1], lat[1:], lon[1:])
        total_distance_km = float(np.sum(d_km))
        dt_s = (ts.iloc[1:].values - ts.iloc[:-1].values) / np.timedelta64(1, "s")
        dt_s = np.maximum(dt_s.astype(float), 0.0)

        if sites_df is not None and not sites_df.empty:
            d_min, site_idx, stypes = site_nearest_with_index(lat, lon, sites_df)
            near = d_min <= NEAR_SITE_KM
            stype_at = [str(x) for x in stypes]
            for i in range(len(dt_s)):
                cat = _segment_category(
                    float(d_min[i]),
                    stype_at[i] if near[i] else None,
                    float(d_km[i]),
                )
                split_s[cat] += float(dt_s[i])
        else:
            for i in range(len(dt_s)):
                cat = "transit_time_s" if float(d_km[i]) >= STATIONARY_SEGMENT_KM else "unknown_time_s"
                split_s[cat] += float(dt_s[i])

    operational_s = (
        split_s["yard_time_s"]
        + split_s["service_time_s"]
        + split_s["store_time_s"]
    )
    transit_s = split_s["transit_time_s"]
    unknown_s = split_s["unknown_time_s"]
    measured = operational_s + transit_s + unknown_s
    denom = measured if measured > 0 else active_s
    productive_pct = round(100.0 * operational_s / denom, 1) if denom > 0 else 0.0

    visits_n = 0
    visit_counts: dict[str, int] = {"yard": 0, "service": 0, "store": 0}
    visit_records: list[dict[str, Any]] = []
    if sites_df is not None and not sites_df.empty and n > 0 and len(near) == n:
        visits_n, visit_counts, visit_records = _compute_visits(near, site_idx, stypes, ts)

    avg_visit = round(operational_s / max(visits_n, 1), 1)
    # per-category average dwell (time in category / visits in that category)
    avg_by_cat: dict[str, float] = {}
    for key, label in (
        ("yard_time_s", "yard"),
        ("service_time_s", "service"),
        ("store_time_s", "store"),
    ):
        vc = visit_counts.get(label, 0)
        avg_by_cat[label] = round(split_s[key] / max(vc, 1), 1)

    eff = round(visits_n / max(total_distance_km, 0.01), 2)
    if eff >= 2.5 and visits_n >= 3:
        eff_label = "Efficient multi-stop route."
    elif total_distance_km > 15 and visits_n <= 2:
        eff_label = "High travel with low engagement."
    elif eff >= 1.2:
        eff_label = "Balanced routing vs visits."
    else:
        eff_label = "Room to consolidate stops."

    stops = detect_stops(_df_for_stops(df))
    short = medium = long = 0
    for _a, _b, dur in stops:
        if dur < 300:
            short += 1
        elif dur <= 1200:
            medium += 1
        else:
            long += 1

    # Movement intensity: 15-minute bins (count of pings + km moved)
    intensity_bins: list[dict[str, Any]] = []
    if n >= 2 and active_s > 0:
        start = ts.iloc[0]
        bin_ms = 15 * 60 * 1000
        end_ms = int((ts.iloc[-1] - start).total_seconds() * 1000)
        nb = max(1, end_ms // bin_ms + 1)
        for b in range(int(nb)):
            t0 = start + pd.Timedelta(milliseconds=b * bin_ms)
            t1 = t0 + pd.Timedelta(minutes=15)
            m = (ts >= t0) & (ts < t1)
            pings = int(m.sum())
            km = 0.0
            idx = np.where(m.values)[0]
            if len(idx) >= 2:
                for ii in range(len(idx) - 1):
                    a, c = idx[ii], idx[ii + 1]
                    if c == a + 1:
                        km += float(d_km[a]) if a < len(d_km) else 0.0
            intensity_bins.append(
                {
                    "start": t0.isoformat(),
                    "pings": pings,
                    "km": round(km, 3),
                    "score": round(pings * 0.1 + km * 2.0, 2),
                }
            )

    # Revisit: group visits by site_index
    loc_visits: dict[int, list[float]] = defaultdict(list)
    for vr in visit_records:
        loc_visits[int(vr["site_index"])].append(float(vr["duration_s"]))
    revisit_rows: list[dict[str, Any]] = []
    if sites_df is not None and not sites_df.empty:
        for sid, durs in loc_visits.items():
            if len(durs) < 2:
                continue
            row = sites_df.iloc[sid]
            revisit_rows.append(
                {
                    "site_index": sid,
                    "site_type": str(row["site_type"]),
                    "name": str(row.get("name", ""))[:80],
                    "visit_count": len(durs),
                    "total_dwell_s": round(sum(durs), 1),
                    "avg_dwell_s": round(float(np.mean(durs)), 1),
                }
            )
    revisit_rows.sort(key=lambda x: -x["visit_count"])

    # Hourly utilization (0–23): movement km, operational s, idle s
    hourly = [
        {"hour": h, "movement_km": 0.0, "operational_s": 0.0, "idle_s": 0.0} for h in range(24)
    ]
    if n >= 2 and len(dt_s) > 0:
        hours = ts.dt.hour.values
        n_seg = len(dt_s)
        for i in range(n_seg):
            h = int(hours[i])
            if i < len(d_km):
                hourly[h]["movement_km"] += float(d_km[i])
            if sites_df is not None and not sites_df.empty and len(d_min) == n:
                dt = float(dt_s[i])
                cat = _segment_category(
                    float(d_min[i]),
                    stype_at[i] if near[i] else None,
                    float(d_km[i]),
                )
                if cat != "transit_time_s" and cat != "unknown_time_s":
                    hourly[h]["operational_s"] += dt
                elif cat == "unknown_time_s":
                    hourly[h]["idle_s"] += dt
        for h in hourly:
            h["movement_km"] = round(h["movement_km"], 3)
            h["operational_s"] = round(h["operational_s"], 1)
            h["idle_s"] = round(h["idle_s"], 1)

    insights: list[str] = []
    if productive_pct >= 55:
        insights.append(f"{productive_pct:.0f}% of active time at operational locations.")
    elif productive_pct > 0:
        insights.append(
            f"{productive_pct:.0f}% of active time at operational locations — opportunity to increase on-site engagement."
        )
    if operational_s > 0 and transit_s > operational_s * 1.35:
        insights.append("Travel-heavy operational day (transit exceeds on-site time).")
    elif operational_s > 0 and transit_s <= operational_s * 0.85:
        insights.append("Balanced movement-to-engagement ratio.")
    top_cat = max(
        [
            ("yard", split_s["yard_time_s"]),
            ("service", split_s["service_time_s"]),
            ("store", split_s["store_time_s"]),
        ],
        key=lambda x: x[1],
    )
    if top_cat[1] > operational_s * 0.45 and operational_s > 0:
        insights.append(f"Strong operational concentration in {top_cat[0]} locations.")
    if revisit_rows and revisit_rows[0]["visit_count"] >= 3:
        insights.append(
            f"Repeat activity at {revisit_rows[0]['name'][:40] or 'a fixed location'} — high-touch operational node."
        )
    # Peak productive hours
    if hourly:
        best_h = max(range(24), key=lambda hh: hourly[hh]["operational_s"])
        if hourly[best_h]["operational_s"] > 0:
            insights.append(f"Peak on-site engagement in the {best_h:02d}:00 hour block.")
    if not insights:
        insights.append("Typical field movement — review map and hourly panels for detail.")

    ratio_label = "Balanced movement-to-engagement ratio."
    if transit_s > operational_s * 1.2:
        ratio_label = "Travel-heavy operational day."
    elif operational_s > transit_s * 1.5:
        ratio_label = "On-site heavy day — limited transit."

    base.update(
        {
            "productive_time_pct": productive_pct,
            "productive_time_s": round(operational_s, 1),
            "active_time_s": round(denom if measured > 0 else active_s, 1),
            "transit_time_s": round(transit_s, 1),
            "operational_time_s": round(operational_s, 1),
            "time_split_s": {k: round(v, 1) for k, v in split_s.items()},
            "transit_vs_work": {
                "transit_s": round(transit_s, 1),
                "operational_s": round(operational_s, 1),
                "ratio_label": ratio_label,
            },
            "operational_visits": visits_n,
            "visit_counts_by_category": visit_counts,
            "avg_visit_duration_s": avg_visit,
            "avg_visit_by_category_s": avg_by_cat,
            "transit_efficiency": eff,
            "transit_efficiency_label": eff_label,
            "stop_distribution": {"short": short, "medium": medium, "long": long},
            "movement_intensity": intensity_bins[: 24 * 4],
            "revisit_analytics": {
                "locations": revisit_rows[:12],
                "summary": {
                    "multi_visit_locations": len(revisit_rows),
                    "total_operational_visits": visits_n,
                },
            },
            "hourly_utilization": hourly,
            "insights": insights[:8],
            "visit_events": visit_records[:40],
            "totals": {
                "distance_km": round(total_distance_km, 2),
                "gps_pings": n,
                "active_hours": round(active_s / 3600.0, 2),
                "num_stops": len(stops),
            },
        }
    )
    return base


def build_route_geometry(
    day_df: pd.DataFrame,
    *,
    max_points: int = 900,
) -> dict[str, Any]:
    """Coordinates + operational stops for map / replay."""
    df = _prep_day_df(day_df)
    if df.empty:
        return {"coordinates": [], "time_iso": [], "stops": []}
    lat_col = REQUIRED_COLUMNS["latitude"]
    lon_col = REQUIRED_COLUMNS["longitude"]
    n = len(df)
    if n > max_points:
        ix = np.unique(np.linspace(0, n - 1, num=max_points, dtype=np.int64))
        df = df.iloc[ix].reset_index(drop=True)
    ts = pd.to_datetime(df["_ts"])
    coords = [[float(r[lat_col]), float(r[lon_col])] for _, r in df.iterrows()]
    times = [t.isoformat() for t in ts]
    stops_out: list[dict[str, Any]] = []
    for a, b, dur in detect_stops(_df_for_stops(_prep_day_df(day_df))):
        sub = day_df[pd.to_datetime(day_df["_ts"]) >= pd.Timestamp(a)]
        if sub.empty:
            continue
        row = sub.iloc[0]
        stops_out.append(
            {
                "lat": float(row[lat_col]),
                "lon": float(row[lon_col]),
                "start": a.isoformat(),
                "end": b.isoformat(),
                "duration_s": round(dur, 1),
            }
        )
    return {"coordinates": coords, "time_iso": times, "stops": stops_out[:30]}


def compute_leaderboard_rows(
    full_df: pd.DataFrame,
    day: date,
    t_from: time,
    t_to: time,
    sites_df: pd.DataFrame | None,
    *,
    max_agents: int = 80,
) -> list[dict[str, Any]]:
    name_col = REQUIRED_COLUMNS["employee_name"]
    if full_df.empty:
        return []
    start = pd.Timestamp.combine(day, t_from)
    end = pd.Timestamp.combine(day, t_to)
    day_all = full_df[(full_df["_ts"] >= start) & (full_df["_ts"] <= end)]
    if day_all.empty:
        return []
    names = day_all[name_col].dropna().astype(str).unique().tolist()
    names = sorted(set(names))[:max_agents]
    rows: list[dict[str, Any]] = []
    for name in names:
        w = slice_employee_window(full_df, name, day, t_from, t_to)
        intel = compute_field_intelligence(w, sites_df)
        rows.append(
            {
                "employee": name,
                "productive_time_pct": intel["productive_time_pct"],
                "operational_visits": intel["operational_visits"],
                "transit_efficiency": intel["transit_efficiency"],
                "active_hours": intel["totals"]["active_hours"],
                "distance_km": intel["totals"]["distance_km"],
            }
        )
    return rows
