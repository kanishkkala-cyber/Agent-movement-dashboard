"""Operations Alert Center — leadership monitoring (not fraud detection)."""

from __future__ import annotations

from datetime import date, time
from typing import Any

import pandas as pd

from analytics import detect_stops, slice_employee_window
from field_ops_analytics import _df_for_stops, compute_field_intelligence

DAY_START = time(0, 0)
DAY_END = time(23, 59, 59)

# Configurable thresholds
THRESHOLDS: dict[str, float | int | tuple[int, int]] = {
    "transit_pct_of_active": 70.0,
    "low_productive_pct": 25.0,
    "long_idle_s": 7200.0,
    "low_active_hours": 2.0,
    "low_distance_km": 2.0,
    "low_pings": 15,
    "high_distance_km": 40.0,
    "low_visits": 2,
    "excessive_stop_s": 10800.0,
    "offsite_unknown_pct": 40.0,
    "noon_hour_start": 12,
    "noon_hour_end": 15,
    "noon_max_pings": 2,
    "noon_max_movement_km": 0.5,
    "transit_efficiency_good": 2.5,
    "transit_efficiency_good_visits": 3,
    "top_performer_min_productive_pct": 55.0,
}

SEVERITY_RANK = {"critical": 4, "warning": 3, "mild": 2, "positive": 1, "neutral": 0}

ALERT_TYPE_LABELS = {
    "insufficient_data": "Insufficient data",
    "high_transit": "High transit time",
    "low_productive": "Low productive time",
    "long_idle": "Long idle period",
    "low_activity": "Low field activity",
    "high_travel_low_visits": "High travel, low visits",
    "excessive_stop": "Extended stop duration",
    "offsite_activity": "Off-site activity",
    "noon_inactivity": "Midday inactivity",
    "transit_efficiency_good": "Efficient routing",
    "transit_efficiency_bad": "Low route efficiency",
    "top_performer": "Top performer",
    "fleet_low_engagement": "Fleet · low engagement",
    "fleet_transit_region": "Fleet · regional transit",
    "fleet_team_leader": "Fleet · team leader",
    "fleet_transit_heavy": "Fleet · travel intensity",
}

ALERT_ICONS: dict[str, str] = {
    "insufficient_data": "○",
    "high_transit": "🚗",
    "low_productive": "📉",
    "long_idle": "⏸",
    "low_activity": "📡",
    "high_travel_low_visits": "🛣",
    "excessive_stop": "📍",
    "offsite_activity": "🗺",
    "noon_inactivity": "🕐",
    "transit_efficiency_good": "✓",
    "transit_efficiency_bad": "⚡",
    "top_performer": "★",
    "fleet_low_engagement": "👥",
    "fleet_transit_region": "🧭",
    "fleet_team_leader": "🏆",
    "fleet_transit_heavy": "🚛",
}

SEVERITY_LABELS = {
    "critical": "Critical",
    "warning": "Warning",
    "mild": "Mild",
    "positive": "Positive",
    "neutral": "Info",
}


