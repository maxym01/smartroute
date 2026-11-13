import { BookOpen, ChevronDown } from 'lucide-react';
import type { ReactNode } from 'react';

const TOPICS: { title: string; body: ReactNode }[] = [
  {
    title: 'Jak powstaje rekomendacja?',
    body: (
      <>
        <p>
          Rekomendację wyznacza backend wyłącznie spośród dostępnych wariantów. Priorytety
          „najszybszy”, „najtańszy” i „eko” wybierają najlepszą wartość danej metryki. Przy remisie
          rozstrzygają kolejne metryki.
        </p>
        <p>
          „Zrównoważony” normalizuje czas, koszt i CO₂ do skali 0–1 i liczy ich średnią (po 1/3).
          Pełny remis rozstrzyga kolejność: rower → komunikacja → samochód.
        </p>
      </>
    ),
  },
  {
    title: 'Skąd biorą się liczby?',
    body: (
      <p>
        Czas samochodu i roweru to dystans ÷ przyjęta średnia prędkość + stałe narzuty. Koszty
        i emisje wynikają z przyjętych parametrów: spalania, ceny paliwa, taryfy i emisji na km.
        Nie są to bieżące ceny ani oficjalne taryfy. Dystans podajesz sam — aplikacja nie wyznacza
        trasy drogowej.
      </p>
    ),
  },
  {
    title: 'Rozkład GTFS Static — kiedy czas jest „z rozkładu”?',
    body: (
      <>
        <p>
          Gdy w planowym rozkładzie ZTM Gdańsk jest kurs <strong>bezpośredni</strong> w ciągu 180 min
          od wybranej godziny, czas komunikacji = oczekiwanie + przejazd. Karta pokazuje wtedy
          „Czas z rozkładu GTFS”, a panel odjazdów oznacza użyty kurs.
        </p>
        <p>
          Gdy takiego kursu nie ma, czas jest <strong>szacunkiem parametrycznym</strong>, oznaczonym
          „brak potwierdzonego kursu GTFS”. Połączeń z przesiadką aplikacja nie wyszukuje. Nie
          uwzględnia też opóźnień ani dojścia na przystanek.
        </p>
      </>
    ),
  },
  {
    title: 'Pogoda — Weatherbit Current',
    body: (
      <p>
        Backend pobiera aktualne warunki dla okolicy przystanku początkowego. To nie jest prognoza,
        więc pogodę uwzględniamy tylko przy wyjeździe w ciągu ok. 2 h. Wpływa ona wyłącznie na
        rower. Klucz API jest przechowywany tylko w backendzie.
      </p>
    ),
  },
  {
    title: 'Ograniczenia aplikacji',
    body: (
      <ul className="list-disc space-y-1 pl-4">
        <li>Gdańsk i okolice — rozkład ZTM Gdańsk, bez SKM/PKM.</li>
        <li>Brak przesiadek, map i wyznaczania trasy drogowej.</li>
        <li>Brak danych o ruchu drogowym i opóźnieniach.</li>
        <li>Rozkład obowiązuje ok. 2 tygodnie i wymaga okresowego importu.</li>
        <li>Każde porównanie zapisuje podróż w lokalnej bazie backendu.</li>
      </ul>
    ),
  },
];

/** Help and documentation (heuristic 10): below the main area, in collapsed accordions. */
export function HelpPanel() {
  return (
    <section id="pomoc" aria-labelledby="help-title" className="scroll-mt-6">
      <h2 id="help-title" className="section-title mb-3">
        <BookOpen aria-hidden="true" className="size-4 text-accent-400" />
        Jak to działa?
      </h2>
      <div className="grid grid-cols-1 items-start gap-2 md:grid-cols-2 xl:grid-cols-3">
        {TOPICS.map((topic) => (
          <details
            key={topic.title}
            className="group rounded-xl border border-navy-700 bg-navy-850/60 px-4 transition-colors open:bg-navy-850"
          >
            <summary className="flex min-h-12 items-center justify-between gap-3 rounded text-sm font-medium text-slate-200 hover:text-white">
              {topic.title}
              <ChevronDown
                aria-hidden="true"
                className="size-4 shrink-0 transition-transform group-open:rotate-180"
              />
            </summary>
            <div className="space-y-2 pb-4 text-sm leading-relaxed text-slate-400">{topic.body}</div>
          </details>
        ))}
      </div>
    </section>
  );
}
