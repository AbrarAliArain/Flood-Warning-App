import { useEffect, useState } from "react";
import {
  fetchAlerts,
  fetchGauges,
  fetchZones,
  type AlertItem,
  type GaugesResponse,
  type ZonesResponse,
} from "./api/client";
import Analytics from "./components/Analytics";
import Assistant from "./components/Assistant";
import BulletinCard from "./components/BulletinCard";
import CriticalDivisions from "./components/CriticalDivisions";
import EmergencyCta from "./components/EmergencyCta";
import FloodRiskScore from "./components/FloodRiskScore";
import FloodRiskSpotlight from "./components/FloodRiskSpotlight";
import Footer from "./components/Footer";
import GaugeBoard from "./components/GaugeBoard";
import Header, { scrollToSection } from "./components/Header";
import Hero, { deriveStats } from "./components/Hero";
import InsightPanel from "./components/InsightPanel";
import {
  IconEdit,
  IconInbox,
  IconMap,
  IconPhone,
  IconShield,
  IconWaves,
} from "./components/icons";
import MapView from "./components/MapView";
import Modal from "./components/Modal";
import QuickActions from "./components/QuickActions";
import ReportForm from "./components/ReportForm";
import ReportsFeed from "./components/ReportsFeed";
import ResponderDashboard from "./components/ResponderDashboard";
import RiskPanel from "./components/RiskPanel";
import RiversNow from "./components/RiversNow";
import SafeLocations from "./components/SafeLocations";
import StatCards from "./components/StatCards";
import WarningCenter from "./components/WarningCenter";
import { useI18n } from "./i18n";

type ModalKind = "contacts" | "privacy" | "terms" | null;

const CONTACTS = [
  { nameKey: "contacts.rescue1122", number: "1122" },
  { nameKey: "contacts.police", number: "15" },
  { nameKey: "contacts.fireBrigade", number: "16" },
  { nameKey: "contacts.ndma", number: "1070" },
];

