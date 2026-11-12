import {
  Ban,
  CalendarCheck,
  CalendarX,
  ChevronDown,
  Clock,
  CloudSun,
  Leaf,
  Sigma,
  TriangleAlert,
  Trophy,
  Wallet,
} from 'lucide-react';
import type { ReactNode } from 'react';
import type { ModeEstimate } from '../types/api';
import { formatCo2, formatCost, formatDuration, formatTime } from '../utils/format';
import { COMFORT_LABELS } from '../utils/labels';
import type { MetricKey } from '../utils/results';
import type { TransitStatus } from '../utils/transit';
import { ModeIcon } from './ModeIcon';

interface VariantCardProps {
  variant: ModeEstimate;
  passengers: number;
  isRecommended: boolean;
  /** Liczba dostępnych wariantów (do „Miejsce 2 z 3”). */
  rankedCount: number;
  /** Metryki, w których wariant wypada najlepiej spośród dostępnych. */
  bestIn: MetricKey[];
  /** Tylko dla komunikacji miejskiej: zgodność z panelem rozkładu GTFS. */
  transit?: TransitStatus;
}

function MetricRow({
  icon,
  label,
  value,
  detail,
  best,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail?: string;
  best?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-2.5 @md:flex-col @md:items-start @md:gap-1 @md:py-0">
      <dt className="flex items-center gap-2 text-sm text-slate-400">
        {icon}
        {label}
      </dt>
      <dd className="text-right @md:text-left">
        <span className="flex flex-wrap items-center justify-end gap-x-2 @md:justify-start">
          {best && (
            <span className="rounded-md bg-accent-400/10 px-1.5 py-0.5 text-[11px] font-medium text-accent-300">
              {best}
            </span>
          )}
          <span className="text-xl font-semibold whitespace-nowrap text-white tabular-nums">
            {value}
          </span>
        </span>
        {detail && <span className="block text-xs text-slate-400 tabular-nums">{detail}</span>}
      </dd>
    </div>
  );
}

const COMFORT_STYLES = {
  good: 'text-emerald-300',
  reduced: 'text-amber-300',
  poor: 'text-rose-300',
} as const;

/** Pochodzenie czasu komunikacji miejskiej — rozkład vs szacunek (problem z ręcznych testów). */
function TransitNote({ status }: { status: TransitStatus }) {
  if (status.kind === 'confirmed') {
    const { connection } = status;
    return (
      <p className="flex items-start gap-2 rounded-lg bg-violet-400/10 px-3 py-2 text-sm text-violet-100">
        <CalendarCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-violet-300" />
        <span>
          <span className="font-medium">Czas z rozkładu GTFS</span>
          {connection && (
            <span className="block text-xs text-violet-200/80">
              Linia {connection.line}
              {connection.headsign && ` → ${connection.headsign}`}, odjazd{' '}
              {formatTime(connection.departure_at)}
            </span>
          )}
        </span>
      </p>
    );
  }

  const text =
    status.kind === 'no_connection'
      ? {
          title: 'Czas szacunkowy — brak potwierdzonego kursu GTFS',
          detail: `Nie znaleziono kursu bezpośredniego w ciągu ${status.windowMin} min. Połączeń z przesiadką aplikacja nie sprawdza.`,
        }
      : status.kind === 'schedule_unavailable'
        ? {
            title: 'Czas szacunkowy — nie sprawdzono rozkładu',
            detail: 'Rozkład GTFS był niedostępny, więc kursu nie potwierdzono.',
          }
        : {
            title: 'Czas szacunkowy (model parametryczny)',
            detail: 'Dystans ÷ średnia prędkość + czas dojścia i oczekiwania.',
          };

  return (
    <p className="flex items-start gap-2 rounded-lg bg-amber-400/10 px-3 py-2 text-sm text-amber-100">
      {status.kind === 'estimate' ? (
        <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-amber-300" />
      ) : (
        <CalendarX aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-amber-300" />
      )}
      <span>
        <span className="font-medium">{text.title}</span>
        <span className="block text-xs text-amber-100/75">{text.detail}</span>
      </span>
    </p>
  );
}

