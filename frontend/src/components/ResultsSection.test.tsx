import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { ComparisonResult, ScheduleState } from '../hooks/useComparison';
import type { ComparisonResponse, Connection, ConnectionList, ModeEstimate } from '../types/api';
import { ResultsSection } from './ResultsSection';

function variant(overrides: Partial<ModeEstimate>): ModeEstimate {
  return {
    mode: 'car',
    label: 'Samochód',
    available: true,
    unavailable_reason: null,
    estimated_duration_min: 13.2,
    estimated_cost_pln: 2.5,
    estimated_cost_per_passenger_pln: 2.5,
    estimated_co2_kg: 0.935,
    estimated_co2_per_passenger_kg: 0.935,
    is_estimate: true,
    data_source: 'parametric_estimate',
    assumptions: ['Średnia prędkość 40 km/h.'],
    score: { rank: 2, normalized_duration: 0, normalized_cost: 1, normalized_co2: 1, balanced_score: 0.66, weather_demoted: false },
    comfort_level: null,
    ...overrides,
  };
}

const car = variant({});
const bike = variant({
  mode: 'bike',
  label: 'Rower',
  estimated_duration_min: 22,
  estimated_cost_pln: 0,
  estimated_cost_per_passenger_pln: 0,
  estimated_co2_kg: 0,
  estimated_co2_per_passenger_kg: 0,
  score: { rank: 1, normalized_duration: 1, normalized_cost: 0, normalized_co2: 0, balanced_score: 0.33, weather_demoted: false },
  comfort_level: 'reduced',
});
const transitUnavailable = variant({
  mode: 'public_transport',
  label: 'Komunikacja miejska',
  available: false,
  unavailable_reason: 'Brak połączenia testowego.',
  score: null,
});
// Wariant z szacunku parametrycznego (tak jak przy Dworzec Główny 02 → Zaspa 01).
const transitEstimate = variant({
  mode: 'public_transport',
  label: 'Komunikacja miejska',
  estimated_duration_min: 27,
  estimated_cost_pln: 8.8,
  estimated_co2_kg: 0.7,
  data_source: 'parametric_estimate',
  assumptions: ['Brak bezpośredniego połączenia w rozkładzie GTFS w ciągu 180 min. Użyto szacunku parametrycznego.'],
  score: { rank: 3, normalized_duration: 0.9, normalized_cost: 1, normalized_co2: 0.6, balanced_score: 0.83, weather_demoted: false },
});
// Wariant z rozkładu — założenia w formacie backendu (gtfs_transit.py).
const transitScheduled = variant({
  ...transitEstimate,
  estimated_duration_min: 25,
  data_source: 'gtfs_schedule',
  assumptions: [
    'Czas z rozkładu GTFS: linia 2 w kierunku Jelitkowo, odjazd 12.11.2026 19:17 z przystanku Dworzec Główny 01, przyjazd 19:39 na przystanek Zaspa 01.',
  ],
});

function connection(overrides: Partial<Connection>): Connection {
  return {
    trip_id: 't1',
    route_id: '8',
    line: '8',
    route_type: 900,
    headsign: 'Strzyża PKM',
    direction_id: 0,
    service_date: '2026-11-12',
    departure_at: '2026-11-12T19:11:00+01:00',
    arrival_at: '2026-11-12T19:33:00+01:00',
    duration_min: 22,
    origin_stop_sequence: 1,
    destination_stop_sequence: 10,
    ...overrides,
  };
}

function connectionList(connections: Connection[]): ConnectionList {
  const stop = { stop_code: null, stop_lat: null, stop_lon: null };
  return {
    origin: { stop_id: '2001', stop_name: 'Dworzec Główny 01', ...stop },
    destination: { stop_id: '2089', stop_name: 'Zaspa 01', ...stop },
    departure_at: '2026-11-12T19:10:00+01:00',
    window_min: 180,
    data_source: 'gtfs_schedule',
    is_realtime: false,
    feed: { source: 'x', imported_at: '2026-11-11T18:00:00Z', timezone: 'Europe/Warsaw', valid_from: '2026-11-11', valid_to: '2026-11-25' },
    connections,
    notes: ['Rozkład planowy GTFS Static — bez opóźnień.', 'Tylko połączenia bezpośrednie (bez przesiadek).'],
  };
}

