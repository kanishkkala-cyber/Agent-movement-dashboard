"""Shared data loading and map logic for Repo Agent Tracking."""

from __future__ import annotations

import io
import os
import re
import urllib.error
import urllib.request
from datetime import time
from pathlib import Path
from typing import BinaryIO

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import folium
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

REQUIRED_COLUMNS = {
    "employee_name": "Employee Name",
    "time_stamp": "Time Stamp",
    "latitude": "Latitude",
    "longitude": "Longitude",
}

# Flexible headers for Google Sheets / CSV (first match wins).
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "employee_name": (
        "Employee Name",
        "Employee",
        "Name",
        "Agent Name",
        "Agent",
        "Employee name",
    ),
    "time_stamp": (
        "Time Stamp",
        "Timestamp",
        "Time",
        "Date Time",
        "DateTime",
        "Punch Time",
        "Date",
    ),
    "latitude": ("Latitude", "Lat", "lat", "LAT"),
    "longitude": ("Longitude", "Long", "Lng", "Lon", "lon", "LNG"),
}

DATA_SUBDIR = "Data-day-wise"
SITES_SUBDIR = "Site Locations"

ALL_AGENTS_LABEL = "All agents"

SITE_TYPE_MFC = "MFC yard"
SITE_TYPE_SERVICE = "Service centre"
SITE_TYPE_STORE = "Turno store"

# Minimal basemap — avoids hospital / ambulance POI clutter on default OSM tiles.
CLEAN_TILE = "CartoDB positron"
CLEAN_TILE_ATTR = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> '
    '&copy; <a href="https://carto.com/attributions">CARTO</a>'
)

# Folium slows down with thousands of markers / poly vertices; thin before render.
MAP_SINGLE_ROUTE_MAX_POINTS = 600
MAP_MULTI_AGENT_ROUTE_MAX_POINTS = 400

SITE_MARKER_STYLES: dict[str, dict[str, str]] = {
    SITE_TYPE_MFC: {"label": "Y", "bg": "#92400e", "border": "#fff"},
    SITE_TYPE_SERVICE: {"label": "SC", "bg": "#0369a1", "border": "#fff"},
    SITE_TYPE_STORE: {"label": "T", "bg": "#7c3aed", "border": "#fff"},
}

TRACKING_PAGE_CSS = """
<style>
    [data-testid="stMain"] > div:first-child {
        padding-top: 0.75rem;
    }
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0.5rem;
        max-width: 100%;
    }
    /* Only size the Folium map iframe — never all iframes (breaks Streamlit navigation). */
    iframe[title*="st_folium"],
    iframe[title*="folium"] {
        height: min(70vh, 720px) !important;
        min-height: 420px !important;
        max-height: 80vh !important;
    }
    .filter-panel {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1rem 1.1rem 0.35rem 1.1rem;
        margin-bottom: 0.75rem;
    }
    div[data-testid="stVerticalBlock"] > div.filter-panel + div {
        margin-top: 0;
    }
    .filter-panel label {
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        color: #475569 !important;
    }
    .filter-panel [data-testid="stCheckbox"] label p {
        font-size: 0.85rem !important;
    }
</style>
"""

# Distinct trajectory colors (cycles if there are more agents than swatches).
AGENT_TRAJECTORY_COLORS = [
    "#2563eb",
    "#dc2626",
    "#16a34a",
    "#ca8a04",
    "#9333ea",
    "#0891b2",
    "#ea580c",
    "#db2777",
    "#4f46e5",
    "#0d9488",
    "#b45309",
    "#7c3aed",
    "#0f766e",
    "#be123c",
    "#1d4ed8",
]


def _start_div_icon() -> folium.DivIcon:
    return folium.DivIcon(
        html=(
            '<div style="background:#16a34a;color:#fff;border:2px solid #fff;'
            "border-radius:50%;width:30px;height:30px;line-height:26px;"
            "text-align:center;font-weight:800;font-size:13px;font-family:system-ui,sans-serif;"
            'box-shadow:0 2px 8px rgba(0,0,0,.45);">S</div>'
        ),
        icon_size=(30, 30),
        icon_anchor=(15, 15),
    )


