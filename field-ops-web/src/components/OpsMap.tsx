import L from "leaflet";
import { useEffect, useMemo } from "react";
import { CircleMarker, MapContainer, Polyline, TileLayer, useMap } from "react-leaflet";
import type { RoutePayload, SiteMarker } from "../types";

function FitBounds({ positions }: { positions: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (positions.length < 2) return;
    const b = L.latLngBounds(positions.map(([la, lo]) => [la, lo] as [number, number]));
    map.fitBounds(b, { padding: [48, 48], maxZoom: 15 });
  }, [map, positions]);
  return null;
}

const siteColor = (t: string) => {
  if (t.includes("yard")) return "#fbbf24";
  if (t.includes("Service")) return "#38bdf8";
  if (t.includes("store")) return "#a78bfa";
  return "#94a3b8";
};

export function OpsMap({
  route,
  sites,
  playbackIndex,
}: {
  route: RoutePayload | null;
  sites: SiteMarker[];
  playbackIndex: number;
}) {
  const positions = useMemo(() => {
    if (!route?.coordinates?.length) return [] as [number, number][];
    return route.coordinates.map(([a, b]) => [a, b] as [number, number]);
  }, [route]);

  const center = positions[0] ?? [20.5937, 78.9629];
  const cur = positions[Math.min(Math.max(0, playbackIndex), Math.max(0, positions.length - 1))];

  return (
    <div className="h-[420px] w-full overflow-hidden rounded-2xl border border-slate-600/40 shadow-glow">
      <MapContainer center={center} zoom={12} className="h-full w-full" scrollWheelZoom>
        <TileLayer
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        {positions.length >= 2 && <FitBounds positions={positions} />}
        {positions.length >= 2 && (
          <Polyline
            positions={positions}
            pathOptions={{ color: "#38bdf8", weight: 4, opacity: 0.88 }}
          />
        )}
        {route?.stops?.map((s, i) => (
          <CircleMarker
            key={`stop-${i}`}
            center={[s.lat, s.lon]}
            radius={7}
            pathOptions={{ color: "#fb923c", fillColor: "#fb923c", fillOpacity: 0.5, weight: 2 }}
          />
        ))}
        {sites.map((s, i) => (
          <CircleMarker
            key={`site-${i}`}
            center={[s.lat, s.lon]}
            radius={5}
            pathOptions={{
              color: siteColor(s.site_type),
              fillColor: siteColor(s.site_type),
              fillOpacity: 0.35,
              weight: 1,
            }}
          />
        ))}
        {cur && (
          <CircleMarker
            center={cur}
            radius={10}
            pathOptions={{ color: "#fff", fillColor: "#22d3ee", fillOpacity: 0.95, weight: 3 }}
          />
        )}
      </MapContainer>
    </div>
  );
}
