import { useState, type FormEvent } from "react";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import {
  createCaseFromReport,
  submitReport,
  type CreatedCase,
  type CommunityReport,
  type ZoneProperties,
} from "../api/client";
import VoiceInput from "./VoiceInput";

const WATER_LEVELS = ["low", "rising", "high", "severe"] as const;
const SEVERITIES = ["low", "moderate", "high", "critical"] as const;
const EMERGENCY_TYPES = [
  "flood",
  "waterlogging",
  "river_overflow",
  "rescue",
  "medical",
  "evacuation",
  "infrastructure",
  "other",
] as const;

const WATER_KEYS: Record<string, string> = {
  low: "reportForm.waterLow",
  rising: "reportForm.waterRising",
  high: "reportForm.waterHigh",
  severe: "reportForm.waterSevere",
};

const SEV_KEYS: Record<string, string> = {
  low: "reportForm.sevLow",
  moderate: "reportForm.sevMedium",
  high: "reportForm.sevHigh",
  critical: "reportForm.sevCritical",
};

const SEV_ICONS: Record<string, string> = {
  low: "\u{1F7E2}",
  moderate: "\u{1F7E1}",
  high: "\u{1F7E0}",
  critical: "\u{1F534}",
};

const TYPE_KEYS: Record<string, string> = {
  flood: "reportForm.typeFlood",
  waterlogging: "reportForm.typeWaterlogging",
  river_overflow: "reportForm.typeRiverOverflow",
  rescue: "reportForm.typeRescue",
  medical: "reportForm.typeMedical",
  evacuation: "reportForm.typeEvacuation",
  infrastructure: "reportForm.typeInfrastructure",
  other: "reportForm.typeOther",
};

type Step = 1 | 2 | 3 | 4 | 5;

interface Props {
  zones: ZoneProperties[];
  onSubmitted: () => void;
}

