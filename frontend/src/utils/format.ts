/** Spójne formatowanie wartości dla polskiego użytkownika (heurystyki 2 i 4). */

export const LOCAL_TIME_ZONE = 'Europe/Warsaw';
const LOCALE = 'pl-PL';

const currency = new Intl.NumberFormat(LOCALE, { style: 'currency', currency: 'PLN' });
const timeFormat = new Intl.DateTimeFormat(LOCALE, {
  hour: '2-digit',
  minute: '2-digit',
  timeZone: LOCAL_TIME_ZONE,
});
const dateTimeFormat = new Intl.DateTimeFormat(LOCALE, {
  weekday: 'short',
  day: 'numeric',
  month: 'long',
  hour: '2-digit',
  minute: '2-digit',
  timeZone: LOCAL_TIME_ZONE,
});
const dateFormat = new Intl.DateTimeFormat(LOCALE, {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: LOCAL_TIME_ZONE,
});

export function formatNumber(value: number, maximumFractionDigits = 1, minimumFractionDigits = 0) {
  return new Intl.NumberFormat(LOCALE, { maximumFractionDigits, minimumFractionDigits }).format(
    value,
  );
}

/** 25 → „25 min”, 65 → „1 h 5 min”. */
export function formatDuration(minutes: number): string {
  const total = Math.max(0, Math.round(minutes));
  if (total < 60) return `${total} min`;
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`;
}

export function formatCost(pln: number): string {
  return currency.format(pln);
}

/** Emisja w kg CO₂; bardzo małe niezerowe wartości z 3 miejscami po przecinku. */
export function formatCo2(kg: number): string {
  const digits = kg !== 0 && Math.abs(kg) < 0.01 ? 3 : 2;
  return `${formatNumber(kg, digits, kg === 0 ? 0 : digits)} kg CO₂`;
}

export function formatDistance(km: number): string {
  return `${formatNumber(km, 1)} km`;
}

/** Godzina w czasie lokalnym Gdańska, np. „18:57”. */
export function formatTime(iso: string): string {
  return timeFormat.format(new Date(iso));
}

/** np. „czw., 12 listopada, 18:54”. */
export function formatDateTime(iso: string): string {
  return dateTimeFormat.format(new Date(iso));
}

export function formatDate(iso: string): string {
  return dateFormat.format(new Date(iso));
}

export function formatTemperature(celsius: number): string {
  return `${formatNumber(celsius, 1)} °C`;
}
