import { useEffect, useRef, useState, type ReactNode } from "react";
import L from "leaflet";
import type { ZonesResponse } from "../api/client";
import { useI18n } from "../i18n";
import { IconLocate, IconSearch } from "./icons";

const SINDH_CENTER: L.LatLngExpression = [26.0, 68.6];

const CATEGORY_COLORS: Record<string, string> = {
  critical: "#DC2626",
  high: "#F97316",
  moderate: "#EAB308",
  low: "#16A34A",
};

function buildLegendHtml(t: (key: string) => string) {
  return `
  <span><i style="background:#16A34A"></i>${t("map.legendNormal")}</span>
  <span><i style="background:#EAB308"></i>${t("map.legendWatch")}</span>
  <span><i style="background:#F97316"></i>${t("map.legendWarning")}</span>
  <span><i style="background:#DC2626"></i>${t("map.legendCritical")}</span>
  <span><i style="background:#087EA4"></i>${t("map.legendWater")}</span>
`;
}

interface Props {
  zones: ZonesResponse | null;
  onSelect: (zoneId: string) => void;
  children?: ReactNode;
}

export default function MapView({ zones, onSelect, children }: Props) {
  const { t } = useI18n();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const zoneLayersRef = useRef<Record<string, L.Path & L.Layer>>({});
  const userMarkerRef = useRef<L.CircleMarker | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  const [query, setQuery] = useState("");
  const [resultsOpen, setResultsOpen] = useState(false);
  const [locateStatus, setLocateStatus] = useState("");

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, { center: SINDH_CENTER, zoom: 7 });
    const tiles = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    const FALLBACK_TILE =
      "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==";
    tiles.on("tileerror", (e) => {
      const img = (e as unknown as { tile: HTMLImageElement }).tile;
      if (img.dataset.fallback) return;
      img.dataset.fallback = "1";
      img.src = FALLBACK_TILE;
    });

    const legend = new L.Control({ position: "bottomleft" });
    legend.onAdd = () => {
      const div = L.DomUtil.create("div", "legend");
      div.innerHTML = buildLegendHtml(t);
      return div;
    };
    legend.addTo(map);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
      zoneLayersRef.current = {};
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !zones) return;
    zoneLayersRef.current = {};
    const layer = L.geoJSON(zones, {
      style: (feature) => ({
        color: "#ffffff",
        weight: 1.5,
        fillColor: CATEGORY_COLORS[feature?.properties.category] ?? feature?.properties.color ?? "#94A3B8",
        fillOpacity: 0.55,
      }),
      onEachFeature: (feature, leafletLayer) => {
        const props = feature.properties;
        zoneLayersRef.current[props.zone_id] = leafletLayer as L.Path & L.Layer;
        leafletLayer.bindTooltip(`${props.name} — ${props.score}/100`, { sticky: true });
        leafletLayer.on("click", () => onSelectRef.current(props.zone_id));
      },
    });
    layer.addTo(map);
    return () => {
      layer.remove();
    };
  }, [zones]);

  const matches = (query.trim()
    ? zones?.features.filter((f) =>
        f.properties.name.toLowerCase().includes(query.trim().toLowerCase())
      ) ?? []
    : []
  ).slice(0, 6);

  const zoomTo = (zoneId: string) => {
    const layer = zoneLayersRef.current[zoneId];
    const map = mapRef.current;
    if (!layer || !map) return;
    const bounds = (layer as L.Polygon).getBounds?.();
    if (bounds) map.flyToBounds(bounds, { padding: [60, 60], maxZoom: 10 });
  };

  const pick = (zoneId: string, name: string) => {
    setQuery(name);
    setResultsOpen(false);
    zoomTo(zoneId);
    onSelectRef.current(zoneId);
  };

  const locate = () => {
    if (!navigator.geolocation) {
      setLocateStatus(t("map.geoNotSupported"));
      return;
    }
    setLocateStatus(t("map.locating"));
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const map = mapRef.current;
        if (!map) return;
        const ll: L.LatLngExpression = [pos.coords.latitude, pos.coords.longitude];
        map.flyTo(ll, 10);
        userMarkerRef.current?.remove();
        userMarkerRef.current = L.circleMarker(ll, {
          radius: 8,
          color: "#087EA4",
          weight: 2,
          fillColor: "#18A9D1",
          fillOpacity: 0.45,
        }).addTo(map);
        setLocateStatus(t("map.showingLocation"));
      },
      () => setLocateStatus(t("map.locationUnavailable"))
    );
  };

  return (
    <>
      <div className="map-toolbar">
        <div className="map-search">
          <IconSearch size={15} />
          <input
            placeholder={t("map.searchDistrict")}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setResultsOpen(true);
            }}
            onFocus={() => setResultsOpen(true)}
            onBlur={() => setTimeout(() => setResultsOpen(false), 150)}
            aria-label={t("map.searchLocation")}
          />
          {resultsOpen && matches.length > 0 && (
            <div className="map-search-results">
              {matches.map((m) => (
                <button
                  key={m.properties.zone_id}
                  onMouseDown={() => pick(m.properties.zone_id, m.properties.name)}
                >
                  {m.properties.name}
                  <span>{m.properties.score}/100</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <button className="icon-btn" title={t("map.currentLocation")} aria-label={t("map.currentLocation")} onClick={locate}>
          <IconLocate size={17} />
        </button>
        {locateStatus && <span className="muted">{locateStatus}</span>}
      </div>
      <div className="map-wrap">
        <div ref={containerRef} className="map-container" />
        {children}
      </div>
    </>
  );
}