export default function ReportForm({ zones, onSubmitted }: Props) {
  const { user, loginDemoCitizen, loginDemoResponder } = useAuth();
  const { t } = useI18n();

  const [zoneId, setZoneId] = useState("hyderabad");
  const [waterLevel, setWaterLevel] = useState<(typeof WATER_LEVELS)[number]>("rising");
  const [severity, setSeverity] = useState<(typeof SEVERITIES)[number]>("moderate");
  const [emergencyType, setEmergencyType] = useState<(typeof EMERGENCY_TYPES)[number]>("flood");
  const [description, setDescription] = useState("");
  const [evidence, setEvidence] = useState<File | undefined>();
  const [gps, setGps] = useState<{ lat: number; lng: number } | null>(null);
  const [gpsStatus, setGpsStatus] = useState("");
  const [requestRescue, setRequestRescue] = useState(false);
  const [status, setStatus] = useState("");
  const [createdCase, setCreatedCase] = useState<CreatedCase | null>(null);
  const [submittedReport, setSubmittedReport] = useState<CommunityReport | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [step, setStep] = useState<Step>(1);
  const [showWaPreview, setShowWaPreview] = useState(false);

  const sortedZones = [...zones].sort((a, b) => a.name.localeCompare(b.name));
  const selectedZone = sortedZones.find((z) => z.zone_id === zoneId);

  const detectLocation = () => {
    if (!navigator.geolocation) {
      setGpsStatus(t("reportForm.geoNotSupported"));
      return;
    }
    setGpsStatus(t("reportForm.detecting"));
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGps({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setGpsStatus("");
      },
      () => setGpsStatus(t("reportForm.locationUnavailable")),
    );
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!description.trim()) {
      setStatus(t("reportForm.pleaseDescribe"));
      return;
    }
    if (gps && (gps.lat < 23.5 || gps.lat > 28.0 || gps.lng < 60.5 || gps.lng > 71.0)) {
      setStatus("The detected GPS location is outside Sindh. Turn off location detection or choose a district.");
      return;
    }
    setSubmitting(true);
    setStatus("");
    setCreatedCase(null);
    setSubmittedReport(null);
    setShowWaPreview(false);
    try {
      const report = await submitReport({
        zone_id: zoneId,
        water_level: waterLevel,
        description: description.trim(),
        evidence,
        latitude: gps?.lat,
        longitude: gps?.lng,
        severity,
        emergency_type: emergencyType,
      });
      setSubmittedReport(report);
      setDescription("");
      setEvidence(undefined);
      onSubmitted();

      if (requestRescue) {
        try {
          const ec = await createCaseFromReport(report.id);
          setCreatedCase(ec);
          setShowWaPreview(true);
        } catch (caseErr) {
          setStatus(t("reportForm.rescueFailed", { error: String(caseErr) }));
        }
      }
    } catch (err) {
      setStatus(t("reportForm.submissionFailed", { error: String(err) }));
    } finally {
      setSubmitting(false);
    }
  };

  const openWhatsApp = (c: CreatedCase) => {
    const matchedNgo = c.matches[0];
    const phone = matchedNgo?.whatsapp_number || matchedNgo?.contact_phone || "";
    const cleanPhone = phone.replace(/[^0-9]/g, "");
    const mapsLink =
      c.latitude != null && c.longitude != null
        ? `https://www.google.com/maps/search/?api=1&query=${c.latitude},${c.longitude}`
        : "";
    const lines = [
      `\u{1F6A8} *${t("reportForm.waAlertEmergency")}*`,
      ``,
      `*${t("reportForm.waAlertLocation")}*: ${selectedZone?.name ?? c.zone_id}`,
      `*${t("reportForm.waAlertIncident")}*: ${t(TYPE_KEYS[c.emergency_type] ?? c.emergency_type)}`,
      `*${t("reportForm.waAlertSeverity")}*: ${c.severity.toUpperCase()}`,
      ``,
      `*${t("reportForm.waAlertCitizenReport")}*:`,
      `"${c.description ?? submittedReport?.description ?? ""}"`,
      ``,
      mapsLink ? `\u{1F4CD} ${t("reportForm.waAlertViewLocation")}: ${mapsLink}` : "",
      `*${t("reportForm.waAlertCaseId")}*: ${c.code}`,
    ].filter(Boolean);
    const text = encodeURIComponent(lines.join("\n"));
    if (cleanPhone) {
      window.open(`https://wa.me/${cleanPhone}?text=${text}`, "_blank");
    } else {
      window.open(`https://wa.me/?text=${text}`, "_blank");
    }
  };

  const resetForm = () => {
    setStep(1);
    setCreatedCase(null);
    setSubmittedReport(null);
    setShowWaPreview(false);
    setStatus("");
    setRequestRescue(false);
  };

  if (!user) {
    return (
      <div className="responder-gate">
        <p>{t("reportForm.loginPrompt")}</p>
        <div className="auth-login-group" style={{ justifyContent: "center" }}>
          <button className="auth-login-btn citizen" onClick={loginDemoCitizen}>
            {t("reportForm.citizenLogin")}
          </button>
          <button className="auth-login-btn responder" onClick={loginDemoResponder}>
            {t("reportForm.responderLogin")}
          </button>
        </div>
      </div>
    );
  }

  /* ── Post-submission confirmation ── */
  if (submittedReport) {
    const isHighPriority = severity === "high" || severity === "critical";
    return (
      <div className="report-confirmation">
        <div className="confirmation-icon">{"\u2705"}</div>
        <h3 className="confirmation-title">{t("reportForm.reportReceived")}</h3>
        <p className="confirmation-text">{t("reportForm.reportReceivedText")}</p>

        {isHighPriority && (
          <div className="high-priority-banner">
            {"\u{1F6A8}"} <strong>{t("reportForm.highPriority")}</strong>
          </div>
        )}

        <div className="confirmation-details">
          <div className="confirmation-row">
            <span>{t("reportForm.reportId")}</span>
            <strong>#{submittedReport.report_id}</strong>
          </div>
          <div className="confirmation-row">
            <span>{t("reportForm.statusLabel")}</span>
            <strong>{t("reportForm.statusPending")}</strong>
          </div>
          <div className="confirmation-row">
            <span>{t("reportForm.summaryLocation")}</span>
            <strong>{selectedZone?.name ?? zoneId}</strong>
          </div>
          <div className="confirmation-row">
            <span>{t("reportForm.timeSubmitted")}</span>
            <strong>{new Date(submittedReport.created_at).toLocaleString()}</strong>
          </div>
        </div>

        {createdCase && showWaPreview && (
          <div className="wa-preview-card">
            <h4>{"\u{1F4F1}"} {t("reportForm.waAlertTitle")}</h4>
            <div className="wa-preview-message">
              <div className="wa-preview-emergency">{"\u{1F6A8}"} {t("reportForm.waAlertEmergency")}</div>
              <div className="wa-preview-row">
                <span>{"\u{1F4CD}"} {t("reportForm.waAlertLocation")}:</span>
                <strong>{selectedZone?.name ?? createdCase.zone_id}</strong>
              </div>
              <div className="wa-preview-row">
                <span>{"\u{1F6A8}"} {t("reportForm.waAlertIncident")}:</span>
                <strong>{t(TYPE_KEYS[createdCase.emergency_type] ?? createdCase.emergency_type)}</strong>
              </div>
              <div className="wa-preview-row">
                <span>{"\u{1F534}"} {t("reportForm.waAlertSeverity")}:</span>
                <strong>{createdCase.severity.toUpperCase()}</strong>
              </div>
              {createdCase.description && (
                <div className="wa-preview-report">
                  <span>{t("reportForm.waAlertCitizenReport")}:</span>
                  <p>"{createdCase.description}"</p>
                </div>
              )}
              {createdCase.latitude != null && createdCase.longitude != null && (
                <div className="wa-preview-row">
                  <span>{"\u{1F4CD}"} {t("reportForm.waAlertViewLocation")}</span>
                </div>
              )}
              <div className="wa-preview-row">
                <span>{t("reportForm.waAlertCaseId")}:</span>
                <strong>{createdCase.code}</strong>
              </div>
            </div>
            <button className="cta wa-send-btn" onClick={() => openWhatsApp(createdCase)}>
              {"\u{1F4E4}"} {t("reportForm.waSendBtn")}
            </button>
            <div className="wa-preview-status">
              {"\u2705"}{" "}
              {createdCase.dispatch?.mode === "demo"
                ? t("reportForm.waPrepared")
                : t("reportForm.waDemoComm")}
            </div>
            {createdCase.matches[0] && (
              <div className="wa-preview-responder">
                <span>{t("reportForm.waResponder")}:</span>
                <strong>{createdCase.matches[0].ngo_name}</strong>
                <span className="wa-preview-time">
                  {t("reportForm.waTime")}: {new Date(createdCase.created_at).toLocaleTimeString()}
                </span>
                <span className="wa-preview-awaiting">{t("reportForm.waAwaitingResponse")}</span>
              </div>
            )}
          </div>
        )}

        {createdCase && !showWaPreview && (
          <div className="case-result">
            <h4>{t("reportForm.caseCreated")}</h4>
            <div className="case-result-code">{createdCase.code}</div>
            <div className="case-result-meta">
              <strong>{t("reportForm.ngoMatched")}</strong>{" "}
              {createdCase.matches[0]?.ngo_name ?? t("reportForm.pendingAssignment")}
              <br />
              <strong>{t("reportForm.priority")}</strong> {createdCase.priority_label}
              <br />
              <strong>{t("reportForm.statusLabel")}</strong> {createdCase.status}
            </div>
            {createdCase.dispatch && (
              <span className={`wa-status ${createdCase.dispatch.mode}`}>
                WhatsApp: {createdCase.dispatch.mode === "demo" ? t("reportForm.waDemo") : t("reportForm.waSent")}
              </span>
            )}
          </div>
        )}

        <button className="cta" onClick={resetForm} style={{ marginTop: 16 }}>
          {t("reportForm.submitReport")} Another
        </button>
      </div>
    );
  }

  /* ── Step wizard ── */
  const stepLabels = [
    t("reportForm.stepLocation"),
    t("reportForm.stepIncident"),
    t("reportForm.stepSeverity"),
    t("reportForm.stepDetails"),
    t("reportForm.stepSummary"),
  ];

  return (
    <form className="report-form" onSubmit={handleSubmit}>
      {/* Step indicator */}
      <div className="step-indicator">
        {stepLabels.map((label, i) => (
          <div key={i} className={`step-dot${step === i + 1 ? " active" : ""}${step > i + 1 ? " done" : ""}`}>
            <span className="step-num">{step > i + 1 ? "\u2713" : i + 1}</span>
            <span className="step-label">{label}</span>
          </div>
        ))}
      </div>

      {/* STEP 1 — Location */}
      {step === 1 && (
        <div className="step-content">
          <label>
            {t("reportForm.location")}
            <div className="gps-row">
              <select value={zoneId} onChange={(e) => setZoneId(e.target.value)} style={{ flex: 1 }}>
                {sortedZones.map((z) => (
                  <option key={z.zone_id} value={z.zone_id}>
                    {z.name}
                  </option>
                ))}
              </select>
              <button type="button" className="gps-btn" onClick={detectLocation}>
                {"\u{1F4CD}"} {t("reportForm.detectMyLocation")}
              </button>
            </div>
            {gps && (
              <span className="gps-coords">
                {gps.lat.toFixed(5)}, {gps.lng.toFixed(5)}
              </span>
            )}
            {gpsStatus && <span className="gps-status">{gpsStatus}</span>}
          </label>
          {gps && (
            <div className="location-detected-banner">
              {"\u{1F4CD}"} <strong>{t("reportForm.locationDetected")}</strong>
              <p>{t("reportForm.adjustLocation")}</p>
            </div>
          )}
          <div className="step-nav">
            <button type="button" className="cta" onClick={() => setStep(2)}>
              {t("reportForm.nextStep")}
            </button>
          </div>
        </div>
      )}

      {/* STEP 2 — Incident Type */}
      {step === 2 && (
        <div className="step-content">
          <label>{t("reportForm.emergencyType")}</label>
          <div className="type-grid">
            {EMERGENCY_TYPES.map((et) => (
              <button
                key={et}
                type="button"
                className={`type-card${emergencyType === et ? " selected" : ""}`}
                onClick={() => setEmergencyType(et)}
              >
                <span className="type-card-label">{t(TYPE_KEYS[et])}</span>
              </button>
            ))}
          </div>
          <div className="step-nav">
            <button type="button" className="btn-back" onClick={() => setStep(1)}>
              {t("reportForm.prevStep")}
            </button>
            <button type="button" className="cta" onClick={() => setStep(3)}>
              {t("reportForm.nextStep")}
            </button>
          </div>
        </div>
      )}

      {/* STEP 3 — Severity */}
      {step === 3 && (
        <div className="step-content">
          <label>{t("reportForm.severity")}</label>
          <div className="severity-grid">
            {SEVERITIES.map((s) => (
              <button
                key={s}
                type="button"
                className={`sev-card sev-${s}${severity === s ? " selected" : ""}`}
                onClick={() => setSeverity(s)}
              >
                <span className="sev-icon">{SEV_ICONS[s]}</span>
                <span className="sev-label">{t(SEV_KEYS[s])}</span>
              </button>
            ))}
          </div>
          <label style={{ marginTop: 16 }}>
            {t("reportForm.waterLevel")}
            <select
              value={waterLevel}
              onChange={(e) => setWaterLevel(e.target.value as (typeof WATER_LEVELS)[number])}
            >
              {WATER_LEVELS.map((w) => (
                <option key={w} value={w}>
                  {t(WATER_KEYS[w])}
                </option>
              ))}
            </select>
          </label>
          <div className="step-nav">
            <button type="button" className="btn-back" onClick={() => setStep(2)}>
              {t("reportForm.prevStep")}
            </button>
            <button type="button" className="cta" onClick={() => setStep(4)}>
              {t("reportForm.nextStep")}
            </button>
          </div>
        </div>
      )}

      {/* STEP 4 — Details */}
      {step === 4 && (
        <div className="step-content">
          <label>
            {t("reportForm.describeSituation")}
            <textarea
              id="report-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t("reportForm.describePlaceholder")}
              rows={3}
            />
            <VoiceInput value={description} onChange={setDescription} fieldId="report-description" />
          </label>

          <label>
            {t("reportForm.uploadEvidence")}
            <input
              type="file"
              accept=".png,.jpg,.jpeg,.webp"
              onChange={(e) => setEvidence(e.target.files?.[0])}
            />
          </label>

          <label className="rescue-toggle">
            <input
              type="checkbox"
              checked={requestRescue}
              onChange={(e) => setRequestRescue(e.target.checked)}
            />
            {t("reportForm.requestRescue")}
          </label>

          {requestRescue && (
            <div className="rescue-confirm">
              {t("reportForm.rescueConfirm")}
            </div>
          )}

          <div className="step-nav">
            <button type="button" className="btn-back" onClick={() => setStep(3)}>
              {t("reportForm.prevStep")}
            </button>
            <button
              type="button"
              className="cta"
              onClick={() => {
                if (!description.trim()) {
                  setStatus(t("reportForm.pleaseDescribe"));
                  return;
                }
                setStatus("");
                setStep(5);
              }}
            >
              {t("reportForm.nextStep")}
            </button>
          </div>
          {status && <span className="form-status">{status}</span>}
        </div>
      )}

      {/* STEP 5 — Summary */}
      {step === 5 && (
        <div className="step-content">
          <h3 className="summary-title">{t("reportForm.summaryTitle")}</h3>
          <div className="summary-list">
            <div className="summary-item">
              <span>{"\u{1F4CD}"}</span>
              <div>
                <strong>{t("reportForm.summaryLocation")}</strong>
                <p>{selectedZone?.name ?? zoneId}{gps ? ` (${gps.lat.toFixed(4)}, ${gps.lng.toFixed(4)})` : ""}</p>
              </div>
              <span className="summary-check">{"\u2713"}</span>
            </div>
            <div className="summary-item">
              <span>{"\u{1F6A8}"}</span>
              <div>
                <strong>{t("reportForm.summaryIncident")}</strong>
                <p>{t(TYPE_KEYS[emergencyType])}</p>
              </div>
              <span className="summary-check">{"\u2713"}</span>
            </div>
            <div className="summary-item">
              <span>{SEV_ICONS[severity]}</span>
              <div>
                <strong>{t("reportForm.summarySeverity")}</strong>
                <p>{t(SEV_KEYS[severity])}</p>
              </div>
              <span className="summary-check">{"\u2713"}</span>
            </div>
            <div className="summary-item">
              <span>{"\u{1F4DD}"}</span>
              <div>
                <strong>{t("reportForm.summaryDescription")}</strong>
                <p>{description.length > 100 ? `${description.slice(0, 100)}...` : description}</p>
              </div>
              <span className="summary-check">{"\u2713"}</span>
            </div>
            <div className="summary-item">
              <span>{"\u{1F4F7}"}</span>
              <div>
                <strong>{t("reportForm.summaryPhoto")}</strong>
                <p>{evidence ? t("reportForm.summaryPhotoYes") : t("reportForm.summaryPhotoNo")}</p>
              </div>
              <span className="summary-check">{evidence ? "\u2713" : "\u2014"}</span>
            </div>
          </div>

          <div className="step-nav">
            <button type="button" className="btn-back" onClick={() => setStep(4)}>
              {t("reportForm.prevStep")}
            </button>
            <button type="submit" className={`cta${severity === "critical" ? " danger" : ""}`} disabled={submitting}>
              {submitting ? t("reportForm.submitting") : t("reportForm.submitReportBtn")}
            </button>
          </div>
          {status && <span className="form-status">{status}</span>}
        </div>
      )}
    </form>
  );
}
