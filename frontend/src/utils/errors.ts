import { ApiError } from '../services/apiClient';
import type { ValidationIssue } from '../types/api';
import { FIELD_LABELS, type TripFormErrors, type TripFormField } from './tripForm';

export interface UserFacingError {
  title: string;
  message: string;
  /** Concrete recovery steps (heuristic 9). */
  hints: string[];
}

const BACKEND_FIELD_MAP: Record<string, TripFormField> = {
  name: 'name',
  origin: 'origin',
  destination: 'destination',
  origin_stop_id: 'origin',
  destination_stop_id: 'destination',
  departure_at: 'date',
  distance_km: 'distanceKm',
  passengers: 'passengers',
};

const PYDANTIC_MESSAGES: Record<string, string> = {
  greater_than: 'Wartość jest za mała.',
  greater_than_equal: 'Wartość jest za mała.',
  less_than: 'Wartość jest za duża.',
  less_than_equal: 'Wartość jest za duża.',
  string_too_long: 'Tekst jest za długi.',
  string_too_short: 'To pole nie może być puste.',
  missing: 'To pole jest wymagane.',
  datetime_parsing: 'Niepoprawny format daty lub godziny.',
  datetime_from_date_parsing: 'Niepoprawny format daty lub godziny.',
  float_parsing: 'Wartość musi być liczbą.',
  int_parsing: 'Wartość musi być liczbą całkowitą.',
};

function issueMessage(issue: ValidationIssue): string {
  if (issue.type === 'value_error') return issue.msg.replace(/^Value error,\s*/i, '');
  return PYDANTIC_MESSAGES[issue.type] ?? issue.msg;
}

/** Turns backend 422 errors into messages attached to specific form fields. */
export function mapValidationIssues(issues: ValidationIssue[]): {
  fields: TripFormErrors;
  general: string[];
} {
  const fields: TripFormErrors = {};
  const general: string[] = [];
  for (const issue of issues) {
    const key = [...issue.loc]
      .reverse()
      .find((part): part is string => typeof part === 'string' && part in BACKEND_FIELD_MAP);
    const field = key ? BACKEND_FIELD_MAP[key] : undefined;
    const message = issueMessage(issue);
    if (field && !fields[field]) fields[field] = message;
    else general.push(message);
  }
  return { fields, general };
}

type ErrorContext = 'compare' | 'stops' | 'schedule';

export function describeError(error: unknown, context: ErrorContext): UserFacingError {
  if (!(error instanceof ApiError)) {
    return {
      title: 'Wystąpił nieoczekiwany błąd',
      message: 'Coś poszło nie tak po stronie przeglądarki.',
      hints: ['Odśwież stronę i spróbuj ponownie.'],
    };
  }

  switch (error.kind) {
    case 'network':
      return {
        title: 'Brak połączenia z backendem',
        message: 'Serwer SmartRoute nie odpowiada. Wprowadzone dane zostały zachowane.',
        hints: [
          'Upewnij się, że backend działa (w katalogu projektu: .\\run.ps1).',
          'Backend powinien nasłuchiwać pod adresem http://127.0.0.1:8000.',
          'Następnie ponów próbę.',
        ],
      };
    case 'gtfs_not_imported':
      return {
        title: 'Rozkład GTFS nie jest zaimportowany',
        message: 'Bez rozkładu ZTM Gdańsk nie można wyszukiwać przystanków ani połączeń.',
        hints: ['Zaimportuj rozkład poleceniem .\\import-gtfs.ps1, a potem odśwież stronę.'],
      };
    case 'validation': {
      const { fields, general } = mapValidationIssues(error.issues);
      const fieldLines = Object.entries(fields).map(
        ([field, msg]) => `${FIELD_LABELS[field as TripFormField]}: ${msg}`,
      );
      return {
        title: 'Serwer odrzucił dane',
        message: 'Popraw wskazane pola i spróbuj ponownie.',
        hints: [...fieldLines, ...general],
      };
    }
    case 'not_found':
      return {
        title: context === 'compare' ? 'Nie znaleziono podróży' : 'Nie znaleziono przystanku',
        message: error.message,
        hints: ['Wybierz przystanki ponownie z listy podpowiedzi i uruchom porównanie.'],
      };
    case 'server':
      return {
        title: 'Błąd serwera',
        message: 'Backend zgłosił błąd podczas przetwarzania żądania.',
        hints: ['Spróbuj ponownie za chwilę. Jeśli błąd się powtarza, sprawdź logi backendu.'],
      };
    default:
      return {
        title: 'Nie udało się wykonać żądania',
        message: error.message,
        hints: ['Spróbuj ponownie.'],
      };
  }
}
