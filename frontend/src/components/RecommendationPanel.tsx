import { Check, ChevronDown, CircleSlash, Info, TriangleAlert } from 'lucide-react';
import type { ComparisonResponse } from '../types/api';
import { formatCo2, formatCost, formatDuration } from '../utils/format';
import { COMFORT_LABELS, MODE_LABELS, priorityLabel } from '../utils/labels';
import { bestMetrics, splitExplanation, type BestMetric, type MetricKey } from '../utils/results';
import type { TransitStatus } from '../utils/transit';
import { ModeIcon } from './ModeIcon';

const BENEFIT_LABELS: Record<MetricKey, string> = {
  duration: 'Najkrótszy czas',
  cost: 'Najniższy koszt',
  co2: 'Najniższa emisja CO₂',
};

function benefitLabel({ metric, sharedWith }: BestMetric): string {
  if (sharedWith.length === 0) return BENEFIT_LABELS[metric];
  return `${BENEFIT_LABELS[metric]} (ex aequo z: ${sharedWith.map((mode) => MODE_LABELS[mode]).join(', ')})`;
}

/**
 * Warning shown when recommended public transport relies on an estimate, not a confirmed trip.
 * A missing direct trip does not mean public transport is unavailable, hence a warning
 * rather than a different recommendation (only the backend chooses that).
 */
function transitWarning(status: TransitStatus | undefined): string | null {
  if (!status || status.kind === 'confirmed') return null;
  const reason =
    status.kind === 'no_connection'
      ? `nie znaleziono potwierdzonego kursu bezpośredniego GTFS w ciągu ${status.windowMin} min, a połączeń z przesiadkami aplikacja nie sprawdza`
      : status.kind === 'schedule_unavailable'
        ? 'nie udało się sprawdzić rozkładu GTFS'
        : 'czas nie pochodzi z rozkładu GTFS';
  return `Komunikacja miejska jest rekomendowana na podstawie czasu szacunkowego: ${reason}. Rekomendacja nie gwarantuje dostępnego połączenia — sprawdź rozkład przed wyjazdem.`;
}

interface RecommendationPanelProps {
  comparison: ComparisonResponse;
  /** Public transport time status (the same as in the card and the departures panel). */
  transit?: TransitStatus;
}

/**
 * The recommendation comes only from the backend. The frontend merely describes the data:
 * which metrics the recommended option is best at, plus explicit warnings.
 */
