import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { fetchDashboard, fetchMeta } from "./api";
import type { FieldDashboard, MetaResponse } from "./types";
import { FieldOpsIntel } from "./components/FieldOpsIntel";
import { GlassCard } from "./components/GlassCard";
import { LeaderboardPanel } from "./components/LeaderboardPanel";
import { OpsMap } from "./components/OpsMap";

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

export default function App() {
  const [searchParams] = useSearchParams();
  const [day, setDay] = useState(() => searchParams.get("day") || todayISO());
  const [from, setFrom] = useState("00:00");
  const [to, setTo] = useState("23:59");
  const [employee, setEmployee] = useState(() => searchParams.get("employee") || "__all__");
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [data, setData] = useState<FieldDashboard | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [playback, setPlayback] = useState(0);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchMeta(day)
      .then((m) => {
        if (!cancelled) setMeta(m);
      })
      .catch(() => {
        if (!cancelled) setMeta({ day, dates: [], employees: [] });
      });
    return () => {
      cancelled = true;
    };
  }, [day]);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const d = await fetchDashboard({ day, from, to, employee });
      setData(d);
      setPlayback(0);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [day, from, to, employee]);

  const maxPlay = useMemo(() => {
    const n = data?.route?.coordinates?.length ?? 0;
    return Math.max(0, n - 1);
  }, [data]);

  useEffect(() => {
    if (!playing || maxPlay <= 0) return;
    const id = window.setInterval(() => {
      setPlayback((p) => (p >= maxPlay ? 0 : p + 1));
    }, 450);
    return () => clearInterval(id);
  }, [playing, maxPlay]);

  return (
    <div className="min-h-screen pb-16">
      <header className="sticky top-0 z-50 border-b border-slate-700/60 bg-slate-950/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1600px] flex-col gap-4 px-5 py-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-sky-400/90">Field Operations</p>
            <h1 className="text-xl font-semibold text-white md:text-2xl">Movement Intelligence Dashboard</h1>
            <p className="text-xs text-slate-500">React · Tailwind · Recharts · Framer Motion · Leaflet</p>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Day
              <input
                type="date"
                value={day}
                onChange={(e) => setDay(e.target.value)}
                className="mt-1 rounded-lg border border-slate-600/60 bg-slate-900/80 px-3 py-2 text-sm text-white"
              />
            </label>
            <label className="flex flex-col text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              From
              <input
                value={from}
                onChange={(e) => setFrom(e.target.value)}
                className="mt-1 w-24 rounded-lg border border-slate-600/60 bg-slate-900/80 px-3 py-2 text-sm text-white"
              />
            </label>
            <label className="flex flex-col text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              To
              <input
                value={to}
                onChange={(e) => setTo(e.target.value)}
                className="mt-1 w-24 rounded-lg border border-slate-600/60 bg-slate-900/80 px-3 py-2 text-sm text-white"
              />
            </label>
            <label className="flex min-w-[200px] flex-col text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Agent
              <select
                value={employee}
                onChange={(e) => setEmployee(e.target.value)}
                className="mt-1 rounded-lg border border-slate-600/60 bg-slate-900/80 px-3 py-2 text-sm text-white"
              >
                <option value="__all__">All agents (leaderboard)</option>
                {(meta?.employees ?? []).map((e) => (
                  <option key={e} value={e}>
                    {e}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => void load()}
              disabled={loading}
              className="rounded-xl bg-gradient-to-r from-sky-500 to-indigo-500 px-5 py-2.5 text-sm font-semibold text-white shadow-glow transition hover:opacity-95 disabled:opacity-50"
            >
              {loading ? "Loading…" : "Load dashboard"}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1600px] space-y-8 px-5 pt-8">
        {err && (
          <div className="rounded-xl border border-red-500/40 bg-red-950/40 px-4 py-3 text-sm text-red-200">
            {err}
          </div>
        )}

        {data && (
          <>
            {data.intelligence && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <FieldOpsIntel intel={data.intelligence} />
              </motion.div>
            )}

            {data.route_note && (
              <GlassCard title="Route & timeline" subtitle="Map replay">
                <p className="text-sm text-slate-400">{data.route_note}</p>
              </GlassCard>
            )}

            {data.intelligence && data.route && (
              <section className="space-y-4">
                <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-sky-400/90">Route map & replay</h2>
                <GlassCard>
                  <OpsMap route={data.route} sites={data.sites} playbackIndex={playback} />
                  <div className="mt-4 flex flex-col gap-3 md:flex-row md:items-center">
                    <label className="flex-1 text-xs text-slate-400">
                      Timeline ({data.route.coordinates.length} points)
                      <input
                        type="range"
                        min={0}
                        max={maxPlay}
                        value={Math.min(playback, maxPlay)}
                        onChange={(e) => setPlayback(Number(e.target.value))}
                        className="mt-2 w-full accent-sky-500"
                      />
                    </label>
                    <button
                      type="button"
                      onClick={() => setPlaying((p) => !p)}
                      className="rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
                    >
                      {playing ? "Pause replay" : "Play replay"}
                    </button>
                  </div>
                </GlassCard>
              </section>
            )}

            <LeaderboardPanel
              by_productive_pct={data.leaderboard.by_productive_pct}
              by_operational_visits={data.leaderboard.by_operational_visits}
              by_transit_efficiency={data.leaderboard.by_transit_efficiency}
              low_activity={data.leaderboard.low_activity}
            />
          </>
        )}

        {!data && !err && (
          <GlassCard title="Getting started" subtitle="Run the API from the project root">
            <ol className="list-decimal space-y-2 pl-5 text-sm text-slate-300">
              <li>
                <code className="rounded bg-slate-800 px-1.5 py-0.5 text-sky-300">
                  pip install -r requirements-field-ops.txt
                </code>
              </li>
              <li>
                <code className="rounded bg-slate-800 px-1.5 py-0.5 text-sky-300">
                  uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
                </code>
              </li>
              <li>
                <code className="rounded bg-slate-800 px-1.5 py-0.5 text-sky-300">cd field-ops-web && npm install</code>
              </li>
              <li>
                <code className="rounded bg-slate-800 px-1.5 py-0.5 text-sky-300">npm run dev</code>
              </li>
              <li>Pick an agent (not “All agents”) and click Load dashboard.</li>
            </ol>
          </GlassCard>
        )}
      </main>
    </div>
  );
}
