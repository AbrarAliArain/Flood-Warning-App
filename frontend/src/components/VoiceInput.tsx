import { useEffect, useRef, useState } from "react";
import { useI18n } from "../i18n";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";
import { IconMic } from "./icons";

/**
 * "Type or speak" control for a free-text field.
 *
 * Dictation only ever *appends*; the text captured before dictation started is
 * kept so a single Undo restores it. Nothing is submitted automatically.
 */
interface Props {
  value: string;
  onChange: (next: string) => void;
  /** Ties the control to its field for screen readers. */
  fieldId: string;
  compact?: boolean;
}

const ERROR_KEYS: Record<string, string> = {
  "not-allowed": "voice.errPermission",
  "service-not-allowed": "voice.errPermission",
  "no-speech": "voice.errNoSpeech",
  "audio-capture": "voice.errNoMic",
  network: "voice.errNetwork",
  aborted: "voice.errAborted",
};

export default function VoiceInput({ value, onChange, fieldId, compact = false }: Props) {
  const { t, lang } = useI18n();
  const speech = useSpeechRecognition(lang);
  const consumedRef = useRef(0);
  const baselineRef = useRef<string | null>(null);
  const [canUndo, setCanUndo] = useState(false);

  // Kept fresh so the append effect can react to new speech alone, rather than
  // re-running on every keystroke the user makes in the field.
  const valueRef = useRef(value);
  const onChangeRef = useRef(onChange);
  valueRef.current = value;
  onChangeRef.current = onChange;

  const listening = speech.state === "listening" || speech.state === "requesting";

  useEffect(() => {
    const fresh = speech.transcript.slice(consumedRef.current);
    if (!fresh.trim()) return;
    consumedRef.current = speech.transcript.length;
    const current = valueRef.current;
    const separator = current && !/\s$/.test(current) ? " " : "";
    onChangeRef.current(`${current}${separator}${fresh.trim()}`);
    setCanUndo(true);
  }, [speech.transcript]);

  if (!speech.supported) {
    return (
      <p className="voice-unsupported">
        {speech.unsupportedReason === "no_locale"
          ? t("voice.unsupportedLanguage")
          : t("voice.unsupportedBrowser")}
      </p>
    );
  }

  const toggle = () => {
    if (listening) {
      speech.stop();
      return;
    }
    baselineRef.current = value;
    consumedRef.current = speech.transcript.length;
    speech.start();
  };

  const undo = () => {
    if (baselineRef.current === null) return;
    onChange(baselineRef.current);
    consumedRef.current = speech.transcript.length;
    setCanUndo(false);
  };

  const statusKey =
    speech.state === "error"
      ? ERROR_KEYS[speech.errorCode ?? ""] ?? "voice.errGeneric"
      : speech.state === "requesting"
        ? "voice.requesting"
        : speech.state === "listening"
          ? "voice.listening"
          : speech.state === "processing"
            ? "voice.processing"
            : null;

  return (
    <div className={`voice-input${compact ? " compact" : ""}`}>
      <div className="voice-row">
        <button
          type="button"
          className={`voice-btn${listening ? " listening" : ""}`}
          onClick={toggle}
          aria-controls={fieldId}
          aria-pressed={listening}
        >
          <IconMic size={16} />
          {listening ? t("voice.tapToStop") : t("voice.speak")}
        </button>
        {!compact && <span className="voice-hint">{t("voice.typeOrSpeak")}</span>}
        {canUndo && !listening && (
          <button type="button" className="voice-undo" onClick={undo}>
            {t("voice.undo")}
          </button>
        )}
      </div>
      {statusKey && (
        <span
          className={`voice-status ${speech.state}`}
          role="status"
          aria-live="polite"
        >
          {listening && <span className="voice-pulse" aria-hidden="true" />}
          {t(statusKey)}
        </span>
      )}
      {speech.interim && <span className="voice-interim">{speech.interim}</span>}
    </div>
  );
}