export function RecommendationPanel({ comparison, transit }: RecommendationPanelProps) {
  const { recommendation, scoring, variants } = comparison;
  const winner = variants.find((variant) => variant.mode === recommendation.mode);
  const benefits = recommendation.mode ? (bestMetrics(variants).get(recommendation.mode) ?? []) : [];
  const { lead } = splitExplanation(recommendation.explanation);

  const transitText = recommendation.mode === 'public_transport' ? transitWarning(transit) : null;
  const tieOrder = scoring.tie_break_order.map((mode) => MODE_LABELS[mode].toLowerCase()).join(' → ');

  const warnings: { key: string; tone: 'warning' | 'info'; text: string }[] = [
    ...(transitText ? [{ key: 'transit-estimate', tone: 'warning' as const, text: transitText }] : []),
    ...variants
      .filter((variant) => variant.available && variant.comfort_level && variant.comfort_level !== 'good')
      .map((variant) => ({
        key: `comfort-${variant.mode}`,
        tone: 'warning' as const,
        text: `${variant.label}: komfort przy bieżącej pogodzie ${COMFORT_LABELS[variant.comfort_level!]}${
          variant.score?.weather_demoted ? ' — przesunięty na koniec rankingu' : ''
        }.`,
      })),
    ...variants
      .filter((variant) => !variant.available)
      .map((variant) => ({
        key: `unavailable-${variant.mode}`,
        tone: 'info' as const,
        text: `${variant.label} pominięty: ${(variant.unavailable_reason ?? 'niedostępny').replace(/\.$/, '')}.`,
      })),
    ...(recommendation.tie_break_applied
      ? [
          {
            key: 'tie',
            tone: 'info' as const,
            text: `Remis — rozstrzygnięto stałą kolejnością: ${tieOrder}.`,
          },
        ]
      : []),
  ];

  return (
    <section aria-labelledby="recommendation-title" className="card p-5 animate-rise sm:p-6">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 items-start gap-4">
          {recommendation.mode ? (
            <ModeIcon mode={recommendation.mode} size="lg" />
          ) : (
            <CircleSlash aria-hidden="true" className="size-12 shrink-0 text-slate-500" />
          )}
          <div className="min-w-0">
            <p className="text-xs font-semibold tracking-wider text-accent-300 uppercase">
              Rekomendacja · {priorityLabel(comparison.priority)}
            </p>
            <h2 id="recommendation-title" className="mt-0.5 text-2xl font-bold tracking-tight text-white">
              {recommendation.label ?? 'Brak rekomendacji'}
            </h2>
            <p className="mt-1 max-w-2xl text-sm leading-relaxed text-slate-300">{lead}</p>
            {benefits.length > 0 && (
              <ul className="mt-2.5 flex flex-wrap gap-1.5" aria-label="Najważniejsze korzyści">
                {benefits.map((benefit) => (
                  <li
                    key={benefit.metric}
                    className="badge border-accent-400/30 bg-accent-400/10 py-1 text-accent-300"
                  >
                    <Check aria-hidden="true" className="size-3.5" />
                    {benefitLabel(benefit)}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {winner && (
          <dl className="grid shrink-0 grid-cols-3 divide-x divide-navy-700 rounded-xl bg-navy-900/70 py-3 text-center">
            {[
              ['Czas', formatDuration(winner.estimated_duration_min)],
              ['Koszt', formatCost(winner.estimated_cost_pln)],
              ['CO₂', formatCo2(winner.estimated_co2_kg).replace(' CO₂', '')],
            ].map(([label, value]) => (
              <div key={label} className="px-3 sm:px-6">
                <dt className="text-xs text-slate-400">{label}</dt>
                <dd className="mt-0.5 text-base font-semibold whitespace-nowrap text-white tabular-nums sm:text-lg">
                  {value}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </div>

      {warnings.length > 0 && (
        <ul className="mt-4 space-y-1.5">
          {warnings.map((warning) => (
            <li
              key={warning.key}
              className={`flex items-start gap-2 text-sm ${
                warning.tone === 'warning' ? 'text-amber-200' : 'text-slate-300'
              }`}
            >
              {warning.tone === 'warning' ? (
                <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-amber-300" />
              ) : (
                <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-sky-300" />
              )}
              <span>
                <span className="sr-only">{warning.tone === 'warning' ? 'Ostrzeżenie: ' : 'Uwaga: '}</span>
                {warning.text}
              </span>
            </li>
          ))}
        </ul>
      )}

      <details className="group mt-4 border-t border-navy-700 pt-3">
        <summary className="flex items-center gap-2 rounded text-sm font-medium text-slate-300 hover:text-white">
          <ChevronDown aria-hidden="true" className="size-4 transition-transform group-open:rotate-180" />
          Pełne uzasadnienie i metoda
        </summary>
        <div className="mt-3 grid gap-4 text-sm leading-relaxed lg:grid-cols-2">
          <div>
            <h3 className="font-medium text-white">Uzasadnienie</h3>
            <p className="mt-1 text-slate-300">{recommendation.explanation}</p>
          </div>
          <div>
            <h3 className="font-medium text-white">Metoda ({priorityLabel(scoring.priority).toLowerCase()})</h3>
            <p className="mt-1 text-slate-400">{scoring.description}</p>
            <p className="mt-1 text-slate-400">{scoring.comfort_rule}</p>
          </div>
        </div>
      </details>
    </section>
  );
}