def _end_div_icon() -> folium.DivIcon:
    return folium.DivIcon(
        html=(
            '<div style="background:#dc2626;color:#fff;border:2px solid #fff;'
            "border-radius:50%;width:30px;height:30px;line-height:26px;"
            "text-align:center;font-weight:800;font-size:13px;font-family:system-ui,sans-serif;"
            'box-shadow:0 2px 8px rgba(0,0,0,.45);">E</div>'
        ),
        icon_size=(30, 30),
        icon_anchor=(15, 15),
    )


def _parse_lat_lon_pair(value) -> tuple[float | None, float | None]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None, None
    if isinstance(value, (int, float)) and not pd.isna(value):
        return None, None
    nums = re.findall(r"-?\d+\.?\d*", str(value).strip())
    if len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    return None, None


def _site_div_icon(site_type: str) -> folium.DivIcon:
    style = SITE_MARKER_STYLES[site_type]
    label = style["label"]
    w = 34 if len(label) > 1 else 28
    fs = 10 if len(label) > 1 else 12
    lh = w - 4
    return folium.DivIcon(
        html=(
            f'<div style="background:{style["bg"]};color:#fff;'
            f'border:2px solid {style["border"]};border-radius:6px;'
            f"width:{w}px;height:{w}px;line-height:{lh}px;"
            f"text-align:center;font-weight:800;font-size:{fs}px;"
            f'font-family:system-ui,sans-serif;box-shadow:0 2px 6px rgba(0,0,0,.4);">'
            f"{label}</div>"
        ),
        icon_size=(w, w),
        icon_anchor=(w // 2, w // 2),
    )


def _single_point_div_icon() -> folium.DivIcon:
    """One punch in the window: start and end coincide."""
    return folium.DivIcon(
        html=(
            '<div style="background:#ca8a04;color:#fff;border:2px solid #fff;'
            "border-radius:50%;width:34px;height:34px;line-height:30px;"
            "text-align:center;font-weight:800;font-size:10px;font-family:system-ui,sans-serif;"
            'box-shadow:0 2px 8px rgba(0,0,0,.45);">S·E</div>'
        ),
        icon_size=(34, 34),
        icon_anchor=(17, 17),
    )


def _rewind(source: Path | BinaryIO) -> None:
    if hasattr(source, "seek"):
        source.seek(0)  # type: ignore[union-attr]


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _find_header_row(source: Path | BinaryIO, sheet: str, max_scan: int = 25) -> int | None:
    _rewind(source)
    peek = pd.read_excel(source, sheet_name=sheet, header=None, nrows=max_scan)
    for i in range(len(peek)):
        cell0 = peek.iloc[i, 0]
        if pd.isna(cell0):
            continue
        if str(cell0).strip() == "Employee Number":
            return i
    return None


def _load_sheet(source: Path | BinaryIO, sheet: str) -> pd.DataFrame:
    hdr = _find_header_row(source, sheet)
    if hdr is None:
        return pd.DataFrame()
    _rewind(source)
    df = pd.read_excel(source, sheet_name=sheet, header=hdr)
    return _normalize_columns(df)


def load_excel_export(source: Path | BinaryIO, source_label: str) -> pd.DataFrame:
    """Load a single Keka location export; tolerates title rows above the header."""
    _rewind(source)
    xl = pd.ExcelFile(source, engine="openpyxl")
    frames: list[pd.DataFrame] = []
    for sheet in xl.sheet_names:
        _rewind(source)
        df = _load_sheet(source, sheet)
        if df.empty:
            continue
        missing = [
            c
            for key, c in REQUIRED_COLUMNS.items()
            if c not in df.columns
        ]
        if missing:
            continue
        df = df.loc[:, [c for c in df.columns if isinstance(c, str)]].copy()
        df["_source_file"] = source_label
        frames.append(df)
    if not frames:
        label = getattr(source, "name", source_label)
        raise ValueError(
            f"Could not find a sheet with columns "
            f"{list(REQUIRED_COLUMNS.values())} in {label}"
        )
    out = pd.concat(frames, ignore_index=True)
    return _prepare_locations(out)


def _prepare_locations(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    name_col = REQUIRED_COLUMNS["employee_name"]
    ts_col = REQUIRED_COLUMNS["time_stamp"]
    lat_col = REQUIRED_COLUMNS["latitude"]
    lon_col = REQUIRED_COLUMNS["longitude"]

    df[name_col] = df[name_col].astype(str).str.strip()
    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")

    df["_ts"] = pd.to_datetime(df[ts_col], errors="coerce", dayfirst=True)

    df = df.dropna(subset=[lat_col, lon_col, "_ts"], how="any")
    df = df[(df[lat_col].between(-90, 90)) & (df[lon_col].between(-180, 180))]
    df = df[(df[name_col].str.len() > 0) & (df[name_col] != "nan")]
    return df


def load_uploaded_bytes(data: bytes, name: str) -> pd.DataFrame:
    buf = io.BytesIO(data)
    p = Path(name)
    return load_excel_export(buf, source_label=p.stem)


def load_excel_from_path(path: Path) -> pd.DataFrame:
    return load_excel_export(path, source_label=path.stem)


def load_folder_raw(folder: str) -> pd.DataFrame:
    """Load all punch exports from a folder (no Streamlit cache — safe for FastAPI / CLI)."""
    p = Path(folder)
    if not p.is_dir():
        return pd.DataFrame()
    files = sorted(p.glob("*.xlsx"))
    if not files:
        return pd.DataFrame()
    parts: list[pd.DataFrame] = []
    for f in files:
        try:
            parts.append(load_excel_from_path(f))
        except Exception:
            parts.append(pd.DataFrame())
    parts = [x for x in parts if not x.empty]
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def google_sheet_export_url() -> str | None:
    """CSV export URL from .env — set GOOGLE_SHEET_URL or GOOGLE_SHEET_ID (+ optional GID)."""
    url = os.environ.get("GOOGLE_SHEET_URL", "").strip()
    if url:
        return url
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "").strip()
    if not sheet_id:
        return None
    gid = os.environ.get("GOOGLE_SHEET_GID", "0").strip() or "0"
    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    )


