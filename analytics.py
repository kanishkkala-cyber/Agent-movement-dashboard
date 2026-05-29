"""Movement analytics for a single employee on one calendar day."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

import numpy as np
import pandas as pd

from core import REQUIRED_COLUMNS, SITE_TYPE_MFC, SITE_TYPE_SERVICE, SITE_TYPE_STORE

EARTH_R_KM = 6371.0088
STATIONARY_SEGMENT_KM = 0.05  # 50 m between consecutive pings → stationary segment
# Fixed-site visit attribution radius.
# Mobile GPS drift + dense built environments often push points outside a strict 200m geofence.
# Use practical radii that improve operational classification.
NEAR_SITE_KM = 0.45  # default/fallback (450 m)
OFFSITE_KM = 2.5  # geo-fence style: far from any fixed site

# Per site-type radii (km). Falls back to NEAR_SITE_KM for unknown types.
SITE_MATCH_RADIUS_KM_BY_TYPE: dict[str, float] = {
    SITE_TYPE_SERVICE: 0.50,  # service centres often have multi-building campuses
    SITE_TYPE_MFC: 0.55,      # yards can be large compounds
    SITE_TYPE_STORE: 0.35,    # stores are smaller / denser footprint
}


def site_match_radius_km(site_type: str | None) -> float:
    if not site_type:
        return NEAR_SITE_KM
    return float(SITE_MATCH_RADIUS_KM_BY_TYPE.get(str(site_type), NEAR_SITE_KM))


def haversine_km(
    lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray
) -> np.ndarray:
    """Element-wise great-circle distance in km."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    l1, l2 = np.radians(lon1), np.radians(lon2)
    dlat, dlon = p2 - p1, l2 - l1
    a = np.sin(dlat / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(np.maximum(0.0, 1.0 - a)))
    return EARTH_R_KM * c


def site_proximity_batch(
    lat: np.ndarray, lon: np.ndarray, sites_df: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray]:
    """
    For each ping (n), distance to nearest site (km) and that site's type label.
    lat, lon shape (n,).
    """
    if sites_df is None or sites_df.empty or len(lat) == 0:
        return np.array([]), np.array([])
    slat = sites_df["latitude"].to_numpy(dtype=np.float64)
    slon = sites_df["longitude"].to_numpy(dtype=np.float64)
    stypes = sites_df["site_type"].to_numpy()
    d = haversine_km(lat[:, np.newaxis], lon[:, np.newaxis], slat[np.newaxis, :], slon[np.newaxis, :])
    j = np.argmin(d, axis=1)
    d_min = d[np.arange(len(lat)), j]
    nearest_type = stypes[j]
    return d_min, nearest_type


