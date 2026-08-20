import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { AffineTransform, BaseMapStatus, MapPlayer } from "../types";

export function applyTransform(t: AffineTransform, worldX: number, worldY: number): [number, number] {
  return [t.a * worldX + t.b * worldY + t.c, t.d * worldX + t.e * worldY + t.f];
}

// Static, maintainer-supplied vanilla map (isometric) tiled by base_map.py into
// a Leaflet-compatible {level}/{y}/{x} pyramid under MAP_TILES_DATA/base, served by the
// same /map-tiles mount map_render.py's own output uses.
export function BaseMapView({
  status, players, transform, calibrating, onMapClick,
}: {
  status: BaseMapStatus;
  players: MapPlayer[];
  transform: AffineTransform | null;
  calibrating: boolean;
  onMapClick?: (pixelX: number, pixelY: number) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<L.LayerGroup | null>(null);
  const onMapClickRef = useRef(onMapClick);
  onMapClickRef.current = onMapClick;
  const calibratingRef = useRef(calibrating);
  calibratingRef.current = calibrating;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    if (status.width == null || status.height == null || status.max_zoom == null) return;

    const map = L.map(containerRef.current, {
      crs: L.CRS.Simple,
      minZoom: 0,
      maxZoom: status.max_zoom,
      attributionControl: false,
    });
    mapRef.current = map;

    const southWest = map.unproject([0, status.height], status.max_zoom);
    const northEast = map.unproject([status.width, 0], status.max_zoom);
    const bounds = L.latLngBounds(southWest, northEast);

    // Floor the zoom at the level where the image just fully covers the
    // viewport (inside=true - the min zoom where the view fits inside the
    // bounds), not the fixed 0 the map was constructed with above. Zooming
    // out past this shows blank space beyond the tile layer's own bounds
    // (maxBounds only constrains panning, not zoom level) - this is what
    // that looked like as "glitchy nothingness" outside the map's edges.
    const fitZoom = Math.min(map.getBoundsZoom(bounds, true), status.max_zoom);
    map.setMinZoom(fitZoom);

    // vips dzsave's "google" layout writes tiles as {level}/{y}/{x}.ext (row
    // folder, then column file) - confirmed from libvips' own dzsave.c - the
    // opposite axis order from Leaflet's usual {z}/{x}/{y} default, so x/y
    // are swapped here to match what's actually on disk.
    L.tileLayer("/map-tiles/base/{z}/{y}/{x}.jpg", {
      minZoom: fitZoom,
      maxZoom: status.max_zoom,
      tileSize: status.tile_size,
      noWrap: true,
      bounds,
    }).addTo(map);

    map.setMaxBounds(bounds);
    map.fitBounds(bounds);

    markersRef.current = L.layerGroup().addTo(map);

    map.on("click", (e: L.LeafletMouseEvent) => {
      if (!calibratingRef.current || !onMapClickRef.current) return;
      const point = map.project(e.latlng, status.max_zoom!);
      onMapClickRef.current(point.x, point.y);
    });

    return () => {
      map.remove();
      mapRef.current = null;
      markersRef.current = null;
    };
  }, [status.width, status.height, status.max_zoom, status.tile_size]);

  useEffect(() => {
    const map = mapRef.current;
    const layer = markersRef.current;
    if (!map || !layer || status.max_zoom == null) return;

    layer.clearLayers();
    if (!transform) return;

    for (const p of players) {
      const [pixelX, pixelY] = applyTransform(transform, p.x, p.y);
      const latlng = map.unproject([pixelX, pixelY], status.max_zoom);
      const marker = L.marker(latlng, {
        icon: L.divIcon({ className: "player-marker", iconSize: [12, 12] }),
      });
      marker.bindTooltip(p.username, {
        permanent: true, direction: "right", className: "player-marker-label", offset: [8, 0],
      });
      marker.addTo(layer);
    }
  }, [players, transform, status.max_zoom]);

  return (
    <div
      ref={containerRef}
      className="live-map"
      style={calibrating ? { cursor: "crosshair" } : undefined}
    />
  );
}
