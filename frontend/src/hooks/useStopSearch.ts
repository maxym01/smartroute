import { useEffect, useState } from 'react';
import { isAbortError } from '../services/apiClient';
import { searchStops, STOP_QUERY_MIN_LENGTH } from '../services/smartrouteApi';
import type { Stop } from '../types/api';

export type StopSearchState =
  | { status: 'idle'; items: Stop[] }
  | { status: 'loading'; items: Stop[] }
  | { status: 'success'; items: Stop[] }
  | { status: 'error'; items: Stop[]; error: unknown };

const DEBOUNCE_MS = 250;

/** Wyszukiwanie przystanków GTFS z opóźnieniem i anulowaniem nieaktualnych żądań. */
export function useStopSearch(query: string, enabled = true): StopSearchState {
  const [state, setState] = useState<StopSearchState>({ status: 'idle', items: [] });
  const trimmed = query.trim();
  const active = enabled && trimmed.length >= STOP_QUERY_MIN_LENGTH;

  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setState((prev) => ({ status: 'loading', items: prev.items }));
      searchStops(trimmed, controller.signal)
        .then((result) => setState({ status: 'success', items: result.items }))
        .catch((error: unknown) => {
          if (!isAbortError(error)) setState({ status: 'error', items: [], error });
        });
    }, DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [trimmed, active]);

  return active ? state : { status: 'idle', items: [] };
}