function makeResult(
  variants: ModeEstimate[],
  schedule: ScheduleState = { status: 'loading' },
  recommended: Pick<ModeEstimate, 'mode' | 'label'> = bike,
): ComparisonResult {
  const comparison: ComparisonResponse = {
    trip_id: 7,
    priority: 'balanced',
    distance_km: 5.5,
    passengers: 1,
    is_estimate: true,
    disclaimer: 'Wszystkie wartości są szacunkami.',
    variants,
    recommendation: {
      mode: recommended.mode,
      label: recommended.label,
      explanation: 'Rower daje najlepszy kompromis (z backendu). Względem wariantu „Samochód”: 9 min dłużej.',
      tie_break_applied: false,
    },
    scoring: {
      priority: 'balanced',
      description: 'Normalizacja min-max.',
      balanced_weights: { duration: 0.3333, cost: 0.3333, co2: 0.3333 },
      tie_break_order: ['bike', 'public_transport', 'car'],
      comfort_rule: 'Reguła komfortu.',
    },
    weather: null,
  };
  return {
    trip: {
      id: 7,
      name: 'Test',
      origin: 'Dworzec Główny 01',
      destination: 'Zaspa 01',
      distance_km: 5.5,
      passengers: 1,
      priority: 'balanced',
      has_car: true,
      allow_bike: true,
      notes: null,
      origin_stop_id: '2001',
      destination_stop_id: '2089',
      departure_at: '2026-11-12T19:10:00+01:00',
      created_at: '2026-11-12T17:54:21Z',
      updated_at: '2026-11-12T17:54:21Z',
    },
    comparison,
    schedule,
  };
}

function renderResults(result: ComparisonResult, handlers: { onPriorityChange?: () => void; onEditTrip?: () => void } = {}) {
  return render(
    <ResultsSection
      result={result}
      isRefreshing={false}
      onPriorityChange={handlers.onPriorityChange ?? vi.fn()}
      onEditTrip={handlers.onEditTrip ?? vi.fn()}
    />,
  );
}

