import type { ModeEstimate, TransportMode } from '../types/api';

export type MetricKey = 'duration' | 'cost' | 'co2';

const METRIC_VALUE: Record<MetricKey, (variant: ModeEstimate) => number> = {
  duration: (variant) => variant.estimated_duration_min,
  cost: (variant) => variant.estimated_cost_pln,
  co2: (variant) => variant.estimated_co2_kg,
};

/**
 * Wskazuje najlepszą wartość każdej metryki wśród dostępnych wariantów.
 * To wyłącznie opis danych z backendu — o rekomendacji decyduje backend.
 */
export function bestMetrics(variants: ModeEstimate[]): Map<TransportMode, MetricKey[]> {
  const available = variants.filter((variant) => variant.available);
  const result = new Map<TransportMode, MetricKey[]>();
  if (available.length < 2) return result;
  for (const metric of Object.keys(METRIC_VALUE) as MetricKey[]) {
    const values = available.map(METRIC_VALUE[metric]);
    const min = Math.min(...values);
    if (values.every((value) => value === min)) continue; // remis — nic nie wyróżniamy
    for (const variant of available) {
      if (METRIC_VALUE[metric](variant) === min) {
        result.set(variant.mode, [...(result.get(variant.mode) ?? []), metric]);
      }
    }
  }
  return result;
}

/** Dostępne warianty według rankingu backendu, niedostępne na końcu. */
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
 * Pierwsze zdanie uzasadnienia backendu jako „lead”; pełny tekst pozostaje w sekcji rozwijanej.
 * Dzielimy tylko przed wielką literą, więc skróty typu „ok. 22 min” nie rozbijają zdania.
 */
export function splitExplanation(explanation: string): { lead: string; rest: string } {
  const [lead = explanation, ...rest] = explanation.split(/(?<=\.)\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ„])/u);
  return { lead, rest: rest.join(' ') };
}
