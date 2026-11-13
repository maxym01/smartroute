import { Bike, Bus, Car } from 'lucide-react';
import type { TransportMode } from '../types/api';

const ICONS = { car: Car, public_transport: Bus, bike: Bike } as const;

/** The icon background colour is fixed per transport mode across the whole app. */
const MODE_ACCENTS: Record<TransportMode, string> = {
  car: 'bg-sky-400/15 text-sky-300 ring-sky-400/30',
  public_transport: 'bg-violet-400/15 text-violet-300 ring-violet-400/30',
  bike: 'bg-emerald-400/15 text-emerald-300 ring-emerald-400/30',
};

export function ModeIcon({ mode, size = 'md' }: { mode: TransportMode; size?: 'sm' | 'md' | 'lg' }) {
  const Icon = ICONS[mode];
  const box = { sm: 'size-8 rounded-lg', md: 'size-10 rounded-xl', lg: 'size-14 rounded-2xl' }[size];
  const icon = { sm: 'size-4', md: 'size-5', lg: 'size-7' }[size];
  return (
    <span
      aria-hidden="true"
      className={`inline-flex shrink-0 items-center justify-center ring-1 ${box} ${MODE_ACCENTS[mode]}`}
    >
      <Icon className={icon} />
    </span>
  );
}
