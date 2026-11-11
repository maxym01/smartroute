# SmartRoute AI

Backend MVP do porównywania środków transportu (samochód, komunikacja miejska, rower) pod kątem
**czasu, kosztu i szacowanej emisji CO₂**, z zapisywaniem podróży i rekomendacją środka transportu
według wybranego priorytetu.

> **Status:** wczesne MVP, tylko backend (REST API). Frontend jest zaplanowany
> (zob. [`architecture-plan.md`](architecture-plan.md)), ale jeszcze nie powstał.
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
- [Konfiguracja](#konfiguracja)
- [Baza danych](#baza-danych)
- [Rozkład GTFS (ZTM Gdańsk)](#rozkład-gtfs-ztm-gdańsk)
- [API: przykładowe żądania](#api-przykładowe-żądania)
- [Testy i jakość kodu](#testy-i-jakość-kodu)
- [Struktura projektu](#struktura-projektu)
- [Ograniczenia MVP](#ograniczenia-mvp)
- [Planowane funkcje](#planowane-funkcje)

## Zaimplementowane funkcje

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

Zależności są zdefiniowane w [`backend/pyproject.toml`](backend/pyproject.toml). Zweryfikowane,
przypięte wersje są w [`backend/requirements-lock.txt`](backend/requirements-lock.txt), który
`setup.ps1` stosuje jako plik constraints.

## Wymagania

- Windows 10/11 z Windows PowerShell 5.1 lub PowerShell 7+
- **Python 3.12.x** (`pyproject.toml` wymaga `>=3.12,<3.13`), instalator z
  [python.org](https://www.python.org/downloads/). Skrypt szuka go przez launcher `py -3.12`
  albo `python` w `PATH`.
- Git
- Dostęp do internetu przy pierwszej instalacji zależności (PyPI)

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

Następnie otwórz Swagger UI: **http://127.0.0.1:8000/docs**

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
    │   │   └── transport/     # kalkulatory, GtfsTransitTimeProvider
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
- **Dystans podaje użytkownik w km.** Brak geokodowania i wyznaczania tras, a punkt startu i cel to
  zwykły tekst.
- **Brak uwierzytelniania.** Jeden anonimowy użytkownik, a dane są wspólne dla wszystkich klientów API.
- **Uproszczone migracje.** Tabele tworzy `create_all`, a nowe kolumny nullable dodaje
  `upgrade_schema()` (zob. [Baza danych](#baza-danych)). Brak Alembica.
- **SQLite** wystarcza do pracy lokalnej i demonstracji, ale nie jest przeznaczona do wdrożeń
  wieloinstancyjnych.
- Tylko waluta PLN. Komunikaty API są po polsku.
- Brak frontendu i konteneryzacji.
- Znane ostrzeżenie w testach: Starlette zgłasza `StarletteDeprecationWarning` dotyczące użycia
  `httpx` w `TestClient`. Nie wpływa ono na wyniki testów.

## Planowane funkcje

- Frontend React + TypeScript + Tailwind (Vite), zgodnie z `architecture-plan.md`
- Połączenia z przesiadkami (np. RAPTOR / CSA na zaimportowanych `stop_times`)
- Wybór najbliższych przystanków po współrzędnych i czas dojścia pieszo
- GTFS-Realtime (opóźnienia) jako osobne, jawnie oznaczone źródło danych
- Automatyczne, cykliczne odświeżanie rozkładu
- Integracja z API map (dystans i trasa zamiast ręcznego wpisu)
- Migracje bazy (Alembic)
- Docker i CI
