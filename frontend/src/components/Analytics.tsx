import { useCallback, useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  fetchAnalytics,
  fetchWeather,
  fetchWeatherZones,
  type AnalyticsData,
  type WeatherData,
  type WeatherZone,
} from "../api/client";
import { useI18n } from "../i18n";
import {
  IconCloud,
  IconDroplet,
  IconThermometer,
  IconWind,
} from "./icons";

const ORDER = [
  { key: "critical", labelKey: "analytics.riskCritical", color: "#DC2626" },
  { key: "high", labelKey: "analytics.riskHigh", color: "#F97316" },
  { key: "moderate", labelKey: "analytics.riskModerate", color: "#EAB308" },
  { key: "low", labelKey: "analytics.riskLow", color: "#16A34A" },
];

const RAIN_SHAPE = [
  28, 42, 55, 60, 75, 52, 68, 80, 64, 58, 72, 85, 66, 54, 48, 62, 70, 58, 50, 64, 72, 60, 46, 40,
];

const ZONE_KEY = "aquashield.weatherZone";
const DEFAULT_ZONE = "hyderabad";

function readZone(): string {
  try {
    return localStorage.getItem(ZONE_KEY) || DEFAULT_ZONE;
  } catch {
    return DEFAULT_ZONE;
  }
}

/** A dash beats a plausible-looking number when the provider is down. */
function fmt(value: number | null | undefined, unit = ""): string {
  return value == null ? "—" : `${value}${unit}`;
}

interface Props {
  rain24: number;
}

