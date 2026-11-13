import { LOCAL_TIME_ZONE } from './format';

export interface LocalDateTime {
  /** YYYY-MM-DD */
  date: string;
  /** HH:MM */
  time: string;
}

const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
const TIME_RE = /^([01]\d|2[0-3]):([0-5]\d)$/;

/** Current date and time in Europe/Warsaw, regardless of the browser's time zone. */
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
 * Format expected by the backend: ISO without a time zone, read as Europe/Warsaw
 * (app/core/timezone.py).
 */
export function toBackendDateTime({ date, time }: LocalDateTime): string {
  return `${date}T${time}:00`;
}

/** Lexicographic comparison works for the fixed YYYY-MM-DDTHH:MM format. */
export function compareLocal(a: LocalDateTime, b: LocalDateTime): number {
  const left = `${a.date}T${a.time}`;
  const right = `${b.date}T${b.time}`;
  return left < right ? -1 : left > right ? 1 : 0;
}

/** Difference in minutes (a − b) between two moments in the same local time zone. */
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
