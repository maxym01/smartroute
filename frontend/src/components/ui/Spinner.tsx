import { LoaderCircle } from 'lucide-react';

export function Spinner({ className = 'size-4', label }: { className?: string; label?: string }) {
  return (
    <>
      <LoaderCircle aria-hidden="true" className={`animate-spin ${className}`} />
      {label && <span className="sr-only">{label}</span>}
    </>
  );
}
