# SmartRoute — plan architektury MVP

Full-stack MVP do porównywania środków transportu (samochód, transport publiczny, rower) pod kątem czasu, kosztu i szacowanej emisji CO₂, z zapisywaniem podróży (pełny CRUD) i rekomendacją środka transportu na podstawie preferencji użytkownika.

**Stack:** Python 3.12, FastAPI, SQLite, SQLAlchemy 2.0 · React, TypeScript, Tailwind CSS (Vite)

> Status: archiwalny dokument planistyczny sprzed implementacji. Aktualny stan projektu opisuje
> [README.md](README.md).
>
> Najważniejsze różnice między tym planem a implementacją:
>
> - Priorytety `fastest`, `cheapest` i `greenest` używają porządku leksykograficznego, a nie wag
>   0.7 / 0.2 / 0.1. Wagi po 1/3 zostały tylko dla `balanced`.
> - Porównanie jest pod `GET /trips/{id}/compare`. Endpointy `POST /comparisons`
>   i `/transport-modes` nie powstały.
> - Frontend to jeden dashboard (bez routera, listy podróży i szybkiego porównania), bez
>   TanStack Query, react-hook-form, zod i MSW.
> - Poza planem dodano rozkład GTFS Static ZTM Gdańsk (`/stops`, `/connections`) oraz
>   opcjonalną pogodę bieżącą Weatherbit.
> - W czasie powstawania planu projekt nazywał się „SmartRoute AI”. Obecna nazwa to
>   „SmartRoute”. Rekomendację wyznacza deterministyczny algorytm oparty na regułach, a nie
>   model AI. Katalog repozytorium i nazwy pakietów (`smartroute-ai`) pozostały bez zmian.

---

## 0. Założenia MVP (do potwierdzenia)

- **Dystans wpisuje użytkownik w km.** Bez zewnętrznego API map ani geokodowania. Punkt startu i cel to zwykły tekst. Integrację z mapami da się dodać później za interfejsem `DistanceProvider`.
- **Jeden użytkownik, bez logowania.**
- **Waluta to PLN.** Parametry kalkulacji (spalanie, ceny, prędkości, emisje) są w konfiguracji backendu, nie w bazie.
- **Porównanie liczymy na bieżąco, nie zapisujemy go w bazie.** Po zmianie parametrów wyniki od razu się aktualizują.

---

## 1. Struktura katalogów

```
smartroute-ai/
├── README.md
├── architecture-plan.md
├── .gitignore
├── backend/
│   ├── pyproject.toml            # zależności + ruff + pytest
│   ├── .env.example
│   ├── app/
│   │   ├── main.py               # create_app(), CORS, lifespan (create_all), routery
│   │   ├── core/
│   │   │   ├── config.py         # pydantic-settings: DB URL, CORS origins, parametry transportu
│   │   │   └── exceptions.py     # NotFoundError + handlery → spójny format błędów
│   │   ├── db/
│   │   │   ├── base.py           # DeclarativeBase
│   │   │   └── session.py        # engine, SessionLocal, get_db()
│   │   ├── models/
│   │   │   └── trip.py
│   │   ├── schemas/
│   │   │   ├── trip.py           # TripCreate / TripUpdate / TripRead / TripList
│   │   │   └── comparison.py     # ModeResult, ComparisonRequest, ComparisonResponse
│   │   ├── repositories/
│   │   │   └── trip_repository.py
│   │   ├── services/
│   │   │   ├── transport/
│   │   │   │   ├── base.py       # Protocol TransportCalculator
│   │   │   │   ├── car.py
│   │   │   │   ├── public_transport.py
│   │   │   │   └── bike.py
│   │   │   ├── comparison_service.py
│   │   │   └── recommendation_service.py
│   │   └── api/
│   │       └── v1/
│   │           ├── router.py
│   │           ├── trips.py
│   │           ├── comparisons.py
│   │           └── meta.py       # health, transport-modes
│   └── tests/
│       ├── conftest.py           # SQLite in-memory + override get_db + TestClient
│       ├── unit/                 # kalkulatory, rekomendacja, walidacja schematów
│       └── api/                  # CRUD, porównania, kody błędów, CORS
└── frontend/
    ├── package.json  vite.config.ts  tailwind.config.ts  tsconfig.json
    ├── .env.example              # VITE_API_URL
    └── src/
        ├── main.tsx  App.tsx     # router
        ├── api/                  # client.ts (fetch + obsługa błędów), trips.ts, comparisons.ts
        ├── types/                # typy odwzorowujące schematy API
        ├── hooks/                # useTrips, useTrip, useComparison (TanStack Query)
        ├── components/
        │   ├── ui/               # Button, Input, Card, Modal, Spinner, EmptyState
        │   ├── trips/            # TripForm, TripTable, DeleteTripDialog
        │   └── comparison/       # ModeCard, MetricBars, RecommendationBanner, PreferenceSelector
        ├── pages/                # TripsListPage, TripFormPage, TripDetailsPage, QuickComparePage, NotFoundPage
        ├── lib/                  # formatowanie (PLN, min, kg CO₂), schematy zod
        └── test/                 # setup Vitest + MSW
```

