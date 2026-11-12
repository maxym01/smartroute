import { describe, expect, it } from 'vitest';
import type { ModeEstimate } from '../types/api';
import { bestMetrics } from './results';

const make = (mode: ModeEstimate['mode'], duration: number, cost: number, co2: number, available = true) =>
  ({
    mode,
    label: mode,
    available,
    estimated_duration_min: duration,
    estimated_cost_pln: cost,
    estimated_co2_kg: co2,
  }) as ModeEstimate;

describe('bestMetrics', () => {
  it('wyróżnia jedyny najlepszy wariant w każdej metryce', () => {
    const best = bestMetrics([make('car', 16, 3.19, 1.19), make('bike', 28, 0, 0), make('public_transport', 27, 8.8, 0.7)]);
    expect(best.get('car')).toEqual([{ metric: 'duration', sharedWith: [] }]);
    expect(best.get('bike')).toEqual([
      { metric: 'cost', sharedWith: [] },
      { metric: 'co2', sharedWith: [] },
    ]);
    expect(best.has('public_transport')).toBe(false);
  });

  it('traktuje wartości identyczne po zaokrągleniu do wyświetlenia jako remis', () => {
    const best = bestMetrics([make('car', 13.2, 3, 1), make('bike', 13.4, 0, 0), make('public_transport', 25, 4, 0.3)]);
    expect(best.get('car')).toEqual([{ metric: 'duration', sharedWith: ['bike'] }]);
    expect(best.get('bike')?.[0]).toEqual({ metric: 'duration', sharedWith: ['car'] });
  });

  it('nie wyróżnia nikogo, gdy wszyscy mają tę samą wartość, i pomija niedostępne warianty', () => {
    const best = bestMetrics([make('car', 20, 5, 1), make('public_transport', 20, 4, 0.5), make('bike', 5, 0, 0, false)]);
    expect(best.get('car')).toBeUndefined();
    expect(best.get('public_transport')).toEqual([
      { metric: 'cost', sharedWith: [] },
      { metric: 'co2', sharedWith: [] },
    ]);
    expect(best.has('bike')).toBe(false);
  });
});
