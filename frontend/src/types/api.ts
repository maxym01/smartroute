/**
 * Typy odwzorowujące kontrakt API backendu (schematy Pydantic w backend/app/schemas).
 * Zmiana schematu po stronie backendu wymaga aktualizacji tego pliku.
 */

// app/core/enums.py
export type TripPriority = 'fastest' | 'cheapest' | 'greenest' | 'balanced';
export type TransportMode = 'car' | 'public_transport' | 'bike';
export type DataSource = 'parametric_estimate' | 'gtfs_schedule';
export type ComfortLevel = 'good' | 'reduced' | 'poor';
export type WeatherStatus =
  | 'applied'
  | 'disabled'
  | 'no_location'
  | 'out_of_time_window'
  | 'unavailable'
  | 'not_applicable';

// app/schemas/trip.py — TripCreate (POST /trips)
export interface TripCreate {
  name: string;
  origin: string;
  destination: string;
  distance_km: number;
  passengers: number;
  priority: TripPriority;
  has_car: boolean;
  allow_bike: boolean;
  notes?: string | null;
  origin_stop_id?: string | null;
  destination_stop_id?: string | null;
  /** ISO 8601; data bez strefy = czas lokalny Europe/Warsaw. */
  departure_at?: string | null;
}

// app/schemas/trip.py — TripRead
export interface TripRead {
  id: number;
  name: string;
  origin: string;
  destination: string;
  distance_km: number;
  passengers: number;
  priority: TripPriority;
  has_car: boolean;
  allow_bike: boolean;
  notes: string | null;
  origin_stop_id: string | null;
  destination_stop_id: string | null;
  departure_at: string | null;
  created_at: string;
  updated_at: string;
}

// app/schemas/gtfs.py
export interface Stop {
  stop_id: string;
  stop_name: string;
  stop_code: string | null;
  stop_lat: number | null;
  stop_lon: number | null;
}

export interface StopList {
  items: Stop[];
  count: number;
}

export interface Feed {
  source: string;
  imported_at: string;
  timezone: string;
  valid_from: string | null;
  valid_to: string | null;
}

export interface Connection {
  trip_id: string;
  route_id: string;
  line: string;
  /** Typ GTFS, np. 3/700 autobus, 0/900 tramwaj. */
  route_type: number;
  headsign: string | null;
  direction_id: number | null;
  service_date: string;
  departure_at: string;
  arrival_at: string;
  duration_min: number;
  origin_stop_sequence: number;
  destination_stop_sequence: number;
}

export interface ConnectionList {
  origin: Stop;
  destination: Stop;
  departure_at: string;
  window_min: number;
  data_source: 'gtfs_schedule';
  is_realtime: false;
  feed: Feed;
  connections: Connection[];
  notes: string[];
}

// app/schemas/comparison.py
export interface ModeScore {
  rank: number;
  normalized_duration: number;
  normalized_cost: number;
  normalized_co2: number;
  balanced_score: number;
  weather_demoted: boolean;
}

export interface ModeEstimate {
  mode: TransportMode;
  label: string;
  available: boolean;
  unavailable_reason: string | null;
  estimated_duration_min: number;
  estimated_cost_pln: number;
  estimated_cost_per_passenger_pln: number;
  estimated_co2_kg: number;
  estimated_co2_per_passenger_kg: number;
  is_estimate: true;
  data_source: DataSource;
  assumptions: string[];
  /** null dla wariantu niedostępnego. */
  score: ModeScore | null;
  comfort_level: ComfortLevel | null;
}

export interface Recommendation {
  mode: TransportMode | null;
  label: string | null;
  explanation: string;
  tie_break_applied: boolean;
}

export interface ScoringMethod {
  priority: TripPriority;
  description: string;
  balanced_weights: Record<string, number>;
  tie_break_order: TransportMode[];
  comfort_rule: string;
}

export interface WeatherConditions {
  source: 'weatherbit_current';
  /** Czas obserwacji (UTC). */
  observed_at: string | null;
  temperature_c: number;
  precipitation_mm_h: number;
  snowfall_mm_h: number;
  wind_speed_kmh: number;
  description: string | null;
}

export interface WeatherLocation {
  stop_id: string;
  stop_name: string;
  lat: number;
  lon: number;
}

export interface WeatherAdjustment {
  mode: TransportMode;
  comfort_level: ComfortLevel;
  duration_factor: number;
  reasons: string[];
}

export interface Weather {
  status: WeatherStatus;
  adjustment_applied: boolean;
  explanation: string;
  is_forecast: false;
  location: WeatherLocation | null;
  conditions: WeatherConditions | null;
  adjustment: WeatherAdjustment | null;
}

export interface ComparisonResponse {
  trip_id: number;
  priority: TripPriority;
  distance_km: number;
  passengers: number;
  is_estimate: true;
  disclaimer: string;
  variants: ModeEstimate[];
  recommendation: Recommendation;
  scoring: ScoringMethod;
  /** null = pogody nie oceniano. */
  weather: Weather | null;
}

// app/api/v1/meta.py
export interface HealthResponse {
  status: 'ok' | 'degraded';
  app: string;
  version: string;
  environment: string;
  database: 'ok' | 'error';
}

// app/core/exceptions.py — spójny format błędów {detail, code}
export interface ValidationIssue {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface ApiErrorBody {
  detail: string | ValidationIssue[];
  code?: 'not_found' | 'validation_error' | 'gtfs_not_imported' | string;
}
