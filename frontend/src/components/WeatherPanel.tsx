import { Bike, CloudOff, CloudSun, Droplets, Snowflake, Thermometer, Wind } from 'lucide-react';
import type { ReactNode } from 'react';
import type { Weather, WeatherStatus } from '../types/api';
import { formatNumber, formatTemperature, formatTime } from '../utils/format';
import { COMFORT_LABELS } from '../utils/labels';
import { InfoTip } from './ui/InfoTip';

/** Neutral titles for cases where the weather was not applied. */
const STATUS_TITLES: Record<Exclude<WeatherStatus, 'applied'>, string> = {
  disabled: 'Integracja pogodowa wyłączona',
  no_location: 'Brak lokalizacji do sprawdzenia pogody',
  out_of_time_window: 'Pogoda bieżąca nie dotyczy tego terminu',
  unavailable: 'Dane pogodowe chwilowo niedostępne',
  not_applicable: 'Pogoda nie wpływa na ten wynik',
};

const COMFORT_STYLES = {
  good: 'text-emerald-300',
  reduced: 'text-amber-300',
  poor: 'text-rose-300',
} as const;

function Reading({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="flex items-center gap-1.5 text-xs text-slate-400">
        <span className="text-sky-300">{icon}</span>
        {label}
      </dt>
      <dd className="mt-0.5 text-base font-semibold whitespace-nowrap text-white tabular-nums">
        {value}
      </dd>
    </div>
  );
}

export function WeatherPanel({ weather }: { weather: Weather | null }) {
  const conditions = weather?.status === 'applied' ? weather.conditions : null;

  return (
    <section aria-labelledby="weather-title" className="card p-5 animate-rise sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id="weather-title" className="section-title">
            <CloudSun aria-hidden="true" className="size-4 text-sky-300" />
            Pogoda bieżąca
          </h2>
          <p className="mt-0.5 text-xs text-slate-400">Weatherbit · aktualne warunki, nie prognoza</p>
        </div>
        <InfoTip label="Jak pogoda wpływa na wynik" align="end">
          Uwzględniamy ją tylko przy wyjeździe teraz lub w ciągu ok. 2 h, dla okolicy przystanku
          początkowego. Wpływa wyłącznie na rower: ocenę komfortu, czas przy silnym wietrze,
          a przy bardzo złych warunkach — pozycję w rankingu.
        </InfoTip>
      </div>

      {conditions && weather ? (
        <>
          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
            <Reading
              icon={<Thermometer aria-hidden="true" className="size-3.5" />}
              label="Temperatura"
              value={formatTemperature(conditions.temperature_c)}
            />
            <Reading
              icon={<Wind aria-hidden="true" className="size-3.5" />}
              label="Wiatr"
              value={`${formatNumber(conditions.wind_speed_kmh, 0)} km/h`}
            />
            <Reading
              icon={<Droplets aria-hidden="true" className="size-3.5" />}
              label="Opady"
              value={`${formatNumber(conditions.precipitation_mm_h, 1)} mm/h`}
            />
            <Reading
              icon={<Snowflake aria-hidden="true" className="size-3.5" />}
              label="Śnieg"
              value={`${formatNumber(conditions.snowfall_mm_h, 1)} mm/h`}
            />
          </dl>
          <p className="mt-3 text-xs text-slate-400">
            {conditions.description && <>{conditions.description} · </>}
            {weather.location && <>okolice: {weather.location.stop_name}</>}
            {conditions.observed_at && <> · pomiar {formatTime(conditions.observed_at)}</>}
          </p>
          {weather.adjustment && (
            <p className="mt-3 flex items-start gap-2 border-t border-navy-700 pt-3 text-sm text-slate-300">
              <Bike aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-emerald-300" />
              <span>
                Wpływ na rower: komfort{' '}
                <span className={`font-medium ${COMFORT_STYLES[weather.adjustment.comfort_level]}`}>
                  {COMFORT_LABELS[weather.adjustment.comfort_level]}
                </span>
                {weather.adjustment.reasons.length > 0 && ` (${weather.adjustment.reasons.join(', ')})`}
                {weather.adjustment.duration_factor !== 1
                  ? `, czas jazdy +${formatNumber((weather.adjustment.duration_factor - 1) * 100, 0)}%.`
                  : '. Pozostałe środki bez zmian.'}
              </span>
            </p>
          )}
        </>
      ) : (
        <div className="mt-4 flex gap-3 text-sm">
          <CloudOff aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-slate-400" />
          <div>
            <p className="font-medium text-white">
              {weather
                ? (STATUS_TITLES[weather.status as Exclude<WeatherStatus, 'applied'>] ??
                  'Brak danych pogodowych')
                : 'Pogody nie oceniano'}
            </p>
            <p className="mt-1 leading-relaxed text-slate-400">
              {weather?.explanation ?? 'Porównanie nie uwzględnia pogody.'}
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
