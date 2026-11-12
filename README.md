# SmartRoute AI

Aplikacja full-stack (FastAPI + React) do porównywania środków transportu (samochód, komunikacja
miejska, rower) pod kątem
**czasu, kosztu i szacowanej emisji CO₂**, z zapisywaniem podróży i rekomendacją środka transportu
według wybranego priorytetu.

> **Status:** MVP: backend REST API oraz frontend React + TypeScript
> ([szczegóły](#frontend-react--typescript)).
> Koszty i emisje to **szacunki z uproszczonego modelu parametrycznego**, a nie bieżące ceny
> paliwa czy oficjalne taryfy. Czas komunikacji miejskiej pochodzi z **planowego rozkładu
> GTFS Static ZTM Gdańsk**, jeśli podróż ma przystanki i datę wyjazdu, a rozkład został
> zaimportowany. W przeciwnym razie używany jest szacunek. Aplikacja nie korzysta z danych
> w czasie rzeczywistym.

## Spis treści

- [Zaimplementowane funkcje](#zaimplementowane-funkcje)
- [Stack technologiczny](#stack-technologiczny)
- [Wymagania](#wymagania)
- [Szybki start (Windows)](#szybki-start-windows)
- [Uruchomienie backendu](#uruchomienie-backendu)
- [Frontend (React + TypeScript)](#frontend-react--typescript)
- [Konfiguracja](#konfiguracja)
- [Baza danych](#baza-danych)
- [Rozkład GTFS (ZTM Gdańsk)](#rozkład-gtfs-ztm-gdańsk)
- [Pogoda bieżąca (Weatherbit)](#pogoda-bieżąca-weatherbit)
- [API: przykładowe żądania](#api-przykładowe-żądania)
- [Testy i jakość kodu](#testy-i-jakość-kodu)
- [Struktura projektu](#struktura-projektu)
- [Ograniczenia MVP](#ograniczenia-mvp)
- [Planowane funkcje](#planowane-funkcje)

## Zaimplementowane funkcje

- **Frontend (dashboard)** ([szczegóły](#frontend-react--typescript)): formularz podróży
  z wyszukiwarką przystanków GTFS, wyniki porównania, rekomendacja, najbliższe odjazdy z rozkładu
  i pogoda bieżąca. Działa bez Swagger UI.
- **CRUD podróży** (`/api/v1/trips`): tworzenie, lista z paginacją i wyszukiwaniem (bez względu
  na wielkość liter, także dla polskich znaków), odczyt, pełna (`PUT`) i częściowa (`PATCH`)
  aktualizacja, usuwanie.
- **Walidacja danych wejściowych**: dystans 0–1000 km, 1–8 pasażerów, punkt startu i cel muszą się
  różnić, nieznane pola są odrzucane, a w `PATCH` nie można ustawić pól wymaganych na `null`.
- **Porównanie środków transportu** (`GET /api/v1/trips/{id}/compare`): dla każdego wariantu
  zwraca czas od drzwi do drzwi, koszt (łączny i na osobę), emisję CO₂ (łączną i na osobę),
  dostępność wariantu z powodem niedostępności oraz listę przyjętych założeń.
- **Rekomendacja** według priorytetu `fastest`, `cheapest`, `greenest` lub `balanced`
  (normalizacja min-max, wagi po 1/3, deterministyczny tie-break) wraz z opisem w języku polskim.
  Priorytet można nadpisać parametrem zapytania bez zapisywania go w bazie.
- **Parametry modelu w konfiguracji** (prędkości, spalanie, ceny, emisje), które można nadpisać
  zmiennymi środowiskowymi.
- **Rozkład GTFS Static ZTM Gdańsk** ([szczegóły](#rozkład-gtfs-ztm-gdańsk)):
  - importer CLI z URL lub lokalnego ZIP-a,
  - wyszukiwanie przystanków (`GET /api/v1/stops`),
  - bezpośrednie połączenia według kalendarza kursowania (`GET /api/v1/connections`),
  - opcjonalne pola podróży `origin_stop_id`, `destination_stop_id` i `departure_at`; gdy są
    ustawione, porównanie używa czasu z rozkładu (`data_source: "gtfs_schedule"`).
- **Pogoda bieżąca Weatherbit** ([szczegóły](#pogoda-bieżąca-weatherbit)): opcjonalna,
  jawna korekta komfortu i czasu roweru dla podróży „teraz”, z cache i bezpiecznym
  fallbackiem.
- **Health check** (`/api/v1/health`) ze sprawdzeniem połączenia z bazą.
- **Spójny format błędów** `{"detail": ..., "code": "not_found" | "validation_error" | "gtfs_not_imported"}`.
- **CORS** skonfigurowany pod przyszły frontend (domyślnie Vite dev server).

## Stack technologiczny

| Obszar      | Technologia                                    |
|-------------|------------------------------------------------|
| Język       | Python 3.12                                    |
| Framework   | FastAPI, Uvicorn                               |
| Baza danych | SQLite, SQLAlchemy 2.0 (ORM)                   |
| Rozkład     | GTFS Static (stdlib `csv`/`zipfile`/`zoneinfo` + `tzdata`) |
| Walidacja   | Pydantic v2, pydantic-settings                 |
| Testy       | pytest, pytest-cov, httpx (FastAPI TestClient) |
| Lint/format | Ruff                                           |
| Frontend    | React 19, TypeScript 6, Vite 8, Tailwind CSS 4, Lucide React |
| Testy (FE)  | Vitest, Testing Library, jsdom; ESLint (typescript-eslint, react-hooks) |

Zależności są zdefiniowane w [`backend/pyproject.toml`](backend/pyproject.toml). Zweryfikowane,
przypięte wersje są w [`backend/requirements-lock.txt`](backend/requirements-lock.txt), który
`setup.ps1` stosuje jako plik constraints.

## Wymagania

- Windows 10/11 z Windows PowerShell 5.1 lub PowerShell 7+
- **Python 3.12.x** (`pyproject.toml` wymaga `>=3.12,<3.13`), instalator z
  [python.org](https://www.python.org/downloads/). Skrypt szuka go przez launcher `py -3.12`
  albo `python` w `PATH`.
- Git
- **Node.js ≥ 22.12** (wymóg Vite 8) z npm, tylko dla frontendu. Testowano na Node 26 i npm 11.
- Dostęp do internetu przy pierwszej instalacji zależności (PyPI, npm)

Sprawdzenie wersji Pythona:

```powershell
py -3.12 --version
```

## Szybki start (Windows)

```powershell
git clone <URL-repozytorium> smartroute-ai
cd smartroute-ai
powershell -ExecutionPolicy Bypass -File .\setup.ps1
powershell -ExecutionPolicy Bypass -File .\import-gtfs.ps1   # opcjonalnie: rozkład ZTM (~30 s)
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Następnie otwórz Swagger UI: **http://127.0.0.1:8000/docs**. Frontend uruchamia się w drugim
terminalu ([instrukcja](#frontend-react--typescript)):

```powershell
cd frontend
npm install
npm run dev          # http://localhost:5173
```

Bez importu rozkładu aplikacja działa jak wcześniej. `/stops` i `/connections` zwracają wtedy
`503 gtfs_not_imported`, a porównanie używa szacunku parametrycznego.

> **Execution Policy:** domyślnie Windows blokuje uruchamianie skryptów `.ps1`. Flaga
> `-ExecutionPolicy Bypass` działa tylko dla tego jednego wywołania i niczego nie zmienia na
> stałe. Jeśli wolisz uruchamiać skrypty bezpośrednio (`.\setup.ps1`), zmień politykę dla
> swojego użytkownika: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### Co robi `setup.ps1`

1. Tworzy `.venv` w katalogu głównym repozytorium z Pythona 3.12, jeśli `.venv` jeszcze nie ma.
   Jeśli istniejące `.venv` ma inną wersję Pythona, skrypt kończy się błędem i niczego nie usuwa.
2. Instaluje backend w trybie edytowalnym z dodatkami dev:
   `pip install -e "backend[dev]" -c backend/requirements-lock.txt`, a potem uruchamia `pip check`.
3. Kopiuje `backend/.env.example` do `backend/.env`, jeśli `backend/.env` nie istnieje.
   Istniejący plik zostaje bez zmian.

Skrypt można bezpiecznie uruchamiać wielokrotnie. Opcja `-NoDev` instaluje tylko zależności
potrzebne do uruchomienia aplikacji.

<details>
<summary>Instalacja ręczna (bez skryptu)</summary>

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]" -c .\backend\requirements-lock.txt
Copy-Item .\backend\.env.example .\backend\.env
```

</details>

## Uruchomienie backendu

```powershell
.\run.ps1                       # http://127.0.0.1:8000, z auto-reload
.\run.ps1 -Port 8080            # inny port
.\run.ps1 -NoReload             # bez auto-reload
.\run.ps1 -BindHost 0.0.0.0     # dostęp z sieci lokalnej
```

`run.ps1` używa interpretera z `.venv` i uruchamia Uvicorn **z katalogu `backend/`**, niezależnie
od tego, skąd wywołano skrypt. Ma to znaczenie, bo z tego katalogu wczytywany jest `.env`
i względem niego liczona jest ścieżka do bazy SQLite.

Odpowiednik ręczny:

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

| Adres                                  | Opis                   |
|----------------------------------------|------------------------|
| http://127.0.0.1:8000/docs             | Swagger UI             |
| http://127.0.0.1:8000/redoc            | ReDoc                  |
| http://127.0.0.1:8000/openapi.json     | Specyfikacja OpenAPI   |
| http://127.0.0.1:8000/api/v1/health    | Health check           |

## Frontend (React + TypeScript)

Jednostronicowy dashboard w katalogu [`frontend/`](frontend). Wszystkie dane pochodzą z API
backendu: frontend nie liczy własnych rekomendacji, nie ma danych demonstracyjnych i nie łączy
się z Weatherbit (klucz zostaje w `backend/.env`).

### Uruchomienie

Wymaga działającego backendu (`.\run.ps1`). Wyszukiwarka przystanków potrzebuje zaimportowanego
rozkładu (`.\import-gtfs.ps1`).

```powershell
cd frontend
npm install          # pierwsza instalacja (wersje przypięte w package-lock.json)
npm run dev          # dev server: http://localhost:5173
```

| Polecenie           | Opis                                                     |
|---------------------|----------------------------------------------------------|
| `npm run dev`       | serwer deweloperski Vite z proxy `/api` → backend        |
| `npm run build`     | kontrola typów (`tsc -b`) + build produkcyjny do `dist/` |
| `npm run preview`   | podgląd buildu produkcyjnego (port 4173, także z proxy)  |
| `npm run typecheck` | sama kontrola TypeScript                                 |
| `npm run lint`      | ESLint                                                   |
| `npm test`          | testy Vitest (jsdom, bez sieci i bez backendu)           |

### Komunikacja z backendem

- Frontend wysyła żądania na względny adres `/api/v1`. Dev server Vite
  ([`vite.config.ts`](frontend/vite.config.ts)) przekazuje `/api` do `http://127.0.0.1:8000`,
  więc przeglądarka widzi jeden origin i CORS nie jest potrzebny.
- Inny adres backendu dla proxy ustawisz zmienną `VITE_BACKEND_PROXY_TARGET` w
  `frontend/.env.local` (wzór: [`frontend/.env.example`](frontend/.env.example)).
- Bez proxy, np. przy statycznym hostingu `dist/`, ustaw `VITE_API_BASE_URL`
  (np. `http://127.0.0.1:8000/api/v1`) i dodaj origin frontendu do `CORS_ORIGINS` w
  `backend/.env`. Domyślnie backend dopuszcza `http://localhost:5173`.

Przepływ porównania ([`useComparison.ts`](frontend/src/hooks/useComparison.ts)):

1. `GET /stops?query=…`: podpowiedzi przystanków (opóźnienie 250 ms, anulowanie nieaktualnych
   żądań).
2. `POST /trips`: zapis podróży z `origin_stop_id`, `destination_stop_id` i `departure_at`
   (czas lokalny Gdańska bez strefy). Jako `origin` i `destination` trafiają nazwy przystanków.
3. `GET /trips/{id}/compare` oraz równolegle `GET /connections` (okno 180 min, zgodne
   z `GTFS_SEARCH_WINDOW_MIN`). Odpowiedź `/compare` zawiera tylko najlepszy kurs w
   `assumptions`, więc listę odjazdów pobieramy osobno.
4. Zmiana samego priorytetu, przy niezmienionych pozostałych danych, nie tworzy nowej podróży.
   Używa wtedy parametru `?priority=` na tej samej podróży.

Typy w [`src/types/api.ts`](frontend/src/types/api.ts) odwzorowują schematy Pydantic
z `backend/app/schemas`. Błędy `{detail, code}` są zamieniane na komunikaty po polsku
([`utils/errors.ts`](frontend/src/utils/errors.ts)), a błędy 422 trafiają do konkretnych pól.

### Układ i decyzje UX

Ekran czyta się od góry do dołu: planer podróży, potem wyniki, a na końcu pomoc.

- **Planer na pełnej szerokości zamiast wąskiej kolumny.** Formularz jest kompaktowym, poziomym
  panelem (kontener do 1440 px). Na desktopie mieści się w 2–3 wierszach: trasa i termin, potem
  dystans i priorytet, potem pasek opcji z przyciskiem „Porównaj”. Wyniki zajmują całą szerokość
  pod formularzem, więc nie zostaje pusta kolumna. Przycisk nie jest przyklejony (sticky), więc
  niczego nie zasłania na małych ekranach.
- **Najważniejsze pola widoczne, drugorzędne zwinięte.** Przystanki, termin, dystans i priorytet
  są zawsze widoczne. Pasażerowie i dostępność samochodu i roweru tworzą kompaktowy pasek.
  Nazwa podróży jest w sekcji „Opcje zaawansowane”, która otwiera się sama, gdy pole ma błąd.
- **Mniej stałego drobnego tekstu.** Dłuższe wyjaśnienia przeniesiono do dymków `InfoTip`
  (hover, focus klawiatury, dotyk, Escape; treść podpięta przez `aria-describedby`) i do
  rozwijanych sekcji. Informacja, że dystans jest szacunkowy, zostaje w etykiecie pola.
- **Karty wariantów z metrykami w wierszach.** Etykieta „Czas / Koszt / CO₂” stoi po lewej,
  a duża wartość liczbowa po prawej. Wartości w kolejnych kartach leżą na tej samej wysokości,
  więc łatwo je porównać. Siatka ma 3 kolumny dopiero od `xl` (≥ 1280 px), 2 + 1 na tabletach
  (ostatnia karta na pełną szerokość) i 1 kolumnę na telefonie. Gdy karta jest szeroka (container
  query `@md`), metryki układają się w 3 kolumny. Miejsce w rankingu to krótki tekst
  („Miejsce 2 z 3”), a rekomendowany wariant ma etykietę „Rekomendowany”, nie tylko kolor.
- **Kompaktowa rekomendacja.** Panel pokazuje nazwę wariantu, priorytet, pierwsze zdanie
  uzasadnienia z backendu, korzyści wynikające z danych (np. „Najniższy koszt”) i trzy kluczowe
  liczby. Pełne uzasadnienie i opis metody są w sekcji rozwijanej. Ostrzeżenia (pogoda,
  pominięte warianty, remis) są zawsze widoczne.
- **Pomoc pod aplikacją.** Sekcja „Jak to działa?” to zwinięte akordeony pod wynikami, a stan
  początkowy to jedna krótka zachęta bez fikcyjnych wyników.
- **Szybka korekta.** Pasek podsumowania nad wynikami pozwala zmienić priorytet jednym kliknięciem
  i ma przycisk „Edytuj”, który przewija do formularza i ustawia focus na pierwszym polu.

### Prezentacja danych GTFS i szacunków

Czas komunikacji miejskiej i lista odjazdów to dwie różne informacje, prezentowane osobno:

| Sytuacja | Karta „Komunikacja miejska” | Panel „Odjazdy z rozkładu” |
|----------|-----------------------------|----------------------------|
| Backend użył rozkładu (`data_source: gtfs_schedule`) | „Czas z rozkładu GTFS” + linia, kierunek i godzina odjazdu | lista kursów, użyty kurs oznaczony „użyty w porównaniu” |
| Szacunek, a rozkład nie ma kursu bezpośredniego w oknie 180 min | etykieta czasu „Czas (szac.)” i ostrzeżenie **„Czas szacunkowy — brak potwierdzonego kursu GTFS”** | „Brak kursu bezpośredniego w rozkładzie”, informacja, że **nie oznacza to braku połączenia z przesiadką**, sugestie i przycisk „Zmień przystanki lub godzinę” |
| Szacunek, a rozkładu nie udało się pobrać | „Czas szacunkowy — nie sprawdzono rozkładu” | komunikat błędu z instrukcją |

- Wariant komunikacji zostaje w porównaniu zawsze wtedy, gdy zwraca go backend. Frontend
  niczego nie przelicza i nie zmienia rankingu.
- Kurs z panelu jest oznaczany jako użyty tylko po jednoznacznym dopasowaniu linii i godziny
  odjazdu do założeń backendu ([`utils/transit.ts`](frontend/src/utils/transit.ts)). Karta
  i panel korzystają z tego samego wyniku, więc nie mogą sobie przeczyć.
- Odjazdy mają etykietę „GTFS Static · bez opóźnień”. Nie pokazujemy fikcyjnych opóźnień ani
  danych w czasie rzeczywistym.

### Najważniejsze funkcje

- Wyszukiwarka przystanków GTFS jako dostępny combobox (strzałki, Enter, Escape). Po wyborze
  widoczna jest nazwa i numer słupka. Dostępne są przyciski „Zmień” i „Zamień kierunek”,
  a przystanku wybranego w drugim polu nie da się wybrać ponownie.
- Data i godzina ustawiają się domyślnie na „teraz” w strefie Europe/Warsaw. Jest przycisk
  „Ustaw teraz” i ostrzeżenie o terminie w przeszłości.
- **Dystans szacunkowy w km** wpisuje użytkownik. Jako punkt odniesienia formularz pokazuje
  odległość w linii prostej między przystankami z dopiskiem „trasa będzie dłuższa”. Aplikacja
  nie wyznacza trasy drogowej.
- Pasażerowie (1–8), priorytet w formie segmentów z opisem wybranej opcji, przełączniki
  samochodu i roweru, opcjonalna nazwa (domyślnie „Start → Cel”).
- Karty wariantów pokazują czas, koszt i CO₂ (łącznie i na osobę), miejsce w rankingu,
  dostępność z powodem, pochodzenie danych, komfort pogodowy oraz rozwijane założenia.
- Panel pogody pokazuje temperaturę, wiatr, opady, śnieg i wpływ na rower, z etykietą „aktualne
  warunki, nie prognoza”. Gdy danych brak, wyświetla neutralny komunikat.
- Wskaźnik stanu backendu i komunikat z instrukcją, gdy backend nie działa.

### Heurystyki Nielsena w interfejsie

| # | Heurystyka | Zastosowanie | Komponenty |
|---|------------|--------------|------------|
| 1 | Widoczność stanu systemu | Spinner w wyszukiwarce i na przycisku („Zapisywanie podróży…”, „Obliczanie porównania…”), szkielet wyników, przyciemnienie przy przeliczaniu, status backendu w nagłówku, komunikaty `aria-live`, blokada ponownego wysłania, przycisk „Porównaj ponownie” po pierwszym wyniku | `StopPicker`, `TripForm`, `DashboardPage`, `Header` |
| 2 | Zgodność ze światem rzeczywistym | Polskie etykiety, `Intl` pl-PL (`2,50 zł`, `0,94 kg`, `1 h 5 min`), godziny w czasie Gdańska, nazwy przystanków zamiast `stop_id`, „tramwaj/autobus” zamiast `route_type`, „za 5 min” zamiast surowego czasu oczekiwania | `utils/format.ts`, `VariantCard`, `SchedulePanel` |
| 3 | Kontrola i swoboda | Formularz zawsze nad wynikami, „Edytuj” w pasku podsumowania, „Zmień przystanki lub godzinę” przy braku kursu, „Zmień” i „Zamień kierunek”, szybka zmiana priorytetu, dane zachowane po błędzie, „Spróbuj ponownie” | `TripForm`, `ResultsSection`, `SchedulePanel`, `StopPicker` |
| 4 | Spójność i standardy | Wspólne klasy `card`/`btn`/`input`/`badge`, ten sam selektor priorytetu w formularzu i nad wynikami, ten sam układ metryk w każdej karcie, stałe kolory i ikony środków transportu, etykiety pól zgodne z podsumowaniem błędów | `index.css`, `PrioritySelector`, `VariantCard`, `ModeIcon` |
| 5 | Zapobieganie błędom | Walidacja przed wysłaniem (przystanki, różne przystanki, dystans > 0 i ≤ 1000, 1–8 pasażerów, poprawna data i godzina), blokada wyboru tego samego przystanku, przyciski +/−, wybór przystanku tylko z listy, `maxLength` nazwy | `utils/tripForm.ts`, `StopPicker`, `TripForm` |
| 6 | Rozpoznawanie zamiast przypominania | Podpowiedzi przystanków bez polskich znaków, nazwa i słupek wybranego przystanku, stały opis wybranego priorytetu, korzyści rekomendacji nazwane wprost, użyty kurs oznaczony w rozkładzie | `StopPicker`, `PrioritySelector`, `RecommendationPanel`, `SchedulePanel` |
| 7 | Elastyczność i efektywność | Kompaktowy planer (mniej przewijania), domyślnie „teraz”, 1 pasażer i „zrównoważony”, automatyczna nazwa, „Wstaw” dystans w linii prostej jako punkt wyjścia, zmiana priorytetu bez tworzenia nowej podróży, automatyczne przewinięcie do wyników | `TripForm`, `useComparison`, `ResultsSection`, `DashboardPage` |
| 8 | Estetyka i minimalizm | Hierarchia: podsumowanie → rekomendacja → karty → rozkład i pogoda → objaśnienia. Lead zamiast pełnego uzasadnienia, szczegóły w dymkach i sekcjach rozwijanych, mniej ramek w ramkach | `RecommendationPanel`, `VariantCard`, `ui/InfoTip`, `HelpPanel` |
| 9 | Rozpoznawanie i naprawa błędów | Komunikaty zamiast kodów HTTP, z krokami naprawy (`run.ps1`, `import-gtfs.ps1`), błędy 422 przy polach, podsumowanie błędów z linkami, przy braku kursu GTFS: wyjaśnienie (inny słupek, godzina, przesiadki nieobsługiwane) i przycisk powrotu do formularza | `utils/errors.ts`, `TripForm`, `SchedulePanel`, `DashboardPage` |
| 10 | Pomoc i dokumentacja | Akordeony „Jak to działa?” pod aplikacją (metoda, szacunki, GTFS, Weatherbit, ograniczenia), dymki przy dystansie, przełącznikach, rozkładzie i pogodzie, metoda przy rekomendacji | `HelpPanel`, `ui/InfoTip`, `RecommendationPanel` |

Dostępność: semantyczne sekcje i nagłówki, etykiety pól, `aria-invalid` i `aria-describedby`
dla błędów, `role="alert"` dla błędów wymagających reakcji, widoczny focus, link „Przejdź do
formularza”, natywne radio i checkbox (`role="switch"`), cele klikalne o wysokości co najmniej
40 px, obsługa `prefers-reduced-motion`. Wyłączony środek transportu jest przekreślony,
a nie tylko wyszarzony. Układ docelowo obsługuje szerokości 360, 768, 1024 i 1440 px; patrz
[ręczna weryfikacja](#ręczna-weryfikacja-układu).

### Ręczna weryfikacja układu

Testy automatyczne (jsdom) nie sprawdzają wyglądu. Przed prezentacją warto w DevTools
(tryb urządzenia) sprawdzić szerokości 360, 768, 1024 i 1440 px:

1. Brak poziomego paska przewijania. Pola daty i godziny oraz pasek opcji mieszczą się w kadrze.
2. Planer: na 1440 px ma 3 wiersze, a przycisk „Porównaj” jest po prawej. Na 360 px pola
   są w jednej kolumnie, a przycisk na pełną szerokość.
3. Karty: 3 w rzędzie na 1440 px, 2 + 1 na 768 i 1024 px, jedna kolumna na 360 px. Nazwy
   i wartości nie łamią się.
4. Trasa bez kursu bezpośredniego (np. **Dworzec Główny 02 → Zaspa 01**): karta komunikacji
   pokazuje „Czas szacunkowy — brak potwierdzonego kursu GTFS”, a panel pokazuje wyjaśnienie
   i przycisk „Zmień przystanki lub godzinę”.
5. Trasa z kursem (np. **Dworzec Główny 01 → Zaspa 01**): karta pokazuje „Czas z rozkładu GTFS”,
   a w panelu jeden kurs ma oznaczenie „użyty w porównaniu”.
6. Nawigacja wyłącznie klawiaturą: Tab, strzałki w liście przystanków i w priorytecie, Escape
   zamyka dymek.

### Struktura

```
frontend/
├── index.html  vite.config.ts  eslint.config.js  tsconfig*.json  .env.example
└── src/
    ├── main.tsx  App.tsx  index.css   # punkt wejścia, motyw Tailwind (@theme)
    ├── pages/DashboardPage.tsx        # układ i orkiestracja przepływu
    ├── components/                    # TripForm, StopPicker, PrioritySelector, ResultsSection,
    │   │                              # VariantCard, RecommendationPanel, SchedulePanel,
    │   │                              # WeatherPanel, HelpPanel, Header, EmptyState, ModeIcon
    │   └── ui/                        # Alert, Spinner, InfoTip
    ├── hooks/                         # useComparison, useStopSearch, useBackendHealth
    ├── services/                      # apiClient (fetch + ApiError), smartrouteApi (endpointy)
    ├── types/api.ts                   # typy kontraktu API
    ├── utils/                         # formatowanie, data/czas, walidacja, błędy, etykiety,
    │                                  # wyniki, status GTFS (transit.ts)
    └── test/setup.ts
```

## Konfiguracja

Konfiguracja jest oparta na `pydantic-settings` ([`backend/app/core/config.py`](backend/app/core/config.py)).
Każda wartość ma rozsądny domyślny odpowiednik, więc plik `.env` **nie jest wymagany**. Wartości
można nadpisać plikiem `backend/.env` albo zmiennymi środowiskowymi, przy czym zmienne środowiskowe
mają pierwszeństwo.

| Zmienna         | Domyślnie                    | Opis                                       |
|-----------------|------------------------------|--------------------------------------------|
| `APP_NAME`      | `SmartRoute AI`              | Nazwa w Swagger UI i health check          |
| `ENVIRONMENT`   | `development`                | `development` / `test` / `production`      |
| `DEBUG`         | `false`                      | Tryb debug FastAPI i logowanie SQL         |
| `DATABASE_URL`  | `sqlite:///./smartroute.db`  | URL bazy; ścieżka względna liczona od `backend/` |
| `CORS_ORIGINS`  | `http://localhost:5173`      | Lista originów rozdzielona przecinkami     |
| `TRANSPORT__*`  | zob. `transport_params.py`   | Parametry modelu, np. `TRANSPORT__CAR__FUEL_PRICE_PLN_PER_L=6.89` |
| `GTFS_DATABASE_URL` | `sqlite:///./gtfs.db`    | Osobna baza rozkładu (tworzy ją importer)  |
| `GTFS_FEED_URL` | oficjalny feed ZTM Gdańsk    | Domyślne źródło importu                    |
| `GTFS_SEARCH_WINDOW_MIN` | `180`               | Okno szukania połączenia przy porównaniu [min] |
| `GTFS_MAX_DOWNLOAD_MB` | `200`                 | Limit rozmiaru pobieranego ZIP-a           |
| `WEATHERBIT_API_KEY` | brak (wyłączone)       | Klucz Weatherbit — tylko w `.env` / env    |
| `WEATHER_TIMEOUT_S` | `5`                     | Timeout zapytania HTTP [s]                 |
| `WEATHER_CACHE_TTL_S` | `1800`                | Cache odczytu na lokalizację [s]           |
| `WEATHER_ERROR_COOLDOWN_S` | `300`            | Przerwa w zapytaniach po błędzie / 429 [s] |
| `WEATHER_MAX_LEAD_MIN` | `120`                | Maks. czas do odjazdu, by użyć pogody [min] |

Pełna lista parametrów modelu z jednostkami jest w [`backend/.env.example`](backend/.env.example)
i [`backend/app/core/transport_params.py`](backend/app/core/transport_params.py).

## Baza danych

- SQLite. Są dwa pliki, oba ignorowane przez Git:
  - `backend/smartroute.db`: podróże; tworzy go aplikacja,
  - `backend/gtfs.db`: rozkład; tworzy go wyłącznie importer, około 125 MB dla feedu ZTM.
- **Nie trzeba wykonywać żadnych ręcznych kroków.** Przy starcie aplikacja wywołuje
  `Base.metadata.create_all()`, które tworzy brakujące tabele (obecnie `trips`), a następnie
  `upgrade_schema()` ([`app/db/migrations.py`](backend/app/db/migrations.py)).
- **Migracja z wcześniejszej wersji:** `upgrade_schema()` dodaje do istniejącej tabeli `trips`
  kolumny `origin_stop_id`, `destination_stop_id` i `departure_at` (`ALTER TABLE ... ADD COLUMN`,
  wszystkie nullable). Operacja jest idempotentna i nie zmienia istniejących wierszy, a stare
  podróże dostają w nowych polach `null`.
- Pełne migracje (Alembic) są poza zakresem MVP. Przy innych zmianach modelu na etapie
  developmentu usuń `backend/smartroute.db` (to usunie zapisane podróże).
- Reset bazy podróży: zatrzymaj serwer i wykonaj `Remove-Item .\backend\smartroute.db`.

## Rozkład GTFS (ZTM Gdańsk)

Źródło: [Otwarte Dane Gdańsk, GTFS Static ZTM](https://ckan.multimediagdansk.pl/dataset/c24aa637-3619-4dc2-a171-a23eec8f2172/resource/30e783e4-2bec-4a7d-bb22-ee3e3b26ca96/download/gtfsgoogle.zip).
Aplikacja **nigdy nie pobiera danych w trakcie obsługi żądania**. Rozkład trafia do lokalnej bazy
SQLite tylko przez importer.

### Import i odświeżanie

```powershell
.\import-gtfs.ps1                                   # pobierz oficjalny feed i zaimportuj
.\import-gtfs.ps1 -Source C:\dane\gtfsgoogle.zip    # import z lokalnego pliku

# to samo bez wrappera:
cd backend
..\.venv\Scripts\python.exe -m app.cli.gtfs import
..\.venv\Scripts\python.exe -m app.cli.gtfs import --source C:\dane\gtfsgoogle.zip
..\.venv\Scripts\python.exe -m app.cli.gtfs info    # źródło, data importu, ważność, liczby rekordów
```

- **Odświeżanie:** ZTM publikuje feed codziennie, a każda wersja obejmuje około 15 dni.
  Uruchamiaj import regularnie, np. raz dziennie z Harmonogramu zadań Windows.
  `GET /connections` zwraca `feed.valid_from` i `feed.valid_to`, a dla daty spoza tego zakresu
  dodaje uwagę w `notes`.
- **Ponowny import** zastępuje cały rozkład w jednej transakcji. Przy błędzie (uszkodzony ZIP,
  brak wymaganego pliku lub kolumny) poprzedni rozkład zostaje nietknięty. Baza działa w trybie
  WAL, więc działający serwer może czytać stare dane w trakcie importu i nie trzeba go zatrzymywać.
- **Pamięć i bezpieczeństwo:** pliki CSV są czytane strumieniowo z ZIP-a i wstawiane partiami.
  Szczyt pamięci przy pełnym feedzie to około 50 MB. Importer niczego nie rozpakowuje na dysk
  i czyta tylko znane pliki z katalogu głównego archiwum. Odrzuca pliki zaszyfrowane, większe
  niż 1 GiB po rozpakowaniu i o podejrzanym współczynniku kompresji. Pobieranie ma limit
  `GTFS_MAX_DOWNLOAD_MB` i timeout.
- **Wadliwe wiersze** (zły format czasu, nieznany kurs lub przystanek, zła data) są pomijane.
  Ich liczbę i pierwsze przykłady pokazuje raport importu.

### Zweryfikowana struktura feedu ZTM (pobranego 11.11.2026)

| Plik | Wiersze | Uwagi |
|---|---:|---|
| `agency.txt` | 1 | `agency_timezone=Europe/Warsaw` |
| `feed_info.txt` | 1 | `feed_start_date` puste, `feed_end_date=20261125` |
| `calendar.txt` | — | **brak pliku**; kalendarz wyłącznie w `calendar_dates.txt` |
| `calendar_dates.txt` | 60 | tylko `exception_type=1`, 11–25.11.2026 |
| `routes.txt` | 93 | `route_type` rozszerzony: 700 (autobus), 900 (tramwaj) |
| `stops.txt` | 1 625 | słupki (np. „Dworzec Główny 01”), bez stacji nadrzędnych |
| `trips.txt` | 92 600 | `direction_id` 0/1, `trip_headsign` |
| `stop_times.txt` | 2 212 094 | czasy do `29:25:00`, `pickup_type`/`drop_off_type` ∈ {0, 1, 3} |
| `shapes.txt` | — | nieimportowany (niepotrzebny do wyznaczania czasu) |

Pliki są w UTF-8 bez BOM, z końcami linii CRLF. Importer akceptuje też `calendar.txt`,
`exception_type=2` i plik z BOM.

### Jak liczone są połączenia

- **Tylko połączenia bezpośrednie.** Kurs musi zatrzymać się na przystanku startowym, a potem,
  z wyższym `stop_sequence`, na docelowym. Kurs w przeciwnym kierunku nie zostanie zwrócony.
- Pomijane są postoje z `pickup_type=1` na starcie i `drop_off_type=1` na celu. Wartość `3`
  (ZTM używa jej dla przystanków na żądanie) jest traktowana jako dostępna.
- **Kalendarz:** kurs liczy się tylko w dniu, w którym jego `service_id` kursuje.
- **Czasy ≥ 24:00 i strefa czasowa:** czasy GTFS są liczone od „południa minus 12 h” dnia
  kursowania w `agency_timezone` (Europe/Warsaw), co poprawnie obsługuje zmianę czasu.
  Kurs z kalendarza 12.11 o `24:20:00` przyjeżdża 13.11 o 00:20. Wyszukiwanie po północy
  uwzględnia też kursy z poprzedniego dnia kursowania (`service_date` w odpowiedzi).
- `departure_at` bez strefy jest interpretowane jako czas lokalny Europe/Warsaw. Odpowiedzi
  zawierają przesunięcie, np. `+01:00`.

### Integracja z porównaniem

Podróż może mieć opcjonalne `origin_stop_id`, `destination_stop_id` (wartości `stop_id`
z `GET /stops`) i `departure_at`. Tekstowe `origin`/`destination` nigdy nie są zamieniane
na przystanek. Wariant „Komunikacja miejska” w `GET /trips/{id}/compare`:

- **`data_source: "gtfs_schedule"`**, gdy istnieje bezpośrednie połączenie w ciągu
  `GTFS_SEARCH_WINDOW_MIN` (180 min) od `departure_at`. Czas to oczekiwanie od `departure_at`
  do odjazdu plus przejazd, bez dojścia do przystanków. Linia, odjazd i przyjazd są opisane
  w `assumptions`.
- **`data_source: "parametric_estimate"`** w każdym innym przypadku. Gdy podano któreś z pól
  GTFS, pierwsza pozycja `assumptions` wyjaśnia powód: brak połączenia, nieznany przystanek,
  brakujące pole albo nie zaimportowany rozkład.
- Podróże bez pól GTFS są liczone dokładnie tak jak wcześniej. Koszt biletu i CO₂ zawsze
  pochodzą z parametrów modelu.

## Pogoda bieżąca (Weatherbit)

Opcjonalna korekta wariantu „Rower” na podstawie **bieżącej** pogody z
[Weatherbit Current Weather API](https://www.weatherbit.io/api/weather-current)
(`GET /v2.0/current`, darmowy plan). Prognozy i płatne funkcje nie są używane.

### Konfiguracja

1. Załóż konto na weatherbit.io i skopiuj klucz API (aktywacja nowego klucza może chwilę potrwać,
   do tego czasu API odpowiada błędem 401/403).
2. Wpisz go **wyłącznie** w `backend/.env` (plik jest w `.gitignore`) albo w zmiennej
   środowiskowej:

   ```
   WEATHERBIT_API_KEY=twoj_klucz
   ```

3. Uruchom ponownie backend (`.\run.ps1`). Bez klucza integracja jest wyłączona, a porównanie
   działa jak wcześniej (`weather.status: "disabled"`).

Klucz jest typu `SecretStr` (maskowany w `repr`), nie trafia do logów ani komunikatów błędów,
a wyjątki HTTP, których URL zawiera klucz, nie są dołączane do tracebacków. Pozostałe ustawienia
(`WEATHER_TIMEOUT_S`, `WEATHER_CACHE_TTL_S`, `WEATHER_ERROR_COOLDOWN_S`, `WEATHER_MAX_LEAD_MIN`)
opisuje [Konfiguracja](#konfiguracja).

### Kiedy pogoda jest uwzględniana

Korekta jest stosowana tylko wtedy, gdy spełnione są wszystkie warunki. Inaczej `weather.status`
podaje powód, a `weather.explanation` go wyjaśnia:

| Warunek | Status przy niespełnieniu |
|---|---|
| Rower jest dostępny dla podróży | `not_applicable` |
| Ustawiono `WEATHERBIT_API_KEY` | `disabled` |
| `departure_at` jest od 60 min wstecz do `WEATHER_MAX_LEAD_MIN` (120 min) w przód od teraz | `out_of_time_window` |
| Podróż ma `origin_stop_id`, a przystanek GTFS ma współrzędne | `no_location` |
| Weatherbit odpowiedział (z cache lub z API) | `unavailable` |

- **Lokalizacja** to współrzędne przystanku startowego z rozkładu GTFS. Tekstowe `origin`
  (np. „Gdańsk”) nigdy nie jest zamieniane na współrzędne.
- **Pogoda bieżąca to nie prognoza** (`weather.is_forecast: false`). Dla podróży za kilka godzin
  lub dni korekta jest pomijana.
- **Błędy nie psują porównania.** Timeout, HTTP 429, odrzucony klucz, brak internetu i niepoprawna
  odpowiedź dają `status: "unavailable"`, a wynik jest identyczny jak bez pogody.

### Limit zapytań

- Timeout HTTP: 5 s.
- Cache w pamięci procesu: 30 min na komórkę siatki 0,1° (kilka km). Zapytanie wysyłane jest dla
  środka komórki, więc wszystkie przystanki w okolicy dzielą jeden odczyt.
- Po każdym błędzie klient przez 5 min nie odpytuje API (dla żadnej lokalizacji).
- Gdy rower jest niedostępny, termin jest poza oknem albo brak lokalizacji, zapytanie w ogóle
  nie jest wysyłane.

Jednostki: zapytanie zawsze ma `units=M`, czyli temperatura w °C, opad (`precip`, `snow`) w mm/h
i wiatr (`wind_spd`) w m/s. Wiatr jest przeliczany na km/h (× 3,6).

### Heurystyki komfortu roweru

Reguły są deterministyczne ([`app/services/weather/adjustment.py`](backend/app/services/weather/adjustment.py)),
a progi są przyjętymi założeniami MVP:

| Czynnik | Komfort `reduced` | Komfort `poor` |
|---|---|---|
| Opad | ≥ 0,2 mm/h | ≥ 2,5 mm/h |
| Burza, śnieg, marznący deszcz (kody 2xx, 511, 6xx) | — | zawsze |
| Wiatr | ≥ 25 km/h (czas roweru +10%) | ≥ 40 km/h (czas roweru +20%) |
| Temperatura | ≤ 3 °C lub ≥ 28 °C | ≤ -5 °C lub ≥ 33 °C |

Wynikowy komfort (`good` / `reduced` / `poor`) to najgorszy z czynników.

**Wpływ na rekomendację:**

- **Wagi czasu, kosztu i CO₂ się nie zmieniają.** Pogoda nie jest ukrytą czwartą metryką.
- **Wiatr** wydłuża szacowany czas roweru. Dlatego zmienia wynik `fastest` i `balanced` tak samo
  jak każda inna zmiana czasu i jest opisany w `assumptions`.
- **Komfort `poor`** uruchamia jawną regułę (`scoring.comfort_rule`): rower trafia na koniec
  rankingu przy każdym priorytecie (`score.weather_demoted: true`), o ile istnieje inny dostępny
  wariant. Wśród pozostałych wariantów priorytet działa bez zmian. Na przykład `greenest` w ulewie
  wybiera najniższą emisję spośród wariantów o akceptowalnym komforcie, a uzasadnienie mówi to
  wprost. `balanced_score` i znormalizowane metryki roweru pozostają niezmienione.
- **Komfort `reduced`** nie zmienia rankingu, tylko dodaje ostrzeżenie do uzasadnienia.
- **Samochód i komunikacja miejska** nie są korygowane. Godziny odjazdów GTFS pozostają
  rozkładowe, bez symulowania korków i opóźnień.

### Odpowiedź API

`GET /trips/{id}/compare` ma nowe, opcjonalne pola. Dotychczasowe pola nie zmieniły się:

- `weather`: `status`, `adjustment_applied`, `explanation`, `is_forecast`, `location`,
  `conditions` i `adjustment`,
- `variants[].comfort_level`: `null`, gdy komfortu nie oceniano,
- `variants[].score.weather_demoted`,
- `scoring.comfort_rule`.

Fragment rzeczywistej odpowiedzi z testu offline z mockiem ulewy (priorytet `greenest`, przystanek
syntetyczny):

```json
"weather": {
  "status": "applied",
  "adjustment_applied": true,
  "explanation": "Uwzględniono bieżącą pogodę Weatherbit w okolicy przystanku Dworzec Główny 01 (tylko komfort i czas roweru). Komfort roweru: niski (intensywny opad 4,0 mm/h).",
  "is_forecast": false,
  "location": {"stop_id": "A1", "stop_name": "Dworzec Główny 01", "lat": 54.355, "lon": 18.645},
  "conditions": {
    "source": "weatherbit_current",
    "observed_at": "2026-11-11T10:20:00Z",
    "temperature_c": 12.0,
    "precipitation_mm_h": 4.0,
    "snowfall_mm_h": 0.0,
    "wind_speed_kmh": 10.8,
    "description": "Heavy rain"
  },
  "adjustment": {"mode": "bike", "comfort_level": "poor", "duration_factor": 1.0, "reasons": ["intensywny opad 4,0 mm/h"]}
},
"recommendation": {
  "mode": "public_transport",
  "explanation": "Komunikacja miejska ma najniższą szacowaną emisję spośród wariantów o akceptowalnym komforcie pogodowym: ok. 0,20 kg CO₂. (…) Wariant „Rower” przesunięto na koniec rankingu: niski komfort przy bieżącej pogodzie. Wszystkie wartości są szacunkowe."
}
```

## API: przykładowe żądania

Wszystkie endpointy mają prefiks `/api/v1`.

| Metoda   | Ścieżka                       | Opis                                         |
|----------|-------------------------------|----------------------------------------------|
| `GET`    | `/health`                     | Status aplikacji i bazy                      |
| `GET`    | `/trips`                      | Lista (`skip`, `limit` ≤ 100, `q`)           |
| `POST`   | `/trips`                      | Nowa podróż (201)                            |
| `GET`    | `/trips/{id}`                 | Szczegóły                                    |
| `PUT`    | `/trips/{id}`                 | Pełna aktualizacja                           |
| `PATCH`  | `/trips/{id}`                 | Częściowa aktualizacja                       |
| `DELETE` | `/trips/{id}`                 | Usunięcie (204)                              |
| `GET`    | `/trips/{id}/compare`         | Porównanie i rekomendacja (`priority` opcjonalnie) |
| `GET`    | `/stops`                      | Przystanki GTFS (`query` ≥ 2 znaki, `limit` ≤ 50) |
| `GET`    | `/connections`                | Połączenia bezpośrednie (`origin_stop_id`, `destination_stop_id`, `departure_at`, `window_min`, `limit`) |

Przykłady w PowerShell. W Windows PowerShell 5.1 `curl` jest aliasem `Invoke-WebRequest`,
dlatego dla prawdziwego curla używaj `curl.exe`.

> Windows PowerShell 5.1 dekoduje odpowiedzi JSON bez `charset` jako ISO-8859-1, więc polskie
> znaki mogą się wyświetlić błędnie (np. `MokotÃ³w`). Dane w API i w bazie są poprawne (UTF-8).
> PowerShell 7+, Swagger UI i `curl.exe` pokazują je prawidłowo.

```powershell
$api = 'http://127.0.0.1:8000/api/v1'

# Health check
Invoke-RestMethod "$api/health"

# Nowa podróż
$body = @{
    name        = 'Dom - praca'
    origin      = 'Mokotów'
    destination = 'Centrum'
    distance_km = 7.5
    passengers  = 1
    priority    = 'balanced'   # fastest | cheapest | greenest | balanced
    has_car     = $true
    allow_bike  = $true
} | ConvertTo-Json
$trip = Invoke-RestMethod "$api/trips" -Method Post -ContentType 'application/json; charset=utf-8' `
    -Body ([Text.Encoding]::UTF8.GetBytes($body))

# Lista z wyszukiwaniem
Invoke-RestMethod "$api/trips?q=mokotów&limit=10"

# Częściowa aktualizacja
Invoke-RestMethod "$api/trips/$($trip.id)" -Method Patch -ContentType 'application/json' `
    -Body '{"passengers": 3}'

# Porównanie (z opcjonalnym nadpisaniem priorytetu)
Invoke-RestMethod "$api/trips/$($trip.id)/compare?priority=fastest" | ConvertTo-Json -Depth 6

# Usunięcie
Invoke-RestMethod "$api/trips/$($trip.id)" -Method Delete
```

Rozkład GTFS (po imporcie). Identyfikatory poniżej pochodzą z feedu z 11.11.2026; przed
użyciem sprawdź je przez `/stops`:

```powershell
# Przystanki: "glowny" znajdzie "Dworzec Główny 01" itd.
Invoke-RestMethod "$api/stops?query=dworzec%20glowny&limit=5"

# Bezpośrednie połączenia Dworzec Główny 01 (2001) -> Zaspa 01 (2089)
Invoke-RestMethod "$api/connections?origin_stop_id=2001&destination_stop_id=2089&departure_at=2026-11-12T07:55:00&limit=3" |
    ConvertTo-Json -Depth 5

# Podróż z przystankami i godziną — porównanie użyje czasu z rozkładu
$body = @{
    name = 'Dworzec - Zaspa'; origin = 'Dworzec'; destination = 'Zaspa'; distance_km = 5.5
    origin_stop_id = '2001'; destination_stop_id = '2089'; departure_at = '2026-11-12T07:55:00'
} | ConvertTo-Json
$trip = Invoke-RestMethod "$api/trips" -Method Post -ContentType 'application/json' -Body $body
(Invoke-RestMethod "$api/trips/$($trip.id)/compare").variants |
    Where-Object mode -eq 'public_transport' | Select-Object data_source, estimated_duration_min, assumptions
```

<details>
<summary>Przykładowa odpowiedź <code>GET /connections</code> (rzeczywiste dane ZTM, skrócona)</summary>

```json
{
  "origin": {
    "stop_id": "2001", "stop_name": "Dworzec Główny 01", "stop_code": "2001",
    "stop_lat": 54.355509269859, "stop_lon": 18.645663339105
  },
  "destination": {
    "stop_id": "2089", "stop_name": "Zaspa 01", "stop_code": "2089",
    "stop_lat": 54.399349725366, "stop_lon": 18.594910597792
  },
  "departure_at": "2026-11-12T07:55:00+01:00",
  "window_min": 120,
  "data_source": "gtfs_schedule",
  "is_realtime": false,
  "feed": {
    "source": "https://ckan.multimediagdansk.pl/.../gtfsgoogle.zip",
    "imported_at": "2026-11-11T18:16:02.268882Z",
    "timezone": "Europe/Warsaw",
    "valid_from": "2026-11-11",
    "valid_to": "2026-11-25"
  },
  "connections": [
    {
      "trip_id": "2202611120733_111_002-06",
      "route_id": "2",
      "line": "2",
      "route_type": 900,
      "headsign": "Jelitkowo",
      "direction_id": 0,
      "service_date": "2026-11-12",
      "departure_at": "2026-11-12T07:57:00+01:00",
      "arrival_at": "2026-11-12T08:19:00+01:00",
      "duration_min": 22.0,
      "origin_stop_sequence": 15,
      "destination_stop_sequence": 30
    }
  ],
  "notes": [
    "Rozkład planowy GTFS Static — bez opóźnień i danych w czasie rzeczywistym.",
    "Tylko połączenia bezpośrednie (bez przesiadek)."
  ]
}
```

W porównaniu podróży wariant „Komunikacja miejska” dostaje wtedy np.:
`"data_source": "gtfs_schedule"`, `"estimated_duration_min": 24.0` oraz założenia
„Czas z rozkładu GTFS: linia 2 w kierunku Jelitkowo, odjazd 12.11.2026 07:57 z przystanku
Dworzec Główny 01, przyjazd 08:19 na przystanek Zaspa 01.” i „Czas = oczekiwanie 2 min…
+ przejazd 22,0 min; bez dojścia do i z przystanku.”

</details>

Odczyt przez `curl.exe` (żądania z ciałem JSON najwygodniej wysyłać przez `Invoke-RestMethod`
lub Swagger UI, bo zasady cytowania argumentów różnią się między wersjami PowerShell):

```powershell
curl.exe http://127.0.0.1:8000/api/v1/trips
curl.exe "http://127.0.0.1:8000/api/v1/trips/1/compare?priority=greenest"
```

<details>
<summary>Przykładowa odpowiedź <code>GET /trips/1/compare</code> (skrócona do jednego wariantu)</summary>

```json
{
  "trip_id": 1,
  "priority": "balanced",
  "distance_km": 7.5,
  "passengers": 1,
  "is_estimate": true,
  "disclaimer": "Wszystkie wartości są szacunkami z uproszczonego modelu i przyjętych parametrów konfiguracji. ...",
  "variants": [
    {
      "mode": "car",
      "label": "Samochód",
      "available": true,
      "unavailable_reason": null,
      "estimated_duration_min": 16.2,
      "estimated_cost_pln": 3.41,
      "estimated_cost_per_passenger_pln": 3.41,
      "estimated_co2_kg": 1.275,
      "estimated_co2_per_passenger_kg": 1.275,
      "is_estimate": true,
      "data_source": "parametric_estimate",
      "assumptions": [
        "Średnia prędkość 40 km/h, bez danych o bieżącym natężeniu ruchu.",
        "Doliczono 5 min na parkowanie.",
        "..."
      ],
      "score": {
        "rank": 2,
        "normalized_duration": 0.0,
        "normalized_cost": 0.775,
        "normalized_co2": 1.0,
        "balanced_score": 0.5917
      }
    }
  ],
  "recommendation": {
    "mode": "bike",
    "label": "Rower",
    "explanation": "Rower daje najlepszy kompromis czasu, kosztu i emisji (wynik 0,33 w skali 0–1, im mniej, tym lepiej). ...",
    "tie_break_applied": false
  },
  "scoring": {
    "priority": "balanced",
    "description": "Normalizacja min-max każdej metryki wśród dostępnych wariantów ...",
    "balanced_weights": { "duration": 0.3333, "cost": 0.3333, "co2": 0.3333 },
    "tie_break_order": ["bike", "public_transport", "car"]
  }
}
```

</details>

Przykładowe błędy:

```json
// 404
{ "detail": "Podróż o id=999 nie istnieje", "code": "not_found" }

// 422
{
  "detail": [{ "loc": ["body", "distance_km"], "msg": "Input should be greater than 0", "type": "greater_than" }],
  "code": "validation_error"
}
```

## Testy i jakość kodu

Testy używają bazy SQLite w pamięci. Nie dotykają plików `smartroute.db` ani `gtfs.db`,
nie wymagają pliku `.env` i **nie łączą się z siecią**. Testy GTFS budują mały syntetyczny ZIP
([`tests/gtfs_factory.py`](backend/tests/gtfs_factory.py)) z samym `calendar_dates.txt`, kursem
po północy (`24:20:00`), przystankiem bez połączeń i celowo błędnymi wierszami.

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest                       # wszystkie testy
..\.venv\Scripts\python.exe -m pytest --cov                 # z raportem pokrycia
..\.venv\Scripts\python.exe -m ruff check .                 # lint
..\.venv\Scripts\python.exe -m ruff format --check .        # kontrola formatowania
```

Testy są podzielone na `tests/unit` (kalkulatory, rekomendacja, schematy, konfiguracja, bez
infrastruktury) oraz `tests/api` (endpointy przez `TestClient`, kody błędów, CORS).

### Aktualizacja zależności

Po zmianie `pyproject.toml` zainstaluj zależności bez pliku constraints, uruchom testy
i odśwież plik z przypiętymi wersjami:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]" --upgrade
.\.venv\Scripts\python.exe -m pip freeze --exclude-editable | Out-File -Encoding utf8 .\backend\requirements-lock.txt
```

## Struktura projektu

```
smartroute-ai/
├── setup.ps1                  # przygotowanie środowiska (Windows)
├── run.ps1                    # uruchomienie backendu
├── import-gtfs.ps1            # import / odświeżenie rozkładu GTFS
├── architecture-plan.md       # docelowa architektura MVP (backend + frontend)
├── frontend/                  # React + TypeScript + Vite (zob. sekcja Frontend)
└── backend/
    ├── pyproject.toml         # zależności, konfiguracja pytest i ruff
    ├── requirements-lock.txt  # przypięte wersje (constraints)
    ├── .env.example
    ├── app/
    │   ├── main.py            # create_app(), CORS, lifespan (create_all + migracja), routery
    │   ├── cli/gtfs.py        # CLI: python -m app.cli.gtfs import | info
    │   ├── core/              # konfiguracja, enumy, strefa czasowa, parametry modelu, błędy
    │   ├── db/                # silniki i sesje (podróże + GTFS), typy, migracje
    │   ├── models/            # modele ORM (trip, gtfs)
    │   ├── schemas/           # schematy Pydantic (kontrakt API)
    │   ├── repositories/      # dostęp do danych (podróże, rozkład)
    │   ├── services/
    │   │   ├── gtfs/          # importer, czas GTFS, wyszukiwanie połączeń
    │   │   ├── transport/     # kalkulatory, GtfsTransitTimeProvider
    │   │   └── weather/       # klient Weatherbit (cache), ocena i korekta pogodowa
    │   └── api/v1/            # endpointy
    └── tests/
        ├── unit/
        └── api/
```

Warstwy: **api → services → repositories → models**. Kalkulatory i rekomendacja nie zależą od
FastAPI ani bazy danych.

## Ograniczenia MVP

- **Szacunki zamiast danych rzeczywistych.** Czas samochodu i roweru liczony jest jako dystans /
  średnia prędkość plus stałe narzuty, a ceny i emisje to przyjęte parametry. Brak danych o ruchu.
- **Rozkład GTFS — ograniczony zakres:**
  - tylko planowy GTFS Static ZTM Gdańsk, bez GTFS-Realtime i opóźnień,
  - tylko połączenia bezpośrednie, bez przesiadek, czasu dojścia do przystanku i SKM/PKM,
  - przystanki trzeba wskazać jawnie przez `stop_id`, bez geokodowania i najbliższego przystanku,
  - rozkład jest ważny około 15 dni i wymaga regularnego importu,
  - `shapes.txt` nie jest importowany,
  - przy imporcie SQLite przez chwilę potrzebuje około 2× rozmiaru bazy na dysku
    (stare i nowe dane do COMMIT).
- **Pogoda — ograniczony zakres:**
  - tylko pogoda bieżąca, bez prognozy, więc działa tylko dla podróży w ciągu ok. 2 h,
  - lokalizacja wyłącznie z przystanku startowego GTFS, a pogoda w miejscu docelowym
    nie jest sprawdzana,
  - progi komfortu to założenia, a kierunek wiatru względem trasy jest nieznany,
  - cache jest w pamięci procesu, więc znika po restarcie i nie jest współdzielony
    między workerami,
  - integracja nie była jeszcze sprawdzona na prawdziwym API, bo klucz jest w trakcie
    aktywacji; testy używają mockowanych odpowiedzi w formacie z dokumentacji.
- **Dystans podaje użytkownik w km.** Brak geokodowania i wyznaczania tras, a punkt startu i cel to
  zwykły tekst.
- **Brak uwierzytelniania.** Jeden anonimowy użytkownik, a dane są wspólne dla wszystkich klientów API.
- **Uproszczone migracje.** Tabele tworzy `create_all`, a nowe kolumny nullable dodaje
  `upgrade_schema()` (zob. [Baza danych](#baza-danych)). Brak Alembica.
- **SQLite** wystarcza do pracy lokalnej i demonstracji, ale nie jest przeznaczona do wdrożeń
  wieloinstancyjnych.
- Tylko waluta PLN. Komunikaty API są po polsku.
- **Frontend:**
  - jedna strona bez historii zapisanych podróży (CRUD jest dostępny w API, ale bez widoku listy),
  - każde porównanie z nowymi danymi zapisuje podróż w bazie backendu,
  - wybór przystanków jest wymagany, więc bez importu GTFS porównania nie da się uruchomić
    z interfejsu (w API nadal działa),
  - tylko ciemny motyw i brak map,
  - opis warunków pogodowych pochodzi z Weatherbit w języku angielskim (np. „Few clouds”).
- Brak konteneryzacji.
- Znane ostrzeżenie w testach: Starlette zgłasza `StarletteDeprecationWarning` dotyczące użycia
  `httpx` w `TestClient`. Nie wpływa ono na wyniki testów.

## Planowane funkcje

- Widok historii zapisanych podróży we frontendzie (edycja i usuwanie przez istniejące API)
- Połączenia z przesiadkami (np. RAPTOR / CSA na zaimportowanych `stop_times`)
- Wybór najbliższych przystanków po współrzędnych i czas dojścia pieszo
- GTFS-Realtime (opóźnienia) jako osobne, jawnie oznaczone źródło danych
- Automatyczne, cykliczne odświeżanie rozkładu
- Integracja z API map (dystans i trasa zamiast ręcznego wpisu)
- Migracje bazy (Alembic)
- Docker i CI
