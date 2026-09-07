import { useEffect, useState } from "react";
import { fetchReports, type CommunityReport } from "../api/client";
import { useI18n } from "../i18n";

interface Props {
  refreshKey: number;
}

export default function ReportsFeed({ refreshKey }: Props) {
  const { t } = useI18n();
  const [reports, setReports] = useState<CommunityReport[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    setError("");
    fetchReports()
      .then((data) => setReports(data.reports))
      .catch((err) => setError(`Unable to load reports: ${String(err)}`));
  }, [refreshKey]);

  return (
    <div className="reports-feed">
      {error && <p className="form-status" style={{ color: "var(--red)" }}>{error}</p>}
      {reports.length === 0 && <p className="muted">{t("reportsFeed.noReports")}</p>}
      <ul>
        {reports.map((r) => (
          <li key={r.id}>
            <div className="report-head">
              <strong>{r.zone_name}</strong>
              <span className={`wl-${r.water_level}`}>{r.water_level.toUpperCase()}</span>
              {r.is_demo && <span className="demo-tag">DEMO</span>}
            </div>
            <p>{r.description}</p>
            <time>{new Date(r.created_at).toLocaleString()}</time>
          </li>
        ))}
      </ul>
    </div>
  );
}
