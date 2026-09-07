import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";

import {
  fetchSafeCities,
  fetchSafeLocations,
  type SafeCategory,
  type SafeCity,
  type SafeLocationLookup,
} from "../api/client";
import { useI18n } from "../i18n";
import {
  IconCross,
  IconGlobe,
  IconHome,
  IconLifeBuoy,
  IconMapPin,
  IconNavigation,
  IconPhone,
  IconSearch,
  IconShield,
  IconShieldCheck,
} from "./icons";

const STORAGE_KEY = "aquashield.safeCity";

/** A curated Sindh district is addressed by zone_id; any other place by free text. */
type CityChoice = { zoneId: string; label: string } | { query: string; label: string };

const DEFAULT_CITY: CityChoice = { zoneId: "hyderabad", label: "Hyderabad" };

const CATEGORY_ICON: Record<SafeCategory, typeof IconHome> = {
  shelter: IconHome,
  hospital: IconCross,
  rescue: IconLifeBuoy,
  police: IconShield,
  relief: IconShieldCheck,
};

function readStored(): CityChoice {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_CITY;
    const stored = JSON.parse(raw) as { label?: unknown; zoneId?: unknown; query?: unknown };
    const label = typeof stored.label === "string" ? stored.label : "";
    if (!label) return DEFAULT_CITY;
    if (typeof stored.zoneId === "string" && stored.zoneId) return { zoneId: stored.zoneId, label };
    if (typeof stored.query === "string" && stored.query) return { query: stored.query, label };
  } catch {
    /* a corrupt entry must not break the safety card */
  }
  return DEFAULT_CITY;
}