describe('ResultsSection', () => {
  it('pokazuje rekomendację z backendu i oznacza najlepszy wariant tekstem, nie tylko kolorem', () => {
    renderResults(makeResult([car, transitUnavailable, bike]));

    expect(screen.getByRole('heading', { level: 2, name: 'Rower' })).toBeInTheDocument();
    // Lead to pierwsze zdanie uzasadnienia; pełny tekst w sekcji rozwijanej.
    expect(screen.getByText('Rower daje najlepszy kompromis (z backendu).')).toBeInTheDocument();
    expect(screen.getByText(/Względem wariantu „Samochód”: 9 min dłużej\./)).toBeInTheDocument();

    const bikeCard = screen.getByRole('article', { name: 'Rower' });
    expect(within(bikeCard).getByText('Rekomendowany')).toBeInTheDocument();
    expect(within(bikeCard).getByText('Miejsce 1 z 2')).toBeInTheDocument();
    expect(within(bikeCard).getByText(/Komfort przy pogodzie/)).toHaveTextContent('Komfort przy pogodzie: obniżony');
  });

  it('pokazuje powód niedostępności i sortuje warianty według rankingu', () => {
    renderResults(makeResult([car, transitUnavailable, bike]));

    const cards = screen.getAllByRole('article').map((card) => within(card).getByRole('heading').textContent);
    expect(cards).toEqual(['Rower', 'Samochód', 'Komunikacja miejska']);
    const transitCard = screen.getByRole('article', { name: 'Komunikacja miejska' });
    expect(within(transitCard).getByText('Pominięty')).toBeInTheDocument();
    expect(within(transitCard).getByText('Brak połączenia testowego.')).toBeInTheDocument();
  });

  it('pokazuje neutralny komunikat, gdy brak danych pogodowych', () => {
    renderResults(makeResult([car, bike]));
    expect(screen.getByText('Pogody nie oceniano')).toBeInTheDocument();
  });

  it('pozwala szybko zmienić priorytet', async () => {
    const onPriorityChange = vi.fn();
    renderResults(makeResult([car, bike]), { onPriorityChange });

    await userEvent.click(screen.getByRole('radio', { name: 'Najtańszy' }));
    expect(onPriorityChange).toHaveBeenCalledWith('cheapest');
  });

  it('oznacza szacunek komunikacji, gdy rozkład nie ma kursu bezpośredniego, i nie pokazuje odjazdów', async () => {
    const onEditTrip = vi.fn();
    renderResults(makeResult([car, transitEstimate, bike], { status: 'success', data: connectionList([]) }), { onEditTrip });

    const transitCard = screen.getByRole('article', { name: 'Komunikacja miejska' });
    expect(within(transitCard).getByText('Czas szacunkowy — brak potwierdzonego kursu GTFS')).toBeInTheDocument();
    expect(within(transitCard).getByText('Czas (szac.)')).toBeInTheDocument();
    expect(within(transitCard).queryByText(/Czas z rozkładu GTFS/)).not.toBeInTheDocument();

    const schedule = screen.getByRole('region', { name: 'Odjazdy z rozkładu' });
    expect(within(schedule).getByText('Brak kursu bezpośredniego w rozkładzie')).toBeInTheDocument();
    expect(within(schedule).getByText(/Nie oznacza to braku połączenia z przesiadką/)).toBeInTheDocument();
    expect(within(schedule).queryByRole('list', { name: 'Najbliższe kursy bezpośrednie' })).not.toBeInTheDocument();

    await userEvent.click(within(schedule).getByRole('button', { name: 'Zmień przystanki lub godzinę' }));
    expect(onEditTrip).toHaveBeenCalledOnce();
  });

  it('wiąże czas z rozkładu z kursem w panelu odjazdów', () => {
    const used = connection({ trip_id: 'used', line: '2', headsign: 'Jelitkowo', departure_at: '2026-11-12T19:17:00+01:00' });
    renderResults(
      makeResult([car, transitScheduled, bike], { status: 'success', data: connectionList([connection({}), used]) }),
    );

    const transitCard = screen.getByRole('article', { name: 'Komunikacja miejska' });
    expect(within(transitCard).getByText('Czas z rozkładu GTFS')).toBeInTheDocument();
    expect(within(transitCard).getByText(/Linia 2 → Jelitkowo, odjazd 19:17/)).toBeInTheDocument();

    const rows = within(screen.getByRole('list', { name: 'Najbliższe kursy bezpośrednie' })).getAllByRole('listitem');
    expect(within(rows[1]!).getByText('użyty w porównaniu')).toBeInTheDocument();
    expect(within(rows[0]!).queryByText('użyty w porównaniu')).not.toBeInTheDocument();
  });

  it('nie twierdzi, że kurs potwierdzono, gdy rozkład był niedostępny', () => {
    renderResults(makeResult([car, transitEstimate, bike], { status: 'error', error: new Error('x') }));
    const transitCard = screen.getByRole('article', { name: 'Komunikacja miejska' });
    expect(within(transitCard).getByText('Czas szacunkowy — nie sprawdzono rozkładu')).toBeInTheDocument();
  });

  it('ostrzega w panelu rekomendacji, gdy komunikacja wygrywa bez potwierdzonego kursu GTFS', () => {
    renderResults(makeResult([car, transitEstimate, bike], { status: 'success', data: connectionList([]) }, transitEstimate));

    const panel = screen.getByRole('region', { name: 'Komunikacja miejska' });
    const warning = within(panel).getByText(/rekomendowana na podstawie czasu szacunkowego/);
    expect(warning).toHaveTextContent('nie znaleziono potwierdzonego kursu bezpośredniego GTFS w ciągu 180 min');
    expect(warning).toHaveTextContent('połączeń z przesiadkami aplikacja nie sprawdza');
    expect(warning).toHaveTextContent('nie gwarantuje dostępnego połączenia');
    // Komunikacja nadal jest w rankingu — brak kursu bezpośredniego ≠ brak komunikacji.
    const card = screen.getByRole('article', { name: 'Komunikacja miejska' });
    expect(within(card).getByText('Rekomendowany')).toBeInTheDocument();
    expect(within(card).queryByText('Pominięty')).not.toBeInTheDocument();
  });

  it('nie ostrzega w panelu rekomendacji, gdy czas komunikacji pochodzi z rozkładu', () => {
    const used = connection({ trip_id: 'used', line: '2', headsign: 'Jelitkowo', departure_at: '2026-11-12T19:17:00+01:00' });
    renderResults(makeResult([car, transitScheduled, bike], { status: 'success', data: connectionList([used]) }, transitScheduled));

    const panel = screen.getByRole('region', { name: 'Komunikacja miejska' });
    expect(within(panel).queryByText(/czasu szacunkowego/)).not.toBeInTheDocument();
  });

  it('nie dodaje ostrzeżenia o komunikacji, gdy rekomendowany jest inny wariant', () => {
    renderResults(makeResult([car, transitEstimate, bike], { status: 'success', data: connectionList([]) }));
    const panel = screen.getByRole('region', { name: 'Rower' });
    expect(within(panel).queryByText(/czasu szacunkowego/)).not.toBeInTheDocument();
  });

  it('oznacza remis najkrótszego czasu jako ex aequo w kartach i w panelu', () => {
    // 13,2 i 13,4 min wyświetlają się jako „13 min” — żaden nie może być „jedynym najkrótszym”.
    const fastBike = variant({ ...bike, estimated_duration_min: 13.4 });
    renderResults(makeResult([car, fastBike, transitEstimate], { status: 'loading' }, car));

    const carCard = screen.getByRole('article', { name: 'Samochód' });
    const bikeCard = screen.getByRole('article', { name: 'Rower' });
    expect(within(carCard).getByText('najkrótszy ex aequo')).toBeInTheDocument();
    expect(within(bikeCard).getByText('najkrótszy ex aequo')).toBeInTheDocument();
    expect(screen.queryByText('najkrótszy')).not.toBeInTheDocument();

    const benefits = screen.getByRole('list', { name: 'Najważniejsze korzyści' });
    expect(within(benefits).getByText('Najkrótszy czas (ex aequo z: Rower)')).toBeInTheDocument();
  });
});
