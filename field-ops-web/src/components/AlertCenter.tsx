import { AnimatePresence, motion } from "framer-motion";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { AlertCenterPayload, OpsAlert } from "../types/daily";
import { GlassCard } from "./GlassCard";

const SEV_STYLE: Record<string, string> = {
  critical:
    "border-l-red-400 shadow-[0_0_22px_rgba(248,113,113,0.18)] ring-1 ring-red-500/10",
  warning:
    "border-l-orange-400 shadow-[0_0_20px_rgba(251,146,60,0.14)] ring-1 ring-orange-500/10",
  mild: "border-l-yellow-400 shadow-[0_0_12px_rgba(250,204,21,0.08)]",
  positive:
    "border-l-emerald-400 shadow-[0_0_20px_rgba(74,222,128,0.14)] ring-1 ring-emerald-500/10",
  neutral: "border-l-slate-600 opacity-60",
};

const SEV_BADGE: Record<string, string> = {
  critical: "bg-red-500/25 text-red-200 border border-red-500/30",
  warning: "bg-orange-500/20 text-orange-200 border border-orange-500/25",
  mild: "bg-yellow-500/15 text-yellow-100 border border-yellow-500/20",
  positive: "bg-emerald-500/20 text-emerald-200 border border-emerald-500/25",
  neutral: "bg-slate-700/40 text-slate-400 border border-slate-600/30",
};

const SEV_DOT: Record<string, string> = {
  critical: "bg-red-400",
  warning: "bg-orange-400",
  mild: "bg-yellow-400",
  positive: "bg-emerald-400",
  neutral: "bg-slate-500",
};

const TREND_BADGE: Record<string, string> = {
  new: "text-sky-300 bg-sky-500/15",
  escalated: "text-red-300 bg-red-500/15",
  improved: "text-emerald-300 bg-emerald-500/15",
  recurring: "text-slate-400 bg-slate-700/50",
};

function metricsLine(m: Record<string, unknown>) {
  return Object.entries(m)
    .map(
      ([k, v]) =>
        `${k.replace(/_/g, " ")}: ${
          typeof v === "number"
            ? Number.isInteger(v)
              ? v
              : (v as number).toFixed(1)
            : v
        }`
    )
    .join(" · ");
}

function deltaLabel(n: number) {
  if (n === 0) return "—";
  return n > 0 ? `+${n}` : `${n}`;
}

type Props = {
  data: AlertCenterPayload;
  day: string;
};

