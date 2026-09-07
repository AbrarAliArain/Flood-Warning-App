import type { AlertItem, GaugesResponse, ZonesResponse } from "../api/client";
import { useI18n } from "../i18n";
import { timeAgo } from "../utils/time";
import { scrollToSection } from "./Header";
import {
  IconAlertTriangle,
  IconArrowUp,
  IconBell,
  IconCloudRain,
  IconMap,
  IconShieldCheck,
} from "./icons";

export function deriveStats(zones: ZonesResponse | null, gauges: GaugesResponse | null) {
  const scores = zones?.features.map((f) => f.properties) ?? [];
  const critical = scores.filter((s) => s.category === "critical").length;
  const high = scores.filter((s) => s.category === "high").length;
  const peakRain = scores.reduce((m, s) => Math.max(m, s.rainfall_mm_hr ?? 0), 0);
  const rain24 = Math.round(peakRain * 24);
  const topGauge =
    gauges && gauges.gauges.length
      ? [...gauges.gauges].sort((a, b) => b.flow_lacs_cusecs - a.flow_lacs_cusecs)[0]
      : null;
  return { scores, critical, high, rain24, topGauge };
}

interface Props {
  zones: ZonesResponse | null;
  gauges: GaugesResponse | null;
  alerts: AlertItem[];
}

const R = 104;
const CIRC = 2 * Math.PI * R;

export default function Hero({ zones, gauges, alerts }: Props) {
  const { t } = useI18n();
  const { scores, critical, high, rain24, topGauge } = deriveStats(zones, gauges);
  const criticalAlerts = alerts.filter((a) => a.severity === "critical").length;

  const riskLevel = critical > 0 ? t("hero.riskCritical") : high > 0 ? t("hero.riskHigh") : scores.length ? t("hero.riskModerate") : "\u2014";
  const riskClass = critical > 0 ? "critical" : high > 0 ? "high" : "";

  const flow = topGauge?.flow_lacs_cusecs ?? 0;
  const max = topGauge?.exceptional ?? 1;
  const pct = Math.min(1, flow / (max || 1));
  const rising = topGauge
    ? ["high", "very high", "exceptional"].includes(topGauge.flood_class)
    : false;

  return (
    <section className="hero" id="home">
      <div className="hero-inner">
        <div className="hero-copy">
          <span className="hero-eyebrow">{t("hero.eyebrow")}</span>
          <h1 className="hero-title">
            {t("hero.title1")}
            <br />
            <span className="highlight">{t("hero.title2")}</span>
          </h1>
          <p className="hero-desc">{t("hero.desc")}</p>
          <div className="hero-actions">
            <button className="btn btn-primary" onClick={() => scrollToSection("live-map")}>
              <IconMap size={17} /> {t("hero.viewLiveMap")}
            </button>
            <button className="btn btn-secondary" onClick={() => scrollToSection("enable-alerts")}>
              <IconBell size={17} /> {t("hero.enableAlerts")}
            </button>
          </div>
          <div className="hero-meta">{t("hero.meta")}</div>
        </div>

        <div className="gauge-wrap" role="img" aria-label={`${t("hero.waterLevel")} ${flow} ${t("hero.lacsCusecs")}`}>
          <svg viewBox="0 0 240 240">
            <defs>
              <linearGradient id="gaugeGrad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#087EA4" />
                <stop offset="100%" stopColor="#18A9D1" />
              </linearGradient>
            </defs>
            <circle className="gauge-track" cx="120" cy="120" r={R} />
            <circle
              className="gauge-progress"
              cx="120"
              cy="120"
              r={R}
              strokeDasharray={CIRC}
              strokeDashoffset={CIRC * (1 - Math.max(0.06, pct))}
            />
          </svg>
          <div className="gauge-center">
            <span className="gauge-label">{t("hero.waterLevel")}</span>
            <span className="gauge-value">
              {flow}
              <small>{t("hero.lacsCusecs")}</small>
            </span>
            <span className="gauge-trend">
              {rising ? (
                <>
                  {t("hero.rising")} <IconArrowUp size={14} />
                </>
              ) : (
                t("hero.steady")
              )}
            </span>
            <span className="gauge-updated">
              {topGauge ? `${topGauge.name} \u00b7 ` : ""}
              {gauges ? timeAgo(gauges.updated_at) : t("hero.waitingData")}
            </span>
          </div>
          <div className="gauge-scale">
            <span>0</span>
            <span>{max}</span>
          </div>
        </div>

        <div className="hero-cards">
          <div className="hcard">
            <span className="hcard-icon blue">
              <IconCloudRain size={20} />
            </span>
            <div>
              <div className="hcard-label">{t("hero.rainfall24h")}</div>
              <div className="hcard-value">{rain24} mm</div>
              <div className="hcard-sub up">{t("hero.fromYesterday")}</div>
            </div>
          </div>
          <div className="hcard">
            <span className="hcard-icon orange">
              <IconShieldCheck size={20} />
            </span>
            <div>
              <div className="hcard-label">{t("hero.riskLevel")}</div>
              <div className={`hcard-value ${riskClass}`}>{riskLevel}</div>
            </div>
          </div>
          <div className="hcard">
            <span className="hcard-icon red">
              <IconAlertTriangle size={20} />
            </span>
            <div>
              <div className="hcard-label">{t("hero.activeAlerts")}</div>
              <div className="hcard-value">{alerts.length}</div>
              <div className="hcard-sub red">{criticalAlerts} {t("hero.critical")}</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
