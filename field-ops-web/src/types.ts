export type TimeSplit = Record<string, number>;

export type Intelligence = {
  productive_time_pct: number;
  productive_time_s: number;
  active_time_s: number;
  transit_time_s: number;
  operational_time_s: number;
  time_split_s: TimeSplit;
  transit_vs_work: { transit_s: number; operational_s: number; ratio_label: string };
  operational_visits: number;
  visit_counts_by_category: Record<string, number>;
  avg_visit_duration_s: number;
  avg_visit_by_category_s: Record<string, number>;
  transit_efficiency: number;
  transit_efficiency_label: string;
  stop_distribution: { short: number; medium: number; long: number };
  movement_intensity: { start: string; pings: number; km: number; score: number }[];
  revisit_analytics: {
    locations: {
      site_index: number;
      site_type: string;
      name: string;
      visit_count: number;
      total_dwell_s: number;
      avg_dwell_s: number;
    }[];
    summary: Record<string, number>;
  };
  hourly_utilization: { hour: number; movement_km: number; operational_s: number; idle_s: number }[];
  insights: string[];
  visit_events: unknown[];
  totals: {
    distance_km: number;
    gps_pings: number;
    active_hours: number;
    num_stops: number;
  };
};

export type LeaderRow = {
  employee: string;
  productive_time_pct: number;
  operational_visits: number;
  transit_efficiency: number;
  active_hours: number;
  distance_km: number;
};

export type RoutePayload = {
  coordinates: [number, number][];
  time_iso: string[];
  stops: { lat: number; lon: number; start: string; end: string; duration_s: number }[];
};

export type SiteMarker = { lat: number; lon: number; name: string; site_type: string };

export type FieldDashboard = {
  day: string;
  time_from: string;
  time_to: string;
  employee: string;
  intelligence: Intelligence | null;
  route: RoutePayload | null;
  route_note: string | null;
  sites: SiteMarker[];
  leaderboard: {
    by_productive_pct: LeaderRow[];
    by_operational_visits: LeaderRow[];
    by_transit_efficiency: LeaderRow[];
    low_activity: LeaderRow[];
  };
};

export type MetaResponse = {
  day: string;
  dates: string[];
  employees: string[];
};
