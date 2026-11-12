import { RefreshCw } from 'lucide-react';
import { useCallback, useRef, useState } from 'react';
import { EmptyState } from '../components/EmptyState';
import { Header } from '../components/Header';
import { HelpPanel } from '../components/HelpPanel';
import { ResultsSection } from '../components/ResultsSection';
import { TripForm } from '../components/TripForm';
import { Alert } from '../components/ui/Alert';
import { Spinner } from '../components/ui/Spinner';
import { useBackendHealth } from '../hooks/useBackendHealth';
import { useComparison } from '../hooks/useComparison';
import { ApiError } from '../services/apiClient';
import type { TripCreate, TripPriority } from '../types/api';
import { describeError, mapValidationIssues } from '../utils/errors';
import {
  defaultFormValues,
  FIELD_IDS,
  toTripPayload,
  type TripFormErrors,
  type TripFormValues,
} from '../utils/tripForm';

const PHASE_LABELS = {
  saving: 'Zapisywanie podróży…',
  comparing: 'Obliczanie porównania…',
} as const;

function ResultsSkeleton() {
  return (
    <div className="space-y-5" aria-hidden="true">
      <div className="h-16 animate-pulse rounded-2xl bg-navy-900/60" />
      <div className="card h-40 animate-pulse" />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {[0, 1, 2].map((key) => (
          <div key={key} className="card h-64 animate-pulse" />
        ))}
      </div>
    </div>
  );
}

export function DashboardPage() {
  const [values, setValues] = useState<TripFormValues>(() => defaultFormValues());
  const [serverErrors, setServerErrors] = useState<TripFormErrors>({});
  const { status: backendStatus, retry: retryHealth, report: reportBackend } = useBackendHealth();
  const { phase, isLoading, result, error, run } = useComparison();
  const [lastPayload, setLastPayload] = useState<TripCreate | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);
  const [announcement, setAnnouncement] = useState('');

  const updateValues = useCallback((patch: Partial<TripFormValues>) => {
    setValues((current) => ({ ...current, ...patch }));
    // Błąd z serwera dotyczy wysłanej wartości — po edycji pola go ukrywamy.
    setServerErrors((current) => {
      const next = { ...current };
      for (const key of Object.keys(patch)) {
        delete next[key as keyof TripFormErrors];
        if (key === 'time') delete next.date;
      }
      return next;
    });
  }, []);

  const execute = useCallback(
    async (payload: TripCreate) => {
      setLastPayload(payload);
      setServerErrors({});
      setAnnouncement(PHASE_LABELS.comparing);
      const outcome = await run(payload);
      if (outcome.ok) {
        reportBackend(true);
        setAnnouncement('Porównanie gotowe. Wyniki poniżej.');
        // Wyniki są pod formularzem — przewijamy do nich, jeśli zaczynają się poniżej połowy ekranu.
        const top = resultsRef.current?.getBoundingClientRect().top ?? 0;
        if (top > window.innerHeight * 0.5) {
          resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      } else if ('error' in outcome) {
        setAnnouncement('Nie udało się wykonać porównania.');
        const caught = outcome.error;
        // Błędy 422 trafiają do konkretnych pól, brak sieci aktualizuje status backendu.
        if (caught instanceof ApiError && caught.kind === 'validation') {
          setServerErrors(mapValidationIssues(caught.issues).fields);
        }
        if (caught instanceof ApiError && caught.kind === 'network') reportBackend(false);
      }
    },
    [run, reportBackend],
  );

  const handleSubmit = () => {
    void execute(toTripPayload(values));
  };

  // Szybkie przeliczenie dla ostatnio wysłanej podróży — bez ponownej walidacji formularza.
  const handlePriorityChange = (priority: TripPriority) => {
    updateValues({ priority });
    if (lastPayload) void execute({ ...lastPayload, priority });
  };

  // Powrót do formularza: przewinięcie i focus na pierwszym polu (heurystyka 3).
  const editTrip = () => {
    document.getElementById('trip-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    document.getElementById(FIELD_IDS.origin)?.focus({ preventScroll: true });
  };

  const retry = () => {
    if (lastPayload) void execute(lastPayload);
  };

  const errorInfo = phase === 'error' ? describeError(error, 'compare') : null;
  const progressLabel = phase === 'saving' || phase === 'comparing' ? PHASE_LABELS[phase] : undefined;

  return (
    <>
      <a
        href="#trip-form"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-accent-400 focus:px-3 focus:py-2 focus:text-navy-950"
      >
        Przejdź do formularza
      </a>
      <Header backendStatus={backendStatus} />

      <main className="mx-auto max-w-[90rem] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <p className="sr-only" role="status" aria-live="polite">
          {announcement}
        </p>

        {backendStatus === 'offline' && (
          <Alert
            tone="error"
            title="Backend jest niedostępny"
            className="mb-6"
            action={
              <button type="button" className="btn btn-secondary py-1.5 text-xs" onClick={retryHealth}>
                <RefreshCw aria-hidden="true" className="size-3.5" />
                Sprawdź ponownie
              </button>
            }
          >
            <p>
              Uruchom backend poleceniem <code className="rounded bg-navy-800 px-1">.\run.ps1</code>{' '}
              w katalogu projektu. Wyszukiwanie przystanków i porównanie zadziałają po jego
              uruchomieniu, a wprowadzone dane zostaną zachowane.
            </p>
          </Alert>
        )}

        <div id="trip-form" className="scroll-mt-4">
          <TripForm
            values={values}
            onChange={updateValues}
            onSubmit={handleSubmit}
            isSubmitting={isLoading}
            serverErrors={serverErrors}
            progressLabel={progressLabel}
            hasResults={result !== null}
          />
        </div>

        <div ref={resultsRef} className="mt-6 min-w-0 scroll-mt-4 space-y-5">
          {errorInfo && (
            <Alert
              tone="error"
              role="alert"
              title={errorInfo.title}
              action={
                lastPayload && (
                  <button type="button" className="btn btn-secondary py-1.5 text-xs" onClick={retry}>
                    <RefreshCw aria-hidden="true" className="size-3.5" />
                    Spróbuj ponownie
                  </button>
                )
              }
            >
              <p>{errorInfo.message}</p>
              {errorInfo.hints.length > 0 && (
                <ul className="list-disc space-y-0.5 pl-4 text-slate-300">
                  {errorInfo.hints.map((hint) => (
                    <li key={hint}>{hint}</li>
                  ))}
                </ul>
              )}
            </Alert>
          )}

          {isLoading && !result && (
            <>
              <p className="flex items-center gap-2 text-sm text-slate-300">
                <Spinner className="size-4 text-accent-400" />
                {progressLabel}
              </p>
              <ResultsSkeleton />
            </>
          )}

          {result && (
            <ResultsSection
              result={result}
              isRefreshing={isLoading}
              onPriorityChange={handlePriorityChange}
              onEditTrip={editTrip}
            />
          )}

          {!result && !isLoading && !errorInfo && <EmptyState />}
        </div>

        <div className="mt-12 border-t border-navy-700/70 pt-8">
          <HelpPanel />
        </div>
      </main>

      <footer className="mx-auto max-w-[90rem] px-4 pb-8 text-xs text-slate-500 sm:px-6 lg:px-8">
        SmartRoute AI · dane: GTFS Static ZTM Gdańsk, Weatherbit Current · wartości szacunkowe
      </footer>
    </>
  );
}