def punch_data_source_label() -> str:
    return "Google Sheet" if google_sheet_export_url() else f"local folder ({DATA_SUBDIR}/)"


def _pick_column(df: pd.DataFrame, canonical: str) -> str | None:
    cols = {str(c).strip(): c for c in df.columns}
    for alias in COLUMN_ALIASES.get(canonical, ()):
        if alias in cols:
            return cols[alias]
    lower = {str(c).strip().lower(): c for c in df.columns}
    for alias in COLUMN_ALIASES.get(canonical, ()):
        if alias.lower() in lower:
            return lower[alias.lower()]
    return None


def _find_csv_header_row(df: pd.DataFrame, max_scan: int = 30) -> int | None:
    """Keka-style exports: header row starts at 'Employee Number'."""
    for i in range(min(max_scan, len(df))):
        v = df.iloc[i, 0]
        if pd.isna(v):
            continue
        if str(v).strip() == "Employee Number":
            return i
    return None


def _dataframe_from_sheet_table(raw: pd.DataFrame) -> pd.DataFrame:
    """Map sheet columns to canonical names and return a prepared locations frame."""
    hdr = _find_csv_header_row(raw)
    if hdr is not None:
        header = [str(x).strip() for x in raw.iloc[hdr].tolist()]
        body = raw.iloc[hdr + 1 :].copy()
        body.columns = header
        df = _normalize_columns(body)
    else:
        df = _normalize_columns(raw)

    mapping: dict[str, str] = {}
    for key in REQUIRED_COLUMNS:
        col = _pick_column(df, key)
        if col is not None:
            mapping[key] = col

    missing = [k for k in REQUIRED_COLUMNS if k not in mapping]
    if missing:
        raise ValueError(
            "Google Sheet is missing columns for: "
            + ", ".join(missing)
            + ". Expected headers like Employee Name, Time Stamp, Latitude, Longitude."
        )

    out = pd.DataFrame(
        {
            REQUIRED_COLUMNS["employee_name"]: df[mapping["employee_name"]],
            REQUIRED_COLUMNS["time_stamp"]: df[mapping["time_stamp"]],
            REQUIRED_COLUMNS["latitude"]: df[mapping["latitude"]],
            REQUIRED_COLUMNS["longitude"]: df[mapping["longitude"]],
        }
    )
    out["_source_file"] = "google_sheet"
    return _prepare_locations(out)


