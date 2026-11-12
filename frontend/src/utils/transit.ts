import type { ScheduleState } from '../hooks/useComparison';
import type { Connection, ModeEstimate } from '../types/api';
import { LOCAL_TIME_ZONE } from './format';

/**
 * Jak interpretować wariant „Komunikacja miejska” względem panelu rozkładu.
 *
 * - `confirmed` — backend policzył czas z rozkładu GTFS (`gtfs_schedule`); `connection` to kurs
 *   z panelu, który odpowiada założeniom backendu (linia i godzina odjazdu), jeśli udało się go
 *   jednoznacznie dopasować.
 * - `no_connection` — szacunek parametryczny, a rozkład potwierdził brak kursu bezpośredniego
 *   w oknie wyszukiwania. Nie oznacza to braku połączenia z przesiadką.
 * - `schedule_unavailable` — szacunek parametryczny, a rozkładu nie udało się sprawdzić.
 * - `estimate` — szacunek parametryczny z innego powodu (np. backend nie użył rozkładu).
 */
export type TransitStatus =
  | { kind: 'confirmed'; connection: Connection | null }
  | { kind: 'no_connection'; windowMin: number }
  | { kind: 'schedule_unavailable' }
  | { kind: 'estimate' };

/** „12.11.2026 19:11” — format, którego backend używa w założeniach (gtfs_transit.py). */
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

/** Kurs z panelu rozkładu, którego użył backend — dopasowany po linii i godzinie odjazdu. */
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
