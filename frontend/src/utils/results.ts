import type { ModeEstimate, TransportMode } from '../types/api';
import { formatCo2, formatCost, formatDuration } from './format';

export type MetricKey = 'duration' | 'cost' | 'co2';

/** A metric in which the option is the best; `sharedWith` ≠ [] means a tie (ex aequo). */
export interface BestMetric {
  metric: MetricKey;
  sharedWith: TransportMode[];
}

const METRIC_VALUE: Record<MetricKey, (variant: ModeEstimate) => number> = {
  duration: (variant) => variant.estimated_duration_min,
  cost: (variant) => variant.estimated_cost_pln,
  co2: (variant) => variant.estimated_co2_kg,
};

// Values are compared as the user sees them (e.g. 13.2 and 13.4 min → "13 min"),
// so that the "shortest" badge never singles out one of two identical-looking numbers.
const METRIC_DISPLAY: Record<MetricKey, (value: number) => string> = {
  duration: formatDuration,
  cost: formatCost,
  co2: formatCo2,
};

/**
 * Finds the best value of each metric among the available options.
 * This only describes the backend data — the backend decides the recommendation.
 */
export function bestMetrics(variants: ModeEstimate[]): Map<TransportMode, BestMetric[]> {
  const available = variants.filter((variant) => variant.available);
  const result = new Map<TransportMode, BestMetric[]>();
  if (available.length < 2) return result;
  for (const metric of Object.keys(METRIC_VALUE) as MetricKey[]) {
    const shown = (variant: ModeEstimate) => METRIC_DISPLAY[metric](METRIC_VALUE[metric](variant));
    const best = METRIC_DISPLAY[metric](Math.min(...available.map(METRIC_VALUE[metric])));
    const leaders = available.filter((variant) => shown(variant) === best);
    if (leaders.length === available.length) continue; // all equal — highlight nothing
    for (const variant of leaders) {
      const sharedWith = leaders.filter((other) => other !== variant).map((other) => other.mode);
      result.set(variant.mode, [...(result.get(variant.mode) ?? []), { metric, sharedWith }]);
    }
  }
  return result;
}

/** Available options in backend ranking order, unavailable ones last. */
export function sortVariants(variants: ModeEstimate[]): ModeEstimate[] {
  const rank = (variant: ModeEstimate) => variant.score?.rank ?? Number.POSITIVE_INFINITY;
  return [...variants].sort((a, b) => rank(a) - rank(b));
}

export function passengersLabel(count: number): string {
  if (count === 1) return '1 osoba';
  const lastDigit = count % 10;
  const lastTwo = count % 100;
  const few = lastDigit >= 2 && lastDigit <= 4 && (lastTwo < 12 || lastTwo > 14);
  return `${count} ${few ? 'osoby' : 'osób'}`;
}

/**
 * First sentence of the backend explanation as the "lead"; the full text stays in the
 * expandable section. Splits only before an upper-case letter, so abbreviations such as
 * "ok. 22 min" do not break the sentence.
 */
export function splitExplanation(explanation: string): { lead: string; rest: string } {
  const [lead = explanation, ...rest] = explanation.split(/(?<=\.)\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ„])/u);
  return { lead, rest: rest.join(' ') };
}
