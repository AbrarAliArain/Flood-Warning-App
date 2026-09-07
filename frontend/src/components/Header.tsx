import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth";
import { type Lang, useI18n } from "../i18n";
import { IconBell, IconGlobe, IconMenu, IconWave, IconX } from "./icons";

export const NAV_ITEMS = [
  { id: "home", labelKey: "nav.home" },
  { id: "live-map", labelKey: "nav.liveMap" },
  { id: "alerts", labelKey: "nav.alerts" },
  { id: "forecast", labelKey: "nav.forecast" },
  { id: "safety", labelKey: "nav.safety" },
  { id: "responder", labelKey: "nav.responder" },
  { id: "about", labelKey: "nav.about" },
];

export function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

const LANG_OPTIONS: { value: Lang; label: string }[] = [
  { value: "en", label: "EN" },
  { value: "ur", label: "\u0627\u0631\u062f\u0648" },
  { value: "sd", label: "\u0633\u0646\u068c\u064a" },
];

interface Props {
  alertCount: number;
  apiStatus: string;
}

export default function Header({ alertCount, apiStatus }: Props) {
  const { t, lang, setLang } = useI18n();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState("home");
  const [langOpen, setLangOpen] = useState(false);
  const langRef = useRef<HTMLDivElement | null>(null);
  const { user, loginDemoCitizen, loginDemoResponder, logout, isLoading } = useAuth();

  useEffect(() => {
    const onScroll = () => {
      const probe = window.scrollY + 120;
      let current = NAV_ITEMS[0].id;
      for (const item of NAV_ITEMS) {
        const el = document.getElementById(item.id);
        if (el && el.offsetTop <= probe) current = item.id;
      }
      setActive(current);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (langRef.current && !langRef.current.contains(e.target as Node)) setLangOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const go = (id: string) => {
    setActive(id);
    setOpen(false);
    scrollToSection(id);
  };

  const currentLabel = LANG_OPTIONS.find((o) => o.value === lang)?.label ?? "EN";

  const roleLabel =
    user?.role === "citizen"
      ? t("header.demoCitizen")
      : user?.role === "responder"
        ? t("header.demoResponder")
        : user?.role === "admin"
          ? t("header.admin")
          : null;

  return (
    <>
      <header className="header">
        <a className="brand" href="#home" onClick={(e) => { e.preventDefault(); go("home"); }}>
          <span className="brand-mark">
            <IconWave size={22} />
          </span>
          <span>
            <span className="brand-name">{t("header.brand")}</span>
            <br />
            <span className="brand-sub">{t("header.brandSub")}</span>
          </span>
        </a>

        <nav className="nav" aria-label="Primary">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              className={`nav-link ${active === item.id ? "active" : ""}`}
              onClick={() => go(item.id)}
            >
              {t(item.labelKey)}
            </button>
          ))}
        </nav>

        <div className="header-actions">
          <span className="muted" style={{ display: "inline" }} title={t("header.backendConn")}>
            {apiStatus}
          </span>
          <div className="lang-switcher" ref={langRef}>
            <button
              className="lang-btn"
              onClick={() => setLangOpen((o) => !o)}
              aria-label="Language"
            >
              <IconGlobe size={15} />
              <span>{currentLabel}</span>
            </button>
            {langOpen && (
              <div className="lang-dropdown">
                {LANG_OPTIONS.map((o) => (
                  <button
                    key={o.value}
                    className={`lang-option ${lang === o.value ? "active" : ""}`}
                    onClick={() => { setLang(o.value); setLangOpen(false); }}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            )}
          </div>
          {user ? (
            <span className="auth-chip" title={user.full_name}>
              <span className="auth-chip-role">{roleLabel}</span>
              <button className="auth-chip-logout" onClick={logout} title="Log out">
                &times;
              </button>
            </span>
          ) : (
            <span className="auth-login-group">
              <button
                className="auth-login-btn citizen"
                onClick={loginDemoCitizen}
                disabled={isLoading}
              >
                {isLoading ? "\u2026" : t("header.citizenLogin")}
              </button>
              <button
                className="auth-login-btn responder"
                onClick={loginDemoResponder}
                disabled={isLoading}
              >
                {isLoading ? "\u2026" : t("header.responderLogin")}
              </button>
            </span>
          )}
          <button
            className="icon-btn"
            aria-label={`${t("nav.alerts")} (${alertCount})`}
            onClick={() => go("alerts")}
          >
            <IconBell size={18} />
            {alertCount > 0 && <span className="bell-badge">{alertCount}</span>}
          </button>
          <button
            className="icon-btn hamburger"
            aria-label={t("header.openMenu")}
            onClick={() => setOpen((o) => !o)}
          >
            {open ? <IconX size={18} /> : <IconMenu size={18} />}
          </button>
        </div>
      </header>

      {open && (
        <div className="mobile-menu">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              className={`nav-link ${active === item.id ? "active" : ""}`}
              onClick={() => go(item.id)}
            >
              {t(item.labelKey)}
            </button>
          ))}
        </div>
      )}
    </>
  );
}
