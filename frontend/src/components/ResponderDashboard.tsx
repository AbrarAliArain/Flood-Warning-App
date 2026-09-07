import { useCallback, useEffect, useRef, useState } from "react";
import L from "leaflet";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import type { ZonesResponse } from "../api/client";
import {
  listCases,
  transitionCase,
  relativeTime,
  type EmergencyCase,
} from "../api/casesClient";

const CATEGORY_COLORS: Record<string, string> = {
  critical: "#DC2626",
  high: "#F97316",
  moderate: "#EAB308",
  low: "#16A34A",
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: "#DC2626",
  high: "#F97316",
  moderate: "#EAB308",
  medium: "#EAB308",
  low: "#16A34A",
};

const TRANSITIONS: Record<string, { next: string; labelKey: string }[]> = {
  pending: [{ next: "assigned", labelKey: "responder.acknowledge" }],
  assigned: [{ next: "in_progress", labelKey: "responder.dispatch" }],
  in_progress: [{ next: "resolved", labelKey: "responder.resolve" }],
};

interface Props {
  zones: ZonesResponse | null;
}

export default function ResponderDashboard({ zones }: Props) {
  const { user, loginDemoResponder, logout } = useAuth();
  const { t } = useI18n();
  const [cases, setCases] = useState<EmergencyCase[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<Record<number, L.Marker>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listCases();
      setCases(data.cases);
    } catch (e) {
      if (String(e).includes("API error 401")) {
        logout();
        return;
      }
      setError(t("responder.loadFailed", { error: String(e) }));
    } finally {
      setLoading(false);
    }
  }, [logout, t]);

  useEffect(() => {
    if (user && (user.role === "responder" || user.role === "admin")) {
      load();
    }
  }, [user, load]);

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;
    const map = L.map(mapContainerRef.current, { center: [26.0, 68.6], zoom: 7 });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
      markersRef.current = {};
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    Object.values(markersRef.current).forEach((m) => m.remove());
    markersRef.current = {};
    for (const c of cases) {
      if (c.latitude == null || c.longitude == null) continue;
      const lat = c.latitude;
      const lng = c.longitude;
      const color = SEVERITY_COLORS[c.severity] ?? "#94A3B8";
      const marker = L.circleMarker([lat, lng], {
        radius: 8,
        color: "#fff",
        weight: 2,
        fillColor: color,
        fillOpacity: 0.8,
      }).addTo(map);
      marker.bindTooltip(`${c.code} — ${c.emergency_type}`);
      marker.on("click", () => {
        setSelectedId(c.id);
        map.flyTo([lat, lng], 10);
      });
      markersRef.current[c.id] = marker as unknown as L.Marker;
    }
  }, [cases]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !zones) return;
    const layer = L.geoJSON(zones, {
      style: (feature) => ({
        color: "#ffffff",
        weight: 1,
        fillColor: CATEGORY_COLORS[feature?.properties.category] ?? "#94A3B8",
        fillOpacity: 0.2,
      }),
    }).addTo(map);
    return () => { layer.remove(); };
  }, [zones]);

  const handleTransition = async (caseId: number, nextStatus: string) => {
    try {
      await transitionCase(caseId, nextStatus);
      await load();
    } catch (e) {
      setError(t("responder.transitionFailed", { error: String(e) }));
    }
  };

  const contactCitizen = (c: EmergencyCase) => {
    if (!c.contact_phone) return;
    const phone = c.contact_phone.replace(/[^0-9]/g, "");
    const mapsLink =
      c.latitude != null && c.longitude != null
        ? `https://www.google.com/maps/search/?api=1&query=${c.latitude},${c.longitude}`
        : "";
    const text = encodeURIComponent(
      `Emergency Case ${c.code}\nType: ${c.emergency_type}\n${mapsLink ? `Location: ${mapsLink}` : ""}`,
    );
    window.open(`https://wa.me/${phone}?text=${text}`, "_blank");
  };

  if (!user || (user.role !== "responder" && user.role !== "admin")) {
    return (
      <div className="responder-gate">
        <p>{t("responder.accessRequired")}</p>
        <button className="auth-login-btn responder" onClick={loginDemoResponder}>
          {t("responder.loginDemo")}
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="responder-header">
        <h3>{t("responder.dashTitle")}</h3>
        {user.ngo_name && <span className="responder-ngo">{user.ngo_name}</span>}
        {user.is_demo && <span className="demo-tag">{t("common.demo")}</span>}
        <button className="case-action-btn" onClick={load} disabled={loading}>
          {loading ? t("responder.loading") : t("responder.refresh")}
        </button>
      </div>

      {error && <p className="form-status" style={{ color: "var(--red)" }}>{error}</p>}

      <div className="responder-body">
        <div className="cases-table-wrap">
          {cases.length === 0 ? (
            <div className="no-cases">
              {loading ? t("responder.loadingCases") : t("responder.noCases")}
            </div>
          ) : (
            <table className="responder-table">
              <thead>
                <tr>
                  <th>{t("responder.colCode")}</th>
                  <th>{t("responder.colLocation")}</th>
                  <th>{t("responder.colType")}</th>
                  <th>{t("responder.colSeverity")}</th>
                  <th>{t("responder.colPriority")}</th>
                  <th>{t("responder.colStatus")}</th>
                  <th>{t("responder.colWhatsApp")}</th>
                  <th>{t("responder.colReported")}</th>
                  <th>{t("responder.colActions")}</th>
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => (
                  <tr
                    key={c.id}
                    className={selectedId === c.id ? "case-row-selected" : ""}
                    onClick={() => setSelectedId(c.id)}
                  >
                    <td><strong>{c.code}</strong></td>
                    <td>{c.location_text ?? c.zone_id}</td>
                    <td>{c.emergency_type.replace("_", " ")}</td>
                    <td>
                      <span
                        className="priority-chip"
                        style={{
                          background: `${SEVERITY_COLORS[c.severity]}20`,
                          color: SEVERITY_COLORS[c.severity],
                        }}
                      >
                        {c.severity}
                      </span>
                    </td>
                    <td>
                      <span className={`priority-chip ${c.priority_label.toLowerCase()}`}>
                        {c.priority_label}
                      </span>
                    </td>
                    <td>
                      <span className={`status-chip ${c.status}`}>{c.status.replace("_", " ")}</span>
                    </td>
                    <td>
                      {c.communication_status && (
                        <span className={`wa-status ${c.communication_status}`}>
                          {c.communication_status}
                        </span>
                      )}
                    </td>
                    <td>{relativeTime(c.created_at)}</td>
                    <td>
                      <div className="case-actions">
                        <button
                          className="case-action-btn wa"
                          onClick={(e) => { e.stopPropagation(); contactCitizen(c); }}
                          disabled={!c.contact_phone}
                          title={c.contact_phone ? t("responder.openWhatsApp") : t("responder.noPhone")}
                        >
                          {t("responder.contact")}
                        </button>
                        {(TRANSITIONS[c.status] ?? []).map((tr) => (
                          <button
                            key={tr.next}
                            className="case-action-btn"
                            onClick={(e) => { e.stopPropagation(); handleTransition(c.id, tr.next); }}
                          >
                            {t(tr.labelKey)}
                          </button>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div ref={mapContainerRef} className="case-map" />
      </div>
    </div>
  );
}
