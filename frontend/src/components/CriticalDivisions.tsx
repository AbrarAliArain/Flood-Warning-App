import { useEffect, useState } from "react";
import { fetchAutoWarnings, type DivisionWarning } from "../api/client";
import { useI18n } from "../i18n";

const DIVISION_IMAGES: Record<string, string> = {
  Karachi: "/divisions/karachi.png",
  Hyderabad: "/divisions/hyderabad.png",
  "Mirpur Khas": "/divisions/mirpur-khas.png",
  Sukkur: "/divisions/sukkur.png",
  Larkana: "/divisions/larkana.png",
};

export default function CriticalDivisions() {
  const { t } = useI18n();
  const [warnings, setWarnings] = useState<DivisionWarning[] | null>(null);

  useEffect(() => {
    fetchAutoWarnings()
      .then((data) => setWarnings(data.warnings))
      .catch(() => setWarnings([]));
  }, []);

  return (
    <section className="cd-section" id="alerts">
      <div className="cd-divider" aria-hidden="true">
        <span className="cd-dot" />
        <span className="cd-dot" />
        <span className="cd-dot" />
        <span className="cd-dot" />
        <span className="cd-star">★</span>
        <span className="cd-dot" />
        <span className="cd-dot" />
        <span className="cd-dot" />
        <span className="cd-dot" />
      </div>
      <h2 className="cd-title">{t("criticalDivisions.title")}</h2>
      <p className="cd-sub">{t("criticalDivisions.sub")}</p>

      {warnings === null ? (
        <p className="cd-empty">{t("criticalDivisions.loading")}</p>
      ) : warnings.length === 0 ? (
        <p className="cd-empty">{t("criticalDivisions.noRisk")}</p>
      ) : (
        <div className="cd-grid">
          {warnings.map((w) => {
            const districts = [...w.districts].sort((a, b) => b.score - a.score);
            return (
              <article className="cd-card" key={w.division}>
                <div className="cd-left">
                  <img
                    className="cd-avatar"
                    src={DIVISION_IMAGES[w.division] ?? "/divisions/hyderabad.png"}
                    alt={t("criticalDivisions.sceneAlt", { name: w.division })}
                  />
                  <div className="cd-name">
                    {w.division}
                    <br />
                    {t("criticalDivisions.divisionLabel")}
                  </div>
                </div>
                <ul className="cd-list">
                  {districts.map((d) => (
                    <li key={d.zone_id} className={`cd-${d.category}`}>
                      <span className="cd-bullet" />
                      <span>
                        {d.name} · {d.score}/100
                      </span>
                    </li>
                  ))}
                </ul>
                <div className="cd-counts">
                  {w.critical_count > 0 && (
                    <span className="cd-chip critical">{t("criticalDivisions.criticalChip", { count: w.critical_count })}</span>
                  )}
                  {w.high_count > 0 && (
                    <span className="cd-chip high">{t("criticalDivisions.highChip", { count: w.high_count })}</span>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
