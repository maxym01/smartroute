import type { Stop } from '../types/api';

const EARTH_RADIUS_KM = 6371;

/**
 * Straight-line distance between stops (haversine formula).
 * Only a reference point — the actual road route is longer.
 */
export function straightLineKm(a: Stop, b: Stop): number | null {
  if (a.stop_lat == null || a.stop_lon == null || b.stop_lat == null || b.stop_lon == null) {
    return null;
  }
  const rad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = rad(b.stop_lat - a.stop_lat);
  const dLon = rad(b.stop_lon - a.stop_lon);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(rad(a.stop_lat)) * Math.cos(rad(b.stop_lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(h));
}
