import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import en from "./i18n/en";
import ur from "./i18n/ur";
import sd from "./i18n/sd";

export type Lang = "en" | "ur" | "sd";

const STORAGE_KEY = "aquashield.lang";

const DICTS: Record<Lang, Record<string, unknown>> = { en, ur, sd };

const RTL_LANGS = new Set<Lang>(["ur", "sd"]);

const FONT_URLS: Partial<Record<Lang, string>> = {
  ur: "https://fonts.googleapis.com/css2?family=Noto+Nastaliq+Urdu:wght@400;700&display=swap",
  sd: "https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@400;500;600;700&display=swap",
};

interface I18nContextValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

function lookup(obj: Record<string, unknown>, path: string): string | undefined {
  const parts = path.split(".");
  let cur: unknown = obj;
  for (const p of parts) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = (cur as Record<string, unknown>)[p];
  }
  return typeof cur === "string" ? cur : undefined;
}

function buildT(lang: Lang) {
  return (key: string, vars?: Record<string, string | number>): string => {
    let val = lookup(DICTS[lang], key) ?? lookup(DICTS.en, key) ?? key;
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        val = val.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
      }
    }
    return val;
  };
}

function readStored(): Lang {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === "en" || raw === "ur" || raw === "sd") return raw;
  } catch {
    /* ignore */
  }
  return "en";
}

let fontLink: HTMLLinkElement | null = null;

function applyFont(lang: Lang) {
  if (fontLink) {
    fontLink.remove();
    fontLink = null;
  }
  const url = FONT_URLS[lang];
  if (url) {
    fontLink = document.createElement("link");
    fontLink.rel = "stylesheet";
    fontLink.href = url;
    document.head.appendChild(fontLink);
  }
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => readStored());

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    localStorage.setItem(STORAGE_KEY, l);
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = RTL_LANGS.has(lang) ? "rtl" : "ltr";
    applyFont(lang);
  }, [lang]);

  const t = useMemo(() => buildT(lang), [lang]);

  const value = useMemo<I18nContextValue>(() => ({ lang, setLang, t }), [lang, setLang, t]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within <I18nProvider>");
  return ctx;
}
