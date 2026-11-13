import {
  ArrowLeftRight,
  ArrowUpDown,
  Bike,
  Car,
  ChevronDown,
  CircleAlert,
  Clock,
  Minus,
  Plus,
  Ruler,
  SlidersHorizontal,
  Users,
} from 'lucide-react';
import { useRef, useState, type FormEvent, type ReactNode } from 'react';
import type { Stop } from '../types/api';
import { nowInGdansk } from '../utils/datetime';
import { formatNumber } from '../utils/format';
import { straightLineKm } from '../utils/geo';
import {
  defaultTripName,
  FIELD_IDS,
  FIELD_LABELS,
  FIELD_ORDER,
  isInPast,
  LIMITS,
  validateTripForm,
  type TripFormErrors,
  type TripFormField,
  type TripFormValues,
} from '../utils/tripForm';
import { PrioritySelector } from './PrioritySelector';
import { StopPicker } from './StopPicker';
import { InfoTip } from './ui/InfoTip';
import { Spinner } from './ui/Spinner';

interface TripFormProps {
  values: TripFormValues;
  onChange: (patch: Partial<TripFormValues>) => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  /** Field errors returned by the backend (422). */
  serverErrors?: TripFormErrors;
  /** Description of the current processing step, e.g. "Zapisywanie podróży…". */
  progressLabel?: string;
  /** After the first comparison the button reads "Porównaj ponownie" (compare again). */
  hasResults?: boolean;
}

const SUMMARY_ID = 'trip-form-errors';

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} className="field-error">
      <CircleAlert aria-hidden="true" className="mt-px size-3.5 shrink-0" />
      {message}
    </p>
  );
}

/** Toggle styled as a compact "chip" — a native checkbox with role="switch". */
function ToggleChip({
  id,
  checked,
  onChange,
  icon,
  label,
  disabled,
}: {
  id: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  icon: ReactNode;
  label: string;
  disabled?: boolean;
}) {
  return (
    <label
      htmlFor={id}
      className={`inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-xl border px-3 text-sm transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-accent-400 ${
        checked
          ? 'border-navy-500 bg-navy-800 text-white'
          : 'border-navy-600 bg-navy-900 text-slate-400 line-through decoration-slate-500'
      } ${disabled ? 'cursor-not-allowed opacity-60' : 'hover:border-navy-500'}`}
    >
      <input
        id={id}
        type="checkbox"
        role="switch"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="peer sr-only"
      />
      <span aria-hidden="true" className={checked ? 'text-accent-400' : 'text-slate-500'}>
        {icon}
      </span>
      {label}
      <span
        aria-hidden="true"
        className="relative ml-1 h-5 w-9 shrink-0 rounded-full bg-navy-600 transition-colors peer-checked:bg-accent-500 after:absolute after:top-0.5 after:left-0.5 after:size-4 after:rounded-full after:bg-white after:shadow after:transition-transform peer-checked:after:translate-x-4"
      />
    </label>
  );
}

