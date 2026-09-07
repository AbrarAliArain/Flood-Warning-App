import { useRef, useState, type FormEvent } from "react";
import { subscribeToAlerts } from "../api/client";
import { useI18n } from "../i18n";
import { scrollToSection } from "./Header";
import { IconBell, IconHome } from "./icons";

export default function EmergencyCta() {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [organization, setOrganization] = useState("");
  const [status, setStatus] = useState("");
  const emailRef = useRef<HTMLInputElement | null>(null);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    try {
      await subscribeToAlerts({
        name: name.trim(),
        email: email.trim(),
        organization: organization.trim() || undefined,
      });
      setStatus(t("emergencyCta.subscribed"));
      setName("");
      setEmail("");
      setOrganization("");
    } catch (err) {
      setStatus(t("emergencyCta.failed", { error: String(err) }));
    }
  };

  return (
    <section className="cta-section" id="enable-alerts">
      <div className="cta-inner">
        <div>
          <h2 className="cta-title">{t("emergencyCta.title")}</h2>
          <p className="cta-text">{t("emergencyCta.text")}</p>
          <div className="cta-buttons">
            <button className="btn btn-primary" onClick={() => emailRef.current?.focus()}>
              <IconBell size={17} /> {t("emergencyCta.enableAlerts")}
            </button>
            <button className="btn btn-secondary" onClick={() => scrollToSection("safe-locations")}>
              <IconHome size={17} /> {t("emergencyCta.findSafe")}
            </button>
          </div>
        </div>

        <form className="cta-form" onSubmit={handleSubmit}>
          <h3>{t("emergencyCta.subscribeTitle")}</h3>
          <div className="si-row">
            <label>
              {t("emergencyCta.yourName")}
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("emergencyCta.namePlaceholder")}
                required
              />
            </label>
            <label>
              {t("emergencyCta.emailAddress")}
              <input
                ref={emailRef}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={t("emergencyCta.emailPlaceholder")}
                required
              />
            </label>
            <label>
              {t("emergencyCta.orgRole")} <em>{t("emergencyCta.optional")}</em>
              <input
                value={organization}
                onChange={(e) => setOrganization(e.target.value)}
                placeholder={t("emergencyCta.orgPlaceholder")}
              />
            </label>
          </div>
          <button type="submit" className="cta">
            {t("emergencyCta.subscribeNow")}
          </button>
          {status && <span className="si-status">{status}</span>}
        </form>
      </div>
    </section>
  );
}
