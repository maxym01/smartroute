import type { ComfortLevel, DataSource, TransportMode, TripPriority } from '../types/api';

export const PRIORITY_OPTIONS: { value: TripPriority; label: string; description: string }[] = [
  {
    value: 'balanced',
    label: 'Zrównoważony',
    description: 'Kompromis czasu, kosztu i emisji — każda metryka waży po 1/3.',
  },
  { value: 'fastest', label: 'Najszybszy', description: 'Najkrótszy czas od drzwi do drzwi.' },
  { value: 'cheapest', label: 'Najtańszy', description: 'Najniższy koszt całego przejazdu.' },
  {
    value: 'greenest',
    label: 'Najbardziej ekologiczny',
    description: 'Najniższa szacowana emisja CO₂.',
  },
];

export function priorityLabel(priority: TripPriority): string {
  return PRIORITY_OPTIONS.find((option) => option.value === priority)?.label ?? priority;
}

export const MODE_LABELS: Record<TransportMode, string> = {
  car: 'Samochód',
  public_transport: 'Komunikacja miejska',
  bike: 'Rower',
};

export const DATA_SOURCE_LABELS: Record<DataSource, { short: string; long: string }> = {
  gtfs_schedule: {
    short: 'Rozkład GTFS',
    long: 'Czas z planowego rozkładu GTFS Static ZTM Gdańsk',
  },
  parametric_estimate: {
    short: 'Szacunek',
    long: 'Szacunek z modelu parametrycznego (dystans ÷ średnia prędkość + narzuty)',
  },
};

export const COMFORT_LABELS: Record<ComfortLevel, string> = {
  good: 'dobry',
  reduced: 'obniżony',
  poor: 'niski',
};

export type RouteKind = 'Tramwaj' | 'Autobus' | 'Pociąg' | 'Linia';

/** GTFS route types (basic and extended). */
export function routeTypeLabel(routeType: number): RouteKind {
  if (routeType === 0 || (routeType >= 900 && routeType < 1000)) return 'Tramwaj';
  if (routeType === 3 || (routeType >= 700 && routeType < 800)) return 'Autobus';
  if (routeType === 2 || (routeType >= 100 && routeType < 200)) return 'Pociąg';
  return 'Linia';
}
