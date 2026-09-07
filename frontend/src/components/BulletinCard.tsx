import { useEffect, useMemo, useState } from "react";
import { useI18n } from "../i18n";

interface Bulletin {
  available: boolean;
  source?: string;
  url?: string;
  date?: string | null;
  text?: string;
}

interface BulletinSection {
  numeral: string;
  heading: string;
  chunks: string[];
}

const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"];
const NUMERAL_RE = /^[IVX]+\.?$/i;
const UPPER_TOKEN_RE = /^[A-Z0-9][A-Z0-9/'&-]*$/;

function isHeading(line: string): boolean {
  if (line.length > 60) return false;
  const tokens = line.split(/\s+/);
  const allCaps = tokens.filter((t) => /^[A-Z]{4,}$/.test(t));
  if (allCaps.length >= 2) return true;
  if (allCaps.length === 0) return false;
  const upper = tokens.filter((t) => UPPER_TOKEN_RE.test(t));
  return upper.length / tokens.length >= 0.5;
}

function parseSections(text: string): BulletinSection[] {
  const sections: BulletinSection[] = [];
  let current: BulletinSection | null = null;
  let pendingNumeral = "";
  let buffer = "";

  const flush = () => {
    if (current && buffer.trim()) current.chunks.push(buffer.trim());
    buffer = "";
  };

  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line) continue;
    if (NUMERAL_RE.test(line)) {
      flush();
      pendingNumeral = line.replace(".", "").toUpperCase();
      continue;
    }
    if (isHeading(line)) {
      flush();
      current = {
        numeral: pendingNumeral || ROMAN[sections.length] || String(sections.length + 1),
        heading: line,
        chunks: [],
      };
      pendingNumeral = "";
      sections.push(current);
      continue;
    }
    if (line === "-" || line === "•") {
      flush();
      continue;
    }
    if (/^[,.;:!?]+$/.test(line)) {
      if (buffer) buffer += line;
      continue;
    }
    buffer = buffer ? `${buffer} ${line}` : line;
  }
  flush();
  return sections.filter((s) => s.chunks.length > 0);
}

export default function BulletinCard() {
  const { t } = useI18n();
  const [bulletin, setBulletin] = useState<Bulletin | null>(null);

  useEffect(() => {
    fetch("/api/bulletin")
      .then((res) => res.json())
      .then(setBulletin)
      .catch(() => setBulletin({ available: false }));
  }, []);

  const sections = useMemo(
    () => (bulletin?.available && bulletin.text ? parseSections(bulletin.text) : []),
    [bulletin],
  );

  return (
    <section className="card">
      <div className="card-head">
        <span className="head-icon">📰</span>
        <div>
          <div className="head-title">{t("bulletin.title")}</div>
          <div className="head-sub">{t("bulletin.sub")}</div>
        </div>
        <span className="live-chip small">{t("common.live")}</span>
      </div>
      {!bulletin && (
        <div className="card-body">
          <p className="muted">{t("bulletin.fetching")}</p>
        </div>
      )}
      {bulletin && !bulletin.available && (
        <div className="card-body">
          <p className="muted">
            {t("bulletin.unavailable")}{" "}
            <a href="https://ffd.pmd.gov.pk/bulletin" target="_blank" rel="noreferrer">
              ffd.pmd.gov.pk
            </a>
            .
          </p>
        </div>
      )}
      {bulletin?.available && bulletin.text && sections.length === 0 && (
        <div className="card-body">
          <div className="bulletin-meta">
            {bulletin.date} · Source: {bulletin.source}
          </div>
          <p className="bulletin-text">{bulletin.text}</p>
        </div>
      )}
      {bulletin?.available && bulletin.text && sections.length > 0 && (
        <div className="bl-body">
          <div className="bl-meta">
            <span className="bl-chip">{bulletin.date}</span>
            <span className="bl-chip">{t("bulletin.source")}: {bulletin.source}</span>
            <a
              className="bl-link"
              href="https://ffd.pmd.gov.pk/bulletin"
              target="_blank"
              rel="noreferrer"
            >
              {t("bulletin.viewOriginal")}
            </a>
          </div>
          <div className="bl-grid">
            {sections.map((s) => (
              <section className="bl-section" key={s.numeral + s.heading}>
                <div className="bl-sec-head">
                  <span className="bl-num">{s.numeral}</span>
                  <h3 className="bl-sec-title">{s.heading}</h3>
                </div>
                {s.chunks.length > 1 ? (
                  <ul className="bl-bullets">
                    {s.chunks.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                ) : (
                  s.chunks.map((c, i) => <p key={i}>{c}</p>)
                )}
              </section>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
