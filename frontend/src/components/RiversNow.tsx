import type { GaugesResponse } from "../api/client";
import { useI18n } from "../i18n";

interface Props {
  gauges: GaugesResponse | null;
}

export default function RiversNow({ gauges }: Props) {
  const { t } = useI18n();
  if (!gauges) return null;
  const updated = new Date(gauges.updated_at).toLocaleString();
  return (
    <div className="rivers-now">
      <span className="rivers-label">{t("riversNow.label")}</span>
      {gauges.gauges.map((g) => (
        <span key={g.id} className="river-pill">
          <i className="dot" style={{ background: g.color }} />
          {g.name}
          <b style={{ color: g.color }}>{g.flood_class.toUpperCase()}</b>
          <em>{g.flow_lacs_cusecs} {t("riversNow.lacs")} ({t("common.demo")})</em>
        </span>
      ))}
      <span className="updated">{t("riversNow.updated", { time: updated })}</span>
    </div>
  );
}
