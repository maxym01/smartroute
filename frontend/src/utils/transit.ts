import type { ScheduleState } from '../hooks/useComparison';
import type { Connection, ModeEstimate } from '../types/api';
import { LOCAL_TIME_ZONE } from './format';

/**
 * How to interpret the "Komunikacja miejska" (public transport) option against the timetable panel.
 *
 * - `confirmed` — the backend computed the time from the GTFS timetable (`gtfs_schedule`);
 *   `connection` is the panel trip that matches the backend assumptions (line and departure
 *   time), if it could be matched unambiguously.
 * - `no_connection` — parametric estimate, and the timetable confirmed there is no direct trip
 *   in the search window. This does not rule out a connection with a transfer.
 * - `schedule_unavailable` — parametric estimate, and the timetable could not be checked.
 * - `estimate` — parametric estimate for another reason (e.g. the backend did not use the timetable).
 */
export type TransitStatus =
  | { kind: 'confirmed'; connection: Connection | null }
  | { kind: 'no_connection'; windowMin: number }
  | { kind: 'schedule_unavailable' }
  | { kind: 'estimate' };

/** "12.11.2026 19:11" — the format the backend uses in its assumptions (gtfs_transit.py). */
export function backendDepartureLabel(iso: string): string {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: LOCAL_TIME_ZONE,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(iso));
  const get = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? '';
  return `${get('day')}.${get('month')}.${get('year')} ${get('hour')}:${get('minute')}`;
}

/** The timetable panel trip the backend used — matched by line and departure time. */
export function findUsedConnection(
  variant: ModeEstimate,
  connections: Connection[],
): Connection | null {
  if (variant.data_source !== 'gtfs_schedule') return null;
  const text = variant.assumptions.join(' ');
  return (
    connections.find(
      (connection) =>
        text.includes(`linia ${connection.line}`) &&
        text.includes(`odjazd ${backendDepartureLabel(connection.departure_at)}`),
    ) ?? null
  );
}

export function transitStatus(variant: ModeEstimate, schedule: ScheduleState): TransitStatus {
  if (variant.data_source === 'gtfs_schedule') {
    const connections = schedule.status === 'success' ? schedule.data.connections : [];
    return { kind: 'confirmed', connection: findUsedConnection(variant, connections) };
  }
  if (schedule.status === 'success' && schedule.data.connections.length === 0) {
    return { kind: 'no_connection', windowMin: schedule.data.window_min };
  }
  if (schedule.status === 'error') return { kind: 'schedule_unavailable' };
  return { kind: 'estimate' };
}