export function VariantCard({
  variant,
  passengers,
  isRecommended,
  rankedCount,
  bestIn,
  transit,
}: VariantCardProps) {
  const rank = variant.score?.rank;
  const perPassenger = passengers > 1;
  const isEstimate = variant.data_source === 'parametric_estimate';

  return (
    <article
      aria-labelledby={`variant-${variant.mode}`}
      className={`card @container flex w-full min-w-0 flex-col gap-3 p-5 animate-rise ${
        isRecommended ? 'border-accent-400/60 ring-1 ring-accent-400/30' : ''
      } ${variant.available ? '' : 'bg-navy-900/60'}`}
    >
      <header className="flex items-center gap-3">
        <ModeIcon mode={variant.mode} />
        <div className="min-w-0 flex-1">
          <h3 id={`variant-${variant.mode}`} className="text-base font-semibold text-white">
            {variant.label}
          </h3>
          <p className="text-xs text-slate-400">
            {variant.available
              ? rank
                ? `Miejsce ${rank} z ${rankedCount}`
                : 'Dostępny'
              : 'Niedostępny'}
          </p>
        </div>
        {isRecommended && (
          <span className="badge shrink-0 border-accent-400/50 bg-accent-400/15 py-1 text-accent-300">
            <Trophy aria-hidden="true" className="size-3.5" />
            Rekomendowany
          </span>
        )}
        {!variant.available && (
          <span className="badge shrink-0 border-navy-500 bg-navy-800 py-1 text-slate-300">
            <Ban aria-hidden="true" className="size-3.5" />
            Pominięty
          </span>
        )}
      </header>

      {variant.available ? (
        <dl className="divide-y divide-navy-700/70 @md:grid @md:grid-cols-3 @md:gap-4 @md:divide-y-0 @md:py-2">
          <MetricRow
            icon={<Clock aria-hidden="true" className="size-4" />}
            label={isEstimate ? 'Czas (szac.)' : 'Czas'}
            value={formatDuration(variant.estimated_duration_min)}
            best={bestIn.includes('duration') ? 'najkrótszy' : undefined}
          />
          <MetricRow
            icon={<Wallet aria-hidden="true" className="size-4" />}
            label="Koszt"
            value={formatCost(variant.estimated_cost_pln)}
            detail={
              perPassenger
                ? `${formatCost(variant.estimated_cost_per_passenger_pln)} / os.`
                : undefined
            }
            best={bestIn.includes('cost') ? 'najniższy' : undefined}
          />
          <MetricRow
            icon={<Leaf aria-hidden="true" className="size-4" />}
            label="CO₂"
            value={formatCo2(variant.estimated_co2_kg).replace(' CO₂', '')}
            detail={
              perPassenger
                ? `${formatCo2(variant.estimated_co2_per_passenger_kg).replace(' CO₂', '')} / os.`
                : undefined
            }
            best={bestIn.includes('co2') ? 'najniższa' : undefined}
          />
        </dl>
      ) : (
        <p className="rounded-lg bg-navy-800 px-3 py-2.5 text-sm text-slate-300">
          {variant.unavailable_reason ?? 'Wariant niedostępny dla tej podróży.'}
        </p>
      )}

      {variant.available && transit && <TransitNote status={transit} />}

      {variant.available && (variant.comfort_level || variant.score?.weather_demoted) && (
        <p className="flex items-center gap-2 text-sm text-slate-300">
          <CloudSun aria-hidden="true" className="size-4 shrink-0 text-sky-300" />
          {variant.comfort_level && (
            <span>
              Komfort przy pogodzie:{' '}
              <span className={`font-medium ${COMFORT_STYLES[variant.comfort_level]}`}>
                {COMFORT_LABELS[variant.comfort_level]}
              </span>
            </span>
          )}
          {variant.score?.weather_demoted && (
            <span className="text-rose-300">· przesunięty w rankingu</span>
          )}
        </p>
      )}

      <div className="mt-auto flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-t border-navy-700/70 pt-3">
        {!transit && (
          <span className="inline-flex items-center gap-1.5 text-xs text-slate-400">
            <Sigma aria-hidden="true" className="size-3.5" />
            {isEstimate ? 'Szacunek z modelu' : 'Rozkład GTFS'}
          </span>
        )}
        {variant.assumptions.length > 0 && (
          <details className="group w-full">
            <summary className="flex items-center justify-between gap-2 rounded text-xs font-medium text-slate-300 hover:text-white">
              Założenia i źródło danych ({variant.assumptions.length})
              <ChevronDown
                aria-hidden="true"
                className="size-4 transition-transform group-open:rotate-180"
              />
            </summary>
            <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-relaxed text-slate-400">
              {variant.assumptions.map((assumption) => (
                <li key={assumption}>{assumption}</li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </article>
  );
}
