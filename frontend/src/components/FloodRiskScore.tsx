import { useEffect, useState } from "react";
import { fetchInsights, type InsightData } from "../api/client";
import {
  bandMeta,
  computeTrend,
  fetchRiskHistory,
  fetchRiskZone,
  FEATURE_LABEL_KEYS,
  intensityKey,
  TREND_META,
  type RiskTrend,
  type RiskZoneAssessment,
} from "../api/riskClient";
import { useI18n } from "../i18n";
import { IconArrowDown, IconArrowRight, IconArrowUp } from "./icons";

/**
 * AI flood risk score plus the "why" breakdown, both sourced from
 * ``/api/risk`` — the engine that publishes real per-feature contributions.
 * Nothing here is computed client-side except the trend, which compares two
 * stored assessments and reports "unknown" when history is too short.
 */
interface Props {
  zoneId: string;
  /** Renders the contributing-factor breakdown and AI explanation. */
  showExplainer?: boolean;
  /** Tighter layout for embedding inside an existing panel. */
  compact?: boolean;
}

function TrendIcon({ direction }: { direction: RiskTrend["direction"] }) {
  if (direction === "up") return <IconArrowUp size={16} />;
  if (direction === "down") return <IconArrowDown size={16} />;
  if (direction === "flat") return <IconArrowRight size={16} />;
  return null;
}

export default function FloodRiskScore({ zoneId, showExplainer = false, compact = false }: Props) {
  const { t } = useI18n();
  const [assessment, setAssessment] = useState<RiskZoneAssessment | null>(null);
  const [trend, setTrend] = useState<RiskTrend | null>(null);
  const [insight, setInsight] = useState<InsightData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setAssessment(null);
    setTrend(null);
    setInsight(null);
    setError(null);

    fetchRiskZone(zoneId)
      .then((data) => {
        if (cancelled) return;
        setAssessment(data);
        // Read history only after scoring, so the row just persisted is included.
        return fetchRiskHistory(zoneId, 20).then((res) => {
          if (!cancelled) setTrend(computeTrend(res.history));
        });
      })
      .catch((err) => {
        if (!cancelled) setError(String(err));
      });

    if (showExplainer) {
      fetchInsights(zoneId)
        .then((data) => {
          if (!cancelled) setInsight(data);
        })
        .catch(() => {
          /* the factor breakdown still works without the narrative */
        });
    }

    return () => {
      cancelled = true;
    };
  }, [zoneId, showExplainer]);

  if (error) {
    return <div className="risk-score-card error">{t("riskScore.unavailable")}</div>;
  }
  if (!assessment) {
    return <div className="risk-score-card loading">{t("riskScore.loading")}</div>;
  }

  const band = bandMeta(assessment.band);
  const trendMeta = trend ? TREND_META[trend.direction] : null;
  const contributions = Object.entries(assessment.contributions).sort((a, b) => b[1] - a[1]);
  const hasContributions = contributions.length > 0;
  const maxContribution = hasContributions ? contributions[0][1] : 0;
  const factorRows = hasContributions
    ? contributions
    : Object.entries(assessment.features).sort((a, b) => b[1] - a[1]);

  return (
    <div className={`risk-score-card${compact ? " compact" : ""}`}>
      <div className="risk-score-head">
        <div>
          <span className="risk-score-district">{assessment.name}</span>
          <span className="risk-score-division">{assessment.division}</span>
        </div>
        {assessment.is_demo && <span className="demo-tag">{t("common.demoData")}</span>}
      </div>

      <div className="risk-score-row">
        <span className="risk-score-value" style={{ color: band.color }}>
          {assessment.score}
        </span>
        <span className="risk-score-outof">/ 100</span>
        <span className="risk-band-chip" style={{ background: band.color }}>
          {t(band.key)}
        </span>
      </div>

      <div className="risk-score-meta">
        <span className="risk-band-range">
          {t("riskScore.bandRange", { range: band.range })}
        </span>
        {trendMeta && (
          <span className={`risk-trend ${trend!.direction}`}>
            <TrendIcon direction={trend!.direction} />
            {t(trendMeta.key)}
            {trend!.delta !== null && trend!.delta !== 0 && (
              <span className="risk-trend-delta">
                {trend!.delta > 0 ? "+" : ""}
                {trend!.delta}
              </span>
            )}
          </span>
        )}
      </div>

      <p className="risk-score-caption">{t("riskScore.caption")}</p>
      <span className="risk-model-note">
        {t("riskScore.modelNote", { model: assessment.model })}
      </span>

      {showExplainer && (
        <div className="risk-why">
          <h3>{t("riskScore.whyTitle", { name: assessment.name })}</h3>
          {assessment.is_demo && (
            <span className="prototype-tag">{t("riskScore.prototypeLabel")}</span>
          )}

          <div className="risk-factor-list">
            {factorRows.map(([key, value]) => (
              <div key={key} className="risk-factor">
                <div className="risk-factor-label">
                  <span>{FEATURE_LABEL_KEYS[key] ? t(FEATURE_LABEL_KEYS[key]) : key}</span>
                  <strong>
                    {hasContributions
                      ? `+${value.toFixed(1)}`
                      : t(intensityKey(value))}
                  </strong>
                </div>
                <div className="bar">
                  <div
                    className="bar-fill"
                    style={{
                      width: `${
                        hasContributions
                          ? maxContribution > 0
                            ? (value / maxContribution) * 100
                            : 0
                          : value * 100
                      }%`,
                      background: band.color,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
          <span className="risk-factor-note">
            {hasContributions
              ? t("riskScore.contributionNote", { score: assessment.score })
              : t("riskScore.intensityNote")}
          </span>

          {insight && (
            <div className="risk-ai-explanation">
              <div className="risk-ai-head">
                <h4>{t("riskScore.aiExplanationTitle")}</h4>
                <span className="ai-badge">
                  {insight.explanation_source === "llm"
                    ? t("riskPanel.llm")
                    : t("riskPanel.ruleBased")}
                </span>
              </div>
              <p>{insight.explanation}</p>
              {insight.inputs_are_demo && (
                <span className="prototype-tag">{t("riskScore.prototypeLabel")}</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
