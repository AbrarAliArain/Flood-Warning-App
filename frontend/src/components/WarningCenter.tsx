import { useCallback, useEffect, useState } from "react";
import { fetchAlerts, issueDemoAlert, type AlertItem } from "../api/client";
import { useI18n } from "../i18n";
import { timeAgo } from "../utils/time";
import { IconAlertTriangle, IconMapPin } from "./icons";

type Sev = "critical" | "warning" | "watch";

function toSev(severity: string): Sev {
  if (severity === "critical") return "critical";
  if (severity === "warning") return "warning";
  return "watch";
}

interface Props {
  onViewZone: (zoneId: string | null) => void;
}

export default function WarningCenter({ onViewZone }: Props) {
  const { t } = useI18n();
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [status, setStatus] = useState("");
  const [showAll, setShowAll] = useState(false);

  const load = useCallback(() => {
    fetchAlerts()
      .then((data) => setAlerts(data.alerts))
      .catch((err) => console.error(err));
  }, []);

  useEffect(load, [load]);

  const issue = async () => {
    try {
      await issueDemoAlert();
      setStatus(t("warningCenter.demoIssued"));
      load();
    } catch (err) {
      setStatus(t("warningCenter.failed", { error: String(err) }));
    }
  };

  const visible = showAll ? alerts : alerts.slice(0, 4);

  return (
    <section className="card alerts-card">
      <div className="card-head">
        <span className="head-icon">
          <IconAlertTriangle size={18} />
        </span>
        <div>
          <div className="head-title">{t("warningCenter.title")}</div>
          <div className="head-sub">{t("warningCenter.sub")}</div>
        </div>
        {alerts.length > 4 && (
          <button className="section-action" onClick={() => setShowAll((s) => !s)}>
            {showAll ? t("warningCenter.showLess") : t("warningCenter.viewAll")}
          </button>
        )}
      </div>

      <div className="card-body">
        {visible.length === 0 && (
          <div className="alerts-empty">{t("warningCenter.noAlerts")}</div>
        )}
        {visible.map((a) => {
          const sev = toSev(a.severity);
          const sevKey = sev === "critical" ? t("warningCenter.sevCritical") : sev === "warning" ? t("warningCenter.sevWarning") : t("warningCenter.sevWatch");
          return (
            <article className={`alert-item ${sev}`} key={a.id}>
              <div className="alert-top">
                <span className={`alert-icon ${sev}`}>
                  <IconAlertTriangle size={17} />
                </span>
                <span className={`alert-sev ${sev}`}>{sevKey}</span>
              </div>
              <p className="alert-msg">{a.message}</p>
              <div className="alert-meta">
                <span className="loc">
                  <IconMapPin size={12} /> {a.zone_name ?? t("warningCenter.sindhWide")}
                </span>
                <time>{timeAgo(a.created_at)}</time>
              </div>
              <div className="alert-actions">
                <button className="btn btn-ghost btn-sm" onClick={() => onViewZone(a.zone_id)}>
                  {t("warningCenter.viewDetails")}
                </button>
              </div>
            </article>
          );
        })}

        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, paddingTop: 4 }}>
          <button className="cta danger" onClick={issue}>
            {t("warningCenter.issueDemo")}
          </button>
          {status && <span className="form-status">{status}</span>}
        </div>
      </div>
    </section>
  );
}