def site_nearest_with_index(
    lat: np.ndarray, lon: np.ndarray, sites_df: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Like site_proximity_batch but also returns nearest site row index into sites_df."""
    if sites_df is None or sites_df.empty or len(lat) == 0:
        return np.array([]), np.array([]), np.array([])
    slat = sites_df["latitude"].to_numpy(dtype=np.float64)
    slon = sites_df["longitude"].to_numpy(dtype=np.float64)
    stypes = sites_df["site_type"].to_numpy()
    d = haversine_km(lat[:, np.newaxis], lon[:, np.newaxis], slat[np.newaxis, :], slon[np.newaxis, :])
    j = np.argmin(d, axis=1)
    d_min = d[np.arange(len(lat)), j]
    nearest_type = stypes[j]
    return d_min, j.astype(np.int64), nearest_type


def _nearest_site_km_and_type(
    lat: float, lon: float, sites_df: pd.DataFrame
) -> tuple[float | None, str | None]:
    if sites_df is None or sites_df.empty:
        return None, None
    d_min, types = site_proximity_batch(
        np.array([lat], dtype=np.float64),
        np.array([lon], dtype=np.float64),
        sites_df,
    )
    if len(d_min) == 0:
        return None, None
    return float(d_min[0]), str(types[0])


def detect_stops(
    df: pd.DataFrame,
    *,
    radius_km: float = 0.075,
    min_stop_seconds: float = 180.0,
    max_intra_gap_seconds: float = 1800.0,
) -> list[tuple[datetime, datetime, float]]:
    """
    Greedy dwell clusters: points within radius_km of cluster anchor, gaps <= max_intra_gap.
    Returns list of (start_ts, end_ts, duration_s).
    """
    lat_col = REQUIRED_COLUMNS["latitude"]
    lon_col = REQUIRED_COLUMNS["longitude"]
    if len(df) < 2:
        return []

    df = df.sort_values("_ts").reset_index(drop=True)
    if len(df) > 1000:
        ix = np.unique(np.linspace(0, len(df) - 1, num=1000, dtype=np.int64))
        df = df.iloc[ix].sort_values("_ts").reset_index(drop=True)

    lats = df[lat_col].astype(float).values
    lons = df[lon_col].astype(float).values
    tss = pd.to_datetime(df["_ts"]).dt.to_pydatetime()

    stops: list[tuple[datetime, datetime, float]] = []
    i = 0
    n = len(df)
    while i < n:
        anchor_lat, anchor_lon = float(lats[i]), float(lons[i])
        sub_lat = lats[i:]
        sub_lon = lons[i:]
        dists = haversine_km(
            np.full(len(sub_lat), anchor_lat, dtype=np.float64),
            np.full(len(sub_lon), anchor_lon, dtype=np.float64),
            sub_lat,
            sub_lon,
        )
        last = i
        j = i + 1
        while j < n and float(dists[j - i]) <= radius_km:
            gap = (tss[j] - tss[last]).total_seconds()
            if gap > max_intra_gap_seconds:
                break
            last = j
            j += 1
        dur = (tss[last] - tss[i]).total_seconds()
        if dur >= min_stop_seconds and last > i:
            stops.append((tss[i], tss[last], dur))
            i = last + 1
        else:
            i += 1
    return stops


@dataclass
class MovementAnalytics:
    total_distance_km: float
    travel_time_seconds: float
    stationary_time_seconds: float
    num_stops: int
    gps_pings: int
    active_hours: float
    longest_stop_seconds: float
    avg_stop_seconds: float
    most_visited_location_type: str
    unique_locations: int
    geofence_violations: int
    first_ts: datetime | None
    last_ts: datetime | None
    productivity_notes: list[str]
    visit_by_type: dict[str, int]


def compute_movement_analytics(
    day_df: pd.DataFrame,
    sites_df: pd.DataFrame | None,
) -> MovementAnalytics:
    """day_df: one employee, one day window (already time-filtered), sorted by _ts."""
    lat_col = REQUIRED_COLUMNS["latitude"]
    lon_col = REQUIRED_COLUMNS["longitude"]
    notes: list[str] = []
    visit_by_type: dict[str, int] = {
        SITE_TYPE_MFC: 0,
        SITE_TYPE_SERVICE: 0,
        SITE_TYPE_STORE: 0,
    }

    if day_df.empty:
        return MovementAnalytics(
            0.0,
            0.0,
            0.0,
            0,
            0,
            0.0,
            0.0,
            0.0,
            "—",
            0,
            0,
            None,
            None,
            ["No GPS data in this window."],
            visit_by_type,
        )

    ts0 = pd.to_datetime(day_df["_ts"])
    if ts0.is_monotonic_increasing:
        df = day_df.reset_index(drop=True)
    else:
        df = day_df.sort_values("_ts").reset_index(drop=True)
    n = len(df)
    lat = df[lat_col].astype(float).values
    lon = df[lon_col].astype(float).values
    ts = pd.to_datetime(df["_ts"])

    first_ts = ts.iloc[0].to_pydatetime()
    last_ts = ts.iloc[-1].to_pydatetime()
    active_hours = max(0.0, (last_ts - first_ts).total_seconds() / 3600.0)

    if n >= 2:
        d_km = haversine_km(lat[:-1], lon[:-1], lat[1:], lon[1:])
        dt_s = (ts.iloc[1:].values - ts.iloc[:-1].values) / np.timedelta64(1, "s")
        dt_s = np.maximum(dt_s.astype(float), 0.0)
        total_distance_km = float(np.sum(d_km))
        stationary_mask = d_km < STATIONARY_SEGMENT_KM
        stationary_time_seconds = float(np.sum(dt_s[stationary_mask]))
        travel_time_seconds = float(np.sum(dt_s[~stationary_mask]))
    else:
        total_distance_km = 0.0
        stationary_time_seconds = 0.0
        travel_time_seconds = 0.0

    stops = detect_stops(df)
    num_stops = len(stops)
    if stops:
        durs = [s[2] for s in stops]
        longest_stop_seconds = max(durs)
        avg_stop_seconds = float(np.mean(durs))
    else:
        longest_stop_seconds = 0.0
        avg_stop_seconds = 0.0

    # Unique locations (coarse grid ~110 m)
    ulat = np.round(lat, 3)
    ulon = np.round(lon, 3)
    unique_locations = int(len(np.unique(np.column_stack([ulat, ulon]), axis=0)))

    geofence_violations = 0
    if sites_df is not None and not sites_df.empty:
        d_min, nearest_type = site_proximity_batch(lat, lon, sites_df)
        geofence_violations = int(np.sum(d_min > OFFSITE_KM))
        # Count site-proximate pings with type-specific radius.
        if len(d_min) == n:
            radius_by_ping = np.array([site_match_radius_km(t) for t in nearest_type], dtype=np.float64)
            near = d_min <= radius_by_ping
            for st in (SITE_TYPE_MFC, SITE_TYPE_SERVICE, SITE_TYPE_STORE):
                visit_by_type[st] = int(np.sum(near & (nearest_type == st)))

    if sum(visit_by_type.values()) == 0:
        most = "No fixed-site visits"
    else:
        most = max(visit_by_type, key=lambda k: visit_by_type[k])

    # Productivity heuristics
    if active_hours > 0 and total_distance_km / active_hours < 2:
        notes.append("Low distance density — possible office / dense-urban day.")
    if active_hours > 0 and total_distance_km / active_hours > 35:
        notes.append("High mileage — heavy field coverage.")
    if stationary_time_seconds > travel_time_seconds * 1.5 and active_hours > 2:
        notes.append("Long dwell vs movement — many stops or traffic.")
    if num_stops > 12:
        notes.append("High stop count — fragmented route.")
    if geofence_violations > n * 0.3:
        notes.append("Many pings far from Y/SC/T — review off-corridor work.")
    if not notes:
        notes.append("Typical field movement pattern for this window.")

    return MovementAnalytics(
        total_distance_km=round(total_distance_km, 2),
        travel_time_seconds=round(travel_time_seconds, 1),
        stationary_time_seconds=round(stationary_time_seconds, 1),
        num_stops=num_stops,
        gps_pings=n,
        active_hours=round(active_hours, 2),
        longest_stop_seconds=round(longest_stop_seconds, 1),
        avg_stop_seconds=round(avg_stop_seconds, 1),
        most_visited_location_type=most,
        unique_locations=unique_locations,
        geofence_violations=int(geofence_violations),
        first_ts=first_ts,
        last_ts=last_ts,
        productivity_notes=notes,
        visit_by_type=visit_by_type,
    )


def slice_employee_window(
    full_df: pd.DataFrame,
    employee: str,
    day: date,
    t_from: time,
    t_to: time,
) -> pd.DataFrame:
    name_col = REQUIRED_COLUMNS["employee_name"]
    start = pd.Timestamp.combine(day, t_from)
    end = pd.Timestamp.combine(day, t_to)
    m = (full_df[name_col] == employee) & (full_df["_ts"] >= start) & (full_df["_ts"] <= end)
    return full_df.loc[m].sort_values("_ts").reset_index(drop=True)


def timeline_chart_data(day_df: pd.DataFrame) -> pd.DataFrame:
    """Timestamps and cumulative km for the movement timeline chart (X = clock time)."""
    lat_col = REQUIRED_COLUMNS["latitude"]
    lon_col = REQUIRED_COLUMNS["longitude"]
    if day_df.empty:
        return pd.DataFrame(columns=["ts", "cum_km"])
    ts0 = pd.to_datetime(day_df["_ts"])
    if ts0.is_monotonic_increasing:
        df = day_df.reset_index(drop=True)
    else:
        df = day_df.sort_values("_ts").reset_index(drop=True)
    if len(df) > 500:
        ix = np.unique(np.linspace(0, len(df) - 1, num=500, dtype=np.int64))
        df = df.iloc[ix].sort_values("_ts").reset_index(drop=True)
    lat = df[lat_col].astype(float).values
    lon = df[lon_col].astype(float).values
    ts = pd.to_datetime(df["_ts"])
    if len(df) < 2:
        return pd.DataFrame({"ts": ts, "cum_km": [0.0]})
    d_km = haversine_km(lat[:-1], lon[:-1], lat[1:], lon[1:])
    cum = np.concatenate([[0.0], np.cumsum(d_km)])
    return pd.DataFrame({"ts": ts, "cum_km": cum})


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    m, s = divmod(int(seconds), 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


def pct_delta(current: float, previous: float) -> float | None:
    if previous <= 0:
        return None
    return round(100.0 * (current - previous) / previous, 1)