export default function SafeLocations() {
  const { t } = useI18n();
  const [city, setCity] = useState<CityChoice>(readStored);
  const [cities, setCities] = useState<SafeCity[]>([]);
  const [term, setTerm] = useState("");
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const [lookup, setLookup] = useState<SafeLocationLookup | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const wrapRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async (choice: CityChoice) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSafeLocations(
        "zoneId" in choice ? { zoneId: choice.zoneId } : { q: choice.query }
      );
      setLookup(data);
    } catch (err) {
      setLookup(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSafeCities()
      .then((data) => setCities(data.cities))
      .catch(() => setCities([]));
  }, []);

  useEffect(() => {
    void load(city);
  }, [city, load]);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(city));
    } catch {
      /* private browsing — the picker still works for this session */
    }
  }, [city]);

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (!wrapRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const needle = term.trim().toLowerCase();

  const matches = useMemo(
    () =>
      needle
        ? cities.filter(
            (c) => c.name.toLowerCase().includes(needle) || c.headquarters.toLowerCase().includes(needle)
          )
        : cities,
    [cities, needle]
  );

  // Typing a place that is not in the curated registry is the "any country"
  // path: it goes to OpenStreetMap instead of dead-ending the user.
  const curatedHit = matches.some(
    (c) => c.name.toLowerCase() === needle || c.headquarters.toLowerCase() === needle
  );
  const worldwide = needle && !curatedHit ? term.trim() : "";

  const options = useMemo(() => {
    const rows: { key: string; choice: CityChoice; detail: string; live: boolean }[] = matches.map((c) => ({
      key: c.zone_id,
      choice: { zoneId: c.zone_id, label: c.name },
      detail: t("safeLocations.optionCurated", { count: c.facility_count }),
      live: false,
    }));
    if (worldwide) {
      rows.unshift({
        key: `q:${worldwide.toLowerCase()}`,
        choice: { query: worldwide, label: worldwide },
        detail: t("safeLocations.optionWorldwide"),
        live: true,
      });
    }
    return rows;
  }, [matches, worldwide, t]);

  useEffect(() => setCursor(0), [term]);

  const choose = (choice: CityChoice) => {
    setCity(choice);
    setTerm("");
    setOpen(false);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      setOpen(false);
      return;
    }
    if (!open) {
      if (event.key === "ArrowDown" || event.key === "Enter") setOpen(true);
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setCursor((c) => (options.length ? (c + 1) % options.length : 0));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setCursor((c) => (options.length ? (c - 1 + options.length) % options.length : 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const picked = options[cursor];
      if (picked) choose(picked.choice);
    }
  };

  const locations = lookup?.locations ?? [];
  const isLive = lookup?.source === "openstreetmap";

  return (
    <section className="card" id="safe-locations">
      <div className="card-head">
        <span className="head-icon">
          <IconMapPin size={18} />
        </span>
        <div>
          <div className="head-title">{t("safeLocations.title")}</div>
          <div className="head-sub">{t("safeLocations.sub")}</div>
        </div>
      </div>

      <div className="safe-picker" ref={wrapRef}>
        <div className="safe-picker-field">
          <div className="safe-picker-bar">
            <span className="safe-picker-icon">
              <IconSearch size={15} />
            </span>
            <input
              className="safe-picker-input"
              type="text"
              role="combobox"
              aria-expanded={open}
              aria-controls="safe-city-list"
              aria-autocomplete="list"
              autoComplete="off"
              placeholder={t("safeLocations.cityPlaceholder")}
              value={term}
              onChange={(e) => {
                setTerm(e.target.value);
                setOpen(true);
              }}
              onFocus={() => setOpen(true)}
              onKeyDown={onKeyDown}
            />
          </div>
          {open && options.length > 0 && (
            <ul className="safe-picker-list" id="safe-city-list" role="listbox">
              {options.map((opt, i) => (
                <li key={opt.key} role="option" aria-selected={i === cursor}>
                  <button
                    type="button"
                    className={i === cursor ? "safe-picker-opt is-active" : "safe-picker-opt"}
                    onMouseEnter={() => setCursor(i)}
                    onClick={() => choose(opt.choice)}
                  >
                    <span className="safe-picker-opt-icon">
                      {opt.live ? <IconGlobe size={14} /> : <IconMapPin size={14} />}
                    </span>
                    <span className="safe-picker-opt-name">{opt.choice.label}</span>
                    <span className="safe-picker-opt-detail">{opt.detail}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {open && options.length === 0 && (
            <p className="safe-picker-none">{t("safeLocations.noCityMatch")}</p>
          )}
        </div>
        <p className="safe-picker-now">{t("safeLocations.showingFor", { city: city.label })}</p>
      </div>

      {error && (
        <div className="safe-empty">
          <p>{t("safeLocations.loadFailed", { error })}</p>
          <button className="safe-retry" type="button" onClick={() => void load(city)}>
            {t("safeLocations.retry")}
          </button>
        </div>
      )}

      {loading && !error && <p className="safe-loading">{t("safeLocations.loading", { city: city.label })}</p>}

      {!loading && !error && locations.length === 0 && (
        <div className="safe-empty">
          <p>{t(`safeLocations.empty.${lookup?.live_status ?? "unavailable"}`)}</p>
          <button className="safe-retry" type="button" onClick={() => void load(city)}>
            {t("safeLocations.retry")}
          </button>
        </div>
      )}

      {!loading && locations.length > 0 && (
        <div className="safe-grid">
          {locations.map((loc) => {
            const Icon = CATEGORY_ICON[loc.category];
            return (
              <div className="safe-card" key={`${loc.category}-${loc.name}-${loc.latitude}`}>
                <span className="safe-icon">
                  <Icon size={19} />
                </span>
                <div className="safe-body">
                  <div className="safe-name">{loc.name}</div>
                  <div className="safe-area">
                    <IconMapPin size={12} />
                    {t(`safeLocations.cat.${loc.category}`)}
                    {loc.area ? ` · ${loc.area}` : ""}
                    {loc.distance_km != null ? ` · ${loc.distance_km} km` : ""}
                  </div>
                  {loc.phone && (
                    <a className="safe-area safe-phone" href={`tel:${loc.phone}`}>
                      <IconPhone size={12} /> {loc.phone}
                    </a>
                  )}
                </div>
                <button
                  className="safe-nav"
                  aria-label={t("safeLocations.navigateTo", { name: loc.name })}
                  onClick={() => window.open(loc.maps_url, "_blank", "noopener")}
                >
                  <IconNavigation size={15} />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {!loading && lookup && (
        <div className="safe-status">
          {isLive && (
            <span className="safe-badge">
              <IconGlobe size={12} /> {t("safeLocations.liveBadge")}
            </span>
          )}
          <span>
            {isLive
              ? lookup.distance_basis === "resolved_city_center"
                ? t("safeLocations.liveNoteFromCentre", {
                    city: lookup.resolved.name ?? city.label,
                    attribution: lookup.attribution ?? "OpenStreetMap contributors",
                  })
                : t("safeLocations.liveNote", {
                    attribution: lookup.attribution ?? "OpenStreetMap contributors",
                  })
              : t("safeLocations.curatedNote", { city: lookup.resolved.name ?? city.label })}
          </span>
        </div>
      )}
    </section>
  );
}
