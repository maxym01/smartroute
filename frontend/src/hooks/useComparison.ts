import { useCallback, useRef, useState } from 'react';
import { ApiError } from '../services/apiClient';
import { compareTrip, createTrip, findConnections } from '../services/smartrouteApi';
import type { ComparisonResponse, ConnectionList, TripCreate, TripRead } from '../types/api';

export type ScheduleState =
  | { status: 'loading' }
  | { status: 'success'; data: ConnectionList }
  | { status: 'error'; error: unknown };

export interface ComparisonResult {
  trip: TripRead;
  comparison: ComparisonResponse;
  schedule: ScheduleState;
}

export type ComparisonPhase = 'idle' | 'saving' | 'comparing' | 'success' | 'error';

export type RunOutcome = { ok: true } | { ok: false; error: unknown } | { ok: false; stale: true };

/** Trip key without the priority: changing only the priority does not create a new trip. */
function tripKey(payload: TripCreate): string {
  const { priority: _priority, ...rest } = payload;
  return JSON.stringify(rest);
}

/**
 * Flow: POST /trips → GET /trips/{id}/compare, with GET /connections in parallel
 * (trip list for the timetable panel — /compare returns only the best trip in its assumptions).
 */
export function useComparison() {
  const [phase, setPhase] = useState<ComparisonPhase>('idle');
  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [error, setError] = useState<unknown>(null);
  const lastTrip = useRef<{ key: string; trip: TripRead } | null>(null);
  const requestId = useRef(0);

  const run = useCallback(async (payload: TripCreate): Promise<RunOutcome> => {
    const id = ++requestId.current;
    const isCurrent = () => id === requestId.current;
    setError(null);

    try {
      const key = tripKey(payload);
      let trip = lastTrip.current?.key === key ? lastTrip.current.trip : null;
      if (!trip) {
        setPhase('saving');
        trip = await createTrip(payload);
        lastTrip.current = { key, trip };
      }
      if (!isCurrent()) return { ok: false, stale: true };

      setPhase('comparing');
      const schedulePromise: Promise<ScheduleState> =
        payload.origin_stop_id && payload.destination_stop_id && payload.departure_at
          ? findConnections({
              originStopId: payload.origin_stop_id,
              destinationStopId: payload.destination_stop_id,
              departureAt: payload.departure_at,
            }).then(
              (data): ScheduleState => ({ status: 'success', data }),
              (scheduleError: unknown): ScheduleState => ({ status: 'error', error: scheduleError }),
            )
          : Promise.resolve({ status: 'error', error: null });

      // A saved trip has a saved priority; when it is reused, the query parameter overrides it.
      const comparison = await compareTrip(trip.id, payload.priority);
      const schedule = await schedulePromise;
      if (!isCurrent()) return { ok: false, stale: true };

      setResult({ trip, comparison, schedule });
      setPhase('success');
      return { ok: true };
    } catch (caught) {
      if (!isCurrent()) return { ok: false, stale: true };
      if (caught instanceof ApiError && caught.kind === 'not_found') lastTrip.current = null;
      setError(caught);
      setPhase('error');
      return { ok: false, error: caught };
    }
  }, []);

  return {
    phase,
    isLoading: phase === 'saving' || phase === 'comparing',
    result,
    error,
    run,
  };
}