def enrich_employee_alert_metrics(
    day_df: pd.DataFrame,
    sites_df: pd.DataFrame | None,
) -> dict[str, Any]:
    """Extra signals for alert rules (one employee-day window)."""
    intel = compute_field_intelligence(day_df, sites_df)
    ts = intel["time_split_s"]
    unknown_s = float(ts.get("unknown_time_s", 0))
    transit_s = float(intel["transit_time_s"])
    operational_s = float(intel["operational_time_s"])
    measured = operational_s + transit_s + unknown_s
    active_s = float(intel.get("active_time_s") or 0)
    denom = measured if measured > 0 else active_s
    transit_pct = round(100.0 * transit_s / denom, 1) if denom > 0 else 0.0
    unknown_pct = round(100.0 * unknown_s / denom, 1) if denom > 0 else 0.0

    stops = detect_stops(_df_for_stops(day_df)) if not day_df.empty else []
    max_stop_s = max((s[2] for s in stops), default=0.0)

    noon_start = int(THRESHOLDS["noon_hour_start"])
    noon_end = int(THRESHOLDS["noon_hour_end"])
    noon_pings = 0
    noon_km = 0.0
    if not day_df.empty and len(day_df) >= 2:
        tss = pd.to_datetime(day_df["_ts"])
        hours = tss.dt.hour
        noon_mask = (hours >= noon_start) & (hours < noon_end)
        noon_pings = int(noon_mask.sum())
        hourly = intel.get("hourly_utilization") or []
        for h in hourly:
            hr = int(h["hour"])
            if noon_start <= hr < noon_end:
                noon_km += float(h.get("movement_km", 0))

    return {
        "unknown_time_s": unknown_s,
        "measured_time_s": denom,
        "transit_pct_of_active": transit_pct,
        "unknown_pct_of_active": unknown_pct,
        "max_stop_duration_s": max_stop_s,
        "noon_pings": noon_pings,
        "noon_movement_km": round(noon_km, 2),
        "transit_efficiency_label": intel.get("transit_efficiency_label", ""),
        "transit_efficiency": float(intel.get("transit_efficiency") or 0),
        "productive_time_pct": float(intel["productive_time_pct"]),
    }


def _fmt_dur(sec: float) -> str:
    if sec < 60:
        return f"{int(sec)}s"
    m, s = divmod(int(sec), 60)
    if m < 60:
        return f"{m}m"
    h, rem = divmod(m, 60)
    return f"{h}h {rem}m"


def _details_for(alert_type: str, metrics: dict[str, Any]) -> list[str]:
    """Operational context bullets for expandable alert cards."""
    lines: list[str] = []
    if alert_type == "high_transit":
        lines.append(
            f"Transit consumed {metrics.get('transit_pct', 0):.0f}% of measured active time "
            f"({metrics.get('active_hours', 0):.1f} h active)."
        )
        lines.append("Review route sequencing and territory assignment for this agent.")
    elif alert_type == "low_productive":
        lines.append(
            f"Only {metrics.get('productive_pct', 0):.0f}% of active hours were at operational sites."
        )
        lines.append("Leadership action: verify visit plan and on-site engagement.")
    elif alert_type in ("long_idle", "excessive_stop"):
        dur = float(metrics.get("duration_s", 0))
        lines.append(f"Longest continuous stationary period: {_fmt_dur(dur)}.")
        lines.append("Confirm whether this aligns with scheduled service or waiting time.")
    elif alert_type == "low_activity":
        lines.append(
            f"Active {metrics.get('active_hours', 0):.1f} h · "
            f"{metrics.get('distance_km', 0):.1f} km · {metrics.get('gps_pings', 0)} pings."
        )
        lines.append("May indicate GPS gaps, leave, or limited field deployment.")
    elif alert_type == "high_travel_low_visits":
        lines.append(
            f"{metrics.get('distance_km', 0):.1f} km travelled with only "
            f"{metrics.get('visits', 0)} operational visits."
        )
        lines.append("High travel with low site engagement — routing inefficiency likely.")
    elif alert_type == "offsite_activity":
        lines.append(f"{metrics.get('unknown_pct', 0):.0f}% of time unclassified or off operational sites.")
    elif alert_type == "noon_inactivity":
        lines.append(
            f"Midday window: {metrics.get('noon_pings', 0)} pings, "
            f"{metrics.get('noon_movement_km', 0):.1f} km movement."
        )
    elif alert_type == "transit_efficiency_good":
        lines.append(
            f"{metrics.get('visits', 0)} visits across {metrics.get('distance_km', 0):.1f} km "
            f"(efficiency {metrics.get('efficiency', 0):.2f})."
        )
    elif alert_type == "transit_efficiency_bad":
        lines.append("Travel distance is high relative to completed operational stops.")
    elif alert_type == "top_performer":
        lines.append(
            f"Productive time {metrics.get('productive_pct', 0):.0f}% · "
            f"efficiency score {metrics.get('efficiency_score', 0):.0f}."
        )
    elif alert_type == "fleet_low_engagement":
        lines.append(f"{metrics.get('count', 0)} employees flagged with low productive time today.")
    elif alert_type == "fleet_transit_region":
        lines.append(
            f"Region {metrics.get('region', '')}: {metrics.get('count', 0)} transit-heavy alerts."
        )
    elif alert_type == "fleet_team_leader":
        lines.append(
            f"Team {metrics.get('team', '')} averaged "
            f"{metrics.get('avg_productive_pct', 0):.0f}% productive time."
        )
    return lines


