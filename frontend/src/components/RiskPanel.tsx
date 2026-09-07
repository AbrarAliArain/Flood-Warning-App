import { useEffect, useState } from "react";
import { fetchZoneDetail, type ZoneDetail } from "../api/client";
import { useI18n } from "../i18n";
import FloodRiskScore from "./FloodRiskScore";

const FACTOR_KEYS: Record<string, string> = {
  rainfall: "riskPanel.factorRainfall",
  river: "riskPanel.factorRiver",
  exposure: "riskPanel.factorExposure",
  historical: "riskPanel.factorHistorical",
};

interface Props {
  zoneId: string;
  onClose: () => void;
}

export default function RiskPanel({ zoneId, onClose }: Props) {
  const { t } = useI18n();
  const [detail, setDetail] = useState<ZoneDetail | null>(null);

  useEffect(() => {
    setDetail(null);
    fetchZoneDetail(zoneId)
      .then(setDetail)
      .catch((err) => console.error(err));
  }, [zoneId]);

  if (!detail) return <aside className="risk-panel">{t("riskPanel.loading")}</aside>;

  return (
    <aside className="risk-panel">
      <div className="risk-panel-head">
        <div>
          <h2>{detail.name}</h2>
          <span className="division">{detail.division} {t("riskPanel.division")}</span>
        </div>
        <button className="close-btn" onClick={onClose} aria-label={t("riskPanel.closePanel")}>
          ×
        </button>
      </div>

      <FloodRiskScore zoneId={zoneId} showExplainer compact />

      <h3>{t("riskPanel.mainRiskFactors")}</h3>
      <div className="chip-row">
        {detail.profile.risk_factors.map((f) => (
          <span key={f} className="factor-chip">
            {f}
          </span>
        ))}
      </div>

      <h3>{t("riskPanel.legacyScoreTitle")}</h3>
      <p className="legacy-score-note">
        {t("riskPanel.legacyScoreNote", {
          score: detail.score,
          category: detail.category.toUpperCase(),
        })}
      </p>
      {Object.entries(detail.factors).map(([key, f]) => (
        <div key={key} className="factor-bar">
          <div className="factor-label">
            <span>{FACTOR_KEYS[key] ? t(FACTOR_KEYS[key]) : key}</span>
            <span>{Math.round(f.weight * 100)}%</span>
          </div>
          <div className="bar">
            <div className="bar-fill" style={{ width: `${f.value * 100}%`, background: detail.color }} />
          </div>
        </div>
      ))}

      <h3>{t("riskPanel.currentConditions")}</h3>
      <ul className="kv-list">
        <li>
          <span>{t("riskPanel.rainfall")}</span>
          <strong>{detail.live.rainfall_mm_hr} {t("common.mmHr")}</strong>
        </li>
        <li>
          <span>{t("riskPanel.riverFlow")}</span>
          <strong>
            {detail.live.river_flow_lacs_cusecs !== null
              ? `${detail.live.river_flow_lacs_cusecs} ${t("common.lacsCusecs")} @ ${detail.live.gauge?.toUpperCase()}`
              : t("riskPanel.rainfallDriven")}
          </strong>
        </li>
        <li>
          <span>{t("riskPanel.rainfallBaseline")}</span>
          <strong>{detail.profile.rainfall_baseline_mm_yr} {t("common.mmYr")}</strong>
        </li>
      </ul>

      <h3>{t("riskPanel.evidenceProvenance")}</h3>
      <ul className="kv-list small">
        <li>
          <span>{t("riskPanel.housesDamaged")}</span>
          <strong>{detail.profile.houses_2022?.toLocaleString() ?? t("riskPanel.notReported")}</strong>
        </li>
        <li>
          <span>{t("riskPanel.floodYears")}</span>
          <strong>{detail.profile.historical_events.join(", ") || "—"}</strong>
        </li>
        <li>
          <span>{t("riskPanel.baselineSource")}</span>
          <strong>{detail.profile.baseline_source}</strong>
        </li>
        <li>
          <span>{t("riskPanel.damageSource")}</span>
          <strong>{detail.profile.houses_source}</strong>
        </li>
      </ul>
    </aside>
  );
}
