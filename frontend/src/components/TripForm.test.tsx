import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Stop } from '../types/api';
import { defaultFormValues, type TripFormValues } from '../utils/tripForm';
import { TripForm } from './TripForm';

const STOPS: Stop[] = [
  { stop_id: '2001', stop_name: 'Dworzec Główny 01', stop_code: '2001', stop_lat: 54.3555, stop_lon: 18.6456 },
  { stop_id: '2002', stop_name: 'Dworzec Główny 02', stop_code: '2002', stop_lat: 54.3551, stop_lon: 18.6454 },
];

function Harness({ onSubmit, initial }: { onSubmit: () => void; initial?: Partial<TripFormValues> }) {
  const [values, setValues] = useState<TripFormValues>({ ...defaultFormValues(), ...initial });
  return (
    <TripForm
      values={values}
      onChange={(patch) => setValues((current) => ({ ...current, ...patch }))}
      onSubmit={onSubmit}
      isSubmitting={false}
    />
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('TripForm', () => {
  it('nie wysyła pustego formularza i pokazuje podsumowanie błędów', async () => {
    const onSubmit = vi.fn();
    render(<Harness onSubmit={onSubmit} />);

    await userEvent.click(screen.getByRole('button', { name: 'Porównaj środki transportu' }));

    expect(onSubmit).not.toHaveBeenCalled();
    const summary = screen.getByRole('alert');
    expect(within(summary).getByText('Przystanek początkowy')).toBeInTheDocument();
    expect(within(summary).getByText('Dystans szacunkowy')).toBeInTheDocument();
    expect(screen.getByLabelText('Dystans szacunkowy')).toHaveAttribute('aria-invalid', 'true');
  });

  it('wyszukuje przystanek po nazwie i pokazuje wybraną nazwę zamiast identyfikatora', async () => {
    const fetchMock = vi.fn(
      async (_url: string) => new Response(JSON.stringify({ items: STOPS, count: 2 }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);
    render(<Harness onSubmit={vi.fn()} />);

    const input = screen.getByRole('combobox', { name: 'Przystanek początkowy' });
    await userEvent.type(input, 'glowny');
    const option = await screen.findByRole('option', { name: /Dworzec Główny 01/ });
    expect(fetchMock.mock.calls.at(-1)?.[0]).toContain('/stops?query=glowny');

    await userEvent.keyboard('{ArrowDown}{Enter}');

    expect(option).not.toBeInTheDocument();
    expect(screen.getByText('Dworzec Główny 01')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Zmień: przystanek początkowy/ })).toBeInTheDocument();
  });

  it('nie pozwala wybrać jako celu przystanku już wybranego jako start', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ items: STOPS, count: 2 }), { status: 200 })));
    render(<Harness onSubmit={vi.fn()} initial={{ origin: STOPS[0] }} />);

    await userEvent.type(screen.getByRole('combobox', { name: 'Przystanek docelowy' }), 'glowny');
    const taken = await screen.findByRole('option', { name: /Dworzec Główny 01/ });

    expect(taken).toHaveAttribute('aria-disabled', 'true');
    await userEvent.click(taken);
    expect(screen.getByRole('combobox', { name: 'Przystanek docelowy' })).toBeInTheDocument();
  });

  it('ukrywa nazwę podróży w opcjach zaawansowanych, ale pozostawia ją dostępną', async () => {
    render(<Harness onSubmit={vi.fn()} initial={{ origin: STOPS[0], destination: STOPS[1] }} />);

    expect(screen.getByLabelText(/Nazwa podróży/)).not.toBeVisible();
    const toggle = screen.getByRole('button', { name: 'Opcje zaawansowane' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');

    await userEvent.click(toggle);

    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByLabelText(/Nazwa podróży/)).toBeVisible();
    expect(screen.getByLabelText(/Nazwa podróży/)).toHaveAttribute(
      'placeholder',
      'Dworzec Główny 01 → Dworzec Główny 02',
    );
  });

  it('wysyła poprawnie wypełniony formularz', async () => {
    const onSubmit = vi.fn();
    render(<Harness onSubmit={onSubmit} initial={{ origin: STOPS[0], destination: STOPS[1] }} />);

    await userEvent.type(screen.getByLabelText('Dystans szacunkowy'), '0,4');
    await userEvent.click(screen.getByRole('button', { name: 'Porównaj środki transportu' }));

    expect(onSubmit).toHaveBeenCalledOnce();
  });
});
