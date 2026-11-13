import type { ApiErrorBody, ValidationIssue } from '../types/api';

/** Relative URL by default — in dev mode the Vite proxy handles it (vite.config.ts). */
export const API_BASE_URL: string = (import.meta.env.VITE_API_BASE_URL ?? '/api/v1').replace(
  /\/$/,
  '',
);

export type ApiErrorKind =
  | 'network' // no connection to the backend
  | 'validation' // 422
  | 'not_found' // 404
  | 'gtfs_not_imported' // 503 from the backend
  | 'server' // other 5xx
  | 'unknown';

/** API error with the backend code and, for 422, the list of validation issues. */
export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly issues: ValidationIssue[];

  constructor(
    kind: ApiErrorKind,
    message: string,
    status: number | null = null,
    issues: ValidationIssue[] = [],
  ) {
    super(message);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = status;
    this.issues = issues;
  }
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function isErrorBody(value: unknown): value is ApiErrorBody {
  return typeof value === 'object' && value !== null && 'detail' in value;
}

function toApiError(status: number, body: unknown): ApiError {
  if (!isErrorBody(body)) {
    // The Vite proxy returns a 5xx without JSON when the backend is down.
    if (status >= 500) {
      return new ApiError('network', 'Backend nie odpowiada.', status);
    }
    return new ApiError('unknown', `Nieoczekiwana odpowiedź serwera (HTTP ${status}).`, status);
  }

  const { detail, code } = body;
  if (Array.isArray(detail)) {
    return new ApiError('validation', 'Dane formularza zostały odrzucone.', status, detail);
  }
  if (code === 'gtfs_not_imported') return new ApiError('gtfs_not_imported', detail, status);
  if (code === 'not_found' || status === 404) return new ApiError('not_found', detail, status);
  if (status >= 500) return new ApiError('server', detail, status);
  return new ApiError('unknown', detail, status);
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...init.headers },
    });
  } catch (error) {
    if (isAbortError(error)) throw error;
    throw new ApiError('network', 'Brak połączenia z backendem.');
  }

  const body = await readJson(response);
  if (!response.ok) throw toApiError(response.status, body);
  return body as T;
}
