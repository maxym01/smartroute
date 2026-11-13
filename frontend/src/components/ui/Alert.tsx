import { CircleAlert, CircleCheck, Info, TriangleAlert } from 'lucide-react';
import type { ReactNode } from 'react';

type Tone = 'info' | 'success' | 'warning' | 'error';

const TONES: Record<Tone, { box: string; icon: typeof Info; iconClass: string }> = {
  info: { box: 'border-sky-400/30 bg-sky-400/10', icon: Info, iconClass: 'text-sky-300' },
  success: {
    box: 'border-emerald-400/30 bg-emerald-400/10',
    icon: CircleCheck,
    iconClass: 'text-emerald-300',
  },
  warning: {
    box: 'border-amber-400/30 bg-amber-400/10',
    icon: TriangleAlert,
    iconClass: 'text-amber-300',
  },
  error: { box: 'border-rose-400/40 bg-rose-500/10', icon: CircleAlert, iconClass: 'text-rose-300' },
};

interface AlertProps {
  tone?: Tone;
  title?: string;
  children?: ReactNode;
  /** `alert` interrupts the screen reader — use it only for errors that need action. */
  role?: 'alert' | 'status';
  action?: ReactNode;
  className?: string;
}

/** Shared message — an icon and a title always accompany the colour (never colour alone). */
export function Alert({ tone = 'info', title, children, role, action, className = '' }: AlertProps) {
  const { box, icon: Icon, iconClass } = TONES[tone];
  return (
    <div role={role} className={`flex gap-3 rounded-xl border p-3.5 text-sm ${box} ${className}`}>
      <Icon aria-hidden="true" className={`mt-0.5 size-4 shrink-0 ${iconClass}`} />
      <div className="min-w-0 flex-1 space-y-1 text-slate-200">
        {title && <p className="font-semibold text-white">{title}</p>}
        {children}
        {action && <div className="pt-1.5">{action}</div>}
      </div>
    </div>
  );
}
