import { CircleQuestionMark, MapPin, Route } from 'lucide-react';
import type { BackendStatus } from '../hooks/useBackendHealth';
import { Spinner } from './ui/Spinner';

const STATUS: Record<BackendStatus, { label: string; dot: string }> = {
  checking: { label: 'Sprawdzanie backendu…', dot: 'bg-slate-400' },
  online: { label: 'Backend połączony', dot: 'bg-emerald-400' },
  degraded: { label: 'Backend: problem z bazą', dot: 'bg-amber-400' },
  offline: { label: 'Backend niedostępny', dot: 'bg-rose-400' },
};

export function Header({ backendStatus }: { backendStatus: BackendStatus }) {
  const status = STATUS[backendStatus];
  return (
    <header className="border-b border-navy-700/70 bg-navy-950/70 backdrop-blur">
      <div className="mx-auto flex max-w-[90rem] flex-wrap items-center justify-between gap-x-6 gap-y-3 px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-3">
          <span className="inline-flex size-10 items-center justify-center rounded-xl bg-linear-to-br from-accent-400 to-sky-500 text-navy-950 shadow-lg shadow-accent-500/20">
            <Route aria-hidden="true" className="size-5" />
          </span>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white">
              Smart<span className="text-accent-400">Route</span>
            </h1>
            <p className="text-xs text-slate-400 sm:text-sm">
              Porównaj samochód, komunikację miejską i rower — czas, koszt i emisję CO₂.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="badge border-navy-600 bg-navy-800 text-slate-300">
            <MapPin aria-hidden="true" className="size-3.5 text-accent-400" />
            Gdańsk i okolice
          </span>
          <span
            className="badge border-navy-600 bg-navy-800 text-slate-300"
            role="status"
            aria-live="polite"
          >
            {backendStatus === 'checking' ? (
              <Spinner className="size-3" />
            ) : (
              <span aria-hidden="true" className={`size-2 rounded-full ${status.dot}`} />
            )}
            {status.label}
          </span>
          <a href="#pomoc" className="btn btn-ghost text-xs">
            <CircleQuestionMark aria-hidden="true" className="size-4" />
            Jak to działa?
          </a>
        </div>
      </div>
    </header>
  );
}
