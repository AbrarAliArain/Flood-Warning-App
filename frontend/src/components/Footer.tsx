import { useI18n } from "../i18n";
import { NAV_ITEMS, scrollToSection } from "./Header";
import { IconClock, IconGlobe, IconRadio, IconShieldCheck, IconWave } from "./icons";

const STATS = [
  { icon: IconRadio, value: "10,000+", labelKey: "footer.monitoringPoints" },
  { icon: IconClock, value: "24/7", labelKey: "footer.liveMonitoring" },
  { icon: IconShieldCheck, value: "99.9%", labelKey: "footer.systemUptime" },
  { icon: IconGlobe, value: "50+", labelKey: "footer.monitoredRegions" },
];

interface Props {
  onOpenModal: (kind: "privacy" | "terms") => void;
}

export default function Footer({ onOpenModal }: Props) {
  const { t } = useI18n();
  return (
    <footer className="footer" id="about">
      <div className="footer-inner">
        <div className="footer-top">
          <div className="footer-brand">
            <span className="brand">
              <span className="brand-mark">
                <IconWave size={22} />
              </span>
              <span>
                <span className="brand-name">{t("footer.brand")}</span>
                <br />
                <span className="brand-sub">{t("footer.brandSub")}</span>
              </span>
            </span>
            <p>{t("footer.desc")}</p>
          </div>

          <div className="footer-col">
            <h4>{t("footer.navigate")}</h4>
            {NAV_ITEMS.map((item) => (
              <button key={item.id} onClick={() => scrollToSection(item.id)}>
                {t(item.labelKey)}
              </button>
            ))}
          </div>

          <div className="footer-col">
            <h4>{t("footer.resources")}</h4>
            <button onClick={() => onOpenModal("privacy")}>{t("footer.privacy")}</button>
            <button onClick={() => onOpenModal("terms")}>{t("footer.terms")}</button>
            <a
              href="https://ffd.pmd.gov.pk/bulletin"
              target="_blank"
              rel="noreferrer"
              style={{ color: "var(--muted)", fontSize: 13.5, fontWeight: 600, textDecoration: "none", display: "block", padding: "4px 0" }}
            >
              {t("footer.pmdBulletins")} ↗
            </a>
          </div>
        </div>

        <div className="footer-stats">
          {STATS.map((s) => {
            const Icon = s.icon;
            return (
              <div className="fstat" key={s.labelKey}>
                <span className="fstat-icon">
                  <Icon size={19} />
                </span>
                <div>
                  <b>{s.value}</b>
                  <span>{t(s.labelKey)}</span>
                </div>
              </div>
            );
          })}
        </div>

        <div className="footer-bottom">
          <span>{t("footer.copyright")}</span>
          <span className="footer-note">{t("footer.disclaimer")}</span>
        </div>
      </div>
    </footer>
  );
}