export function AlertCenter({ data, day }: Props) {
  const navigate = useNavigate();
  const [sev, setSev] = useState<string[]>(["critical", "warning", "mild", "positive", "neutral"]);
  const [types, setTypes] = useState<string[]>([]);
  const [teams, setTeams] = useState<string[]>([]);
  const [regions, setRegions] = useState<string[]>([]);
  const [sort, setSort] = useState<"severity" | "impact" | "employee" | "timestamp">("severity");
  const [expanded, setExpanded] = useState<string | null>(null);

  const teamsOpt = useMemo(
    () =>
      [...new Set(data.alerts.map((a) => a.team).filter(Boolean))].sort() as string[],
    [data.alerts]
  );
  const regionsOpt = useMemo(
    () =>
      [...new Set(data.alerts.map((a) => a.region).filter(Boolean))].sort() as string[],
    [data.alerts]
  );

  const filtered = useMemo(() => {
    let list = [...data.alerts];
    if (sev.length) list = list.filter((a) => sev.includes(a.severity));
    if (types.length) list = list.filter((a) => types.includes(a.type));
    if (teams.length) list = list.filter((a) => !a.employee || teams.includes(a.team));
    if (regions.length) list = list.filter((a) => !a.employee || regions.includes(a.region));
    if (sort === "impact") list.sort((a, b) => b.impact_score - a.impact_score);
    else if (sort === "employee")
      list.sort(
        (a, b) =>
          (a.employee || "zzz").localeCompare(b.employee || "zzz") ||
          b.severity_rank - a.severity_rank
      );
    else if (sort === "timestamp")
      list.sort(
        (a, b) =>
          b.timestamp.localeCompare(a.timestamp) || b.severity_rank - a.severity_rank
      );
    else list.sort((a, b) => b.severity_rank - a.severity_rank || b.impact_score - a.impact_score);
    return list;
  }, [data.alerts, sev, types, teams, regions, sort]);

  const drill = (a: OpsAlert) => {
    if (!a.employee) return;
    navigate(`/tracking?employee=${encodeURIComponent(a.employee)}&day=${day}`);
  };

  const toggleSev = (s: string) => {
    setSev((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));
  };

  const s = data.summary;
  const insights = data.smart_insights ?? [];
  const trends = data.trends;

  return (
    <GlassCard
      title="Operations Alert Center"
      subtitle="Field-force command center · operational monitoring · leadership attention signals"
      className="mb-6 overflow-hidden"
    >
      {/* Executive summary strip */}
      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-6">
        {[
          ["Actionable", s.total, "text-white"],
          ["Critical", s.critical, "text-red-400"],
          ["Warning", s.warning, "text-orange-400"],
          ["Mild", s.mild, "text-yellow-300"],
          ["Positive", s.positive, "text-emerald-400"],
          ...(s.insufficient_data ? [["No data", s.insufficient_data, "text-slate-500"]] : []),
        ].map(([lbl, n, col]) => (
          <div
            key={lbl as string}
            className="relative overflow-hidden rounded-xl border border-slate-600/40 bg-gradient-to-br from-slate-950/80 to-slate-900/40 px-3 py-2.5"
          >
            <div className={`text-2xl font-bold tabular-nums ${col}`}>{n}</div>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              {lbl}
            </div>
          </div>
        ))}
      </div>

      {trends && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-slate-600/30 bg-slate-950/60 px-3 py-2 text-xs text-slate-400">
          <span className="font-semibold uppercase tracking-wide text-slate-500">
            vs {trends.previous_day}
          </span>
          <span>
            Critical{" "}
            <strong className={trends.critical_delta > 0 ? "text-red-400" : "text-emerald-400"}>
              {deltaLabel(trends.critical_delta)}
            </strong>
          </span>
          <span>
            Warning{" "}
            <strong className={trends.warning_delta > 0 ? "text-orange-400" : "text-emerald-400"}>
              {deltaLabel(trends.warning_delta)}
            </strong>
          </span>
          <span>
            Positive{" "}
            <strong className="text-emerald-400">{deltaLabel(trends.positive_delta)}</strong>
          </span>
          <span>
            Total {deltaLabel(trends.total_delta)}
          </span>
        </div>
      )}

      {insights.length > 0 && (
        <div className="mb-4 space-y-1.5">
          <div className="text-[10px] font-bold uppercase tracking-widest text-sky-500/80">
            Smart operational insights
          </div>
          {insights.map((line, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.04 }}
              className="rounded-lg border-l-2 border-sky-500/60 bg-slate-900/50 px-3 py-2 text-sm text-slate-300"
            >
              {line}
            </motion.div>
          ))}
        </div>
      )}

      {data.alerts.length === 0 ? (
        <p className="text-sm text-slate-500">No operational alerts for this date and filter set.</p>
      ) : (
        <>
          {/* Filters */}
          <div className="mb-3 space-y-2">
            <div className="flex flex-wrap gap-1.5">
              <span className="self-center text-[10px] font-semibold uppercase text-slate-500">
                Severity
              </span>
              {(["critical", "warning", "mild", "positive", "neutral"] as const).map((x) => (
                <button
                  key={x}
                  type="button"
                  onClick={() => toggleSev(x)}
                  className={`rounded-lg px-2.5 py-1 text-[10px] font-bold uppercase transition ${
                    sev.includes(x) ? SEV_BADGE[x] : "bg-slate-800/60 text-slate-500"
                  }`}
                >
                  <span className={`mr-1.5 inline-block h-1.5 w-1.5 rounded-full ${SEV_DOT[x]}`} />
                  {x}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <select
                className="rounded-lg border border-slate-600/60 bg-slate-950 px-2 py-1.5 text-xs text-slate-200"
                value={types.length ? types[0] : ""}
                onChange={(e) => {
                  const v = e.target.value;
                  setTypes(v ? [v] : []);
                }}
              >
                <option value="">All alert types</option>
                {data.alert_types.map((t) => (
                  <option key={t} value={t}>
                    {t.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
              <select
                className="rounded-lg border border-slate-600/60 bg-slate-950 px-2 py-1.5 text-xs text-slate-200"
                value={teams.length ? teams[0] : ""}
                onChange={(e) => setTeams(e.target.value ? [e.target.value] : [])}
              >
                <option value="">All teams</option>
                {teamsOpt.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <select
                className="rounded-lg border border-slate-600/60 bg-slate-950 px-2 py-1.5 text-xs text-slate-200"
                value={regions.length ? regions[0] : ""}
                onChange={(e) => setRegions(e.target.value ? [e.target.value] : [])}
              >
                <option value="">All regions</option>
                {regionsOpt.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
              <select
                className="rounded-lg border border-slate-600/60 bg-slate-950 px-2 py-1.5 text-xs text-slate-200"
                value={sort}
                onChange={(e) => setSort(e.target.value as typeof sort)}
              >
                <option value="severity">Sort: severity</option>
                <option value="impact">Sort: productivity impact</option>
                <option value="employee">Sort: employee</option>
                <option value="timestamp">Sort: timestamp</option>
              </select>
            </div>
          </div>

          <p className="mb-2 text-xs text-slate-500">
            Showing {filtered.length} of {data.alerts.length} alerts · click card to expand ·
            double-click employee alerts to open detail
          </p>

          <div className="max-h-[520px] space-y-2 overflow-y-auto pr-1">
            <AnimatePresence mode="popLayout">
              {filtered.slice(0, 40).map((a, i) => {
                const isOpen = expanded === a.id;
                return (
                  <motion.div
                    key={a.id}
                    layout
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ delay: Math.min(i * 0.02, 0.35) }}
                    className={`cursor-pointer rounded-xl border border-slate-700/50 border-l-4 bg-slate-900/55 px-3.5 py-3 transition hover:bg-slate-800/70 ${SEV_STYLE[a.severity] ?? ""}`}
                    onClick={() => setExpanded(isOpen ? null : a.id)}
                    onDoubleClick={() => drill(a)}
                  >
                    <div className="flex items-start gap-2.5">
                      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-800/80 text-base">
                        {a.icon ?? "◆"}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`rounded-md px-1.5 py-0.5 text-[10px] font-bold uppercase ${SEV_BADGE[a.severity]}`}
                          >
                            {a.severity_label ?? a.severity}
                          </span>
                          {a.trend && a.trend !== "recurring" && (
                            <span
                              className={`rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase ${TREND_BADGE[a.trend] ?? ""}`}
                            >
                              {a.trend}
                            </span>
                          )}
                          <span className="font-semibold text-slate-100">{a.title}</span>
                        </div>
                        {a.employee && (
                          <p className="mt-0.5 text-xs font-medium text-sky-400/90">{a.employee}</p>
                        )}
                        <p className="mt-1 text-sm leading-snug text-slate-400">{a.message}</p>
                        <p className="mt-1.5 text-[10px] uppercase tracking-wide text-slate-500">
                          {!a.employee && "Fleet insight · "}
                          {a.type_label}
                          {a.team && a.employee ? ` · ${a.team}` : ""}
                          {a.region && a.employee ? ` · ${a.region}` : ""}
                          {Object.keys(a.metrics).length > 0 && ` · ${metricsLine(a.metrics)}`}
                        </p>
                        {isOpen && (a.details?.length ?? 0) > 0 && (
                          <motion.ul
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            className="mt-2 space-y-1 border-t border-slate-700/50 pt-2 text-xs text-slate-400"
                          >
                            {a.details!.map((d, j) => (
                              <li key={j} className="flex gap-2">
                                <span className="text-slate-600">›</span>
                                {d}
                              </li>
                            ))}
                          </motion.ul>
                        )}
                        {isOpen && a.employee && (
                          <button
                            type="button"
                            className="mt-2 text-xs font-medium text-sky-400 hover:text-sky-300"
                            onClick={(e) => {
                              e.stopPropagation();
                              drill(a);
                            }}
                          >
                            Open employee timeline →
                          </button>
                        )}
                      </div>
                      <div className="shrink-0 text-right">
                        <div className="text-[10px] text-slate-500">Impact</div>
                        <div className="text-sm font-bold tabular-nums text-slate-300">
                          {a.impact_score.toFixed(0)}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
          {filtered.length > 40 && (
            <p className="mt-2 text-xs text-slate-500">
              {filtered.length - 40} more alerts — narrow filters to see all.
            </p>
          )}
        </>
      )}
    </GlassCard>
  );
}
