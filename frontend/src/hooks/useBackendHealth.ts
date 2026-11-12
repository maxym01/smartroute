import { useCallback, useEffect, useState } from 'react';
import { isAbortError } from '../services/apiClient';
import { getHealth } from '../services/smartrouteApi';

export type BackendStatus = 'checking' | 'online' | 'degraded' | 'offline';

/** Sprawdza dostępność backendu przy starcie i na żądanie (heurystyki 1 i 9). */
export function useBackendHealth() {
  const [status, setStatus] = useState<BackendStatus>('checking');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal)
      .then((health) => setStatus(health.status === 'ok' ? 'online' : 'degraded'))
      .catch((error: unknown) => {
        if (!isAbortError(error)) setStatus('offline');
      });
    return () => controller.abort();
  }, [attempt]);

  const retry = useCallback(() => {
    setStatus('checking');
    setAttempt((value) => value + 1);
  }, []);

  /** Pozwala oznaczyć backend jako dostępny/niedostępny na podstawie innych żądań. */
  const report = useCallback((online: boolean) => setStatus(online ? 'online' : 'offline'), []);

  return { status, retry, report };
}
