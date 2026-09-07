import { authHeaders } from "../auth";

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
}

export interface ZoneProperties {
  zone_id: string;
  name: string;
  score: number;
  category: string;
  color: string;
  rainfall_mm_hr: number;
  is_demo: boolean;
  area_sqkm: number | null;
}

export interface ZoneFeature {
  type: "Feature";
  properties: ZoneProperties;
  geometry: { type: string; coordinates: unknown };
}

export interface ZonesResponse {
  type: "FeatureCollection";
  features: ZoneFeature[];
}

export interface ZoneDetail {
  zone_id: string;
  name: string;
  division: string;
  score: number;
  category: string;
  color: string;
  factors: Record<string, { value: number; weight: number }>;
  live: {
    rainfall_mm_hr: number;
    river_flow_lacs_cusecs: number | null;
    gauge: string | null;
    is_demo: boolean;
  };
  profile: {
    rainfall_baseline_mm_yr: number;
    baseline_source: string;
    houses_2022: number | null;
    houses_source: string;
    exposure_source: string;
    historical_source: string;
    historical_events: number[];
    risk_factors: string[];
  };
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch("/api/health", { headers: authHeaders() });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function fetchZones(): Promise<ZonesResponse> {
  const res = await fetch("/api/zones", { headers: authHeaders() });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function fetchZoneDetail(zoneId: string): Promise<ZoneDetail> {
  const res = await fetch(`/api/zones/${zoneId}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export interface GaugeStation {
  id: string;
  name: string;
  river: string;
  design_capacity: number | null;
  low: number;
  medium: number;
  high: number;
  very_high: number;
  exceptional: number;
  flow_lacs_cusecs: number;
  flood_class: string;
  color: string;
  is_demo: boolean;
}

export interface GaugesResponse {
  gauges: GaugeStation[];
  updated_at: string;
  source_thresholds: string;
  source_flows: string;
}

export async function fetchGauges(): Promise<GaugesResponse> {
  const res = await fetch("/api/gauges", { headers: authHeaders() });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export interface CommunityReport {
  id: number;
  report_id: number;
  zone_id: string;
  zone_name: string;
  water_level: string;
  severity: string;
  emergency_type: string;
  description: string;
  status: string;
  latitude: number | null;
  longitude: number | null;
  location_text: string | null;
  evidence_path: string | null;
  evidence_url: string | null;
  photo_url: string | null;
  ai_analysis?: Record<string, unknown> | null;
  is_demo: boolean;
  created_at: string;
  timestamp: string;
}

export interface AlertItem {
  id: number;
  zone_id: string | null;
  zone_name: string | null;
  severity: string;
  message: string;
  is_demo: boolean;
  created_at: string;
}

export interface AnalyticsData {
  distribution: Record<string, number>;
  trend: number[];
  trend_is_demo: boolean;
  reports_count: number;
  active_alerts_count: number;
}

export async function fetchReports(): Promise<{ reports: CommunityReport[] }> {
  const res = await fetch("/api/reports", {
    cache: "no-store",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function submitReport(payload: {
  zone_id: string;
  water_level: string;
  description: string;
  evidence?: File;
  latitude?: number;
  longitude?: number;
  severity?: string;
  emergency_type?: string;
  location_text?: string;
}): Promise<CommunityReport> {
  const form = new FormData();
  form.append("zone_id", payload.zone_id);
  form.append("water_level", payload.water_level);
  form.append("description", payload.description);
  if (payload.evidence) form.append("evidence", payload.evidence);
  if (payload.latitude != null) form.append("latitude", String(payload.latitude));
  if (payload.longitude != null) form.append("longitude", String(payload.longitude));
  if (payload.severity) form.append("severity", payload.severity);
  if (payload.emergency_type) form.append("emergency_type", payload.emergency_type);
  if (payload.location_text) form.append("location_text", payload.location_text);
  const res = await fetch("/api/reports", {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) throw new Error(await describeError(res));
  return res.json();
}

/** Surfaces the backend's ``detail`` so validation errors are actionable. */
async function describeError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    /* fall through to the status code */
  }
  return `API error ${res.status}`;
}

export async function fetchAlerts(): Promise<{ alerts: AlertItem[] }> {
  const res = await fetch("/api/alerts", { headers: authHeaders() });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function issueDemoAlert(zoneId?: string): Promise<AlertItem> {
  const res = await fetch("/api/alerts/demo", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ zone_id: zoneId ?? null }),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function fetchAnalytics(): Promise<AnalyticsData> {
  const res = await fetch("/api/analytics", { headers: authHeaders() });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export interface InsightData {
  zone_id: string;
  name: string;
  score: number;
  category: string;
  explanation: string;
  explanation_source: "template" | "llm";
  recommendations: { action: string; source: string }[];
  retrieved: { doc: string; heading: string; snippet: string; score: number }[];
  inputs_are_demo: boolean;
}

export async function fetchInsights(zoneId: string): Promise<InsightData> {
  const res = await fetch(`/api/insights/${zoneId}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function subscribeToAlerts(payload: {
  name: string;
  email: string;
  organization?: string;
}): Promise<{ status: string }> {
  const res = await fetch("/api/subscribe", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export interface DivisionDistrict {
  zone_id: string;
  name: string;
  score: number;
  category: string;
}

export interface DivisionWarning {
  division: string;
  severity: "critical" | "high";
  message: string;
  districts: DivisionDistrict[];
  critical_count: number;
  high_count: number;
  is_demo: boolean;
  generated_at: string;
}

export async function fetchAutoWarnings(): Promise<{ warnings: DivisionWarning[] }> {
  const res = await fetch("/api/alerts/auto", { headers: authHeaders() });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export interface CaseMatch {
  ngo_id: number;
  ngo_name: string;
  score: number;
  reasons: string[];
  distance_km: number | null;
  /** Raw numbers reach responder and admin callers only. */
  whatsapp_number?: string | null;
  contact_phone?: string | null;
  /** Citizen callers get these instead — redacted server-side. */
  contact_masked?: string | null;
  contact_available?: boolean;
}

export interface CaseDispatch {
  case_id: number;
  case_code: string;
  mode: string;
  message: string;
  status: string;
  recipient?: string | null;
  recipient_masked?: string | null;
  recipient_available?: boolean;
}

export interface CreatedCase {
  id: number;
  code: string;
  status: string;
  zone_id: string;
  report_id: number | null;
  severity: string;
  emergency_type: string;
  description: string | null;
  latitude: number | null;
  longitude: number | null;
  priority: number;
  priority_label: string;
  risk_score: number | null;
  risk_category: string | null;
  communication_status: string | null;
  created_at: string;
  ngo_id: number | null;
  matches: CaseMatch[];
  dispatch?: CaseDispatch;
}

export async function createCaseFromReport(reportId: number): Promise<CreatedCase> {
  const res = await fetch("/api/cases/from-report", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ report_id: reportId }),
  });
  if (!res.ok) throw new Error(await describeError(res));
  return res.json();
}

export type SafeCategory = "shelter" | "hospital" | "rescue" | "police" | "relief";

/**
 * ``distance_km`` is null whenever the backend has no real origin to measure
 * from, so the UI must say "distance unavailable" rather than show 0.
 */
export interface SafeLocation {
  name: string;
  category: SafeCategory;
  area: string | null;
  latitude: number;
  longitude: number;
  coordinate_source: "surveyed" | "district_center";
  phone: string | null;
  capacity: number | null;
  notes: string | null;
  is_demo: boolean;
  maps_url: string;
  distance_km: number | null;
  id?: number | null;
  zone_id?: string | null;
  osm_type?: string;
  osm_id?: number;
  resolved_city?: string;
  resolved_country?: string;
}

/** Why a live lookup returned what it did — "no results" has several causes. */
export type LiveStatus = "ok" | "not_needed" | "rate_limited" | "unavailable" | "disabled";

export interface SafeLocationLookup {
  source: "curated" | "openstreetmap";
  live_lookup_available: boolean;
  live_status: LiveStatus;
  resolved: {
    zone_id?: string;
    name?: string;
    headquarters?: string;
    query?: string;
    latitude?: number;
    longitude?: number;
  };
  distance_basis: "user_location" | "resolved_city_center" | "unavailable";
  attribution: string | null;
  locations: SafeLocation[];
}

export interface SafeCity {
  zone_id: string;
  name: string;
  headquarters: string;
  latitude: number;
  longitude: number;
  source: "curated";
  facility_count: number;
}

export interface SafeCitiesResponse {
  cities: SafeCity[];
  live_search_enabled: boolean;
  hint: string;
}

export async function fetchSafeCities(q = ""): Promise<SafeCitiesResponse> {
  const res = await fetch(`/api/safe-locations/cities?q=${encodeURIComponent(q)}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function fetchSafeLocations(params: {
  zoneId?: string;
  q?: string;
  category?: SafeCategory;
  limit?: number;
}): Promise<SafeLocationLookup> {
  const search = new URLSearchParams();
  if (params.zoneId) search.set("zone_id", params.zoneId);
  if (params.q) search.set("q", params.q);
  if (params.category) search.set("category", params.category);
  if (params.limit) search.set("limit", String(params.limit));
  const res = await fetch(`/api/safe-locations?${search}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

/** Fields are absent entirely when ``available`` is false. */
export interface WeatherData {
  available: boolean;
  reason?: "provider_unreachable" | "live_lookups_disabled";
  source: string;
  zone_id: string | null;
  latitude: number;
  longitude: number;
  temperature_c?: number | null;
  humidity_percent?: number | null;
  wind_speed_kmh?: number | null;
  wind_direction_deg?: number | null;
  precipitation_mm?: number | null;
  weather_code?: number | null;
  conditions?: string;
  rain_probability_percent?: number | null;
  observed_at?: string | null;
  timezone?: string | null;
  units?: { temperature: string; wind_speed: string; humidity: string };
}

export async function fetchWeather(zoneId: string): Promise<WeatherData> {
  const res = await fetch(`/api/weather?zone_id=${encodeURIComponent(zoneId)}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export interface WeatherZone {
  zone_id: string;
  name: string;
  headquarters: string;
  latitude: number;
  longitude: number;
}

export interface WeatherZonesResponse {
  zones: WeatherZone[];
  live_enabled: boolean;
  source: string;
}

export async function fetchWeatherZones(): Promise<WeatherZonesResponse> {
  const res = await fetch("/api/weather/zones", { headers: authHeaders() });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}
