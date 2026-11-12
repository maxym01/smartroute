import { describe, expect, it } from 'vitest';
import { ApiError } from '../services/apiClient';
import { describeError, mapValidationIssues } from './errors';
import { formatCo2, formatCost, formatDuration, formatTime } from './format';

// Intl używa twardej spacji (U+00A0) przed „zł” — normalizujemy ją w asercjach.
const plain = (text: string) => text.replace(/\u00a0/g, ' ');

describe('formatowanie wartości', () => {
  it('formatuje czas w minutach i godzinach', () => {
    expect(formatDuration(13.2)).toBe('13 min');
    expect(formatDuration(60)).toBe('1 h');
    expect(formatDuration(95.4)).toBe('1 h 35 min');
  });

  it('formatuje koszt w złotych z przecinkiem', () => {
    expect(plain(formatCost(2.5))).toBe('2,50 zł');
    expect(plain(formatCost(0))).toBe('0,00 zł');
  });

  it('formatuje emisję CO₂', () => {
    expect(formatCo2(0.935)).toBe('0,94 kg CO₂');
    expect(formatCo2(0)).toBe('0 kg CO₂');
    expect(formatCo2(0.004)).toBe('0,004 kg CO₂');
  });

  it('pokazuje godzinę w strefie Gdańska', () => {
    expect(formatTime('2026-11-12T18:57:00+01:00')).toBe('18:57');
    expect(formatTime('2026-11-12T17:57:00Z')).toBe('18:57');
  });
});

describe('obsługa błędów API', () => {
  it('mapuje błędy 422 na pola formularza i tłumaczy komunikaty', () => {
    const { fields, general } = mapValidationIssues([
      { loc: ['body', 'distance_km'], msg: 'Input should be greater than 0', type: 'greater_than' },
      {
        loc: ['body'],
        msg: 'Value error, Przystanek startowy i docelowy muszą się różnić',
        type: 'value_error',
      },
    ]);
    expect(fields.distanceKm).toBe('Wartość jest za mała.');
    expect(general).toEqual(['Przystanek startowy i docelowy muszą się różnić']);
  });

  it('zamienia brak połączenia na zrozumiały komunikat z instrukcją', () => {
    const info = describeError(new ApiError('network', 'x'), 'compare');
    expect(info.title).toBe('Brak połączenia z backendem');
    expect(info.hints.join(' ')).toMatch(/run\.ps1/);
  });
});
