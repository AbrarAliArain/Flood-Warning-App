import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Lang } from "../i18n";

/**
 * Speech-to-text on top of the browser's Web Speech API. No new dependency and
 * no backend involvement — recognition happens in the browser.
 *
 * The language registry is the extension point: adding a locale is a one-line
 * change here. A `null` entry means "we do not claim to recognise this
 * language", which the UI must surface honestly rather than silently falling
 * back to English and producing nonsense transcripts.
 */
export const SPEECH_LOCALES: Record<Lang, string | null> = {
  en: "en-US",
  ur: "ur-PK",
  sd: null,
};

export type SpeechState = "idle" | "requesting" | "listening" | "processing" | "error";

/** Why voice is unavailable, so the UI can explain rather than just hide. */
export type SpeechUnsupportedReason = "no_api" | "no_locale" | null;

interface SpeechRecognitionAlternative {
  transcript: string;
}
interface SpeechRecognitionResult {
  readonly length: number;
  isFinal: boolean;
  [index: number]: SpeechRecognitionAlternative;
}
interface SpeechRecognitionResultList {
  readonly length: number;
  [index: number]: SpeechRecognitionResult;
}
interface SpeechRecognitionEventLike extends Event {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}
interface SpeechRecognitionErrorEventLike extends Event {
  error: string;
}
interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getConstructor(): SpeechRecognitionCtor | null {
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export interface UseSpeechRecognition {
  state: SpeechState;
  supported: boolean;
  unsupportedReason: SpeechUnsupportedReason;
  /** Confirmed text for this dictation session. */
  transcript: string;
  /** Live partial text — shown greyed out, never committed on its own. */
  interim: string;
  errorCode: string | null;
  locale: string | null;
  start: () => void;
  stop: () => void;
  reset: () => void;
}

export function useSpeechRecognition(lang: Lang): UseSpeechRecognition {
  const [state, setState] = useState<SpeechState>("idle");
  const [transcript, setTranscript] = useState("");
  const [interim, setInterim] = useState("");
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  /** Distinguishes a user-initiated stop from the engine ending on its own. */
  const stoppingRef = useRef(false);

  const locale = SPEECH_LOCALES[lang];
  const ctor = useMemo(getConstructor, []);
  const supported = ctor !== null && locale !== null;
  const unsupportedReason: SpeechUnsupportedReason =
    ctor === null ? "no_api" : locale === null ? "no_locale" : null;

  const stop = useCallback(() => {
    stoppingRef.current = true;
    const recognition = recognitionRef.current;
    if (recognition) {
      setState("processing");
      recognition.stop();
    } else {
      setState("idle");
    }
  }, []);

  const start = useCallback(() => {
    if (!ctor || !locale) return;
    if (recognitionRef.current) return;

    const recognition = new ctor();
    recognition.lang = locale;
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    stoppingRef.current = false;
    setErrorCode(null);
    setInterim("");
    setState("requesting");

    recognition.onstart = () => setState("listening");

    recognition.onresult = (event) => {
      let finalChunk = "";
      let pending = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const text = result[0]?.transcript ?? "";
        if (result.isFinal) finalChunk += text;
        else pending += text;
      }
      if (finalChunk) {
        setTranscript((prev) => (prev ? `${prev} ${finalChunk.trim()}` : finalChunk.trim()));
      }
      setInterim(pending);
    };

    recognition.onerror = (event) => {
      setErrorCode(event.error);
      setState("error");
      recognitionRef.current = null;
    };

    recognition.onend = () => {
      recognitionRef.current = null;
      setInterim("");
      setState((prev) => (prev === "error" ? prev : "idle"));
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch (err) {
      recognitionRef.current = null;
      setErrorCode(String(err));
      setState("error");
    }
  }, [ctor, locale]);

  const reset = useCallback(() => {
    setTranscript("");
    setInterim("");
    setErrorCode(null);
  }, []);

  useEffect(
    () => () => {
      recognitionRef.current?.abort();
      recognitionRef.current = null;
    },
    [],
  );

  return {
    state,
    supported,
    unsupportedReason,
    transcript,
    interim,
    errorCode,
    locale,
    start,
    stop,
    reset,
  };
}
