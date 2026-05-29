import type { DailyOverview } from "./types/daily";
import type { FieldDashboard, MetaResponse } from "./types";

const base = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(`${base}${path}`);
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<T>;
}

export function fetchMeta(day: string) {
  return getJson<MetaResponse>(`/api/meta?day=${encodeURIComponent(day)}`);
}

export function fetchDashboard(params: {
  day: string;
  from: string;
  to: string;
  employee: string;
}) {
  const q = new URLSearchParams({
    day: params.day,
    from: params.from,
    to: params.to,
    employee: params.employee,
  });
  return getJson<FieldDashboard>(`/api/field-dashboard?${q}`);
}

export function fetchDailyOverview(params: {
  day: string;
  teams?: string[];
  regions?: string[];
  locationTypes?: string[];
  search?: string;
}) {
  const q = new URLSearchParams({ day: params.day });
  if (params.teams?.length) q.set("teams", params.teams.join(","));
  if (params.regions?.length) q.set("regions", params.regions.join(","));
  if (params.locationTypes?.length) q.set("location_types", params.locationTypes.join(","));
  if (params.search) q.set("search", params.search);
  return getJson<DailyOverview>(`/api/daily-overview?${q}`);
}
