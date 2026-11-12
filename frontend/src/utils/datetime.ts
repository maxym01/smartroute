import { LOCAL_TIME_ZONE } from './format';

export interface LocalDateTime {
  /** YYYY-MM-DD */
  date: string;
  /** HH:MM */
  time: string;
}

const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
const TIME_RE = /^([01]\d|2[0-3]):([0-5]\d)$/;

/** Bieżąca data i godzina w strefie Europe/Warsaw — niezależnie od strefy przeglądarki. */
export function nowInGdansk(now: Date = new Date()): LocalDateTime {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: LOCAL_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(now);
  const get = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? '00';
  return {
    date: `${get('year')}-${get('month')}-${get('day')}`,
    time: `${get('hour')}:${get('minute')}`,
  };
}

export function isValidDate(value: string): boolean {
  const match = DATE_RE.exec(value);
  if (!match) return false;
  const [, y, m, d] = match.map(Number) as [number, number, number, number];
  const date = new Date(Date.UTC(y, m - 1, d));
  return date.getUTCFullYear() === y && date.getUTCMonth() === m - 1 && date.getUTCDate() === d;
}

export function isValidTime(value: string): boolean {
  return TIME_RE.test(value);
}

/**
 * Format oczekiwany przez backend: ISO bez strefy, interpretowany jako Europe/Warsaw
 * (app/core/timezone.py).
 */
export function toBackendDateTime({ date, time }: LocalDateTime): string {
  return `${date}T${time}:00`;
}

/** Porównanie leksykograficzne działa dla stałego formatu YYYY-MM-DDTHH:MM. */
export function compareLocal(a: LocalDateTime, b: LocalDateTime): number {
  const left = `${a.date}T${a.time}`;
  const right = `${b.date}T${b.time}`;
  return left < right ? -1 : left > right ? 1 : 0;
}

/** Różnica w minutach (a − b) dla dwóch momentów w tej samej strefie lokalnej. */
export function minutesBetween(a: LocalDateTime, b: LocalDateTime): number {
  const toMinutes = ({ date, time }: LocalDateTime) =>
    Date.UTC(
      Number(date.slice(0, 4)),
      Number(date.slice(5, 7)) - 1,
      Number(date.slice(8, 10)),
      Number(time.slice(0, 2)),
      Number(time.slice(3, 5)),
    ) / 60000;
  return toMinutes(a) - toMinutes(b);
}
