import { useState } from "react";
import {
  fetchAlerts,
  fetchGauges,
  fetchInsights,
  type ZonesResponse,
} from "../api/client";
import { useI18n } from "../i18n";
import VoiceInput from "./VoiceInput";

interface Message {
  from: "user" | "assistant";
  text: string;
}

const QUICK_QUESTION_KEYS = [
  "assistant.qCritical",
  "assistant.qAlerts",
  "assistant.qGauges",
  "assistant.qBadin",
] as const;

type TFunc = (key: string, vars?: Record<string, string | number>) => string;

async function answer(question: string, zones: ZonesResponse, t: TFunc): Promise<string> {
  const lower = question.toLowerCase();

  if (/critical|worst|highest/.test(lower)) {
    const critical = zones.features
      .map((f) => f.properties)
      .filter((p) => p.category === "critical")
      .sort((a, b) => b.score - a.score);
    return t("assistant.criticalAnswer", {
      list: critical.map((p) => `${p.name} ${p.score}/100`).join(", "),
    });
  }

  if (/alert|warning/.test(lower)) {
    const { alerts } = await fetchAlerts();
    if (!alerts.length) return t("assistant.noAlerts");
    return t("assistant.alertsAnswer", {
      count: alerts.length,
      list: alerts.slice(0, 3).map((a) => a.message).join(" "),
    });
  }

  if (/gauge|river|indus|flow/.test(lower)) {
    const { gauges } = await fetchGauges();
    return gauges
      .map((g) =>
        t("assistant.gaugeAnswer", {
          name: g.name,
          flow: g.flow_lacs_cusecs,
          floodClass: g.flood_class.toUpperCase(),
        })
      )
      .join(" · ");
  }

  const zone = zones.features.find((f) =>
    lower.includes(f.properties.name.toLowerCase())
  );
  if (zone) {
    const insight = await fetchInsights(zone.properties.zone_id);
    const actions = insight.recommendations
      .slice(0, 2)
      .map((r) => r.action)
      .join(" ");
    return `${insight.explanation} ${t("assistant.priorityActions", { actions })}`;
  }

  return t("assistant.fallback", {
    questions: QUICK_QUESTION_KEYS.map((k) => t(k)).join(" / "),
  });
}

interface Props {
  zones: ZonesResponse | null;
}

export default function Assistant({ zones }: Props) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { from: "assistant", text: t("assistant.greeting") },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  const ask = async (question: string) => {
    if (!question.trim() || busy || !zones) return;
    setBusy(true);
    setMessages((m) => [...m, { from: "user", text: question }]);
    setInput("");
    try {
      const text = await answer(question, zones, t);
      setMessages((m) => [...m, { from: "assistant", text }]);
    } catch (err) {
      setMessages((m) => [...m, { from: "assistant", text: t("assistant.fetchError", { error: String(err) }) }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {open && (
        <div className="assistant-panel">
          <div className="assistant-head">
            <span className="dot green" />
            {t("assistant.title")} <span className="beta">{t("common.beta")}</span>
            <button className="close-btn" onClick={() => setOpen(false)} aria-label={t("assistant.closeAssistant")}>
              ×
            </button>
          </div>
          <div className="assistant-body">
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.from}`}>
                {m.text}
              </div>
            ))}
            {busy && <div className="msg assistant">{t("assistant.thinking")}</div>}
          </div>
          <div className="assistant-quick">
            {QUICK_QUESTION_KEYS.map((key) => (
              <button key={key} onClick={() => ask(t(key))}>
                {t(key)}
              </button>
            ))}
          </div>
          <form
            className="assistant-input"
            onSubmit={(e) => {
              e.preventDefault();
              ask(input);
            }}
          >
            <input
              id="assistant-chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t("assistant.placeholder")}
            />
            <button type="submit" className="cta">
              {t("assistant.send")}
            </button>
          </form>
          <VoiceInput value={input} onChange={setInput} fieldId="assistant-chat-input" compact />
        </div>
      )}
      <button className="assistant-fab" onClick={() => setOpen((o) => !o)}>
        <span className="dot green" />
        {t("assistant.title")} <span className="beta">{t("common.beta")}</span>
      </button>
    </>
  );
}
