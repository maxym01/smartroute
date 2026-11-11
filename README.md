# SmartRoute AI

Backend MVP do porównywania środków transportu (samochód, komunikacja miejska, rower) pod kątem
**czasu, kosztu i szacowanej emisji CO₂**, z zapisywaniem podróży i rekomendacją środka transportu
według wybranego priorytetu.

> **Status:** wczesne MVP, tylko backend (REST API). Frontend jest zaplanowany
> (zob. [`architecture-plan.md`](architecture-plan.md)), ale jeszcze nie powstał.
> Wszystkie wyniki porównania to **szacunki z uproszczonego modelu parametrycznego**, a nie
> rzeczywiste rozkłady jazdy, bieżące ceny paliwa czy oficjalne taryfy.

## Spis treści

- [Zaimplementowane funkcje](#zaimplementowane-funkcje)
- [Stack technologiczny](#stack-technologiczny)
- [Wymagania](#wymagania)
- [Szybki start (Windows)](#szybki-start-windows)
- [Uruchomienie backendu](#uruchomienie-backendu)
- [Konfiguracja](#konfiguracja)
- [Baza danych](#baza-danych)
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
- **Health check** (`/api/v1/health`) ze sprawdzeniem połączenia z bazą.
- **Spójny format błędów** `{"detail": ..., "code": "not_found" | "validation_error"}`.
- **CORS** skonfigurowany pod przyszły frontend (domyślnie Vite dev server).

## Stack technologiczny

| Obszar      | Technologia                                    |
|-------------|------------------------------------------------|
| Język       | Python 3.12                                    |
| Framework   | FastAPI, Uvicorn                               |
| Baza danych | SQLite, SQLAlchemy 2.0 (ORM)                   |
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
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Następnie otwórz Swagger UI: **http://127.0.0.1:8000/docs**

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

Pełna lista parametrów modelu z jednostkami jest w [`backend/.env.example`](backend/.env.example)
i [`backend/app/core/transport_params.py`](backend/app/core/transport_params.py).

## Baza danych

- SQLite. Domyślny plik to `backend/smartroute.db` (ignorowany przez Git).
- **Nie trzeba wykonywać żadnych ręcznych kroków.** Przy starcie aplikacja wywołuje
  `Base.metadata.create_all()`, które tworzy brakujące tabele (obecnie `trips`).
- Migracje (Alembic) są poza zakresem MVP. `create_all` **nie modyfikuje** istniejących tabel.
  Po zmianie modelu na etapie developmentu usuń lokalny plik `backend/smartroute.db`, a aplikacja
  utworzy go od nowa. Spowoduje to utratę zapisanych podróży.
- Reset bazy: zatrzymaj serwer i wykonaj `Remove-Item .\backend\smartroute.db`.

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

Testy używają bazy SQLite w pamięci. Nie dotykają pliku `smartroute.db` i nie wymagają pliku `.env`.

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
├── architecture-plan.md       # docelowa architektura MVP (backend + frontend)
└── backend/
    ├── pyproject.toml         # zależności, konfiguracja pytest i ruff
    ├── requirements-lock.txt  # przypięte wersje (constraints)
    ├── .env.example
    ├── app/
    │   ├── main.py            # create_app(), CORS, lifespan (create_all), routery
    │   ├── core/              # konfiguracja, enumy, parametry modelu, obsługa błędów
    │   ├── db/                # silnik, sesje, DeclarativeBase
    │   ├── models/            # modele ORM
    │   ├── schemas/           # schematy Pydantic (kontrakt API)
    │   ├── repositories/      # dostęp do danych
    │   ├── services/          # kalkulatory transportu, porównanie, rekomendacja
    │   └── api/v1/            # endpointy
    └── tests/
        ├── unit/
        └── api/
```

Warstwy: **api → services → repositories → models**. Kalkulatory i rekomendacja nie zależą od
FastAPI ani bazy danych.

## Ograniczenia MVP

- **Szacunki zamiast danych rzeczywistych.** Czas liczony jest jako dystans / średnia prędkość plus
  stałe narzuty, a ceny i emisje to przyjęte parametry. Brak danych o ruchu i rozkładach jazdy.
- **Dystans podaje użytkownik w km.** Brak geokodowania i wyznaczania tras, a punkt startu i cel to
  zwykły tekst.
- **Brak uwierzytelniania.** Jeden anonimowy użytkownik, a dane są wspólne dla wszystkich klientów API.
- **Brak migracji bazy.** Tabele tworzy `create_all` przy starcie (zob. [Baza danych](#baza-danych)).
- **SQLite** wystarcza do pracy lokalnej i demonstracji, ale nie jest przeznaczona do wdrożeń
  wieloinstancyjnych.
- Tylko waluta PLN. Komunikaty API są po polsku.
- Brak frontendu i konteneryzacji.
- Znane ostrzeżenie w testach: Starlette zgłasza `StarletteDeprecationWarning` dotyczące użycia
  `httpx` w `TestClient`. Nie wpływa ono na wyniki testów.

## Planowane funkcje

- Frontend React + TypeScript + Tailwind (Vite), zgodnie z `architecture-plan.md`
- Czasy przejazdu komunikacją z rozkładów GTFS (punkt wpięcia: `transit_time_provider`
  w `ComparisonService`, `DataSource.GTFS_SCHEDULE`)
- Integracja z API map (dystans i trasa zamiast ręcznego wpisu)
- Migracje bazy (Alembic)
- Docker i CI