export function TripForm({
  values,
  onChange,
  onSubmit,
  isSubmitting,
  serverErrors = {},
  progressLabel,
  hasResults = false,
}: TripFormProps) {
  const [attempted, setAttempted] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const summaryRef = useRef<HTMLDivElement>(null);

  const clientErrors = validateTripForm(values);
  // Errors are shown after the first submit attempt, then updated live.
  const errors: TripFormErrors = attempted ? { ...serverErrors, ...clientErrors } : serverErrors;
  const errorFields = FIELD_ORDER.filter((field) => errors[field]);
  // A field with an error must not stay hidden in a collapsed section.
  const showAdvanced = advancedOpen || Boolean(errors.name);

  const errorId = (field: TripFormField) => `${FIELD_IDS[field]}-error`;
  const invalid = (field: TripFormField) => (errors[field] ? true : undefined);
  const describe = (...ids: (string | false | undefined)[]) =>
    ids.filter(Boolean).join(' ') || undefined;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isSubmitting) return; // prevent repeated submission (heuristic 1)
    setAttempted(true);
    if (Object.keys(clientErrors).length > 0) {
      requestAnimationFrame(() => summaryRef.current?.focus());
      return;
    }
    onSubmit();
  };

  const straightLine =
    values.origin && values.destination && values.origin.stop_id !== values.destination.stop_id
      ? straightLineKm(values.origin, values.destination)
      : null;

  const passengers = Number(values.passengers);
  const stepPassengers = (delta: number) => {
    const base = Number.isInteger(passengers) ? passengers : 1;
    const next = Math.min(LIMITS.passengersMax, Math.max(LIMITS.passengersMin, base + delta));
    onChange({ passengers: String(next) });
  };

  const past = isInPast(values);

  return (
    <form
      noValidate
      onSubmit={handleSubmit}
      aria-labelledby="trip-form-title"
      aria-describedby={errorFields.length ? SUMMARY_ID : undefined}
      aria-busy={isSubmitting}
      className="card p-4 sm:p-6"
    >
      <div className="mb-5 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="trip-form-title" className="text-lg font-semibold text-white">
          Zaplanuj podróż
        </h2>
        <p className="text-sm text-slate-400">
          Wybierz przystanki i godzinę, a porównamy samochód, komunikację i rower.
        </p>
      </div>

      {attempted && errorFields.length > 0 && (
        <div
          ref={summaryRef}
          id={SUMMARY_ID}
          tabIndex={-1}
          role="alert"
          className="mb-5 rounded-xl border border-rose-400/40 bg-rose-500/10 p-3.5 text-sm"
        >
          <p className="font-semibold text-white">
            Popraw {errorFields.length === 1 ? 'pole' : `pola (${errorFields.length})`}, aby
            uruchomić porównanie:
          </p>
          <ul className="mt-1.5 list-disc space-y-0.5 pl-5 text-rose-200">
            {errorFields.map((field) => (
              <li key={field}>
                <a
                  href={`#${FIELD_IDS[field]}`}
                  className="underline decoration-rose-300/50 underline-offset-2 hover:text-white"
                  onClick={(event) => {
                    event.preventDefault();
                    document.getElementById(FIELD_IDS[field])?.focus();
                  }}
                >
                  {FIELD_LABELS[field]}
                </a>
                : {errors[field]}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid grid-cols-1 gap-x-5 gap-y-4 lg:grid-cols-12">
        {/* Route */}
        <fieldset className="lg:col-span-7">
          <legend className="sr-only">Trasa</legend>
          <div className="grid grid-cols-1 items-start gap-x-2 gap-y-1 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
            <StopPicker
              id={FIELD_IDS.origin}
              label="Przystanek początkowy"
              value={values.origin}
              onChange={(origin: Stop | null) => onChange({ origin })}
              excludeStopId={values.destination?.stop_id}
              error={errors.origin}
              disabled={isSubmitting}
            />
            <div className="flex justify-center md:pt-7">
              <button
                type="button"
                onClick={() => onChange({ origin: values.destination, destination: values.origin })}
                disabled={isSubmitting || (!values.origin && !values.destination)}
                className="btn btn-ghost size-10 p-0"
                aria-label="Zamień przystanek początkowy z docelowym"
                title="Zamień kierunek"
              >
                <ArrowUpDown aria-hidden="true" className="size-4 md:hidden" />
                <ArrowLeftRight aria-hidden="true" className="hidden size-4 md:block" />
              </button>
            </div>
            <StopPicker
              id={FIELD_IDS.destination}
              label="Przystanek docelowy"
              value={values.destination}
              onChange={(destination: Stop | null) => onChange({ destination })}
              excludeStopId={values.origin?.stop_id}
              error={errors.destination}
              placeholder="Nazwa przystanku, np. Zaspa"
              disabled={isSubmitting}
            />
          </div>
        </fieldset>

        {/* Date and time */}
        <fieldset className="lg:col-span-5">
          <legend className="sr-only">Termin wyjazdu</legend>
          <div className="grid grid-cols-2 gap-2 [&>*]:min-w-0">
            <div>
              <label htmlFor={FIELD_IDS.date} className="field-label">
                Data wyjazdu
              </label>
              <input
                id={FIELD_IDS.date}
                type="date"
                className="input"
                value={values.date}
                onChange={(event) => onChange({ date: event.target.value })}
                aria-invalid={invalid('date')}
                aria-describedby={describe('departure-hint', errors.date && errorId('date'))}
                disabled={isSubmitting}
                required
              />
            </div>
            <div>
              <label htmlFor={FIELD_IDS.time} className="field-label">
                Godzina wyjazdu
              </label>
              <input
                id={FIELD_IDS.time}
                type="time"
                className="input"
                value={values.time}
                onChange={(event) => onChange({ time: event.target.value })}
                aria-invalid={invalid('time')}
                aria-describedby={describe('departure-hint', errors.time && errorId('time'))}
                disabled={isSubmitting}
                required
              />
            </div>
          </div>
          <FieldError id={errorId('date')} message={errors.date} />
          <FieldError id={errorId('time')} message={errors.time} />
          <div className="mt-1.5 flex items-start justify-between gap-2">
            <p id="departure-hint" className="text-xs leading-relaxed text-slate-400">
              {past ? (
                <span className="text-amber-300">
                  Termin w przeszłości — rozkład zadziała, pogoda bieżąca nie.
                </span>
              ) : (
                'Czas lokalny Gdańska. Pogoda bieżąca: tylko dla wyjazdu w ciągu ok. 2 h.'
              )}
            </p>
            <button
              type="button"
              onClick={() => onChange(nowInGdansk())}
              disabled={isSubmitting}
              className="inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium text-accent-300 hover:bg-navy-700 hover:text-accent-400"
            >
              <Clock aria-hidden="true" className="size-3" />
              Ustaw teraz
            </button>
          </div>
        </fieldset>

        {/* Distance */}
        <div className="lg:col-span-4">
          <div className="mb-1.5 flex items-center gap-1">
            <label htmlFor={FIELD_IDS.distanceKm} className="text-sm font-medium text-slate-200">
              Dystans szacunkowy
            </label>
            <InfoTip label="Więcej o dystansie szacunkowym" align="start">
              Aplikacja nie wyznacza trasy drogowej. Podany dystans służy do szacunku czasu,
              kosztu i emisji samochodu oraz roweru. Rzeczywista trasa może być dłuższa.
            </InfoTip>
          </div>
          <div className="relative">
            <input
              id={FIELD_IDS.distanceKm}
              type="text"
              inputMode="decimal"
              autoComplete="off"
              className="input pr-12"
              placeholder="np. 5,5"
              value={values.distanceKm}
              onChange={(event) => onChange({ distanceKm: event.target.value })}
              aria-invalid={invalid('distanceKm')}
              aria-describedby={describe('distance-hint', errors.distanceKm && errorId('distanceKm'))}
              disabled={isSubmitting}
              required
            />
            <span className="pointer-events-none absolute top-1/2 right-3.5 -translate-y-1/2 text-sm text-slate-400">
              km
            </span>
          </div>
          <FieldError id={errorId('distanceKm')} message={errors.distanceKm} />
          <p id="distance-hint" className="field-hint">
            {straightLine !== null ? (
              <span className="inline-flex flex-wrap items-center gap-x-1.5">
                <Ruler aria-hidden="true" className="size-3.5 text-slate-500" />
                Linia prosta: {formatNumber(straightLine, 1)} km (trasa będzie dłuższa).
                <button
                  type="button"
                  className="font-medium text-accent-300 underline underline-offset-2 hover:text-accent-400"
                  onClick={() => onChange({ distanceKm: formatNumber(straightLine, 1) })}
                  disabled={isSubmitting}
                >
                  Wstaw
                </button>
              </span>
            ) : (
              'Przybliżona długość trasy w km — wpisujesz ją samodzielnie.'
            )}
          </p>
        </div>

        {/* Priority */}
        <div className="lg:col-span-8">
          <p id="priority-label" className="field-label">
            Priorytet
          </p>
          <PrioritySelector
            value={values.priority}
            onChange={(priority) => onChange({ priority })}
            disabled={isSubmitting}
            labelledBy="priority-label"
          />
        </div>
      </div>

      {/* Options bar and the primary action */}
      <div className="mt-5 flex flex-col gap-4 border-t border-navy-700 pt-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex items-center gap-1 rounded-xl border border-navy-600 bg-navy-900 p-0.5">
            <label htmlFor={FIELD_IDS.passengers} className="flex items-center gap-1.5 pl-2.5 text-sm text-slate-300">
              <Users aria-hidden="true" className="size-4 text-accent-400" />
              Pasażerowie
            </label>
            <button
              type="button"
              className="btn btn-ghost size-9 p-0"
              onClick={() => stepPassengers(-1)}
              disabled={isSubmitting || passengers <= LIMITS.passengersMin}
              aria-label="Mniej pasażerów"
            >
              <Minus aria-hidden="true" className="size-4" />
            </button>
            <input
              id={FIELD_IDS.passengers}
              type="number"
              inputMode="numeric"
              min={LIMITS.passengersMin}
              max={LIMITS.passengersMax}
              step={1}
              className="w-9 [appearance:textfield] bg-transparent text-center text-sm font-semibold text-white tabular-nums focus:outline-none focus-visible:rounded focus-visible:outline-2 focus-visible:outline-accent-400 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
              value={values.passengers}
              onChange={(event) => onChange({ passengers: event.target.value })}
              aria-invalid={invalid('passengers')}
              aria-describedby={errors.passengers ? errorId('passengers') : undefined}
              disabled={isSubmitting}
              required
            />
            <button
              type="button"
              className="btn btn-ghost size-9 p-0"
              onClick={() => stepPassengers(1)}
              disabled={isSubmitting || passengers >= LIMITS.passengersMax}
              aria-label="Więcej pasażerów"
            >
              <Plus aria-hidden="true" className="size-4" />
            </button>
          </div>
          <ToggleChip
            id="has-car"
            checked={values.hasCar}
            onChange={(hasCar) => onChange({ hasCar })}
            icon={<Car className="size-4" />}
            label="Samochód"
            disabled={isSubmitting}
          />
          <ToggleChip
            id="allow-bike"
            checked={values.allowBike}
            onChange={(allowBike) => onChange({ allowBike })}
            icon={<Bike className="size-4" />}
            label="Rower"
            disabled={isSubmitting}
          />
          <InfoTip label="Co oznaczają przełączniki środków transportu" align="end">
            Wyłącz środek, z którego nie możesz skorzystać — zostanie pominięty w rekomendacji.
            Rower jest uwzględniany do 20 km.
          </InfoTip>
          <button
            type="button"
            className="btn btn-ghost text-sm"
            aria-expanded={showAdvanced}
            aria-controls="advanced-options"
            onClick={() => setAdvancedOpen((open) => !open)}
          >
            <SlidersHorizontal aria-hidden="true" className="size-4" />
            Opcje zaawansowane
            <ChevronDown
              aria-hidden="true"
              className={`size-4 transition-transform ${showAdvanced ? 'rotate-180' : ''}`}
            />
          </button>
        </div>

        <button
          type="submit"
          className="btn btn-primary min-h-11 w-full px-6 text-base lg:w-auto lg:min-w-64"
          disabled={isSubmitting}
        >
          {isSubmitting ? (
            <>
              <Spinner />
              {progressLabel ?? 'Przetwarzanie…'}
            </>
          ) : hasResults ? (
            'Porównaj ponownie'
          ) : (
            'Porównaj środki transportu'
          )}
        </button>
      </div>
      <FieldError id={errorId('passengers')} message={errors.passengers} />

      <div id="advanced-options" hidden={!showAdvanced} className="mt-4 max-w-xl">
        <label htmlFor={FIELD_IDS.name} className="field-label">
          Nazwa podróży <span className="font-normal text-slate-400">(opcjonalnie)</span>
        </label>
        <input
          id={FIELD_IDS.name}
          type="text"
          className="input"
          maxLength={LIMITS.nameMax}
          placeholder={defaultTripName(values) || 'Domyślnie: „Skąd → Dokąd”'}
          value={values.name}
          onChange={(event) => onChange({ name: event.target.value })}
          aria-invalid={invalid('name')}
          aria-describedby={errors.name ? errorId('name') : undefined}
          disabled={isSubmitting}
        />
        <FieldError id={errorId('name')} message={errors.name} />
      </div>
    </form>
  );
}
