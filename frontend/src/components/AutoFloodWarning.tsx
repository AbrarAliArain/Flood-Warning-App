import { useEffect, useRef, useState } from "react";
import { fetchAutoWarnings, type DivisionWarning } from "../api/client";

const POLL_MS = 30_000;

export default function AutoFloodWarning() {
  const [warnings, setWarnings] = useState<DivisionWarning[]>([]);
  const [lastUpdated, setLastUpdated] = useState<string>("");
  const [collapsed, setCollapsed] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = () => {
    fetchAutoWarnings()
      .then(({ warnings: w }) => {
        setWarnings(w);
        setLastUpdated(new Date().toLocaleTimeString());
      })
      .catch(() => {});
  };

  useEffect(() => {
    load();
    timerRef.current = setInterval(load, POLL_MS);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  if (!warnings.length) return null;

  const hasCritical = warnings.some((w) => w.severity === "critical");

  return (
    <div className={`auto-flood-warning ${hasCritical ? "afw-critical" : "afw-high"}`}>
      <div className="afw-header" onClick={() => setCollapsed((c) => !c)}>
        <span className="afw-icon">{hasCritical ? "⚠️" : "🔔"}</span>
        <span className="afw-title">
          {hasCritical ? "FLOOD WARNING — CRITICAL DIVISIONS" : "FLOOD WATCH — HIGH RISK DIVISIONS"}
        </span>
        <span className="afw-badge">DEMO DATA</span>
        <span className="afw-meta">Auto-updated · {lastUpdated}</span>
        <span className="afw-toggle">{collapsed ? "▼ Show" : "▲ Hide"}</span>
      </div>

      {!collapsed && (
        <div className="afw-body">
          {warnings.map((w) => (
            <div key={w.division} className={`afw-card ${w.severity === "critical" ? "afw-card-critical" : "afw-card-high"}`}>
              <div className="afw-card-head">
                <span className={`afw-sev ${w.severity}`}>
                  {w.severity === "critical" ? "CRITICAL" : "HIGH RISK"}
                </span>
                <strong>{w.division} Division</strong>
                <span className="afw-counts">
                  {w.critical_count > 0 && (
                    <span className="count-critical">{w.critical_count} Critical</span>
                  )}
                  {w.high_count > 0 && (
                    <span className="count-high">{w.high_count} High</span>
                  )}
                </span>
              </div>

              <p className="afw-message">{w.message}</p>

              <div className="afw-districts">
                {w.districts
                  .sort((a, b) => b.score - a.score)
                  .map((d) => (
                    <span key={d.zone_id} className={`afw-district-pill ${d.category}`}>
                      {d.name}
                      <span className="pill-score">{d.score}</span>
                    </span>
                  ))}
              </div>

              <div className="afw-time">
                Generated: {new Date(w.generated_at).toLocaleString()} · DEMO — not an official PMD/NDMA advisory
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