export default function Analytics({ rain24 }: Props) {
  const { t } = useI18n();
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [zoneId, setZoneId] = useState<string>(readZone);
  const [zones, setZones] = useState<WeatherZone[]>([]);
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [weatherError, setWeatherError] = useState<string | null>(null);

  useEffect(() => {
    fetchAnalytics()
      .then(setData)
      .catch((err) => console.error(err));
  }, []);

  useEffect(() => {
    fetchWeatherZones()
      .then((res) => setZones(res.zones))
      .catch(() => setZones([]));
  }, []);

  const loadWeather = useCallback((id: string) => {
    setWeatherError(null);
    fetchWeather(id)
      .then(setWeather)
      .catch((err: unknown) => {
        setWeather(null);
        setWeatherError(err instanceof Error ? err.message : String(err));
      });
  }, []);

  useEffect(() => {
    loadWeather(zoneId);
  }, [zoneId, loadWeather]);

  const pickZone = (id: string) => {
    setZoneId(id);
    try {
      localStorage.setItem(ZONE_KEY, id);
    } catch {
      /* private browsing — the selector still works for this session */
    }
  };

  const shapeSum = RAIN_SHAPE.reduce((a, b) => a + b, 0);
  const factor = (rain24 > 0 ? rain24 : 82) / shapeSum;
  const rainSeries = RAIN_SHAPE.map((v, i) => ({
    hour: `${i.toString().padStart(2, "0")}:00`,
    mm: +(v * factor).toFixed(1),
  }));

  const trendSeries = (data?.trend ?? []).map((v, i) => ({ t: `${i * 2}h`, v }));
  const lastTrend = trendSeries.length ? trendSeries[trendSeries.length - 1].v : 0;

  const total = Object.values(data?.distribution ?? {}).reduce((a, b) => a + b, 0) || 1;

  const zoneName = zones.find((z) => z.zone_id === zoneId)?.name ?? zoneId;
  const units = weather?.units;
  const weatherRows = [
    {
      icon: IconThermometer,
      labelKey: "analytics.temperature",
      value: fmt(weather?.temperature_c, units?.temperature ?? "°C"),
    },
    {
      icon: IconCloud,
      labelKey: "analytics.rainProbability",
      value: fmt(weather?.rain_probability_percent, "%"),
    },
    {
      icon: IconWind,
      labelKey: "analytics.windSpeed",
      value: fmt(weather?.wind_speed_kmh, ` ${units?.wind_speed ?? "km/h"}`),
    },
    {
      icon: IconDroplet,
      labelKey: "analytics.humidity",
      value: fmt(weather?.humidity_percent, units?.humidity ?? "%"),
    },
  ];

  let weatherNote: string;
  if (weatherError) weatherNote = t("analytics.weatherFailed", { error: weatherError });
  else if (!weather) weatherNote = t("analytics.loadingWeather");
  else if (!weather.available) weatherNote = t(`analytics.weather.${weather.reason ?? "unavailable"}`);
  else
    weatherNote = t("analytics.weatherSource", {
      city: zoneName,
      conditions: weather.conditions ?? "—",
      source: weather.source,
    });

  return (
    <div className="analytics-grid">
      <div className="a-card">
        <div className="a-head">
          <h3 className="a-title">{t("analytics.rainfall24h")}</h3>
          <span className="a-value">{rain24 > 0 ? rain24 : 82} mm</span>
        </div>
        <div className="chart-box">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rainSeries} margin={{ top: 8, right: 4, left: -22, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" vertical={false} />
              <XAxis
                dataKey="hour"
                interval={3}
                tick={{ fontSize: 10, fill: "#64748B" }}
                axisLine={{ stroke: "#E2E8F0" }}
                tickLine={false}
              />
              <YAxis tick={{ fontSize: 10, fill: "#64748B" }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{
                  borderRadius: 10,
                  border: "1px solid #E2E8F0",
                  fontSize: 12,
                }}
              />
              <Bar dataKey="mm" fill="#18A9D1" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="a-sub">{t("analytics.hourlyAccumulation")}</p>
      </div>

      <div className="a-card">
        <div className="a-head">
          <h3 className="a-title">{t("analytics.waterLevelToday")}</h3>
          <span className="a-value">{lastTrend}</span>
        </div>
        <div className="chart-box">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trendSeries} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
              <defs>
                <linearGradient id="waterFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#18A9D1" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#18A9D1" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" vertical={false} />
              <XAxis
                dataKey="t"
                tick={{ fontSize: 10, fill: "#64748B" }}
                axisLine={{ stroke: "#E2E8F0" }}
                tickLine={false}
              />
              <YAxis tick={{ fontSize: 10, fill: "#64748B" }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{
                  borderRadius: 10,
                  border: "1px solid #E2E8F0",
                  fontSize: 12,
                }}
              />
              <Area
                type="monotone"
                dataKey="v"
                stroke="#087EA4"
                strokeWidth={2.5}
                fill="url(#waterFill)"
                dot={{ r: 2.5, fill: "#087EA4", strokeWidth: 0 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <p className="a-sub">{t("analytics.liveTrend")}</p>
      </div>

      <div className="a-card">
        <div className="a-head">
          <h3 className="a-title">{t("analytics.weatherOverview")}</h3>
          <select
            className="a-select"
            aria-label={t("analytics.weatherDistrict")}
            value={zoneId}
            onChange={(e) => pickZone(e.target.value)}
          >
            {zones.length === 0 && <option value={zoneId}>{zoneName}</option>}
            {zones.map((z) => (
              <option key={z.zone_id} value={z.zone_id}>
                {z.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          {weatherRows.map((w) => {
            const Icon = w.icon;
            return (
              <div className="weather-row" key={w.labelKey}>
                <span className="w-icon">
                  <Icon size={17} />
                </span>
                <span className="w-label">{t(w.labelKey)}</span>
                <span className="w-value">{w.value}</span>
              </div>
            );
          })}
        </div>
        <p className="a-sub">{weatherNote}</p>
      </div>

      <div className="a-card wide">
        <div className="dist-block">
          <h3 className="a-title" style={{ marginBottom: 12 }}>
            {t("analytics.riskDistribution")}
          </h3>
          {(data ? ORDER : []).map((row) => {
            const count = data?.distribution[row.key] ?? 0;
            const pct = Math.round((count / total) * 100);
            return (
              <div key={row.key} className="dist-row">
                <div className="factor-label">
                  <span>
                    <i className="dot" style={{ background: row.color }} /> {t(row.labelKey)}
                  </span>
                  <span>
                    {count} · {pct}%
                  </span>
                </div>
                <div className="bar">
                  <div className="bar-fill" style={{ width: `${pct}%`, background: row.color }} />
                </div>
              </div>
            );
          })}
          {!data && <p className="a-sub">{t("analytics.loadingAnalytics")}</p>}
        </div>

        <div className="counters-block counters">
          <div className="stat">
            <b>{data?.reports_count ?? 0}</b>
            <span>{t("analytics.communityReports")}</span>
          </div>
          <div className="stat">
            <b className="red">{data?.active_alerts_count ?? 0}</b>
            <span>{t("analytics.activeAlerts")}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
