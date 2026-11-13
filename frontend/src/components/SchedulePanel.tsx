import { ArrowRight, Bus, CalendarX, Pencil, TrainFront, TramFront } from 'lucide-react';
import type { ScheduleState } from '../hooks/useComparison';
import type { Connection } from '../types/api';
import { describeError } from '../utils/errors';
import { formatDate, formatDuration, formatTime } from '../utils/format';
import { routeTypeLabel, type RouteKind } from '../utils/labels';
import { InfoTip } from './ui/InfoTip';
import { Spinner } from './ui/Spinner';

const ROUTE_ICONS: Record<RouteKind, typeof Bus> = {
  Tramwaj: TramFront,
  Autobus: Bus,
  Pociąg: TrainFront,
  Linia: Bus,
};

/** Backend notes that the panel already presents in its own words. */
const STANDARD_NOTES = [
  'Rozkład planowy GTFS Static',
  'Tylko połączenia bezpośrednie',
  'Brak bezpośredniego połączenia',
];

function waitMinutes(requestedAt: string, connection: Connection): number {
  return (new Date(connection.departure_at).getTime() - new Date(requestedAt).getTime()) / 60000;
}

interface SchedulePanelProps {
  schedule: ScheduleState;
  /** The trip the backend used for the public transport time (null = none / not matched). */
  usedConnection: Connection | null;
  /** Takes the user to the form to change the stops or the time. */
  onEditTrip: () => void;
}

/**
 * Departures from the GTFS Static timetable (GET /connections), separate from the estimated
 * travel time. No delays and no real-time data.
 */
export function SchedulePanel({ schedule, usedConnection, onEditTrip }: SchedulePanelProps) {
  const extraNotes =
    schedule.status === 'success'
      ? schedule.data.notes.filter((note) => !STANDARD_NOTES.some((prefix) => note.startsWith(prefix)))
      : [];

  return (
    <section aria-labelledby="schedule-title" className="card p-5 animate-rise sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id="schedule-title" className="section-title">
            <TramFront aria-hidden="true" className="size-4 text-violet-300" />
            Odjazdy z rozkładu
          </h2>
          <p className="mt-0.5 text-xs text-slate-400">
            Kursy bezpośrednie · GTFS Static ZTM Gdańsk · bez opóźnień
          </p>
        </div>
        <InfoTip label="Skąd pochodzą odjazdy" align="end">
          Planowy rozkład GTFS Static, nie dane w czasie rzeczywistym. Wyszukujemy tylko kursy
          bez przesiadki w ciągu{' '}
          {schedule.status === 'success' ? schedule.data.window_min : 180} min od wybranej godziny.
          Czas oczekiwania liczymy od tej godziny, bez dojścia na przystanek.
        </InfoTip>
      </div>

      {schedule.status === 'loading' && (
        <p className="mt-4 flex items-center gap-2 text-sm text-slate-400" role="status">
          <Spinner /> Wczytywanie rozkładu…
        </p>
      )}

      {schedule.status === 'error' && (
        <div className="mt-4 flex gap-3 text-sm">
          <CalendarX aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-slate-400" />
          <div>
            <p className="font-medium text-white">{describeError(schedule.error, 'schedule').title}</p>
            <p className="mt-1 text-slate-400">
              {describeError(schedule.error, 'schedule').hints[0]} Czas komunikacji w porównaniu
              jest wtedy szacunkiem.
            </p>
          </div>
        </div>
      )}

      {schedule.status === 'success' && schedule.data.connections.length === 0 && (
        <div className="mt-4 rounded-xl bg-amber-400/10 p-4 text-sm">
          <p className="flex items-center gap-2 font-medium text-white">
            <CalendarX aria-hidden="true" className="size-4 shrink-0 text-amber-300" />
            Brak kursu bezpośredniego w rozkładzie
          </p>
          <p className="mt-1.5 leading-relaxed text-slate-300">
            W ciągu {schedule.data.window_min} min od {formatTime(schedule.data.departure_at)} nie
            ma kursu bez przesiadki z <strong className="font-medium text-white">{schedule.data.origin.stop_name}</strong> do{' '}
            <strong className="font-medium text-white">{schedule.data.destination.stop_name}</strong>.
            Nie oznacza to braku połączenia z przesiadką — aplikacja takich połączeń nie wyszukuje.
            Czas komunikacji w porównaniu jest szacunkiem.
          </p>
          <ul className="mt-2 list-disc space-y-0.5 pl-5 text-slate-300">
            <li>Spróbuj innego słupka przystanku (np. „01” zamiast „02”) — słupki obsługują różne kierunki.</li>
            <li>Zmień godzinę lub datę wyjazdu.</li>
          </ul>
          <button type="button" className="btn btn-secondary mt-3 py-2 text-sm" onClick={onEditTrip}>
            <Pencil aria-hidden="true" className="size-4" />
            Zmień przystanki lub godzinę
          </button>
        </div>
      )}

      {schedule.status === 'success' && schedule.data.connections.length > 0 && (
        <ol className="mt-4 divide-y divide-navy-700/70" aria-label="Najbliższe kursy bezpośrednie">
          {schedule.data.connections.map((connection) => {
            const kind = routeTypeLabel(connection.route_type);
            const Icon = ROUTE_ICONS[kind];
            const wait = waitMinutes(schedule.data.departure_at, connection);
            const used = usedConnection?.trip_id === connection.trip_id;
            return (
              <li key={connection.trip_id} className="flex items-center gap-3 py-2.5 sm:gap-4">
                <span className="inline-flex w-16 shrink-0 items-center justify-center gap-1.5 rounded-lg bg-violet-400/15 py-1.5 text-sm font-bold text-violet-200">
                  <Icon aria-hidden="true" className="size-4" />
                  <span className="sr-only">{kind} </span>
                  {connection.line}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-x-2 text-sm font-medium text-white">
                    <span className="truncate">
                      <span className="sr-only">Kierunek: </span>
                      {connection.headsign ?? 'Kierunek nieznany'}
                    </span>
                    {used && (
                      <span className="rounded-md bg-accent-400/10 px-1.5 py-0.5 text-[11px] font-medium text-accent-300">
                        użyty w porównaniu
                      </span>
                    )}
                  </p>
                  <p className="flex flex-wrap items-center gap-x-1.5 text-sm text-slate-300 tabular-nums">
                    <span className="font-semibold text-white">{formatTime(connection.departure_at)}</span>
                    <ArrowRight aria-hidden="true" className="size-3.5 text-slate-500" />
                    <span className="sr-only">przyjazd</span>
                    <span>{formatTime(connection.arrival_at)}</span>
                    <span className="text-slate-500">· {formatDuration(connection.duration_min)} jazdy</span>
                  </p>
                </div>
                <span className="shrink-0 text-right text-xs text-slate-400 tabular-nums">
                  {wait < 1 ? 'od razu' : <>za {formatDuration(wait)}</>}
                </span>
              </li>
            );
          })}
        </ol>
      )}

      {schedule.status === 'success' && (
        <p className="mt-3 text-xs text-slate-500">
          Rozkład ważny
          {schedule.data.feed.valid_from && ` od ${formatDate(schedule.data.feed.valid_from)}`}
          {schedule.data.feed.valid_to && ` do ${formatDate(schedule.data.feed.valid_to)}`}.
          {extraNotes.map((note) => (
            <span key={note} className="block text-amber-300">
              {note}
            </span>
          ))}
        </p>
      )}
    </section>
  );
}
