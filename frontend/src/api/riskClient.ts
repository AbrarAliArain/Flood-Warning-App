import { authHeaders } from "../auth";

/**
 * Client for the ``/api/risk`` engine (spec bands 0-24/25-49/50-74/75-100 with
 * per-feature numeric contributions), as opposed to the legacy ``/api/zones``
 * scorer which uses its own 40/60/78 bands.
 */

export type RiskBand = "Low" | "Medium" | "High" | "Critical";

export interface RiskZoneAssessment {
  zone_id: string;
  name: string;
  division: string;
  score: number;
  band: RiskBand;
  model: string;
  features: Record<string, number>;
  contributions: Record<string, number>;
  is_demo: boolean;
}

export interface RiskHistoryEntry {
  score: number;
  band: RiskBand;
  model: string;
  features: Record<string, number>;
  contributions: Record<string, number>;
  is_demo: boolean;
  computed_at: string;
}

export interface RiskModelInfo {
  active: string;
  xgboost_available: boolean;
  model_file_exists?: boolean;
  fallback_reason?: string;
}

export interface RiskZoneSummary {
  zone_id: string;
  name: string;
  division: string;
  score: number;
  band: RiskBand;
  model: string;
  factors: Record<string, number>;
  is_demo: boolean;
  computed_at?: string;
}

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function fetchRiskZone(zoneId: string): Promise<RiskZoneAssessment> {
  return get(`/api/risk/zones/${encodeURIComponent(zoneId)}`);
}

export async function fetchRiskHistory(
  zoneId: string,
  limit = 20,
): Promise<{ zone_id: string; history: RiskHistoryEntry[] }> {
  return get(`/api/risk/zones/${encodeURIComponent(zoneId)}/history?limit=${limit}`);
}

export async function fetchRiskZones(): Promise<{ zones: RiskZoneSummary[]; source: string }> {
  return get("/api/risk/zones");
}

export async function fetchRiskModel(): Promise<RiskModelInfo> {
  return get("/api/risk/model");
}

/**
 * Display vocabulary requested for the dashboard, mapped onto the bands the
 * engine actually produces. ``range`` is the engine's real boundary, not a
 * rounded-off approximation.
 */
export const BAND_META: Record<RiskBand, { key: string; color: string; range: string }> = {
  Low: { key: "riskScore.bandNormal", color: "var(--green)", range: "0–24" },
  Medium: { key: "riskScore.bandWatch", color: "var(--yellow)", range: "25–49" },
  High: { key: "riskScore.bandWarning", color: "var(--orange)", range: "50–74" },
  Critical: { key: "riskScore.bandCritical", color: "var(--red)", range: "75–100" },
};

export function bandMeta(band: string) {
  return BAND_META[band as RiskBand] ?? BAND_META.Low;
}

export type TrendDirection = "up" | "down" | "flat" | "unknown";

export interface RiskTrend {
  direction: TrendDirection;
  delta: number | null;
  previousScore: number | null;
  comparedAt: string | null;
  samples: number;
}

/**
 * Compares the newest assessment against the most recent earlier one. Returns
 * ``unknown`` when fewer than two distinct timestamps exist, so the UI can say
 * "not enough history" instead of implying a flat trend.
 */
export function computeTrend(history: RiskHistoryEntry[]): RiskTrend {
  const samples = history.length;
  if (samples < 2) {
    return { direction: "unknown", delta: null, previousScore: null, comparedAt: null, samples };
  }
  const newest = history[0];
  const previous = history.find((entry) => entry.computed_at !== newest.computed_at);
  if (!previous) {
    return { direction: "unknown", delta: null, previousScore: null, comparedAt: null, samples };
  }
  const delta = newest.score - previous.score;
  return {
    direction: delta > 0 ? "up" : delta < 0 ? "down" : "flat",
    delta,
    previousScore: previous.score,
    comparedAt: previous.computed_at,
    samples,
  };
}

export const TREND_META: Record<TrendDirection, { arrow: string; key: string }> = {
  up: { arrow: "↑", key: "riskScore.trendIncreasing" },
  down: { arrow: "↓", key: "riskScore.trendDecreasing" },
  flat: { arrow: "→", key: "riskScore.trendStable" },
  unknown: { arrow: "", key: "riskScore.trendUnknown" },
};

export const FEATURE_LABEL_KEYS: Record<string, string> = {
  rainfall_intensity: "riskScore.featRainfall",
  river_flow: "riskScore.featRiverFlow",
  elevation: "riskScore.featElevation",
  drainage: "riskScore.featDrainage",
  exposure: "riskScore.featExposure",
  historical: "riskScore.featHistorical",
  report_density: "riskScore.featReportDensity",
};

/** Bucket a 0-1 normalised feature value when no numeric contribution exists. */
export function intensityKey(value: number): string {
  if (value >= 0.66) return "riskScore.intensityHigh";
  if (value >= 0.33) return "riskScore.intensityModerate";
  return "riskScore.intensityLow";
}