def _alert(
    *,
    alert_type: str,
    severity: str,
    employee: str,
    team: str,
    region: str,
    title: str,
    message: str,
    metrics: dict[str, Any],
    day: str,
    impact_score: float,
    details: list[str] | None = None,
) -> dict[str, Any]:
    det = details if details is not None else _details_for(alert_type, metrics)
    return {
        "id": f"{day}:{employee or 'fleet'}:{alert_type}",
        "type": alert_type,
        "type_label": ALERT_TYPE_LABELS.get(alert_type, alert_type),
        "icon": ALERT_ICONS.get(alert_type, "◆"),
        "severity": severity,
        "severity_label": SEVERITY_LABELS.get(severity, severity.title()),
        "severity_rank": SEVERITY_RANK.get(severity, 2),
        "employee": employee,
        "team": team,
        "region": region,
        "title": title,
        "message": message,
        "metrics": metrics,
        "details": det,
        "day": day,
        "timestamp": day,
        "impact_score": round(impact_score, 1),
        "trend": "new",
    }


_MIN_PINGS_FOR_ALERTS = 3
_MIN_ACTIVE_HOURS_FOR_ALERTS = 0.5   # 30 minutes


def _has_sufficient_data(row: dict[str, Any]) -> bool:
    """Return True only if the employee has enough data to generate meaningful alerts."""
    pings = int(row.get("gps_pings", 0))
    active_h = float(row.get("active_hours", 0))
    return pings >= _MIN_PINGS_FOR_ALERTS and active_h >= _MIN_ACTIVE_HOURS_FOR_ALERTS


def _insufficient_data_alert(row: dict[str, Any], day: str) -> dict[str, Any]:
    """Neutral informational alert for employees with too little GPS data."""
    emp = row["employee"]
    pings = int(row.get("gps_pings", 0))
    active_h = float(row.get("active_hours", 0))
    return _alert(
        alert_type="insufficient_data",
        severity="neutral",
        employee=emp,
        team=row.get("team", "Unassigned"),
        region=row.get("region", "Unassigned"),
        title="Insufficient data",
        message=(
            f"Limited GPS records for {emp} — "
            f"{pings} ping{'s' if pings != 1 else ''} captured"
            + (f", {active_h:.1f} h active" if active_h > 0 else "")
            + ". No operational alerts generated."
        ),
        metrics={"gps_pings": pings, "active_hours": round(active_h, 2)},
        day=day,
        impact_score=0.0,
        details=[
            f"Only {pings} GPS ping{'s' if pings != 1 else ''} recorded for this employee on this date.",
            "Alerts require ≥3 pings and ≥30 min active time to avoid false positives.",
            "This may indicate GPS off, no field activity, leave, or device issues.",
        ],
    )


