import { useEffect, useState } from "react";
import { fetchInsights, type InsightData, type ZoneProperties } from "../api/client";
import { useI18n } from "../i18n";

const CATEGORY_COLORS: Record<string, string> = {
  critical: "#DC2626",
  high: "#F97316",
  moderate: "#EAB308",
  low: "#16A34A",
};

function DocIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  );
}

interface Props {
  zones: ZoneProperties[];
}

export default function InsightPanel({ zones }: Props) {
  const { t } = useI18n();
  const sorted = [...zones].sort((a, b) => b.score - a.score);
  const [zoneId, setZoneId] = useState(sorted[0]?.zone_id ?? "karachi");
  const [insight, setInsight] = useState<InsightData | null>(null);

  useEffect(() => {
    setInsight(null);
    fetchInsights(zoneId)
      .then(setInsight)
      .catch((err) => console.error(err));
  }, [zoneId]);

  const catColor = insight ? (CATEGORY_COLORS[insight.category] ?? "#94A3B8") : "#94A3B8";
  const scoreDeg = insight ? (insight.score / 100) * 360 : 0;

  return (
    <div className="insight-panel">
      {/* Header bar */}
      <div className="insight-head">
        <div className="insight-selector">
          <label htmlFor="insight-zone">{t("insightPanel.district")}</label>
          <select id="insight-zone" value={zoneId} onChange={(e) => setZoneId(e.target.value)}>
            {sorted.map((z) => (
              <option key={z.zone_id} value={z.zone_id}>
                {z.name} — {z.score}/100
              </option>
            ))}
          </select>
        </div>

        {insight && (
          <div className="insight-score-block">
            <div
              className="insight-score-ring"
              style={{
                background: `conic-gradient(${catColor} ${scoreDeg}deg, #e2e8f0 ${scoreDeg}deg)`,
              }}
            >
              <span className="insight-score-num">{insight.score}</span>
            </div>
            <div className="insight-score-meta">
              <strong>{insight.name}</strong>
              <span className="insight-cat-chip" style={{ background: catColor, color: "#fff" }}>
                {insight.category.toUpperCase()}
              </span>
            </div>
          </div>
        )}

        <div className="insight-badges">
          {insight && (
            <span className="ai-badge">
              {t("insightPanel.aiLabel")}: {insight.explanation_source === "llm" ? t("insightPanel.llm") : t("insightPanel.ruleBased")}
            </span>
          )}
          {insight?.inputs_are_demo && <span className="demo-tag">{t("common.demo")} INPUTS</span>}
        </div>
      </div>

      {insight && (
        <>
          <div className="insight-callout" style={{ borderLeftColor: catColor }}>
            <h4>{t("insightPanel.whyAtRisk", { name: insight.name })}</h4>
            <p>{insight.explanation}</p>
          </div>

          <div className="insight-section">
            <h4>{t("insightPanel.recommendedActions")}</h4>
            <div className="insight-actions-grid">
              {insight.recommendations.map((rec, i) => (
                <div key={rec.action} className="insight-action-card">
                  <span className="insight-step-num">{i + 1}</span>
                  <p className="insight-action-text">{rec.action}</p>
                  <span className="src-chip">{rec.source}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="insight-section">
            <h4>{t("insightPanel.retrievedSources")}</h4>
            <ul className="insight-sources">
              {insight.retrieved.map((r, i) => (
                <li key={`${r.doc}-${i}`} className="insight-source-card">
                  <span className="insight-source-icon"><DocIcon /></span>
                  <div className="insight-source-body">
                    <strong>{r.doc} <span className="insight-source-sep">&mdash;</span> {r.heading}</strong>
                    <p>{r.snippet}&hellip;</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
