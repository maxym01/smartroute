import { describe, expect, it } from 'vitest';
import type { Connection, ConnectionList, ModeEstimate } from '../types/api';
import { splitExplanation } from './results';
import { backendDepartureLabel, findUsedConnection, transitStatus } from './transit';

const base = {
  mode: 'public_transport',
  label: 'Komunikacja miejska',
  available: true,
  unavailable_reason: null,
  estimated_duration_min: 25,
  estimated_cost_pln: 4.4,
  estimated_cost_per_passenger_pln: 4.4,
  estimated_co2_kg: 0.28,
  estimated_co2_per_passenger_kg: 0.28,
  is_estimate: true,
  score: null,
  comfort_level: null,
} as const;

const scheduled: ModeEstimate = {
  ...base,
  data_source: 'gtfs_schedule',
  assumptions: ['Czas z rozkładu GTFS: linia 2 w kierunku Strzyża PKM, odjazd 12.11.2026 18:57 z przystanku Dworzec Główny 01.'],
};
const estimated: ModeEstimate = { ...base, data_source: 'parametric_estimate', assumptions: [] };

const conn = (line: string, departure: string): Connection => ({
  trip_id: `${line}-${departure}`,
  route_id: line,
  line,
  route_type: 900,
  headsign: null,
  direction_id: null,
  service_date: '2026-11-12',
  departure_at: departure,
  arrival_at: departure,
  duration_min: 22,
  origin_stop_sequence: 1,
  destination_stop_sequence: 2,
});

const list = (connections: Connection[]) => ({ connections, window_min: 180 }) as unknown as ConnectionList;

describe('transitStatus', () => {
  it('formatuje odjazd tak jak backend w założeniach', () => {
    expect(backendDepartureLabel('2026-11-12T17:57:00Z')).toBe('12.11.2026 18:57');
  });

  it('dopasowuje kurs po linii i godzinie odjazdu', () => {
    const other = conn('8', '2026-11-12T18:57:00+01:00'); // same time, different line
    const used = conn('2', '2026-11-12T18:57:00+01:00');
    expect(findUsedConnection(scheduled, [other, used])).toBe(used);
    expect(findUsedConnection(estimated, [used])).toBeNull();
  });

  it('rozróżnia potwierdzony kurs, brak kursu i niedostępny rozkład', () => {
    const used = conn('2', '2026-11-12T18:57:00+01:00');
    expect(transitStatus(scheduled, { status: 'success', data: list([used]) })).toEqual({ kind: 'confirmed', connection: used });
    expect(transitStatus(estimated, { status: 'success', data: list([]) })).toEqual({ kind: 'no_connection', windowMin: 180 });
    expect(transitStatus(estimated, { status: 'error', error: null })).toEqual({ kind: 'schedule_unavailable' });
    expect(transitStatus(estimated, { status: 'success', data: list([used]) })).toEqual({ kind: 'estimate' });
  });
});

describe('splitExplanation', () => {
  it('nie dzieli zdania na skrócie „ok.”', () => {
    const { lead, rest } = splitExplanation(
      'Rower to najszybszy dostępny wariant: ok. 22 min. Względem wariantu „Samochód”: 9 min dłużej.',
    );
    expect(lead).toBe('Rower to najszybszy dostępny wariant: ok. 22 min.');
    expect(rest).toBe('Względem wariantu „Samochód”: 9 min dłużej.');
  });
});