def _employee_alerts(row: dict[str, Any], metrics: dict[str, Any], day: str) -> list[dict[str, Any]]:
    if not row.get("has_activity"):
        return []

    if not _has_sufficient_data(row):
        return [_insufficient_data_alert(row, day)]

    emp = row["employee"]
    team = row.get("team", "Unassigned")
    region = row.get("region", "Unassigned")
    alerts: list[dict[str, Any]] = []

    active_h = float(row["active_hours"])
    dist = float(row["distance_km"])
    visits = int(row["operational_visits"])
    prod_pct = float(row["productive_time_pct"])
    pings = int(row["gps_pings"])
    transit_pct = float(metrics["transit_pct_of_active"])
    unknown_pct = float(metrics["unknown_pct_of_active"])
    max_stop = float(metrics["max_stop_duration_s"])
    eff = float(metrics["transit_efficiency"])
    eff_label = str(metrics.get("transit_efficiency_label") or "")

    t = THRESHOLDS

    if transit_pct >= float(t["transit_pct_of_active"]) and active_h >= 1.0:
        alerts.append(
            _alert(
                alert_type="high_transit",
                severity="warning",
                employee=emp,
                team=team,
                region=region,
                title="High transit time",
                message=f"{emp} spent {transit_pct:.0f}% of active hours in transit.",
                metrics={"transit_pct": transit_pct, "active_hours": active_h},
                day=day,
                impact_score=transit_pct * 0.4,
            )
        )

    if prod_pct < float(t["low_productive_pct"]) and active_h >= 1.5:
        alerts.append(
            _alert(
                alert_type="low_productive",
                severity="critical",
                employee=emp,
                team=team,
                region=region,
                title="Low productive time",
                message=f"{emp} spent only {prod_pct:.0f}% of active hours at operational locations.",
                metrics={"productive_pct": prod_pct, "active_hours": active_h},
                day=day,
                impact_score=100 - prod_pct,
            )
        )

    if max_stop >= float(t["long_idle_s"]):
        alerts.append(
            _alert(
                alert_type="long_idle",
                severity="warning",
                employee=emp,
                team=team,
                region=region,
                title="Long idle period",
                message=f"{emp} remained stationary for {_fmt_dur(max_stop)} during active hours.",
                metrics={"duration_s": max_stop},
                day=day,
                impact_score=min(90.0, max_stop / 120),
            )
        )

    low_act = (
        active_h < float(t["low_active_hours"])
        or dist < float(t["low_distance_km"])
        or pings < int(t["low_pings"])
    )
    if low_act:
        alerts.append(
            _alert(
                alert_type="low_activity",
                severity="mild",
                employee=emp,
                team=team,
                region=region,
                title="Low field activity",
                message=f"Low field activity detected for {emp} today ({active_h:.1f} h active, {dist:.1f} km, {pings} pings).",
                metrics={
                    "active_hours": active_h,
                    "distance_km": dist,
                    "gps_pings": pings,
                },
                day=day,
                impact_score=50 - min(active_h * 10, dist * 2, pings),
            )
        )

    if dist >= float(t["high_distance_km"]) and visits < int(t["low_visits"]):
        alerts.append(
            _alert(
                alert_type="high_travel_low_visits",
                severity="warning",
                employee=emp,
                team=team,
                region=region,
                title="High travel, low visits",
                message=f"{emp}: high travel ({dist:.1f} km) with low operational engagement ({visits} visits).",
                metrics={"distance_km": dist, "visits": visits},
                day=day,
                impact_score=dist * 0.5 + (10 - visits) * 5,
            )
        )

    if max_stop >= float(t["excessive_stop_s"]):
        alerts.append(
            _alert(
                alert_type="excessive_stop",
                severity="mild",
                employee=emp,
                team=team,
                region=region,
                title="Extended stop duration",
                message=f"Extended stop duration observed for {emp} ({_fmt_dur(max_stop)} at one location).",
                metrics={"duration_s": max_stop},
                day=day,
                impact_score=max_stop / 200,
            )
        )

    if unknown_pct >= float(t["offsite_unknown_pct"]) and active_h >= 2.0:
        alerts.append(
            _alert(
                alert_type="offsite_activity",
                severity="warning",
                employee=emp,
                team=team,
                region=region,
                title="Off-site activity",
                message=f"Significant field time away from operational sites for {emp} ({unknown_pct:.0f}% unclassified/off-site).",
                metrics={"unknown_pct": unknown_pct},
                day=day,
                impact_score=unknown_pct * 0.6,
            )
        )

    noon_start = int(t["noon_hour_start"])
    noon_end = int(t["noon_hour_end"])
    spans_noon = active_h >= 4.0
    if spans_noon:
        noon_p = int(metrics["noon_pings"])
        noon_km = float(metrics["noon_movement_km"])
        if noon_p <= int(t["noon_max_pings"]) and noon_km < float(t["noon_max_movement_km"]):
            alerts.append(
                _alert(
                    alert_type="noon_inactivity",
                    severity="mild",
                    employee=emp,
                    team=team,
                    region=region,
                    title="Midday inactivity",
                    message=f"Operational inactivity detected for {emp} during core hours ({noon_start}:00–{noon_end}:00).",
                    metrics={"noon_pings": noon_p, "noon_movement_km": noon_km},
                    day=day,
                    impact_score=25.0,
                )
            )

    if (
        eff >= float(t["transit_efficiency_good"])
        and visits >= int(t["transit_efficiency_good_visits"])
        and prod_pct >= 40
    ):
        alerts.append(
            _alert(
                alert_type="transit_efficiency_good",
                severity="positive",
                employee=emp,
                team=team,
                region=region,
                title="Efficient routing",
                message=f"Highly efficient multi-stop routing observed for {emp} ({visits} visits, {dist:.1f} km).",
                metrics={"visits": visits, "distance_km": dist, "efficiency": eff},
                day=day,
                impact_score=eff * 10,
            )
        )
    elif dist > float(t["high_distance_km"]) * 0.75 and visits <= int(t["low_visits"]) and active_h >= 3:
        alerts.append(
            _alert(
                alert_type="transit_efficiency_bad",
                severity="critical",
                employee=emp,
                team=team,
                region=region,
                title="Low route efficiency",
                message=f"Very low operational efficiency for {emp} — {eff_label or 'high travel, few stops'}.",
                metrics={
                    "distance_km": dist,
                    "visits": visits,
                    "transit_efficiency": eff,
                },
                day=day,
                impact_score=70.0,
            )
        )

    return alerts


