export type OpsAlert = {
  id: string;
  type: string;
  type_label: string;
  icon?: string;
  severity: "critical" | "warning" | "mild" | "positive" | "neutral";
  severity_label?: string;
  severity_rank: number;
  employee: string;
  team: string;
  region: string;
  title: string;
  message: string;
  metrics: Record<string, number | string>;
  details?: string[];
  day: string;
  timestamp: string;
  impact_score: number;
  trend?: "new" | "recurring" | "escalated" | "improved";
};

export type AlertTrends = {
  previous_day: string;
  total_delta: number;
  critical_delta: number;
  warning_delta: number;
  positive_delta: number;
};

export type AlertCenterPayload = {
  alerts: OpsAlert[];
  summary: {
    total: number;
    critical: number;
    warning: number;
    mild: number;
    positive: number;
    insufficient_data?: number;
  };
  smart_insights?: string[];
  alert_types: string[];
  thresholds: Record<string, number>;
  trends: AlertTrends | null;
};

export type DailyOverview = {
  day: string;
  filter_options: { teams: string[]; regions: string[]; dates?: string[] };
  executive_kpis: {
    active_employees: number;
    total_employees: number;
    total_distance_km: number;
    total_operational_visits: number;
    avg_productive_time_pct: number;
    avg_transit_hours: number;
    avg_active_hours: number;
    total_gps_pings: number;
    avg_visit_duration_s: number;
    top_performer: string;
    top_performer_score: number;
    lowest_activity: string;
    lowest_activity_hours: number;
  };
  leaderboard: LeaderRow[];
  productivity_distribution: { high: number; medium: number; low: number };
  top_performers: LeaderRow[];
  bottom_performers: LeaderRow[];
  team_comparison: {
    team: string;
    employees: number;
    distance_km: number;
    visits: number;
    avg_productive_pct: number;
    avg_active_hours: number;
  }[];
  hourly_operations: { hour: number; pings: number; operational_s: number; movement_km: number }[];
  location_breakdown_s: Record<string, number>;
  movement_distribution: { low: number; moderate: number; heavy: number };
  region_analytics: {
    region: string;
    employees: number;
    distance_km: number;
    avg_productive_pct: number;
    visits: number;
  }[];
  insights: string[];
  alert_center: AlertCenterPayload;
};

export type LeaderRow = {
  rank: number;
  employee: string;
  team: string;
  region: string;
  distance_km: number;
  productive_time_pct: number;
  operational_visits: number;
  active_hours: number;
  transit_time_s: number;
  productive_time_s: number;
  avg_visit_duration_s: number;
  unique_locations: number;
  gps_pings: number;
  transit_efficiency: number;
  efficiency_score: number;
  performance_tier: string;
  has_activity: boolean;
};