Backend ma warstwy: **api → services → repositories → models**. Logika obliczeń nie zależy od FastAPI ani od bazy, więc testuje się ją jednostkowo bez żadnej infrastruktury.

---

## 2. Model danych (SQLAlchemy 2.0, typowane `Mapped[...]`)

### Tabela `Trip`

| Pole | Typ | Uwagi |
|---|---|---|
| `id` | int PK | |
| `name` | str(100) | np. „Dom → praca” |
| `origin` | str(200) | |
| `destination` | str(200) | |
| `distance_km` | float | > 0, ≤ 1000 |
| `passengers` | int | 1–8; koszt i CO₂ auta dzielimy na osoby |
| `priority` | Enum | `fastest` / `cheapest` / `greenest` / `balanced` |
| `has_car` | bool | false → auto wykluczone z rekomendacji |
| `allow_bike` | bool | false → rower wykluczony |
| `notes` | str(500) \| null | |
| `created_at`, `updated_at` | datetime (UTC) | `server_default` / `onupdate` |

### Obiekty wyliczane (schematy Pydantic, nie tabele)

- `ModeResult`: `mode`, `duration_min`, `cost_pln`, `co2_kg`, `feasible`, `infeasible_reason`, `score`.
- `ComparisonResponse`: `results: list[ModeResult]`, `recommended_mode`, `recommendation_reason`, `priority`, `weights`.

### Parametry transportu

Parametry są w `config.py` i można je nadpisać przez `.env`. Przykładowe wartości:

- **Auto:** 40 km/h średnio, 5 min na parkowanie, 7 l/100 km, 6,50 zł/l, 0,17 kg CO₂/km.
- **Transport publiczny:** 22 km/h, 8 min dojścia i czekania, bilet 4,40 zł do 10 km (powyżej stawka za km), 0,05 kg CO₂ na pasażerokilometr.
- **Rower:** 15 km/h, 0 zł, 0 kg CO₂, maksymalnie 20 km. Powyżej tej odległości rower jest oznaczony jako `feasible=false`.

---

## 3. Logika rekomendacji

1. Liczymy metryki dla 3 środków transportu.
2. Odrzucamy niewykonalne: rower powyżej limitu lub `allow_bike=false`, auto przy `has_car=false`.
3. Normalizujemy metodą min-max każdą metrykę wśród pozostałych środków (0 = najlepszy).
4. Score to suma ważona. Wagi (czas/koszt/CO₂) zależą od priorytetu:
   - `fastest` = 0.7 / 0.2 / 0.1
   - `cheapest` = 0.2 / 0.7 / 0.1
   - `greenest` = 0.1 / 0.2 / 0.7
   - `balanced` = ⅓ / ⅓ / ⅓
5. Wygrywa najniższy score. Przy remisie decyduje stała kolejność: rower → transport publiczny → auto. Dzięki temu wynik jest deterministyczny.
6. Generujemy uzasadnienie po polsku, np. „Transport publiczny: o 12 zł taniej niż auto i tylko 6 min dłużej”.

---

## 4. REST API (`/api/v1`)

| Metoda | Ścieżka | Opis | Kody |
|---|---|---|---|
| GET | `/health` | status | 200 |
| GET | `/transport-modes` | aktualne parametry kalkulacji | 200 |
| GET | `/trips?skip=0&limit=20&q=` | lista z paginacją i wyszukiwaniem po nazwie/miejscach | 200 |
| POST | `/trips` | utworzenie podróży | 201, 422 |
| GET | `/trips/{id}` | szczegóły | 200, 404 |
| PUT | `/trips/{id}` | pełna aktualizacja | 200, 404, 422 |
| PATCH | `/trips/{id}` | częściowa aktualizacja | 200, 404, 422 |
| DELETE | `/trips/{id}` | usunięcie | 204, 404 |
| GET | `/trips/{id}/comparison?priority=` | porównanie i rekomendacja dla zapisanej podróży; `priority` opcjonalnie nadpisuje zapisany | 200, 404 |
| POST | `/comparisons` | szybkie porównanie bez zapisu (te same pola co trip, bez nazwy) | 200, 422 |

Lista zwraca `{ items, total, skip, limit }`. Wszystkie błędy mają jeden format: `{ "detail": ..., "code": "not_found" | "validation_error" }`.

---

## 5. Walidacja

### Backend (Pydantic v2)

- `Field(gt=0, le=1000)` dla dystansu, `ge=1, le=8` dla pasażerów.
- Teksty mają `min_length` i `max_length`, a `str_strip_whitespace` usuwa białe znaki z brzegów.
- `model_validator` pilnuje, żeby `origin != destination` (bez rozróżniania wielkości liter).
- `priority` jako Enum. `limit` ograniczony do 1–100.
- `TripUpdate` (PATCH) ma wszystkie pola opcjonalne i odrzuca `null` w polach wymaganych.

