import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Intelligence } from "../types";
import { GlassCard } from "./GlassCard";
import { ProductiveRing } from "./ProductiveRing";

function fmtDur(sec: number) {
  if (!sec || sec < 60) return `${Math.round(sec)}s`;
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

const DONUT_COLORS: Record<string, string> = {
  yard_time_s: "#92400e",
  service_time_s: "#0369a1",
  store_time_s: "#7c3aed",
  transit_time_s: "#64748b",
  unknown_time_s: "#334155",
};

const DONUT_LABELS: Record<string, string> = {
  yard_time_s: "Yard",
  service_time_s: "Service",
  store_time_s: "Store",
  transit_time_s: "Transit",
  unknown_time_s: "Unknown",
};

export function FieldOpsIntel({ intel }: { intel: Intelligence }) {
  const ts = intel.time_split_s;
  const donutData = Object.entries(ts)
    .filter(([, v]) => v > 30)
    .map(([k, v]) => ({
      name: DONUT_LABELS[k] ?? k,
      value: Math.round(v / 60),
      key: k,
    }));

  const stackRow = [
    {
      label: "Today",
      transit: Math.round(intel.transit_vs_work.transit_s / 60),
      operational: Math.round(intel.transit_vs_work.operational_s / 60),
    },
  ];

  const stops = [
    { name: "<5 min", n: intel.stop_distribution.short, fill: "#38bdf8" },
    { name: "5–20 min", n: intel.stop_distribution.medium, fill: "#818cf8" },
    { name: ">20 min", n: intel.stop_distribution.long, fill: "#f472b6" },
  ];

  const intensity = intel.movement_intensity.slice(0, 64).map((b, i) => ({
    i,
    score: b.score,
    km: b.km,
  }));

  const maxH = Math.max(
    ...intel.hourly_utilization.map((h) => h.movement_km + h.operational_s / 3600 + h.idle_s / 3600),
    0.01
  );

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-1 border-b border-slate-700/50 pb-4">
        <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-sky-400/90">
          Field Operations Intelligence
        </h2>
        <p className="text-sm text-slate-400">
          Operational efficiency, movement intelligence, and location engagement — GPS as source of truth.
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-12">
        <GlassCard className="lg:col-span-4" title="Productive time %" subtitle="At operational locations vs active time">
          <ProductiveRing pct={intel.productive_time_pct} />
          <p className="mt-3 text-center text-xs text-slate-400">
            {intel.productive_time_pct.toFixed(0)}% of tracked time attributed to yards, service centres, and stores
            (within 200 m).
          </p>
        </GlassCard>

        <GlassCard className="lg:col-span-4" title="Transit vs work" subtitle={intel.transit_vs_work.ratio_label}>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart layout="vertical" data={stackRow} margin={{ left: 8, right: 16 }}>
                <XAxis type="number" tickFormatter={(v) => `${v}m`} stroke="#64748b" />
                <YAxis type="category" dataKey="label" width={48} stroke="#64748b" />
                <Tooltip
                  formatter={(v: number) => [`${v} min`, ""]}
                  contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 12 }}
                />
                <Bar dataKey="transit" stackId="s" name="Transit" fill="#475569" radius={[0, 6, 6, 0]} />
                <Bar dataKey="operational" stackId="s" name="On-site" fill="#38bdf8" radius={[6, 0, 0, 6]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>

        <GlassCard className="lg:col-span-4" title="Transit efficiency" subtitle={intel.transit_efficiency_label}>
          <div className="flex flex-col items-center justify-center py-2">
            <span className="text-4xl font-bold text-white">{intel.transit_efficiency.toFixed(2)}</span>
            <span className="mt-1 text-xs uppercase tracking-wider text-slate-500">visits / km</span>
            <p className="mt-4 text-center text-xs text-slate-400">
              Useful operational visits relative to distance covered — higher suggests tighter multi-stop routing.
            </p>
          </div>
        </GlassCard>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <GlassCard title="Location category time split" subtitle="Minutes accumulated by segment type">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={donutData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={58}
                  outerRadius={88}
                  paddingAngle={2}
                >
                  {donutData.map((e) => (
                    <Cell key={e.key} fill={DONUT_COLORS[e.key] ?? "#64748b"} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v: number) => [`${v} min`, ""]}
                  contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 12 }}
                />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>

        <GlassCard title="Average time per visit" subtitle="Total on-site time ÷ operational visits">
          <div className="mb-4 rounded-xl border border-slate-700/50 bg-slate-950/40 p-4 text-center">
            <div className="text-3xl font-semibold text-white">{fmtDur(intel.avg_visit_duration_s)}</div>
            <div className="text-xs text-slate-500">overall average dwell</div>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {Object.entries(intel.avg_visit_by_category_s).map(([k, v]) => (
              <div key={k} className="rounded-lg border border-slate-700/40 bg-slate-900/50 px-3 py-2">
                <div className="font-semibold capitalize text-slate-200">{k}</div>
                <div className="text-slate-400">{fmtDur(v)}</div>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <GlassCard title="Stop duration distribution" subtitle="Detected dwell clusters from GPS">
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stops}>
                <XAxis dataKey="name" stroke="#64748b" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                <YAxis stroke="#64748b" allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 12 }}
                />
                <Bar dataKey="n" name="Stops" radius={[8, 8, 0, 0]}>
                  {stops.map((e) => (
                    <Cell key={e.name} fill={e.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>

        <GlassCard title="Movement intensity" subtitle="15-minute bins — activity score">
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={intensity}>
                <defs>
                  <linearGradient id="int" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.5} />
                    <stop offset="100%" stopColor="#38bdf8" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="i" hide />
                <YAxis stroke="#64748b" />
                <Tooltip
                  contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 12 }}
                />
                <Area type="monotone" dataKey="score" stroke="#38bdf8" fill="url(#int)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>
      </div>

      <GlassCard title="Hourly utilization" subtitle="Movement (km) vs on-site vs idle — 24h heatmap">
        <div className="space-y-2">
          {["movement_km", "operational_s", "idle_s"].map((rowKey, ri) => (
            <div key={rowKey} className="flex items-center gap-2">
              <span className="w-28 shrink-0 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                {rowKey === "movement_km" ? "Movement km" : rowKey === "operational_s" ? "On-site (s)" : "Idle (s)"}
              </span>
              <div
                className="grid flex-1 gap-0.5"
                style={{ gridTemplateColumns: "repeat(24, minmax(0, 1fr))" }}
              >
                {intel.hourly_utilization.map((h) => {
                  const raw =
                    rowKey === "movement_km"
                      ? h.movement_km / maxH
                      : rowKey === "operational_s"
                        ? h.operational_s / (maxH * 3600)
                        : h.idle_s / (maxH * 3600);
                  const op = Math.min(1, raw * 2.5);
                  return (
                    <div
                      key={`${ri}-${h.hour}`}
                      title={`${h.hour}:00`}
                      className="h-7 rounded-sm"
                      style={{
                        background:
                          rowKey === "movement_km"
                            ? `rgba(56,189,248,${0.15 + op * 0.85})`
                            : rowKey === "operational_s"
                              ? `rgba(129,140,248,${0.15 + op * 0.85})`
                              : `rgba(248,113,113,${0.12 + op * 0.75})`,
                      }}
                    />
                  );
                })}
              </div>
            </div>
          ))}
          <div className="flex justify-between pl-32 text-[10px] text-slate-600">
            <span>0h</span>
            <span>6h</span>
            <span>12h</span>
            <span>18h</span>
            <span>23h</span>
          </div>
        </div>
      </GlassCard>

      <div className="grid gap-5 lg:grid-cols-2">
        <GlassCard title="Repeat visit analytics" subtitle="Locations with multiple operational visits">
          <div className="max-h-64 overflow-auto text-sm">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-slate-900/95 text-slate-500">
                <tr>
                  <th className="py-2 pr-2">Location</th>
                  <th className="py-2">Type</th>
                  <th className="py-2">Visits</th>
                  <th className="py-2">Total dwell</th>
                </tr>
              </thead>
              <tbody className="text-slate-300">
                {intel.revisit_analytics.locations.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-6 text-center text-slate-500">
                      No repeat visits in this window.
                    </td>
                  </tr>
                ) : (
                  intel.revisit_analytics.locations.map((r) => (
                    <tr key={`${r.site_index}-${r.name}`} className="border-t border-slate-800/80">
                      <td className="py-2 pr-2">{r.name || "—"}</td>
                      <td className="py-2 text-slate-400">{r.site_type}</td>
                      <td className="py-2 font-mono">{r.visit_count}</td>
                      <td className="py-2 text-slate-400">{fmtDur(r.total_dwell_s)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </GlassCard>

        <GlassCard title="Operational insights" subtitle="Auto-generated from movement patterns">
          <ul className="space-y-3 text-sm text-slate-300">
            {intel.insights.map((line, i) => (
              <li key={i} className="flex gap-2 border-l-2 border-sky-500/50 pl-3">
                {line}
              </li>
            ))}
          </ul>
        </GlassCard>
      </div>
    </section>
  );
}