def _fleet_context_alerts(
    alerts: list[dict[str, Any]],
    active: list[dict[str, Any]],
    team_comparison: list[dict[str, Any]],
    region_stats: list[dict[str, Any]],
    day: str,
) -> list[dict[str, Any]]:
    """Territory / team level summaries (no single employee)."""
    out: list[dict[str, Any]] = []
    if not active:
        return out

    low_prod = [a for a in alerts if a["type"] == "low_productive"]
    if len(low_prod) >= 3:
        out.append(
            _alert(
                alert_type="fleet_low_engagement",
                severity="warning",
                employee="",
                team="",
                region="",
                title="Widespread low engagement",
                message=f"Multiple employees ({len(low_prod)}) showing low operational engagement today.",
                metrics={"count": len(low_prod)},
                day=day,
                impact_score=float(len(low_prod) * 12),
            )
        )

    by_region: dict[str, int] = {}
    for a in alerts:
        if a["type"] == "high_transit" and a.get("region"):
            by_region[a["region"]] = by_region.get(a["region"], 0) + 1
    if by_region:
        top_reg = max(by_region, key=by_region.get)
        if by_region[top_reg] >= 2:
            out.append(
                _alert(
                    alert_type="fleet_transit_region",
                    severity="warning",
                    employee="",
                    team="",
                    region=top_reg,
                    title="Regional transit pattern",
                    message=f"Travel-heavy activity observed across {top_reg} region ({by_region[top_reg]} agents).",
                    metrics={"region": top_reg, "count": by_region[top_reg]},
                    day=day,
                    impact_score=float(by_region[top_reg] * 15),
                )
            )

    if team_comparison:
        top = team_comparison[0]
        if top.get("avg_productive_pct", 0) >= 45:
            out.append(
                _alert(
                    alert_type="fleet_team_leader",
                    severity="positive",
                    employee="",
                    team=top["team"],
                    region="",
                    title="Team productivity leader",
                    message=f"Service team {top['team']} showed strongest productivity today ({top['avg_productive_pct']:.0f}% avg).",
                    metrics={"team": top["team"], "avg_productive_pct": top["avg_productive_pct"]},
                    day=day,
                    impact_score=float(top["avg_productive_pct"]),
                )
            )

    heavy = sum(1 for r in active if r["distance_km"] > 20)
    if heavy >= max(2, len(active) // 4):
        out.append(
            _alert(
                alert_type="fleet_transit_heavy",
                severity="mild",
                employee="",
                team="",
                region="",
                title="Fleet travel intensity",
                message=f"{heavy} employees logged more than 20 km today — review routing and territory coverage.",
                metrics={"count": heavy},
                day=day,
                impact_score=float(heavy * 8),
            )
        )

    return out


def build_smart_insights(
    alerts: list[dict[str, Any]],
    active: list[dict[str, Any]],
    team_comparison: list[dict[str, Any]],
    region_stats: list[dict[str, Any]],
) -> list[str]:
    """Contextual fleet summaries for the alert center header."""
    if not active:
        return ["No field activity in the current view."]

    insights: list[str] = []
    low_prod = [a for a in alerts if a["type"] == "low_productive"]
    high_transit = [a for a in alerts if a["type"] == "high_transit"]

    if len(low_prod) >= 2:
        insights.append(
            f"Multiple employees ({len(low_prod)}) showing low operational engagement today."
        )

    by_region: dict[str, int] = {}
    for a in high_transit:
        reg = a.get("region") or "Unassigned"
        by_region[reg] = by_region.get(reg, 0) + 1
    if by_region:
        top_reg = max(by_region, key=by_region.get)
        if by_region[top_reg] >= 2:
            insights.append(
                f"Transit inefficiency concentrated in {top_reg} territory ({by_region[top_reg]} agents)."
            )

    if team_comparison:
        top = team_comparison[0]
        if top.get("avg_productive_pct", 0) >= 50:
            insights.append(
                f"Team {top['team']} showed strongest productivity today "
                f"({top['avg_productive_pct']:.0f}% avg on-site)."
            )

    heavy = sum(1 for r in active if r["distance_km"] > 25)
    if heavy >= max(2, len(active) // 5):
        insights.append(
            f"Travel-heavy activity observed — {heavy} employees exceeded 25 km today."
        )

    positives = [a for a in alerts if a["severity"] == "positive" and a.get("employee")]
    if len(positives) >= 2:
        insights.append(
            f"{len(positives)} positive operational signals — strong routing or productivity today."
        )

    if region_stats:
        weak = [r for r in region_stats if r.get("avg_productive_pct", 100) < 30]
        strong = [r for r in region_stats if r.get("avg_productive_pct", 0) >= 55]
        if weak:
            insights.append(
                f"{weak[0]['region']} territory averaging "
                f"{weak[0]['avg_productive_pct']:.0f}% productive time — review coverage."
            )
        if strong:
            insights.append(
                f"{strong[0]['region']} region leads fleet productive time "
                f"({strong[0]['avg_productive_pct']:.0f}% avg)."
            )

    crit_emp = {a["employee"] for a in alerts if a["severity"] == "critical" and a.get("employee")}
    if crit_emp:
        names = ", ".join(sorted(crit_emp)[:3])
        suffix = f" +{len(crit_emp) - 3} more" if len(crit_emp) > 3 else ""
        insights.append(f"Employees needing immediate attention: {names}{suffix}.")

    if not insights:
        insights.append("Field operations are within normal parameters for the selected filters.")
    return insights[:6]


def enrich_with_previous_day(
    payload: dict[str, Any],
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    """Attach day-over-day trend metadata to alerts and summary."""
    if not previous:
        payload["trends"] = None
        return payload

    prev_alerts = previous.get("alerts") or []
    prev_summary = previous.get("summary") or {}
    cur_summary = payload["summary"]

    prev_keys: dict[tuple[str, str], str] = {}
    for a in prev_alerts:
        key = (a.get("employee") or "", a.get("type", ""))
        prev_keys[key] = a.get("severity", "mild")

    for a in payload["alerts"]:
        key = (a.get("employee") or "", a.get("type", ""))
        if key not in prev_keys:
            a["trend"] = "new"
        else:
            prev_rank = SEVERITY_RANK.get(prev_keys[key], 2)
            cur_rank = a.get("severity_rank", 2)
            if cur_rank > prev_rank:
                a["trend"] = "escalated"
            elif cur_rank < prev_rank:
                a["trend"] = "improved"
            else:
                a["trend"] = "recurring"

    payload["trends"] = {
        "previous_day": previous.get("day"),
        "total_delta": cur_summary.get("total", 0) - prev_summary.get("total", 0),
        "critical_delta": cur_summary.get("critical", 0) - prev_summary.get("critical", 0),
        "warning_delta": cur_summary.get("warning", 0) - prev_summary.get("warning", 0),
        "positive_delta": cur_summary.get("positive", 0) - prev_summary.get("positive", 0),
    }
    return payload


def build_operations_alerts(
    full_df: pd.DataFrame,
    day: date,
    sites_df: pd.DataFrame | None,
    rows: list[dict[str, Any]],
    *,
    team_comparison: list[dict[str, Any]] | None = None,
    region_stats: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Generate all alerts + executive summary for the alert center."""
    day_s = str(day)
    active = [r for r in rows if r.get("has_activity")]
    # Only employees with sufficient data participate in operational alert rules
    sufficient = [r for r in active if _has_sufficient_data(r)]
    all_alerts: list[dict[str, Any]] = []

    for row in active:
        w = slice_employee_window(full_df, row["employee"], day, DAY_START, DAY_END)
        metrics = enrich_employee_alert_metrics(w, sites_df)
        all_alerts.extend(_employee_alerts(row, metrics, day_s))

    if sufficient:
        top_prod = max(sufficient, key=lambda x: x["productive_time_pct"])
        if top_prod["productive_time_pct"] >= float(THRESHOLDS["top_performer_min_productive_pct"]):
            all_alerts.append(
                _alert(
                    alert_type="top_performer",
                    severity="positive",
                    employee=top_prod["employee"],
                    team=top_prod.get("team", "Unassigned"),
                    region=top_prod.get("region", "Unassigned"),
                    title="Top performer",
                    message=f"{top_prod['employee']} achieved highest productive time today ({top_prod['productive_time_pct']:.0f}%).",
                    metrics={
                        "productive_pct": top_prod["productive_time_pct"],
                        "efficiency_score": top_prod["efficiency_score"],
                    },
                    day=day_s,
                    impact_score=float(top_prod["productive_time_pct"]),
                )
            )

    # Fleet-level insights use only employees with sufficient data
    all_alerts.extend(
        _fleet_context_alerts(
            [a for a in all_alerts if a["type"] != "insufficient_data"],
            sufficient,
            team_comparison or [],
            region_stats or [],
            day_s,
        )
    )

    # Neutral insufficient-data entries sort to the bottom
    all_alerts.sort(key=lambda a: (-a["severity_rank"], -a["impact_score"], a.get("employee", "")))

    # Summary excludes neutral/informational entries from actionable counts
    operational = [a for a in all_alerts if a["severity"] != "neutral"]
    summary = {
        "total": len(operational),
        "critical": sum(1 for a in operational if a["severity"] == "critical"),
        "warning": sum(1 for a in operational if a["severity"] == "warning"),
        "mild": sum(1 for a in operational if a["severity"] == "mild"),
        "positive": sum(1 for a in operational if a["severity"] == "positive"),
        "insufficient_data": sum(1 for a in all_alerts if a["type"] == "insufficient_data"),
    }

    alert_types = sorted({a["type"] for a in all_alerts if a["type"] != "insufficient_data"})
    smart_insights = build_smart_insights(
        operational,
        sufficient,
        team_comparison or [],
        region_stats or [],
    )

    return {
        "alerts": all_alerts,
        "summary": summary,
        "smart_insights": smart_insights,
        "alert_types": alert_types,
        "thresholds": {k: v for k, v in THRESHOLDS.items() if not isinstance(v, tuple)},
        "trends": None,
    }
