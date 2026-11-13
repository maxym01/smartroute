import { Info } from 'lucide-react';
import { useId, useState, type ReactNode } from 'react';

interface InfoTipProps {
  /** Accessible name of the button, e.g. "Więcej o dystansie". */
  label: string;
  children: ReactNode;
  /** Tooltip alignment relative to the icon — keeps it on screen on narrow phones. */
  align?: 'start' | 'center' | 'end';
}

const ALIGN = {
  start: 'left-0',
  center: 'left-1/2 -translate-x-1/2',
  end: 'right-0',
} as const;

/**
 * Tooltip with an extra explanation: opens on hover, keyboard focus or click (touch) and
 * closes with Escape. The content is always linked via aria-describedby, so a screen reader
 * reads it even when the tooltip is closed.
 */
export function InfoTip({ label, children, align = 'center' }: InfoTipProps) {
  const [open, setOpen] = useState(false);
  const id = useId();

  return (
    <span
      className="relative inline-flex align-middle"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        aria-label={label}
        aria-describedby={id}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') setOpen(false);
        }}
        className="inline-flex size-6 items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-navy-700 hover:text-white"
      >
        <Info aria-hidden="true" className="size-3.5" />
      </button>
      <span
        id={id}
        role="tooltip"
        className={`absolute bottom-full z-30 mb-2 w-64 max-w-[calc(100vw-2rem)] rounded-lg border border-navy-500 bg-navy-700 px-3 py-2 text-xs leading-relaxed font-normal text-slate-100 shadow-xl shadow-black/40 ${ALIGN[align]} ${
          open ? 'block animate-fade-in' : 'hidden'
        }`}
      >
        {children}
      </span>
    </span>
  );
}
