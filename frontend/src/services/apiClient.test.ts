import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, request } from './apiClient';

function mockFetch(impl: () => Promise<Response>) {
  vi.stubGlobal('fetch', vi.fn(impl));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('request', () => {
  it('zwraca JSON przy sukcesie', async () => {
    mockFetch(async () => new Response(JSON.stringify({ status: 'ok' }), { status: 200 }));
    await expect(request('/health')).resolves.toEqual({ status: 'ok' });
  });

  it('zgłasza błąd sieci, gdy backend nie odpowiada', async () => {
    mockFetch(async () => {
      throw new TypeError('Failed to fetch');
    });
    await expect(request('/health')).rejects.toMatchObject({ kind: 'network' });
  });

  it('traktuje 5xx bez JSON-a (proxy Vite) jako niedostępny backend', async () => {
    mockFetch(async () => new Response('', { status: 502 }));
    await expect(request('/health')).rejects.toMatchObject({ kind: 'network', status: 502 });
  });

  it('rozpoznaje brak zaimportowanego rozkładu GTFS', async () => {
    mockFetch(
      async () =>
        new Response(JSON.stringify({ detail: 'Rozkład GTFS nie został zaimportowany.', code: 'gtfs_not_imported' }), {
          status: 503,
        }),
    );
    await expect(request('/stops?query=ab')).rejects.toMatchObject({ kind: 'gtfs_not_imported' });
  });

  it('przekazuje listę błędów walidacji 422', async () => {
    const detail = [{ loc: ['body', 'passengers'], msg: 'too big', type: 'less_than_equal' }];
    mockFetch(async () => new Response(JSON.stringify({ detail, code: 'validation_error' }), { status: 422 }));
    const error = await request('/trips').catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).kind).toBe('validation');
    expect((error as ApiError).issues).toEqual(detail);
  });
});
