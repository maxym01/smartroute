import { describe, expect, it } from 'vitest';
import type { Stop } from '../types/api';
import { nowInGdansk } from './datetime';
import { defaultFormValues, parseDecimal, toTripPayload, validateTripForm, type TripFormValues } from './tripForm';

const DWORZEC: Stop = {
  stop_id: '2001',
  stop_name: 'Dworzec Główny 01',
  stop_code: '2001',
  stop_lat: 54.3555,
  stop_lon: 18.6456,
};
const ZASPA: Stop = { stop_id: '2089', stop_name: 'Zaspa 01', stop_code: '2089', stop_lat: 54.3993, stop_lon: 18.5949 };

function valid(overrides: Partial<TripFormValues> = {}): TripFormValues {
  return {
    ...defaultFormValues(new Date('2026-11-12T17:30:00Z')),
    origin: DWORZEC,
    destination: ZASPA,
    distanceKm: '5,5',
    ...overrides,
  };
}

describe('validateTripForm', () => {
  it('akceptuje poprawny formularz', () => {
    expect(validateTripForm(valid())).toEqual({});
  });

  it('wymaga obu przystanków', () => {
    const errors = validateTripForm(valid({ origin: null, destination: null }));
    expect(errors.origin).toBeDefined();
    expect(errors.destination).toBeDefined();
  });

  it('odrzuca identyczny przystanek początkowy i docelowy', () => {
    const errors = validateTripForm(valid({ destination: { ...DWORZEC } }));
    expect(errors.destination).toMatch(/inny niż początkowy/);
  });

  it.each([
    ['', /Podaj/],
    ['0', /większy od 0/],
    ['-3', /liczbą/],
    ['abc', /liczbą/],
    ['1000,5', /1000/],
  ])('odrzuca dystans %j', (distanceKm, message) => {
    expect(validateTripForm(valid({ distanceKm })).distanceKm).toMatch(message);
  });

  it.each(['0', '9', '1.5', ''])('odrzuca liczbę pasażerów %j', (passengers) => {
    expect(validateTripForm(valid({ passengers })).passengers).toBeDefined();
  });

  it('odrzuca nieistniejącą datę i błędną godzinę', () => {
    const errors = validateTripForm(valid({ date: '2026-02-30', time: '25:00' }));
    expect(errors.date).toBeDefined();
    expect(errors.time).toBeDefined();
  });
});

describe('parseDecimal', () => {
  it('obsługuje przecinek i kropkę', () => {
    expect(parseDecimal('5,5')).toBe(5.5);
    expect(parseDecimal(' 12.25 ')).toBe(12.25);
    expect(parseDecimal('1e3')).toBeNaN();
  });
});

describe('toTripPayload', () => {
  it('buduje kontrakt POST /trips z nazwami przystanków i czasem lokalnym bez strefy', () => {
    const payload = toTripPayload(valid({ date: '2026-11-12', time: '07:55', passengers: '2' }));
    expect(payload).toEqual({
      name: 'Dworzec Główny 01 → Zaspa 01',
      origin: 'Dworzec Główny 01',
      destination: 'Zaspa 01',
      origin_stop_id: '2001',
      destination_stop_id: '2089',
      departure_at: '2026-11-12T07:55:00',
      distance_km: 5.5,
      passengers: 2,
      priority: 'balanced',
      has_car: true,
      allow_bike: true,
    });
  });
});

describe('nowInGdansk', () => {
  it('zwraca czas w strefie Europe/Warsaw niezależnie od strefy przeglądarki', () => {
    // 17:30 UTC w listopadzie = 18:30 w Gdańsku (CET, UTC+1).
    expect(nowInGdansk(new Date('2026-11-12T17:30:00Z'))).toEqual({ date: '2026-11-12', time: '18:30' });
  });
});
