import type { GaugeStation } from "../api/client";
import { useI18n } from "../i18n";

const ROWS: Array<{ key: "low" | "medium" | "high" | "very_high" | "exceptional"; labelKey: string }> = [
  { key: "low", labelKey: "gaugeBoard.lowFlood" },
  { key: "medium", labelKey: "gaugeBoard.mediumFlood" },
  { key: "high", labelKey: "gaugeBoard.highFlood" },
  { key: "very_high", labelKey: "gaugeBoard.veryHigh" },
  { key: "exceptional", labelKey: "gaugeBoard.exceptional" },
];

const CLASS_ROW: Record<string, string> = {
  low: "low",
  medium: "medium",
  high: "high",
  "very high": "very_high",
  exceptional: "exceptional",
};

function GaugeCard({ gauge, t }: { gauge: GaugeStation; t: (key: string, vars?: Record<string, string | number>) => string }) {
  const activeRow = CLASS_ROW[gauge.flood_class];
  return (
    <div className="gauge-card">
      <div className="gauge-head">
        <h3>{gauge.name}</h3>
        <span className="gauge-river">{gauge.river}</span>
      </div>
      <div className="gauge-current" style={{ color: gauge.color }}>
        {gauge.flow_lacs_cusecs} {t("common.lacsCusecs")} — {gauge.flood_class.toUpperCase()}
      </div>
      <table className="gauge-table">
        <tbody>
          <tr>
            <td>{t("gaugeBoard.designCapacity")}</td>
            <td>{gauge.design_capacity !== null ? `${gauge.design_capacity} ${t("gaugeBoard.lacs")}` : "—"}</td>
          </tr>
          {ROWS.map((row) => (
            <tr key={row.key} className={row.key === activeRow ? "active" : undefined}>
              <td>{t(row.labelKey)}</td>
              <td>{gauge[row.key]} {t("gaugeBoard.lacs")}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="gauge-note">{t("gaugeBoard.levelsNote")}</div>
    </div>
  );
}

interface Props {
  gauges: GaugeStation[];
}

export default function GaugeBoard({ gauges }: Props) {
  const { t } = useI18n();
  return (
    <div className="gauge-board">
      {gauges.map((g) => (
        <GaugeCard key={g.id} gauge={g} t={t} />
      ))}
    </div>
  );
}
