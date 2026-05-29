import { motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchDailyOverview } from "../api";
import { AlertCenter } from "../components/AlertCenter";
import { GlassCard } from "../components/GlassCard";
import type { DailyOverview, LeaderRow } from "../types/daily";

function fmtDur(sec: number) {
  if (sec < 60) return `${Math.round(sec)}s`;
  const m = Math.floor(sec / 60);
  const h = Math.floor(m / 60);
  if (h > 0) return `${h}h ${m % 60}m`;
  return `${m}m`;
}

const TIER_ROW: Record<string, string> = {
  high: "bg-emerald-950/40 hover:bg-emerald-900/30",
  medium: "bg-amber-950/20 hover:bg-amber-900/20",
  low: "bg-red-950/25 hover:bg-red-900/20",
};

export default function DailyOverviewPage() {
  const navigate = useNavigate();
  const [day, setDay] = useState(new Date().toISOString().slice(0, 10));
  const [teams, setTeams] = useState<string[]>([]);
  const [regions, setRegions] = useState<string[]>([]);
  const [locTypes, setLocTypes] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [data, setData] = useState<DailyOverview | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sortKey, setSortKey] = useState<keyof LeaderRow>("rank");
  const [sortAsc, setSortAsc] = useState(true);
  const [tableSearch, setTableSearch] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 15;

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const d = await fetchDailyOverview({
        day,
        teams,
        regions,
        locationTypes: locTypes,
        search,
      });
      setData(d);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Load failed");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [day, teams, regions, locTypes, search]);

  useEffect(() => {
    void load();
  }, [load]);

  const resetFilters = () => {
    setTeams([]);
    setRegions([]);
    setLocTypes([]);
    setSearch("");
    setTableSearch("");
    setPage(0);
  };

  const sortedRows = useMemo(() => {
    if (!data?.leaderboard) return [];
    let rows = [...data.leaderboard];
    if (tableSearch.trim()) {
      const q = tableSearch.toLowerCase();
      rows = rows.filter((r) => r.employee.toLowerCase().includes(q));
    }
    rows.sort((a, b) => {
      const av = a[sortKey] as number | string;
      const bv = b[sortKey] as number | string;
      if (typeof av === "number" && typeof bv === "number") {
        return sortAsc ? av - bv : bv - av;
      }
      return sortAsc
        ? String(av).localeCompare(String(bv))
        : String(bv).localeCompare(String(av));
    });
    return rows;
  }, [data, sortKey, sortAsc, tableSearch]);

  const pagedRows = useMemo(() => {
    const start = page * pageSize;
    return sortedRows.slice(start, start + pageSize);
  }, [sortedRows, page]);

  const totalPages = Math.max(1, Math.ceil(sortedRows.length / pageSize));

  const exportCsv = () => {
    if (!sortedRows.length) return;
    const headers = [
      "rank",
      "employee",
      "team",
      "distance_km",
      "productive_time_pct",
      "operational_visits",
      "active_hours",
      "efficiency_score",
    ];
    const lines = [
      headers.join(","),
      ...sortedRows.map((r) =>
        headers.map((h) => String((r as Record<string, unknown>)[h] ?? "")).join(",")
      ),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `leaderboard-${day}.csv`;
    a.click();
  };

  const k = data?.executive_kpis;

  const drill = (emp: string) => {
    navigate(`/tracking?employee=${encodeURIComponent(emp)}&day=${day}`);
  };

  return (
    <div className="p-6 pb-16">
      <header className="mb-6">
        <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-sky-400/90">
          Leadership overview
        </p>
        <h2 className="text-2xl font-semibold text-white">Daily Operations Overview</h2>
        <p className="mt-1 text-sm text-slate-400">
          All field employees for one day — rankings, comparisons, and operational visibility.
        </p>
      </header>

      <GlassCard className="mb-6">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Date
            <input
              type="date"
              value={day}
              onChange={(e) => setDay(e.target.value)}
              className="mt-1 rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-white"
            />
          </label>
          {data?.filter_options.teams && (
            <label className="text-[10px] font-semibold uppercase text-slate-500">
              Team
              <select
                multiple
                className="mt-1 block max-h-24 min-w-[120px] rounded-lg border border-slate-600 bg-slate-900 text-sm text-white"
                value={teams}
                onChange={(e) =>
                  setTeams(Array.from(e.target.selectedOptions, (o) => o.value))
                }
              >
                {data.filter_options.teams.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
          )}
          {data?.filter_options.regions && (
            <label className="text-[10px] font-semibold uppercase text-slate-500">
              Region
              <select
                multiple
                className="mt-1 block max-h-24 min-w-[120px] rounded-lg border border-slate-600 bg-slate-900 text-sm text-white"
                value={regions}
                onChange={(e) =>
                  setRegions(Array.from(e.target.selectedOptions, (o) => o.value))
                }
              >
                {data.filter_options.regions.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="text-[10px] font-semibold uppercase text-slate-500">
            Location
            <select
              multiple
              className="mt-1 block rounded-lg border border-slate-600 bg-slate-900 text-sm text-white"
              value={locTypes}
              onChange={(e) =>
                setLocTypes(Array.from(e.target.selectedOptions, (o) => o.value))
              }
            >
              {["yard", "service", "store"].map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <input
            placeholder="Employee search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-white"
          />
          <button
            type="button"
            onClick={resetFilters}
            className="rounded-xl border border-slate-600 px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-800/60"
          >
            Reset
          </button>
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            className="rounded-xl bg-gradient-to-r from-sky-500 to-indigo-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg disabled:opacity-50"
          >
            {loading ? "Loading…" : "Apply filters"}
          </button>
        </div>
      </GlassCard>

      {err && <div className="mb-4 rounded-lg border border-red-500/40 bg-red-950/40 p-3 text-red-200">{err}</div>}

      {loading && !data && <p className="text-slate-400">Loading leadership overview…</p>}

      {k && (
        <>
          <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {[
              ["Active employees", String(k.active_employees)],
              ["Total distance", `${k.total_distance_km.toFixed(1)} km`],
              ["Visits", String(k.total_operational_visits)],
              ["Avg productive %", `${k.avg_productive_time_pct.toFixed(1)}%`],
              ["Avg active h", k.avg_active_hours.toFixed(2)],
              ["GPS pings", String(k.total_gps_pings)],
              ["Avg visit", fmtDur(k.avg_visit_duration_s)],
              ["Avg transit h", k.avg_transit_hours.toFixed(2)],
              ["Top performer", k.top_performer.slice(0, 18)],
              ["Low activity", k.lowest_activity.slice(0, 18)],
            ].map(([lbl, val], i) => (
              <motion.div
                key={lbl}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
                className="rounded-xl border border-slate-600/40 bg-slate-900/60 p-3 shadow-[0_0_24px_rgba(56,189,248,0.06)]"
              >
                <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                  {lbl}
                </div>
                <div className="mt-1 text-lg font-bold text-white">{val}</div>
              </motion.div>
            ))}
          </div>

          {data.alert_center && (
            <AlertCenter data={data.alert_center} day={day} />
          )}

          <GlassCard title="Employee leaderboard" subtitle="Sort columns · click row to open detail view">
            <div className="mb-3 flex flex-wrap gap-2">
              <input
                placeholder="Filter table…"
                value={tableSearch}
                onChange={(e) => setTableSearch(e.target.value)}
                className="rounded-lg border border-slate-600 bg-slate-950 px-3 py-1.5 text-sm text-white"
              />
              <button
                type="button"
                className="rounded-lg border border-slate-600 px-3 py-1.5 text-xs text-slate-300 hover:border-sky-500/40"
                onClick={exportCsv}
              >
                Download CSV
              </button>
            </div>
            <div className="max-h-[420px] overflow-auto rounded-xl border border-slate-700/50">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="sticky top-0 z-10 bg-slate-900/95 text-slate-500">
                  <tr>
                    {(
                      [
                        ["rank", "Rank"],
                        ["employee", "Employee"],
                        ["team", "Team"],
                        ["distance_km", "Distance"],
                        ["productive_time_pct", "Productive %"],
                        ["operational_visits", "Visits"],
                        ["active_hours", "Active h"],
                        ["transit_time_s", "Transit"],
                        ["avg_visit_duration_s", "Avg visit"],
                        ["unique_locations", "Locations"],
                        ["efficiency_score", "Efficiency"],
                      ] as const
                    ).map(([key, label]) => (
                      <th
                        key={key}
                        className="cursor-pointer px-2 py-2 hover:text-sky-300"
                        onClick={() => {
                          if (sortKey === key) setSortAsc(!sortAsc);
                          else {
                            setSortKey(key);
                            setSortAsc(false);
                          }
                        }}
                      >
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {pagedRows.map((r) => (
                    <tr
                      key={r.employee}
                      className={`cursor-pointer border-t border-slate-800/80 ${TIER_ROW[r.performance_tier] ?? ""}`}
                      onClick={() => drill(r.employee)}
                    >
                      <td className="px-2 py-2">{r.rank}</td>
                      <td className="px-2 py-2 font-medium text-white">{r.employee}</td>
                      <td className="px-2 py-2">{r.team}</td>
                      <td className="px-2 py-2">{r.distance_km.toFixed(1)}</td>
                      <td className="px-2 py-2">{r.productive_time_pct.toFixed(0)}%</td>
                      <td className="px-2 py-2">{r.operational_visits}</td>
                      <td className="px-2 py-2">{r.active_hours.toFixed(2)}</td>
                      <td className="px-2 py-2">{fmtDur(r.transit_time_s)}</td>
                      <td className="px-2 py-2">{fmtDur(r.avg_visit_duration_s)}</td>
                      <td className="px-2 py-2">{r.unique_locations}</td>
                      <td className="px-2 py-2 text-sky-300">{r.efficiency_score.toFixed(0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
              <span>
                {sortedRows.length} employees · page {page + 1} of {totalPages}
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={page <= 0}
                  className="rounded border border-slate-600 px-2 py-1 disabled:opacity-40"
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                >
                  Prev
                </button>
                <button
                  type="button"
                  disabled={page >= totalPages - 1}
                  className="rounded border border-slate-600 px-2 py-1 disabled:opacity-40"
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                >
                  Next
                </button>
              </div>
            </div>
          </GlassCard>

          <GlassCard title="Quick actions" className="mb-5">
            <div className="flex flex-wrap gap-2">
              {data.top_performers[0] && (
                <button
                  type="button"
                  className="rounded-lg border border-slate-600 bg-slate-900/60 px-3 py-2 text-xs text-slate-200 hover:border-sky-500/50"
                  onClick={() => drill(data.top_performers[0].employee)}
                >
                  Open top performer
                </button>
              )}
              {data.bottom_performers[0] && (
                <button
                  type="button"
                  className="rounded-lg border border-slate-600 bg-slate-900/60 px-3 py-2 text-xs text-slate-200 hover:border-sky-500/50"
                  onClick={() => drill(data.bottom_performers[0].employee)}
                >
                  View lowest activity
                </button>
              )}
              <button
                type="button"
                className="rounded-lg border border-slate-600 bg-slate-900/60 px-3 py-2 text-xs text-slate-200 hover:border-sky-500/50"
                onClick={exportCsv}
              >
                Export leaderboard CSV
              </button>
            </div>
          </GlassCard>

          <div className="grid gap-5 lg:grid-cols-2">
            <GlassCard title="Productivity distribution">
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={[
                        { name: "High", value: data.productivity_distribution.high },
                        { name: "Medium", value: data.productivity_distribution.medium },
                        { name: "Low", value: data.productivity_distribution.low },
                      ]}
                      dataKey="value"
                      innerRadius={45}
                      outerRadius={70}
                    >
                      <Cell fill="#4ade80" />
                      <Cell fill="#fbbf24" />
                      <Cell fill="#f87171" />
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </GlassCard>
            <GlassCard title="Movement bands (km)">
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={[
                      { band: "<5 km", n: data.movement_distribution.low },
                      { band: "5–20", n: data.movement_distribution.moderate },
                      { band: ">20", n: data.movement_distribution.heavy },
                    ]}
                  >
                    <XAxis dataKey="band" stroke="#64748b" />
                    <YAxis stroke="#64748b" />
                    <Tooltip />
                    <Bar dataKey="n" fill="#38bdf8" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </GlassCard>
          </div>

          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <GlassCard title="Top 5 performers">
              {data.top_performers.map((r) => (
                <button
                  key={r.employee}
                  type="button"
                  className="mb-2 block w-full rounded-lg border border-slate-700/50 bg-slate-900/50 px-3 py-2 text-left text-sm hover:border-sky-500/40"
                  onClick={() => drill(r.employee)}
                >
                  <span className="font-semibold text-white">{r.employee}</span>
                  <span className="ml-2 text-slate-400">
                    {r.productive_time_pct.toFixed(0)}% · {r.operational_visits} visits
                  </span>
                </button>
              ))}
            </GlassCard>
            <GlassCard title="Lowest activity">
              {data.bottom_performers.map((r) => (
                <button
                  key={r.employee}
                  type="button"
                  className="mb-2 block w-full rounded-lg border border-slate-700/50 bg-slate-900/50 px-3 py-2 text-left text-sm hover:border-sky-500/40"
                  onClick={() => drill(r.employee)}
                >
                  <span className="font-semibold text-white">{r.employee}</span>
                  <span className="ml-2 text-slate-400">
                    {r.active_hours.toFixed(2)} h · {r.distance_km.toFixed(1)} km
                  </span>
                </button>
              ))}
            </GlassCard>
          </div>

          {data.team_comparison.length > 0 && (
            <GlassCard title="Team comparison" className="mt-5">
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.team_comparison} layout="vertical">
                    <XAxis type="number" stroke="#64748b" />
                    <YAxis type="category" dataKey="team" width={100} stroke="#64748b" />
                    <Tooltip />
                    <Bar dataKey="avg_productive_pct" fill="#818cf8" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </GlassCard>
          )}

          {data.hourly_operations.length > 0 && (
            <GlassCard title="Hourly operations heatmap" className="mt-5" subtitle="Field activity by hour">
              <div className="flex flex-wrap gap-1">
                {data.hourly_operations.map((h) => {
                  const maxP = Math.max(...data.hourly_operations.map((x) => x.pings), 1);
                  const intensity = h.pings / maxP;
                  return (
                    <div
                      key={h.hour}
                      title={`${h.hour}:00 — ${h.pings} pings · ${(h.movement_km).toFixed(1)} km`}
                      className="rounded-md border border-slate-800/80 p-1 text-center text-[9px] text-slate-500"
                      style={{
                        background: `rgba(56,189,248,${0.08 + intensity * 0.72})`,
                      }}
                    >
                      {h.hour}
                    </div>
                  );
                })}
              </div>
            </GlassCard>
          )}

          {data.location_breakdown_s && (
            <GlassCard title="Location time breakdown" className="mt-5">
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={[
                      { type: "Yard", min: (data.location_breakdown_s.yard_s ?? 0) / 60 },
                      { type: "Service", min: (data.location_breakdown_s.service_s ?? 0) / 60 },
                      { type: "Store", min: (data.location_breakdown_s.store_s ?? 0) / 60 },
                      { type: "Transit", min: (data.location_breakdown_s.transit_s ?? 0) / 60 },
                      { type: "Unknown", min: (data.location_breakdown_s.unknown_s ?? 0) / 60 },
                    ]}
                  >
                    <XAxis dataKey="type" stroke="#64748b" />
                    <YAxis stroke="#64748b" unit=" min" />
                    <Tooltip />
                    <Bar dataKey="min" fill="#a78bfa" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </GlassCard>
          )}

          {data.region_analytics.length > 0 && (
            <GlassCard title="Region / territory" className="mt-5">
              <div className="overflow-auto rounded-xl border border-slate-700/50">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-900/95 text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Region</th>
                      <th className="px-3 py-2">Employees</th>
                      <th className="px-3 py-2">Distance</th>
                      <th className="px-3 py-2">Avg productive %</th>
                      <th className="px-3 py-2">Visits</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.region_analytics.map((r) => (
                      <tr key={r.region} className="border-t border-slate-800/80">
                        <td className="px-3 py-2 font-medium text-white">{r.region}</td>
                        <td className="px-3 py-2">{r.employees}</td>
                        <td className="px-3 py-2">{r.distance_km.toFixed(1)} km</td>
                        <td className="px-3 py-2">{r.avg_productive_pct.toFixed(0)}%</td>
                        <td className="px-3 py-2">{r.visits}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </GlassCard>
          )}

          <GlassCard title="Operational insights" className="mt-5">
            <ul className="space-y-2 text-sm text-slate-300">
              {data.insights.map((line, i) => (
                <li key={i} className="border-l-2 border-sky-500/60 pl-3">
                  {line}
                </li>
              ))}
            </ul>
          </GlassCard>
        </>
      )}
    </div>
  );
}
