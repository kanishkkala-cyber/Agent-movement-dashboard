import { motion } from "framer-motion";
import type { LeaderRow } from "../types";
import { GlassCard } from "./GlassCard";

function MiniTable({ title, rows, highlight }: { title: string; rows: LeaderRow[]; highlight: keyof LeaderRow }) {
  return (
    <GlassCard title={title}>
      <div className="max-h-72 overflow-auto text-xs">
        <table className="w-full text-left">
          <thead className="sticky top-0 bg-slate-900/95 text-slate-500">
            <tr>
              <th className="py-2 pr-2">#</th>
              <th className="py-2">Agent</th>
              <th className="py-2 text-right">Value</th>
            </tr>
          </thead>
          <tbody className="text-slate-300">
            {rows.map((r, i) => (
              <motion.tr
                key={r.employee}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.03 }}
                className="border-t border-slate-800/80"
              >
                <td className="py-2 pr-2 font-mono text-slate-500">{i + 1}</td>
                <td className="max-w-[140px] truncate py-2" title={r.employee}>
                  {r.employee}
                </td>
                <td className="py-2 text-right font-mono text-sky-300">
                  {highlight === "productive_time_pct"
                    ? `${(r[highlight] as number).toFixed(1)}%`
                    : highlight === "active_hours"
                      ? `${(r[highlight] as number).toFixed(2)} h`
                      : highlight === "operational_visits"
                        ? `${Math.round(r[highlight] as number)}`
                        : (r[highlight] as number).toFixed(2)}
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </GlassCard>
  );
}

export function LeaderboardPanel({
  by_productive_pct,
  by_operational_visits,
  by_transit_efficiency,
  low_activity,
}: {
  by_productive_pct: LeaderRow[];
  by_operational_visits: LeaderRow[];
  by_transit_efficiency: LeaderRow[];
  low_activity: LeaderRow[];
}) {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-sky-400/90">Agent leaderboard</h2>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MiniTable title="Top — productive time %" rows={by_productive_pct} highlight="productive_time_pct" />
        <MiniTable title="Top — operational visits" rows={by_operational_visits} highlight="operational_visits" />
        <MiniTable title="Top — transit efficiency" rows={by_transit_efficiency} highlight="transit_efficiency" />
        <MiniTable title="Low activity (hours)" rows={low_activity} highlight="active_hours" />
      </div>
    </section>
  );
}
