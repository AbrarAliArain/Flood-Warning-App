import { useState } from "react";
import { useI18n } from "../i18n";
import { scrollToSection } from "./Header";
import { IconAlertTriangle, IconHome, IconPhone, IconShare } from "./icons";

interface Props {
  onContacts: () => void;
  onReport: () => void;
}

export default function QuickActions({ onContacts, onReport }: Props) {
  const { t } = useI18n();
  const [status, setStatus] = useState("");

  const shareLocation = () => {
    if (!navigator.geolocation) {
      setStatus(t("quickActions.geoNotSupported"));
      return;
    }
    setStatus(t("quickActions.locating"));
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const url = `https://maps.google.com/?q=${pos.coords.latitude.toFixed(5)},${pos.coords.longitude.toFixed(5)}`;
        if (navigator.share) {
          try {
            await navigator.share({ title: "My location", url });
            setStatus(t("quickActions.locationShared"));
          } catch {
            setStatus(t("quickActions.shareCancelled"));
          }
        } else {
          try {
            await navigator.clipboard.writeText(url);
            setStatus(t("quickActions.linkCopied"));
          } catch {
            setStatus(url);
          }
        }
      },
      () => setStatus(t("quickActions.locationUnavailable"))
    );
  };

  return (
    <section className="card">
      <div className="card-head">
        <span className="head-icon">
          <IconAlertTriangle size={18} />
        </span>
        <div>
          <div className="head-title">{t("quickActions.title")}</div>
          <div className="head-sub">{t("quickActions.sub")}</div>
        </div>
      </div>
      <div className="quick-grid">
        <button className="qa-tile" onClick={onContacts}>
          <span className="qa-icon red">
            <IconPhone size={20} />
          </span>
          {t("quickActions.emergencyContacts")}
        </button>
        <button className="qa-tile" onClick={() => scrollToSection("safe-locations")}>
          <span className="qa-icon green">
            <IconHome size={20} />
          </span>
          {t("quickActions.findSafe")}
        </button>
        <button className="qa-tile" onClick={shareLocation}>
          <span className="qa-icon blue">
            <IconShare size={20} />
          </span>
          {t("quickActions.shareLocation")}
        </button>
        <button className="qa-tile" onClick={onReport}>
          <span className="qa-icon orange">
            <IconAlertTriangle size={20} />
          </span>
          {t("quickActions.reportHazard")}
        </button>
        {status && <div className="qa-status">{status}</div>}
      </div>
    </section>
  );
}
