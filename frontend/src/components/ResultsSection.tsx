import { CalendarDays, Info, MapPin, Pencil, Ruler, Users } from 'lucide-react';
import type { ComparisonResult } from '../hooks/useComparison';
import type { TripPriority } from '../types/api';
import { formatDateTime, formatDistance } from '../utils/format';
import { bestMetrics, passengersLabel, sortVariants } from '../utils/results';
import { transitStatus } from '../utils/transit';
import { PrioritySelector } from './PrioritySelector';
import { RecommendationPanel } from './RecommendationPanel';
import { SchedulePanel } from './SchedulePanel';
import { Spinner } from './ui/Spinner';
import { VariantCard } from './VariantCard';
import { WeatherPanel } from './WeatherPanel';

interface ResultsSectionProps {
  result: ComparisonResult;
  isRefreshing: boolean;
  onPriorityChange: (priority: TripPriority) => void;
  /** Przenosi do formularza (zmiana przystanków, daty, godziny). */
  onEditTrip: () => void;
}

export function ResultsSection({
  result,
  isRefreshing,
  onPriorityChange,
  onEditTrip,
}: ResultsSectionProps) {
  const { comparison, trip, schedule } = result;
  const variants = sortVariants(comparison.variants);
  const best = bestMetrics(comparison.variants);
  const rankedCount = comparison.variants.filter((variant) => variant.available).length;
  const transitVariant = comparison.variants.find((variant) => variant.mode === 'public_transport');
  // Jedno źródło prawdy dla karty komunikacji i panelu odjazdów.
  const transit = transitVariant ? transitStatus(transitVariant, schedule) : undefined;
  const usedConnection = transit?.kind === 'confirmed' ? transit.connection : null;

  return (
    <div className="space-y-5" aria-busy={isRefreshing}>
      <section
        aria-label="Podsumowanie podróży"
        className="flex flex-col gap-4 rounded-2xl border border-navy-700 bg-navy-900/60 px-4 py-3 sm:px-5 xl:flex-row xl:items-center xl:justify-between"
      >
        <div className="min-w-0">
          <p className="flex min-w-0 items-center gap-2 font-semibold text-white">
            <MapPin aria-hidden="true" className="size-4 shrink-0 text-accent-400" />
            <span className="min-w-0 break-words">
              {trip.origin} <span className="text-slate-500">→</span> {trip.destination}
            </span>
          </p>
          <p className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-400">
            {trip.departure_at && (
              <span className="inline-flex items-center gap-1.5">
                <CalendarDays aria-hidden="true" className="size-3.5" />
                {formatDateTime(trip.departure_at)}
              </span>
            )}
            <span className="inline-flex items-center gap-1.5">
              <Ruler aria-hidden="true" className="size-3.5" />
              {formatDistance(comparison.distance_km)} (szacunkowo)
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Users aria-hidden="true" className="size-3.5" />
              {passengersLabel(comparison.passengers)}
            </span>
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <span id="quick-priority" className="flex items-center gap-2 text-xs text-slate-400">
            Priorytet
            {isRefreshing && <Spinner className="size-3" label="Przeliczanie" />}
          </span>
          <PrioritySelector
            variant="compact"
            name="quick-priority"
            labelledBy="quick-priority"
            value={comparison.priority}
            onChange={onPriorityChange}
            disabled={isRefreshing}
          />
          <button type="button" className="btn btn-ghost text-sm" onClick={onEditTrip}>
            <Pencil aria-hidden="true" className="size-4" />
            Edytuj
          </button>
        </div>
      </section>

      <div className={`space-y-5 transition-opacity ${isRefreshing ? 'opacity-60' : ''}`}>
        <RecommendationPanel comparison={comparison} />

        <section aria-labelledby="variants-title">
          <h2 id="variants-title" className="sr-only">
            Porównanie wariantów
          </h2>
          {/* 3 kolumny tylko od xl (karta ≥ ~19rem); 2 + 1 na tabletach, 1 na telefonach. */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {variants.map((variant, index) => (
              <div
                key={variant.mode}
                className={`flex min-w-0 ${
                  index === variants.length - 1 && variants.length % 2 === 1
                    ? 'md:col-span-2 xl:col-span-1'
                    : ''
                }`}
              >
                <VariantCard
                  variant={variant}
                  passengers={comparison.passengers}
                  isRecommended={variant.mode === comparison.recommendation.mode}
                  rankedCount={rankedCount}
                  bestIn={best.get(variant.mode) ?? []}
                  transit={variant.mode === 'public_transport' ? transit : undefined}
                />
              </div>
            ))}
          </div>
        </section>

        <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <SchedulePanel schedule={schedule} usedConnection={usedConnection} onEditTrip={onEditTrip} />
          <WeatherPanel weather={comparison.weather} />
        </div>

        <p className="flex gap-2 text-xs leading-relaxed text-slate-500">
          <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          {comparison.disclaimer}
        </p>
      </div>
    </div>
  );
}
