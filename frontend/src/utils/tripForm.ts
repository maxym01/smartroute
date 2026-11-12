import type { Stop, TripCreate, TripPriority } from '../types/api';
import { compareLocal, isValidDate, isValidTime, nowInGdansk, toBackendDateTime } from './datetime';

/** Ograniczenia zgodne z app/schemas/trip.py. */
export const LIMITS = {
  nameMax: 100,
  distanceMax: 1000,
  passengersMin: 1,
  passengersMax: 8,
} as const;

export interface TripFormValues {
  name: string;
  origin: Stop | null;
  destination: Stop | null;
  date: string;
  time: string;
  /** Tekst z pola — walidowany i zamieniany na liczbę przy wysyłce. */
  distanceKm: string;
  passengers: string;
  priority: TripPriority;
  hasCar: boolean;
  allowBike: boolean;
}

export type TripFormField =
  | 'name'
  | 'origin'
  | 'destination'
  | 'date'
  | 'time'
  | 'distanceKm'
  | 'passengers';
export type TripFormErrors = Partial<Record<TripFormField, string>>;

/** Kolejność pól w formularzu — dla podsumowania błędów i ustawiania focusu. */
export const FIELD_ORDER: TripFormField[] = [
  'origin',
  'destination',
  'date',
  'time',
  'distanceKm',
  'passengers',
  'name',
];

export const FIELD_LABELS: Record<TripFormField, string> = {
  name: 'Nazwa podróży',
  origin: 'Przystanek początkowy',
  destination: 'Przystanek docelowy',
  date: 'Data wyjazdu',
  time: 'Godzina wyjazdu',
  distanceKm: 'Dystans szacunkowy',
  passengers: 'Pasażerowie',
};

/** Id elementu formularza dla danego pola (focus z podsumowania błędów). */
export const FIELD_IDS: Record<TripFormField, string> = {
  name: 'trip-name',
  origin: 'origin-stop',
  destination: 'destination-stop',
  date: 'departure-date',
  time: 'departure-time',
  distanceKm: 'distance-km',
  passengers: 'passengers',
};

export function defaultFormValues(now: Date = new Date()): TripFormValues {
  const { date, time } = nowInGdansk(now);
  return {
    name: '',
    origin: null,
    destination: null,
    date,
    time,
    distanceKm: '',
    passengers: '1',
    priority: 'balanced',
    hasCar: true,
    allowBike: true,
  };
}

/** Akceptuje przecinek dziesiętny („5,5”). Zwraca NaN dla niepoprawnego tekstu. */
export function parseDecimal(value: string): number {
  const normalized = value.trim().replace(',', '.');
  if (!/^\d+(\.\d+)?$/.test(normalized)) return Number.NaN;
  return Number(normalized);
}

export function validateTripForm(values: TripFormValues): TripFormErrors {
  const errors: TripFormErrors = {};

  if (!values.origin) errors.origin = 'Wybierz przystanek początkowy z listy podpowiedzi.';
  if (!values.destination) errors.destination = 'Wybierz przystanek docelowy z listy podpowiedzi.';
  if (values.origin && values.destination && values.origin.stop_id === values.destination.stop_id) {
    errors.destination = 'Przystanek docelowy musi być inny niż początkowy.';
  }

  if (!values.date) errors.date = 'Podaj datę wyjazdu.';
  else if (!isValidDate(values.date)) errors.date = 'Niepoprawna data — użyj formatu RRRR-MM-DD.';

  if (!values.time) errors.time = 'Podaj godzinę wyjazdu.';
  else if (!isValidTime(values.time)) errors.time = 'Niepoprawna godzina — użyj formatu GG:MM.';

  const distance = parseDecimal(values.distanceKm);
  if (!values.distanceKm.trim()) {
    errors.distanceKm = 'Podaj szacunkowy dystans w kilometrach.';
  } else if (Number.isNaN(distance)) {
    errors.distanceKm = 'Dystans musi być liczbą, np. 5,5.';
  } else if (distance <= 0) {
    errors.distanceKm = 'Dystans musi być większy od 0 km.';
  } else if (distance > LIMITS.distanceMax) {
    errors.distanceKm = `Dystans nie może przekraczać ${LIMITS.distanceMax} km.`;
  }

  const passengers = Number(values.passengers);
  if (
    !values.passengers.trim() ||
    !Number.isInteger(passengers) ||
    passengers < LIMITS.passengersMin ||
    passengers > LIMITS.passengersMax
  ) {
    errors.passengers = `Podaj liczbę całkowitą od ${LIMITS.passengersMin} do ${LIMITS.passengersMax}.`;
  }

  if (values.name.trim().length > LIMITS.nameMax) {
    errors.name = `Nazwa może mieć maksymalnie ${LIMITS.nameMax} znaków.`;
  }

  return errors;
}

/** Nazwa domyślna, gdy użytkownik jej nie poda. */
export function defaultTripName(values: Pick<TripFormValues, 'origin' | 'destination'>): string {
  if (!values.origin || !values.destination) return '';
  return `${values.origin.stop_name} → ${values.destination.stop_name}`.slice(0, LIMITS.nameMax);
}

/** Wymaga wcześniejszej pomyślnej walidacji. */
export function toTripPayload(values: TripFormValues): TripCreate {
  if (!values.origin || !values.destination) throw new Error('Brak przystanków');
  return {
    name: values.name.trim() || defaultTripName(values),
    // Backend wymaga tekstowych nazw miejsc — przekazujemy nazwy przystanków GTFS.
    origin: values.origin.stop_name,
    destination: values.destination.stop_name,
    origin_stop_id: values.origin.stop_id,
    destination_stop_id: values.destination.stop_id,
    departure_at: toBackendDateTime({ date: values.date, time: values.time }),
    distance_km: parseDecimal(values.distanceKm),
    passengers: Number(values.passengers),
    priority: values.priority,
    has_car: values.hasCar,
    allow_bike: values.allowBike,
  };
}

export function isInPast(values: Pick<TripFormValues, 'date' | 'time'>, now: Date = new Date()) {
  if (!isValidDate(values.date) || !isValidTime(values.time)) return false;
  return compareLocal(values, nowInGdansk(now)) < 0;
}
