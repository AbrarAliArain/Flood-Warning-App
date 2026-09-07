import { authHeaders } from "../auth";

export interface EmergencyCase {
  id: number;
  code: string;
  user_id: number;
  report_id: number;
  zone_id: string;
  latitude: number | null;
  longitude: number | null;
  emergency_type: string;
  severity: string;
  description: string;
  contact_phone: string | null;
  risk_score: number | null;
  risk_category: string | null;
  priority: number;
  priority_label: string;
  status: string;
  ngo_id: number | null;
  communication_status: string | null;
  is_demo: boolean;
  created_at: string;
  assigned_at: string | null;
  responded_at: string | null;
  resolved_at: string | null;
  evidence_url: string | null;
  location_text: string | null;
}

export interface CaseEvent {
  id: number;
  case_id: number;
  event_type: string;
  detail: string | null;
  created_at: string;
}

export interface CommunicationLog {
  id: number;
  case_id: number;
  direction: string;
  channel: string;
  recipient: string | null;
  message: string;
  status: string;
  created_at: string;
}

export interface NGO {
  id: number;
  name: string;
  service_area: string;
  contact_phone: string | null;
  whatsapp_number: string | null;
  capabilities: string[];
  is_demo: boolean;
}

/** Responder identity for citizen-facing views — never carries a raw number. */
export interface PreviewResponder {
  ngo_id: number;
  name: string;
  organisation_type: string;
  service_area: string | null;
  capabilities: string[];
  available: boolean;
  active_cases: number;
  max_concurrent_cases: number;
  is_demo: boolean;
  contact_masked: string | null;
  contact_available: boolean;
}

export interface WhatsAppPreview {
  case_id: number;
  case_code: string;
  mode: string;
  is_live: boolean;
  message: string;
  responder: PreviewResponder | null;
  wa_link: string | null;
  communication_status: string | null;
  priority_label: string;
  status: string;
  assigned_at: string | null;
  created_at: string;
  is_demo: boolean;
}

const BASE = "/api";

async function authed(url: string, init?: RequestInit) {
  const res = await fetch(url, {
    ...init,
    headers: { ...authHeaders(), ...(init?.headers ?? {}) },
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function listCases(): Promise<{ cases: EmergencyCase[] }> {
  return authed(`${BASE}/cases`);
}

export async function getCase(id: number): Promise<EmergencyCase> {
  return authed(`${BASE}/cases/${id}`);
}

export async function getCaseEvents(id: number): Promise<{ events: CaseEvent[] }> {
  return authed(`${BASE}/cases/${id}/events`);
}

export async function getCaseComms(id: number): Promise<{ communications: CommunicationLog[] }> {
  return authed(`${BASE}/cases/${id}/communications`);
}

export async function getWhatsAppPreview(id: number): Promise<WhatsAppPreview> {
  return authed(`${BASE}/cases/${id}/whatsapp-preview`);
}

export async function transitionCase(
  id: number,
  status: string,
  note?: string,
): Promise<EmergencyCase> {
  return authed(`${BASE}/cases/${id}/transition`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, note }),
  });
}

export async function listNGOs(): Promise<{ ngos: NGO[] }> {
  return authed(`${BASE}/ngos`);
}

export function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}