### Frontend

- Schematy zod odwzorowują reguły backendu i współpracują z react-hook-form.
- Błędy 422 z API mapujemy na pola formularza, żeby jedno źródło prawdy działało też przy rozjechaniu się reguł.

---

## 6. CORS i konfiguracja

- `CORSMiddleware` z `allow_origins` z env `CORS_ORIGINS`. Domyślnie `http://localhost:5173` (Vite).
- `allow_methods` obejmuje GET/POST/PUT/PATCH/DELETE, nie `*` z credentials.
- `DATABASE_URL` domyślnie `sqlite:///./smartroute.db`, z `check_same_thread=False`.
- Tabele tworzy `create_all` w `lifespan`. Alembic opisujemy w README jako następny krok, nie wchodzi do MVP.

---

## 7. Ekrany interfejsu

1. **Lista podróży (`/`)**
   - Tabela na desktopie, karty na mobile: nazwa, trasa, dystans, ikona rekomendowanego środka.
   - Wyszukiwarka, paginacja, przyciski „Nowa podróż” i „Szybkie porównanie”, stan pusty.
2. **Formularz podróży (`/trips/new`, `/trips/:id/edit`)**
   - Pola modelu, wybór priorytetu jako 4 kafelki, przełączniki „mam auto” i „rower OK”.
   - Walidacja inline, przy zapisie przycisk się blokuje i pojawia się spinner.
3. **Szczegóły i porównanie (`/trips/:id`)**
   - Banner rekomendacji z uzasadnieniem.
   - 3 karty środków transportu: czas, koszt, CO₂ i oznaczenie „niedostępne” z powodem.
   - Paski porównawcze dla każdej metryki w CSS/Tailwind, bez biblioteki wykresów.
   - Przełącznik priorytetu pozwala sprawdzić wariant „co jeśli” bez zapisu.
   - Przyciski Edytuj i Usuń (z modalem potwierdzenia).
4. **Szybkie porównanie (`/compare`)**: formularz i wyniki na jednej stronie, opcja „Zapisz jako podróż”.
5. **404 i stany błędów**: globalny toast przy błędach sieci lub API.

---

## 8. Testy

### Backend (pytest)

- Testy jednostkowe kalkulatorów: wartości brzegowe, podział na pasażerów, limit roweru.
- Testy jednostkowe rekomendacji: każdy priorytet, wykluczenia, remisy.
- Testy schematów (walidacja).
- Testy API przez `TestClient` na SQLite in-memory (`StaticPool`): pełny CRUD, 404, 422, paginacja, porównania, nagłówki CORS przy preflight.
- Cel pokrycia ≥ 85% w `pytest-cov`. Lint przez `ruff`.

### Frontend (Vitest + React Testing Library + MSW)

- Walidacja formularza.
- Renderowanie porównania i bannera rekomendacji.
- Przepływ usuwania z potwierdzeniem.
- Obsługa błędu API.
- Do tego `tsc --noEmit` i ESLint.

---

## 9. README

Zawartość:

- opis i zrzuty ekranu,
- wymagania (Python 3.12, Node 20+),
- uruchomienie backendu (venv, `pip install -e ".[dev]"`, `uvicorn`) i frontendu (`npm i`, `npm run dev`),
- zmienne środowiskowe,
- link do dokumentacji API (`/docs` w Swaggerze),
- opis algorytmu rekomendacji i założeń parametrów,
- uruchamianie testów,
- ograniczenia MVP i roadmapa (mapy/geokodowanie, Alembic, konta użytkowników, Docker).

---

## 10. Kolejność implementacji

Każdy etap to osobny commit, testy przechodzą przed przejściem dalej.

1. **Szkielet backendu:** `pyproject`, config, `main` z CORS, `/health`, conftest z testową bazą.
2. **Model i CRUD podróży:** model, schematy z walidacją, repozytorium, endpointy, testy API.
3. **Kalkulatory transportu i `ComparisonService`:** testy jednostkowe.
4. **Rekomendacja i endpointy porównań:** `/trips/{id}/comparison`, `/comparisons`, `/transport-modes`, z testami.
5. **Szkielet frontendu:** Vite, TS, Tailwind, router, klient API, typy, komponenty UI.
6. **Ekrany CRUD:** lista, formularz, usuwanie.
7. **Ekrany porównania:** szczegóły, przełącznik priorytetu, szybkie porównanie.
8. **Testy frontendu, dopracowanie UX** (stany ładowania, błędów i puste), responsywność.
9. **README i końcowe sprawdzenie:** lint, typy, pokrycie, ręczny test end-to-end.

---

## 11. Otwarte pytania

W nawiasach domyślne odpowiedzi, przyjmowane bez innej decyzji:

1. Czy dystans wpisywany ręcznie jest OK w MVP? (tak)
2. Czy zostajemy przy PLN i domyślnych parametrach z punktu 2? (tak)
3. Na froncie TanStack Query, react-hook-form i zod, a na backendzie `pip` + venv zamiast `uv`. Pasuje? (tak)
