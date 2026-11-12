import { Leaf, PiggyBank, Scale, Zap } from 'lucide-react';
import { useId } from 'react';
import type { TripPriority } from '../types/api';
import { PRIORITY_OPTIONS } from '../utils/labels';

const ICONS: Record<TripPriority, typeof Zap> = {
  balanced: Scale,
  fastest: Zap,
  cheapest: PiggyBank,
  greenest: Leaf,
};

/** Krótkie etykiety dla segmentów — pełne nazwy są w opisie i w dostępnej nazwie. */
const SHORT_LABELS: Record<TripPriority, string> = {
  balanced: 'Zrównoważony',
  fastest: 'Najszybszy',
  cheapest: 'Najtańszy',
  greenest: 'Eko',
};

interface PrioritySelectorProps {
  value: TripPriority;
  onChange: (priority: TripPriority) => void;
  disabled?: boolean;
  /** `full` — w formularzu, z opisem wybranej opcji; `compact` — szybka zmiana nad wynikami. */
  variant?: 'full' | 'compact';
  name?: string;
  /** Id elementu z etykietą grupy. */
  labelledBy?: string;
}

/**
 * Segmenty oparte na natywnych radio: strzałki zmieniają wybór, Tab przechodzi dalej.
 * Opis wybranego priorytetu jest stale widoczny pod segmentami (heurystyka 6).
 */
export function PrioritySelector({
  value,
  onChange,
  disabled,
  variant = 'full',
  name = 'priority',
  labelledBy,
}: PrioritySelectorProps) {
  const descriptionId = useId();
  const selected = PRIORITY_OPTIONS.find((option) => option.value === value);
  const compact = variant === 'compact';

  return (
    <div>
      <div
        role="radiogroup"
        aria-labelledby={labelledBy}
        aria-describedby={compact ? undefined : descriptionId}
        className={`grid gap-1 rounded-xl border border-navy-600 bg-navy-900 p-1 ${
          compact ? 'grid-cols-2 sm:grid-cols-4' : 'grid-cols-2 sm:grid-cols-4'
        }`}
      >
        {PRIORITY_OPTIONS.map((option) => {
          const Icon = ICONS[option.value];
          const checked = value === option.value;
          return (
            <label
              key={option.value}
              title={option.description}
              className={`flex min-h-10 cursor-pointer items-center justify-center gap-1.5 rounded-lg px-2 text-sm font-medium whitespace-nowrap transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-1 has-[:focus-visible]:outline-accent-400 ${
                checked
                  ? 'bg-accent-400/15 text-accent-300 ring-1 ring-accent-400/50'
                  : 'text-slate-300 hover:bg-navy-700 hover:text-white'
              } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
            >
              <input
                type="radio"
                name={name}
                value={option.value}
                checked={checked}
                disabled={disabled}
                onChange={() => onChange(option.value)}
                aria-label={option.label}
                className="sr-only"
              />
              <Icon aria-hidden="true" className="size-4 shrink-0" />
              <span aria-hidden="true">{SHORT_LABELS[option.value]}</span>
            </label>
          );
        })}
      </div>
      {!compact && selected && (
        <p id={descriptionId} className="mt-1.5 text-xs text-slate-400">
          <span className="font-medium text-slate-300">{selected.label}:</span>{' '}
          {selected.description}
        </p>
      )}
    </div>
  );
}