export default function App() {
  const { t } = useI18n();
  const [zones, setZones] = useState<ZonesResponse | null>(null);
  const [gauges, setGauges] = useState<GaugesResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [spotlightZone, setSpotlightZone] = useState<string | null>(null);
  const [apiStatus, setApiStatus] = useState("connecting…");
  const [refreshKey, setRefreshKey] = useState(0);
  const [modal, setModal] = useState<ModalKind>(null);

  useEffect(() => {
    fetchZones()
      .then((data) => {
        setZones(data);
        setApiStatus(t("header.apiConnected"));
        const highest = [...data.features].sort(
          (a, b) => b.properties.score - a.properties.score,
        )[0];
        if (highest) setSpotlightZone(highest.properties.zone_id);
      })
      .catch(() => setApiStatus(t("header.apiOffline")));
    fetchGauges().then(setGauges).catch(() => setApiStatus(t("header.apiOffline")));
    fetchAlerts().then((data) => setAlerts(data.alerts)).catch(() => {});
  }, []);

  const { rain24 } = deriveStats(zones, gauges);
  const zoneProps = zones?.features.map((f) => f.properties) ?? [];

  const selectDistrict = (zoneId: string) => {
    setSelected(zoneId);
    setSpotlightZone(zoneId);
  };

  const viewZone = (zoneId: string | null) => {
    if (zoneId) selectDistrict(zoneId);
    scrollToSection("live-map");
  };

  return (
    <div className="app">
      <Header alertCount={alerts.length} apiStatus={apiStatus} />

      <main>
        <Hero zones={zones} gauges={gauges} alerts={alerts} />
        <StatCards zones={zones} gauges={gauges} alerts={alerts} />
        <RiversNow gauges={gauges} />

        {spotlightZone && (
          <section className="section" id="risk-score">
            <FloodRiskSpotlight
              zones={zoneProps}
              zoneId={spotlightZone}
              onZoneChange={setSpotlightZone}
            />
          </section>
        )}

        <section className="section" id="live-map">
          <div className="section-head">
            <div>
              <h2 className="section-title">{t("app.liveMapTitle")}</h2>
              <p className="section-sub">{t("app.liveMapSub")}</p>
            </div>
            <button className="section-action" onClick={() => scrollToSection("alerts")}>
              {t("app.viewAllAlerts")}
            </button>
          </div>
          <div className="map-alerts">
            <section className="card map-card">
              <div className="card-head">
                <span className="head-icon">
                  <IconMap size={18} />
                </span>
                <div>
                  <div className="head-title">{t("app.mapTitle")}</div>
                  <div className="head-sub">{t("app.mapSub")}</div>
                </div>
                <span className="live-chip small">{t("common.live")}</span>
              </div>
              <MapView zones={zones} onSelect={selectDistrict}>
                {selected && <RiskPanel zoneId={selected} onClose={() => setSelected(null)} />}
              </MapView>
            </section>

            <WarningCenter onViewZone={viewZone} />
          </div>
        </section>

        <CriticalDivisions />

        <section className="section" id="insights" style={{ paddingTop: 0 }}>
          <div className="section-head">
            <div>
              <h2 className="section-title">{t("app.insightsTitle")}</h2>
              <p className="section-sub">{t("app.insightsSub")}</p>
            </div>
          </div>
          <section className="card">
            <InsightPanel zones={zoneProps} />
          </section>
        </section>

        <section className="section" id="gauges">
          <div className="section-head">
            <div>
              <h2 className="section-title">{t("app.gaugesTitle")}</h2>
              <p className="section-sub">{t("app.gaugesSub")}</p>
            </div>
          </div>
          <section className="card">
            <div className="card-head">
              <span className="head-icon">
                <IconWaves size={18} />
              </span>
              <div>
                <div className="head-title">{t("app.sindhGauges")}</div>
                <div className="head-sub">{t("app.sindhGaugesSub")}</div>
              </div>
            </div>
            <GaugeBoard gauges={gauges?.gauges ?? []} />
          </section>
        </section>

        <div className="section" style={{ paddingTop: 0 }}>
          <BulletinCard />
        </div>

        <section className="section" id="reports" style={{ paddingTop: 0 }}>
          <div className="grid-2">
            <section className="card">
              <div className="card-head">
                <span className="head-icon">
                  <IconEdit size={18} />
                </span>
                <div>
                  <div className="head-title">{t("app.reportsTitle")}</div>
                  <div className="head-sub">{t("app.reportsSub")}</div>
                </div>
              </div>
              <div className="card-body">
                <ReportForm
                  zones={zoneProps}
                  onSubmitted={() => setRefreshKey((k) => k + 1)}
                />
              </div>
            </section>

            <section className="card">
              <div className="card-head">
                <span className="head-icon">
                  <IconInbox size={18} />
                </span>
                <div>
                  <div className="head-title">{t("app.feedTitle")}</div>
                  <div className="head-sub">{t("app.feedSub")}</div>
                </div>
              </div>
              <div className="card-body">
                <ReportsFeed refreshKey={refreshKey} />
              </div>
            </section>
          </div>
        </section>

        <section className="section" id="forecast" style={{ paddingTop: 0 }}>
          <div className="section-head">
            <div>
              <h2 className="section-title">{t("app.forecastTitle")}</h2>
              <p className="section-sub">{t("app.forecastSub")}</p>
            </div>
          </div>
          {spotlightZone && (
            <section className="card forecast-risk-card">
              <div className="card-head">
                <span className="head-icon">
                  <IconShield size={18} />
                </span>
                <div>
                  <div className="head-title">{t("riskScore.sectionTitle")}</div>
                  <div className="head-sub">{t("riskScore.forecastSub")}</div>
                </div>
              </div>
              <div className="card-body">
                <FloodRiskScore zoneId={spotlightZone} compact />
              </div>
            </section>
          )}
          <Analytics rain24={rain24} />
        </section>

        <section className="section" id="safety" style={{ paddingTop: 0 }}>
          <div className="section-head">
            <div>
              <h2 className="section-title">{t("app.safetyTitle")}</h2>
              <p className="section-sub">{t("app.safetySub")}</p>
            </div>
          </div>
          <div className="safety-grid">
            <QuickActions
              onContacts={() => setModal("contacts")}
              onReport={() => scrollToSection("reports")}
            />
            <SafeLocations />
          </div>
        </section>

        <section className="section" id="responder" style={{ paddingTop: 0 }}>
          <div className="section-head">
            <div>
              <h2 className="section-title">{t("app.responderTitle")}</h2>
              <p className="section-sub">{t("app.responderSub")}</p>
            </div>
          </div>
          <section className="card">
            <div className="card-body">
              <ResponderDashboard zones={zones} />
            </div>
          </section>
        </section>

        <EmergencyCta />
      </main>

      <Footer onOpenModal={(kind) => setModal(kind)} />

      {modal === "contacts" && (
        <Modal title={t("app.contactsTitle")} onClose={() => setModal(null)}>
          <ul>
            {CONTACTS.map((c) => (
              <li key={c.number}>
                <strong>
                  <IconPhone size={14} /> {t(c.nameKey)}
                </strong>
                <a href={`tel:${c.number}`}>{c.number}</a>
              </li>
            ))}
          </ul>
        </Modal>
      )}
      {modal === "privacy" && (
        <Modal title={t("app.privacyTitle")} onClose={() => setModal(null)}>
          <p>{t("app.privacyText")}</p>
        </Modal>
      )}
      {modal === "terms" && (
        <Modal title={t("app.termsTitle")} onClose={() => setModal(null)}>
          <p>{t("app.termsText")}</p>
        </Modal>
      )}

      <Assistant zones={zones} />
    </div>
  );
}