def load_google_sheet_raw(url: str | None = None) -> pd.DataFrame:
    """Fetch published Google Sheet as CSV and parse lat/long punches."""
    export_url = (url or google_sheet_export_url() or "").strip()
    if not export_url:
        return pd.DataFrame()
    req = urllib.request.Request(
        export_url,
        headers={"User-Agent": "FieldOpsDashboard/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = resp.read()
    except urllib.error.HTTPError as e:
        raise ValueError(
            f"Could not read Google Sheet (HTTP {e.code}). "
            "Share the sheet: Anyone with the link → Viewer, or use File → Share → Publish."
        ) from e
    except urllib.error.URLError as e:
        raise ValueError(f"Could not reach Google Sheet: {e.reason}") from e

    raw = pd.read_csv(io.BytesIO(payload), header=None, low_memory=False)
    if raw.empty:
        return pd.DataFrame()
    return _dataframe_from_sheet_table(raw)


def load_punch_data_raw() -> pd.DataFrame:
    """Single source of truth: Google Sheet if configured, else Data-day-wise Excel files."""
    url = google_sheet_export_url()
    if url:
        return load_google_sheet_raw(url)
    return load_folder_raw(str(punch_data_dir()))


@st.cache_data(show_spinner="Loading GPS data…")
def load_punch_data_cached() -> pd.DataFrame:
    return load_punch_data_raw()


@st.cache_data(show_spinner=False)
def load_folder_cached(folder: str) -> pd.DataFrame:
    """Backward compatible — prefers Google Sheet when GOOGLE_SHEET_URL/ID is set."""
    if google_sheet_export_url():
        return load_punch_data_raw()
    return load_folder_raw(folder)


def clear_punch_data_cache() -> None:
    load_punch_data_cached.clear()
    load_folder_cached.clear()


def merge_folder_and_uploads(
    folder_df: pd.DataFrame, uploads: list[tuple[str, bytes]]
) -> pd.DataFrame:
    frames = []
    if not folder_df.empty:
        frames.append(folder_df)
    for fname, raw in uploads:
        try:
            frames.append(load_uploaded_bytes(raw, fname))
        except Exception as e:
            st.warning(f"Skipped upload **{fname}**: {e}")
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def load_site_locations_raw(folder: str) -> pd.DataFrame:
    """Load fixed sites from Site Locations/ (no Streamlit cache — safe for FastAPI)."""
    p = Path(folder)
    if not p.is_dir():
        return pd.DataFrame()
    rows: list[dict] = []

    mfc_path = p / "MFC Yards.xlsx"
    if mfc_path.is_file():
        mfc = pd.read_excel(mfc_path)
        for _, r in mfc.iterrows():
            lat = pd.to_numeric(r.get("Latitude"), errors="coerce")
            lon = pd.to_numeric(r.get("Longitude"), errors="coerce")
            if pd.isna(lat) or pd.isna(lon):
                continue
            rows.append(
                {
                    "site_type": SITE_TYPE_MFC,
                    "name": str(r.get("Yard Name", "")).strip(),
                    "city": str(r.get("City", "")).strip(),
                    "state": str(r.get("State", "")).strip(),
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "notes": str(r.get("Notes", "")).strip() if pd.notna(r.get("Notes")) else "",
                }
            )

    sc_path = p / "Service centres.xlsx"
    if sc_path.is_file():
        sc = pd.read_excel(sc_path)
        coord_col = "Coordinates (lat, long)"
        for _, r in sc.iterrows():
            lat, lon = _parse_lat_lon_pair(r.get(coord_col))
            if lat is None or lon is None:
                lat = pd.to_numeric(r.get("Latitude"), errors="coerce")
                lon = pd.to_numeric(r.get("Longitude"), errors="coerce")
                if pd.isna(lat) or pd.isna(lon):
                    continue
                lat, lon = float(lat), float(lon)
            rows.append(
                {
                    "site_type": SITE_TYPE_SERVICE,
                    "name": str(r.get("Service Centre", "")).strip(),
                    "city": str(r.get("City", "")).strip(),
                    "state": str(r.get("State", "")).strip(),
                    "latitude": lat,
                    "longitude": lon,
                    "notes": (
                        str(r["Note"]).strip()
                        if "Note" in r.index and pd.notna(r["Note"])
                        else (
                            str(r["Notes"]).strip()
                            if "Notes" in r.index and pd.notna(r["Notes"])
                            else ""
                        )
                    ),
                }
            )

    store_path = p / "Turno Stores.xlsx"
    if store_path.is_file():
        stores = pd.read_excel(store_path)
        for _, r in stores.iterrows():
            lat, lon = _parse_lat_lon_pair(r.get("Cordinates"))
            if lat is None or lon is None:
                continue
            addr = str(r.get("Store Address", "")).strip() if pd.notna(r.get("Store Address")) else ""
            rows.append(
                {
                    "site_type": SITE_TYPE_STORE,
                    "name": str(r.get("Store Name", "")).strip(),
                    "city": str(r.get("City", "")).strip(),
                    "state": str(r.get("State", "")).strip(),
                    "latitude": lat,
                    "longitude": lon,
                    "notes": addr,
                }
            )

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out = out[(out["latitude"].between(-90, 90)) & (out["longitude"].between(-180, 180))]
    return out.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_site_locations(folder: str) -> pd.DataFrame:
    """Streamlit-cached sites loader (same data as load_site_locations_raw)."""
    return load_site_locations_raw(folder)


def _make_base_map(center_lat: float, center_lon: float, zoom: int = 13) -> folium.Map:
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        control_scale=True,
        tiles=None,
    )
    folium.TileLayer(CLEAN_TILE, name="Clean map", attr=CLEAN_TILE_ATTR, control=False).add_to(m)
    return m


def _add_fixed_sites(
    m: folium.Map,
    sites_df: pd.DataFrame,
    *,
    show_mfc: bool,
    show_service: bool,
    show_stores: bool,
) -> None:
    if sites_df.empty:
        return
    type_filters = {
        SITE_TYPE_MFC: show_mfc,
        SITE_TYPE_SERVICE: show_service,
        SITE_TYPE_STORE: show_stores,
    }
    for site_type, visible in type_filters.items():
        if not visible:
            continue
        sub = sites_df[sites_df["site_type"] == site_type]
        if sub.empty:
            continue
        fg = folium.FeatureGroup(name=f"Fixed: {site_type}", show=True)
        for _, row in sub.iterrows():
            lat, lon = float(row["latitude"]), float(row["longitude"])
            name = row["name"]
            city = row.get("city", "")
            state = row.get("state", "")
            notes = row.get("notes", "")
            popup_html = (
                f"<b>{site_type}</b><br/><b>{name}</b><br/>"
                f"{city}, {state}<br/><small>{notes}</small>"
            )
            folium.Marker(
                location=[lat, lon],
                icon=_site_div_icon(site_type),
                popup=folium.Popup(popup_html, max_width=340),
                tooltip=f"{site_type}: {name[:40]}",
            ).add_to(fg)
        fg.add_to(m)


def _decimate_path_df(path_df: pd.DataFrame, max_points: int) -> tuple[pd.DataFrame, int]:
    """Return at most max_points rows (evenly spaced), preserving endpoints. Second value is original length."""
    n = len(path_df)
    if n <= max_points:
        return path_df.reset_index(drop=True), n
    ix = np.unique(np.linspace(0, n - 1, num=max_points, dtype=np.int64))
    return path_df.iloc[ix].reset_index(drop=True), n


def _fit_map_bounds(m: folium.Map, path_df: pd.DataFrame, lat_col: str, lon_col: str) -> None:
    if path_df.empty:
        return
    pad = 0.002
    south = float(path_df[lat_col].min()) - pad
    north = float(path_df[lat_col].max()) + pad
    west = float(path_df[lon_col].min()) - pad
    east = float(path_df[lon_col].max()) + pad
    if south == north and west == east:
        return
    m.fit_bounds([[south, west], [north, east]], padding=(28, 28))


def build_map(
    path_df: pd.DataFrame,
    *,
    all_agents: bool,
    sites_df: pd.DataFrame | None = None,
    show_mfc: bool = True,
    show_service: bool = True,
    show_stores: bool = True,
) -> folium.Map:
    name_col = REQUIRED_COLUMNS["employee_name"]
    lat_col = REQUIRED_COLUMNS["latitude"]
    lon_col = REQUIRED_COLUMNS["longitude"]
    addr_col = "Address" if "Address" in path_df.columns else None
    geo_col = "Geo-Location Name" if "Geo-Location Name" in path_df.columns else None

    center_lat = float(path_df[lat_col].mean())
    center_lon = float(path_df[lon_col].mean())
    m = _make_base_map(center_lat, center_lon, zoom=13)

    if sites_df is not None and not sites_df.empty:
        _add_fixed_sites(
            m,
            sites_df,
            show_mfc=show_mfc,
            show_service=show_service,
            show_stores=show_stores,
        )

    if path_df.empty:
        if sites_df is not None and not sites_df.empty:
            folium.LayerControl(collapsed=False).add_to(m)
        return m

    if not all_agents:
        map_df, orig_n = _decimate_path_df(path_df, MAP_SINGLE_ROUTE_MAX_POINTS)
        coords = list(zip(map_df[lat_col].tolist(), map_df[lon_col].tolist()))
        n_rows = len(map_df)
        pop_extra = ""
        if orig_n > n_rows:
            pop_extra = f'<br/><small><i>Map: {n_rows} of {orig_n} pings</i></small>'
        if n_rows >= 2:
            folium.PolyLine(
                coords,
                color="#2563eb",
                weight=4,
                opacity=0.85,
                smooth_factor=1.2,
            ).add_to(m)

        if n_rows == 1:
            row = map_df.iloc[0]
            lat, lon = float(row[lat_col]), float(row[lon_col])
            ts = row["_ts"]
            addr = ""
            if addr_col and pd.notna(row.get(addr_col)):
                addr = str(row[addr_col]).replace("\n", " ")[:500]
            geo = ""
            if geo_col and pd.notna(row.get(geo_col)):
                geo = str(row[geo_col])
            popup_html = (
                f"<b>Single punch</b> (start and end here)<br/>{ts}<br/>"
                f"<small>{geo}</small><br/><small>{addr}</small>"
            )
            folium.Marker(
                location=[lat, lon],
                icon=_single_point_div_icon(),
                popup=folium.Popup(popup_html, max_width=320),
                tooltip="Only punch in window — start and end",
            ).add_to(m)
        else:
            for idx, (_, row) in enumerate(map_df.iterrows()):
                lat, lon = float(row[lat_col]), float(row[lon_col])
                ts = row["_ts"]
                seq = idx + 1
                addr = ""
                if addr_col and pd.notna(row.get(addr_col)):
                    addr = str(row[addr_col]).replace("\n", " ")[:500]
                geo = ""
                if geo_col and pd.notna(row.get(geo_col)):
                    geo = str(row[geo_col])
                popup_html = (
                    f"<b>#{seq}</b> of {n_rows}<br/>{ts}<br/>"
                    f"<small>{geo}</small><br/><small>{addr}</small>{pop_extra}"
                )
                if idx == 0:
                    folium.Marker(
                        location=[lat, lon],
                        icon=_start_div_icon(),
                        popup=folium.Popup(popup_html, max_width=320),
                        tooltip=f"START — 1 of {n_rows} · {ts.strftime('%H:%M:%S')}",
                    ).add_to(m)
                elif idx == n_rows - 1:
                    folium.Marker(
                        location=[lat, lon],
                        icon=_end_div_icon(),
                        popup=folium.Popup(popup_html, max_width=320),
                        tooltip=f"END — {n_rows} of {n_rows} · {ts.strftime('%H:%M:%S')}",
                    ).add_to(m)
                else:
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=5,
                        color="#1d4ed8",
                        weight=2,
                        fill=True,
                        fill_color="#93c5fd",
                        fill_opacity=0.85,
                        popup=folium.Popup(popup_html, max_width=320),
                        tooltip=f"#{seq} of {n_rows} · {ts.strftime('%H:%M:%S')}",
                    ).add_to(m)
        _fit_map_bounds(m, path_df, lat_col, lon_col)
        if sites_df is not None and not sites_df.empty:
            folium.LayerControl(collapsed=False).add_to(m)
    else:
        names = sorted(path_df[name_col].dropna().unique().tolist())
        for i, agent in enumerate(names):
            color = AGENT_TRAJECTORY_COLORS[i % len(AGENT_TRAJECTORY_COLORS)]
            sub_full = path_df[path_df[name_col] == agent].sort_values("_ts").reset_index(drop=True)
            sub, sub_orig = _decimate_path_df(sub_full, MAP_MULTI_AGENT_ROUTE_MAX_POINTS)
            layer_name = agent if len(agent) <= 42 else agent[:39] + "…"
            fg = folium.FeatureGroup(name=layer_name, show=True)

            coords = list(zip(sub[lat_col].tolist(), sub[lon_col].tolist()))
            n_sub = len(sub)
            sub_pop_extra = ""
            if sub_orig > n_sub:
                sub_pop_extra = f'<br/><small><i>Map: {n_sub} of {sub_orig} pings</i></small>'
            if n_sub >= 2:
                folium.PolyLine(
                    coords,
                    color=color,
                    weight=4,
                    opacity=0.88,
                    smooth_factor=1.2,
                ).add_to(fg)

            if n_sub == 1:
                row = sub.iloc[0]
                lat, lon = float(row[lat_col]), float(row[lon_col])
                ts = row["_ts"]
                addr = ""
                if addr_col and pd.notna(row.get(addr_col)):
                    addr = str(row[addr_col]).replace("\n", " ")[:400]
                geo = ""
                if geo_col and pd.notna(row.get(geo_col)):
                    geo = str(row[geo_col])
                popup_html = (
                    f"<b>{agent}</b><br/>Single punch (start = end)<br/>{ts}<br/>"
                    f"<small>{geo}</small><br/><small>{addr}</small>"
                )
                folium.Marker(
                    location=[lat, lon],
                    icon=_single_point_div_icon(),
                    popup=folium.Popup(popup_html, max_width=320),
                    tooltip=f"{agent[:22]} — only punch",
                ).add_to(fg)
            else:
                for idx, (_, row) in enumerate(sub.iterrows()):
                    lat, lon = float(row[lat_col]), float(row[lon_col])
                    ts = row["_ts"]
                    seq = idx + 1
                    addr = ""
                    if addr_col and pd.notna(row.get(addr_col)):
                        addr = str(row[addr_col]).replace("\n", " ")[:400]
                    geo = ""
                    if geo_col and pd.notna(row.get(geo_col)):
                        geo = str(row[geo_col])
                    popup_html = (
                        f"<b>{agent}</b><br/>#{seq} of {n_sub} · {ts}<br/>"
                        f"<small>{geo}</small><br/><small>{addr}</small>{sub_pop_extra}"
                    )
                    if idx == 0:
                        folium.Marker(
                            location=[lat, lon],
                            icon=_start_div_icon(),
                            popup=folium.Popup(popup_html, max_width=320),
                            tooltip=f"{agent[:18]} · START 1/{n_sub} · {ts.strftime('%H:%M')}",
                        ).add_to(fg)
                    elif idx == n_sub - 1:
                        folium.Marker(
                            location=[lat, lon],
                            icon=_end_div_icon(),
                            popup=folium.Popup(popup_html, max_width=320),
                            tooltip=f"{agent[:18]} · END {n_sub}/{n_sub} · {ts.strftime('%H:%M')}",
                        ).add_to(fg)
                    else:
                        folium.CircleMarker(
                            location=[lat, lon],
                            radius=4,
                            color=color,
                            weight=2,
                            fill=True,
                            fill_color=color,
                            fill_opacity=0.35,
                            popup=folium.Popup(popup_html, max_width=320),
                            tooltip=f"{agent[:18]} · #{seq}/{n_sub} · {ts.strftime('%H:%M')}",
                        ).add_to(fg)
            fg.add_to(m)

        folium.LayerControl(collapsed=len(names) > 10).add_to(m)
        _fit_map_bounds(m, path_df, lat_col, lon_col)

    return m




def project_root() -> Path:
    return Path(__file__).resolve().parent


def punch_data_dir() -> Path:
    d = project_root() / DATA_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def sites_data_dir() -> Path:
    return project_root() / SITES_SUBDIR


def list_punch_files() -> list[Path]:
    return sorted(punch_data_dir().glob("*.xlsx"))


def save_punch_upload(filename: str, data: bytes) -> Path:
    safe = Path(filename).name
    if not safe.lower().endswith(".xlsx"):
        safe += ".xlsx"
    dest = punch_data_dir() / safe
    dest.write_bytes(data)
    clear_punch_data_cache()
    return dest


def delete_punch_file(path: Path) -> None:
    path = Path(path)
    if path.is_file() and path.parent.resolve() == punch_data_dir().resolve():
        path.unlink()
        clear_punch_data_cache()


def preview_upload(data: bytes, name: str) -> tuple[bool, str, int]:
    try:
        df = load_uploaded_bytes(data, name)
        n = len(df)
        if n == 0:
            return False, "No valid location rows found.", 0
        return True, f"{n} punches loaded OK.", n
    except Exception as e:
        return False, str(e), 0
