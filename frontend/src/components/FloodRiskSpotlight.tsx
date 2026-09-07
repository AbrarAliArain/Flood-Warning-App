import type { ZoneProperties } from "../api/client";
import { useI18n } from "../i18n";
import FloodRiskScore from "./FloodRiskScore";
import { IconShield } from "./icons";

/**
 * Dashboard-level entry point for the risk score: pick a district, see its
 * score and the factors behind it. Selecting a district on the live map keeps
 * this in sync via the shared `zoneId` in App.
 */
interface Props {
  zones: ZoneProperties[];
  zoneId: string;
  onZoneChange: (zoneId: string) => void;
}

export default function FloodRiskSpotlight({ zones, zoneId, onZoneChange }: Props) {
  const { t } = useI18n();
  const sorted = [...zones].sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className="card risk-spotlight">
      <div className="risk-spotlight-head">
        <h2>
          <IconShield size={18} /> {t("riskScore.sectionTitle")}
        </h2>
        <label className="risk-spotlight-picker">
          {t("riskScore.selectDistrict")}
          <select value={zoneId} onChange={(e) => onZoneChange(e.target.value)}>
            {sorted.map((zone) => (
              <option key={zone.zone_id} value={zone.zone_id}>
                {zone.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="section-sub">{t("riskScore.sectionSub")}</p>
      <FloodRiskScore zoneId={zoneId} showExplainer />
    </div>
  );
}
