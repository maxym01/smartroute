import { Info } from 'lucide-react';
import { useId, useState, type ReactNode } from 'react';

interface InfoTipProps {
  /** Dostępna nazwa przycisku, np. „Więcej o dystansie”. */
  label: string;
  children: ReactNode;
  /** Wyrównanie dymka względem ikony — chroni przed wyjściem poza ekran na wąskich telefonach. */
  align?: 'start' | 'center' | 'end';
}

const ALIGN = {
  start: 'left-0',
  center: 'left-1/2 -translate-x-1/2',
  end: 'right-0',
} as const;

/**
 * Dymek z dodatkowym wyjaśnieniem: otwiera się po najechaniu, focusie klawiatury lub kliknięciu
 * (dotyk), zamyka klawiszem Escape. Treść jest zawsze podpięta przez aria-describedby,
 * więc czytnik ekranu odczyta ją także bez otwierania.
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
