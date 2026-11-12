import type {
  ComparisonResponse,
  ConnectionList,
  HealthResponse,
  StopList,
  TripCreate,
  TripPriority,
  TripRead,
} from '../types/api';
import { request } from './apiClient';

/**
 * Okno wyszukiwania połączeń dla panelu rozkładu. Odpowiada domyślnemu
 * GTFS_SEARCH_WINDOW_MIN=180 w backendzie, którego używa porównanie podróży.
 */
export const CONNECTIONS_WINDOW_MIN = 180;
export const STOP_QUERY_MIN_LENGTH = 2;

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>('/health', { signal });
}

export function searchStops(query: string, signal?: AbortSignal, limit = 8): Promise<StopList> {
  const params = new URLSearchParams({ query, limit: String(limit) });
  return request<StopList>(`/stops?${params}`, { signal });
}

export function createTrip(payload: TripCreate): Promise<TripRead> {
  return request<TripRead>('/trips', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function compareTrip(tripId: number, priority?: TripPriority): Promise<ComparisonResponse> {
  const query = priority ? `?${new URLSearchParams({ priority })}` : '';
  return request<ComparisonResponse>(`/trips/${tripId}/compare${query}`);
}

export function findConnections(params: {
  originStopId: string;
  destinationStopId: string;
  departureAt: string;
  limit?: number;
}): Promise<ConnectionList> {
  const query = new URLSearchParams({
    origin_stop_id: params.originStopId,
    destination_stop_id: params.destinationStopId,
    departure_at: params.departureAt,
    window_min: String(CONNECTIONS_WINDOW_MIN),
    limit: String(params.limit ?? 5),
  });
  return request<ConnectionList>(`/connections?${query}`);
}
