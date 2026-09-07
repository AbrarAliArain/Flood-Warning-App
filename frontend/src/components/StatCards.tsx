import type { AlertItem, GaugesResponse, ZonesResponse } from "../api/client";
import { useI18n } from "../i18n";
import { deriveStats } from "./Hero";
import {
  IconAlertTriangle,
  IconArrowUp,
  IconCloudRain,
  IconMapPin,
  IconWaves,
} from "./icons";

interface Props {
  zones: ZonesResponse | null;
  gauges: GaugesResponse | null;
  alerts: AlertItem[];
}

export default function StatCards({ zones, gauges, alerts }: Props) {
  const { t } = useI18n();
  const { scores, critical, rain24, topGauge } = deriveStats(zones, gauges);
  const rising = topGauge
    ? ["high", "very high", "exceptional"].includes(topGauge.flood_class)
    : false;

  return (
    <div className="stat-cards">
      <div className="scard">
        <span className="scard-icon">
          <IconCloudRain size={22} />
        </span>
        <div>
          <div className="scard-label">{t("statCards.rainfall24h")}</div>
          <div className="scard-value">{rain24} mm</div>
          <div className="scard-sub up">+12%</div>
        </div>
      </div>

      <div className="scard">
        <span className="scard-icon">
          <IconWaves size={22} />
        </span>
        <div>
          <div className="scard-label">{t("statCards.waterLevel")}</div>
          <div className="scard-value">
            {topGauge ? `${topGauge.flow_lacs_cusecs} ${t("statCards.lacs")}` : "\u2014"}
          </div>
          <div className={`scard-sub ${rising ? "rising" : "blue"}`}>
            {rising ? (
              <>
                <IconArrowUp size={11} /> {t("statCards.rising")}
              </>
            ) : (
              t("statCards.steady")
            )}
          </div>
        </div>
      </div>

      <div className="scard">
        <span className="scard-icon red">
          <IconAlertTriangle size={22} />
        </span>
        <div>
          <div className="scard-label">{t("statCards.activeAlerts")}</div>
          <div className="scard-value">{alerts.length}</div>
          <div className="scard-sub red">{t("statCards.criticalZones", { count: critical })}</div>
        </div>
      </div>

      <div className="scard">
        <span className="scard-icon">
          <IconMapPin size={22} />
        </span>
        <div>
          <div className="scard-label">{t("statCards.affectedAreas")}</div>
          <div className="scard-value">{scores.length}</div>
          <div className="scard-sub blue">{t("statCards.monitored")}</div>
        </div>
      </div>
    </div>
  );
}
