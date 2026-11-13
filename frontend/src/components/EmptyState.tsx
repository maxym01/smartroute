import { Bike, Bus, Car } from 'lucide-react';

/** Short initial state: no fake results and no lengthy instructions. */
export function EmptyState() {
  return (
    <section
      aria-labelledby="empty-title"
      className="flex flex-col items-center gap-4 rounded-2xl border border-dashed border-navy-600 px-6 py-10 text-center sm:flex-row sm:text-left"
    >
      <span aria-hidden="true" className="flex -space-x-2">
        <span className="inline-flex size-11 items-center justify-center rounded-full bg-sky-400/15 text-sky-300 ring-2 ring-navy-950">
          <Car className="size-5" />
        </span>
        <span className="inline-flex size-11 items-center justify-center rounded-full bg-violet-400/15 text-violet-300 ring-2 ring-navy-950">
          <Bus className="size-5" />
        </span>
        <span className="inline-flex size-11 items-center justify-center rounded-full bg-emerald-400/15 text-emerald-300 ring-2 ring-navy-950">
          <Bike className="size-5" />
        </span>
      </span>
      <div>
        <h2 id="empty-title" className="font-semibold text-white">
          Tu pojawi się porównanie
        </h2>
        <p className="mt-0.5 text-sm text-slate-400">
          Wybierz dwa przystanki i dystans — data i godzina są już ustawione na teraz. Zobaczysz
          czas, koszt, CO₂, odjazdy z rozkładu i wpływ pogody.
        </p>
      </div>
    </section>
  );
}
