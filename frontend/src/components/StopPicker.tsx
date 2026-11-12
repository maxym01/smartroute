import { CircleAlert, MapPin, Search, X } from 'lucide-react';
import { useId, useRef, useState, type KeyboardEvent } from 'react';
import { useStopSearch } from '../hooks/useStopSearch';
import { STOP_QUERY_MIN_LENGTH } from '../services/smartrouteApi';
import type { Stop } from '../types/api';
import { describeError } from '../utils/errors';
import { Spinner } from './ui/Spinner';

interface StopPickerProps {
  id: string;
  label: string;
  value: Stop | null;
  onChange: (stop: Stop | null) => void;
  /** Przystanek wybrany w drugim polu — nie można go wybrać ponownie (heurystyka 5). */
  excludeStopId?: string;
  error?: string;
  placeholder?: string;
  disabled?: boolean;
}

/**
 * Wyszukiwarka przystanków GTFS w układzie ARIA combobox (strzałki, Enter, Escape).
 * Po wyborze pokazuje nazwę przystanku zamiast identyfikatora (heurystyki 2 i 6).
 */
export function StopPicker({
  id,
  label,
  value,
  onChange,
  excludeStopId,
  error,
  placeholder = 'Nazwa przystanku, np. Dworzec Główny',
  disabled,
}: StopPickerProps) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const changeButtonRef = useRef<HTMLButtonElement>(null);
  const listId = useId();
  const hintId = useId();
  const errorId = useId();

  const search = useStopSearch(query, open && !value);
  const tooShort = query.trim().length < STOP_QUERY_MIN_LENGTH;
  const options = search.items;

  const select = (stop: Stop) => {
    if (stop.stop_id === excludeStopId) return;
    onChange(stop);
    setOpen(false);
    setQuery('');
    setActiveIndex(-1);
    // Focus na przycisk „Zmień”, aby użytkownik klawiatury nie stracił pozycji.
    requestAnimationFrame(() => changeButtonRef.current?.focus());
  };

  const clear = () => {
    onChange(null);
    setOpen(true);
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((index) => Math.min(index + 1, options.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === 'Enter') {
      const option = options[activeIndex];
      if (open && option) {
        event.preventDefault();
        select(option);
      }
    } else if (event.key === 'Escape') {
      setOpen(false);
      setActiveIndex(-1);
    }
  };

  const describedBy = [hintId, error ? errorId : null].filter(Boolean).join(' ');

  if (value) {
    return (
      <div>
        <span className="field-label" id={`${id}-label`}>
          {label}
        </span>
        <div
          className={`flex min-h-[2.625rem] items-center gap-2.5 rounded-xl border bg-navy-900 py-1 pr-1 pl-3.5 animate-fade-in ${
            error ? 'border-rose-400/70' : 'border-accent-500/40'
          }`}
          aria-labelledby={`${id}-label`}
          role="group"
        >
          <MapPin aria-hidden="true" className="size-4 shrink-0 text-accent-400" />
          <p className="min-w-0 flex-1 truncate text-sm font-medium text-white" title={value.stop_name}>
            {value.stop_name}
            {value.stop_code && (
              <span className="ml-2 text-xs font-normal text-slate-400">
                <span className="sr-only">słupek </span>#{value.stop_code}
              </span>
            )}
          </p>
          <button
            ref={changeButtonRef}
            type="button"
            id={id}
            onClick={clear}
            disabled={disabled}
            className="btn btn-ghost text-xs"
            aria-label={`Zmień: ${label.toLowerCase()} (${value.stop_name})`}
          >
            <X aria-hidden="true" className="size-3.5" />
            Zmień
          </button>
        </div>
        {error && (
          <p id={errorId} className="field-error">
            <CircleAlert aria-hidden="true" className="mt-px size-3.5 shrink-0" />
            {error}
          </p>
        )}
      </div>
    );
  }

  const showList = open && !tooShort;
  const activeOption = options[activeIndex];

  return (
    <div className="relative">
      <label htmlFor={id} className="field-label">
        {label}
      </label>
      <div className="relative">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-slate-500"
        />
        <input
          ref={inputRef}
          id={id}
          type="text"
          role="combobox"
          autoComplete="off"
          spellCheck={false}
          aria-autocomplete="list"
          aria-expanded={showList}
          aria-controls={listId}
          aria-activedescendant={showList && activeOption ? `${listId}-${activeOption.stop_id}` : undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className="input pr-10 pl-10"
          placeholder={placeholder}
          value={query}
          disabled={disabled}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
            setActiveIndex(-1);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
        />
        {search.status === 'loading' && (
          <span className="absolute top-1/2 right-3.5 -translate-y-1/2 text-accent-400">
            <Spinner label="Wyszukiwanie przystanków" />
          </span>
        )}
      </div>

      <p id={hintId} className="sr-only">
        Wpisz co najmniej {STOP_QUERY_MIN_LENGTH} znaki nazwy. Polskie znaki nie są wymagane.
      </p>
      {open && query.trim().length > 0 && tooShort && (
        <p className="absolute z-20 mt-1 w-full rounded-xl border border-navy-600 bg-navy-800 px-3.5 py-2.5 text-xs text-slate-300 shadow-xl animate-fade-in">
          Wpisz jeszcze co najmniej jeden znak — polskie znaki nie są wymagane.
        </p>
      )}
      {error && (
        <p id={errorId} className="field-error">
          <CircleAlert aria-hidden="true" className="mt-px size-3.5 shrink-0" />
          {error}
        </p>
      )}

      {showList && (
        <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-xl border border-navy-600 bg-navy-800 shadow-2xl shadow-black/40 animate-fade-in">
          <ul id={listId} role="listbox" aria-label={`Podpowiedzi: ${label}`} className="max-h-72 overflow-y-auto py-1">
            {options.map((stop, index) => {
              const excluded = stop.stop_id === excludeStopId;
              return (
                <li
                  key={stop.stop_id}
                  id={`${listId}-${stop.stop_id}`}
                  role="option"
                  aria-selected={index === activeIndex}
                  aria-disabled={excluded || undefined}
                  // onMouseDown zamiast onClick: wybór przed utratą focusu (onBlur zamyka listę).
                  onMouseDown={(event) => {
                    event.preventDefault();
                    select(stop);
                  }}
                  onMouseEnter={() => setActiveIndex(index)}
                  className={`flex cursor-pointer items-center gap-2.5 px-3.5 py-2 text-sm ${
                    index === activeIndex ? 'bg-navy-700 text-white' : 'text-slate-200'
                  } ${excluded ? 'cursor-not-allowed opacity-50' : ''}`}
                >
                  <MapPin aria-hidden="true" className="size-3.5 shrink-0 text-slate-500" />
                  <span className="flex-1 truncate">{stop.stop_name}</span>
                  {excluded ? (
                    <span className="text-xs text-slate-400">już wybrany</span>
                  ) : (
                    stop.stop_code && <span className="text-xs text-slate-500">{stop.stop_code}</span>
                  )}
                </li>
              );
            })}
          </ul>
          <div role="status" aria-live="polite" className="px-3.5 text-xs text-slate-400 empty:hidden">
            {search.status === 'success' && options.length === 0 && (
              <p className="py-3">
                Brak przystanków pasujących do „{query.trim()}”. Spróbuj krótszego fragmentu nazwy.
              </p>
            )}
            {search.status === 'loading' && options.length === 0 && <p className="py-3">Szukam przystanków…</p>}
            {search.status === 'error' && (
              <div className="py-3 text-rose-300">
                <p className="font-semibold">{describeError(search.error, 'stops').title}</p>
                <p className="text-slate-300">{describeError(search.error, 'stops').hints[0]}</p>
              </div>
            )}
            {search.status === 'success' && options.length > 0 && (
              <p className="sr-only">Znaleziono {options.length} przystanków. Użyj strzałek, aby wybrać.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
