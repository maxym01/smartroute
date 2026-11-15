# SmartRoute

SmartRoute is a full-stack web application (FastAPI + React) that compares **car**, **public
transport** and **bike** for a trip in Gdańsk by **travel time, cost and estimated CO₂ emissions**,
and recommends one option for the priority you choose (fastest, cheapest, greenest or balanced).
The recommendation comes from a **deterministic, rule-based multi-criteria algorithm**, not from
a machine learning model or an LLM. The same input always gives the same result.

- Public transport times come from the **official GTFS Static timetable of ZTM Gdańsk** when a
  direct connection exists. These are scheduled times, without live delays. Otherwise the app
  falls back to a clearly labelled estimate.
- **Current weather from Weatherbit** (optional, current conditions only, not a forecast)
  adjusts the bike option's comfort level and, in strong wind, its travel time.
- Car and bike times, costs and emissions are **estimates from a simple parametric model**.
  They are not traffic data, live fuel prices, official fares or measurements. The UI and the
  API label every value accordingly.

> **Status:** working MVP. The user interface and API messages are in Polish. A more detailed
> Polish version of this document is in [`docs/README.pl.md`](docs/README.pl.md). The project
> was built with substantial help from AI tools; see
> [AI-assisted development](#ai-assisted-development).

## Demo

> 🎬 **Demo recording:** _coming soon — link will be added here._
>
> <!-- Replace with e.g. [![Demo](docs/demo-thumbnail.png)](https://...) -->

## Table of contents

- [Features](#features)
- [What is real data and what is estimated](#what-is-real-data-and-what-is-estimated)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [GTFS integration (ZTM Gdańsk)](#gtfs-integration-ztm-gdańsk)
- [Weather integration (Weatherbit)](#weather-integration-weatherbit)
- [Comparison model and recommendation](#comparison-model-and-recommendation)
- [API overview](#api-overview)
- [Testing and code quality](#testing-and-code-quality)
- [Project structure](#project-structure)
- [AI-assisted development](#ai-assisted-development)
- [Known limitations](#known-limitations)
- [Possible next steps](#possible-next-steps)

## Features

**Frontend (single-page dashboard)**

- Trip planner with accessible GTFS stop search (ARIA combobox: arrow keys, Enter, Escape),
  swap direction, date and time in Europe/Warsaw (defaults to "now"), distance in km,
  passengers (1–8), car / bike availability and a priority selector.
- Client-side validation that mirrors the API rules, with an error summary and per-field
  messages. Backend 422 errors are mapped back to the corresponding fields.
- Results: the backend recommendation with its reasoning and warnings, one card per transport
  mode (time, cost, CO₂ in total and per passenger, rank, availability, data source,
  assumptions), the next direct departures from the timetable and current weather.
- Changing only the priority re-runs the comparison for the same saved trip (`?priority=`),
  so no duplicate trips are created.
- Loading, empty, offline and error states with recovery hints. Responsive layout for
  phone, tablet and desktop. Keyboard support and `prefers-reduced-motion` are respected.
- The UI never computes its own recommendation and contains no demo data. Everything shown
  comes from the API.

**Backend (REST API)**

- Trip CRUD (`/api/v1/trips`) with pagination, case-insensitive search (Polish characters
  included), full (`PUT`) and partial (`PATCH`) updates, and validation: distance in (0, 1000] km,
  1–8 passengers, origin ≠ destination, unknown fields rejected.
- Comparison and recommendation (`GET /api/v1/trips/{id}/compare`) with an explanation,
  the scoring method and a deterministic tie-break.
- GTFS Static importer (CLI), stop search (`GET /api/v1/stops`) and direct connections
  honouring the service calendar (`GET /api/v1/connections`).
- Optional Weatherbit current-weather adjustment with caching and a safe fallback.
- Health check with a database probe, a consistent error format
  `{"detail": ..., "code": "not_found" | "validation_error" | "gtfs_not_imported"}`, and CORS
  configured for the Vite dev server.

## What is real data and what is estimated

| Value | Source | Real or estimated? |
|---|---|---|
| Public transport time with a direct connection found | GTFS Static timetable of ZTM Gdańsk (`data_source: "gtfs_schedule"`) | **Scheduled** time from the official timetable: waiting from the chosen departure time plus ride time. No delays, no walking to and from stops. |
| Public transport time without a direct connection | Parametric model (`data_source: "parametric_estimate"`) | **Estimate.** The UI shows "estimated time — no confirmed GTFS trip". Transfers are not searched, so this does **not** mean that no connection exists. |
| Departures list | GTFS Static (`GET /connections`) | Scheduled departures, direct trips only, no real-time data. |
| Car and bike times | Parametric model | **Estimate**: distance ÷ average speed + fixed overheads. |
| Costs (fuel, tickets) | Configured parameters | **Estimate.** The ticket tariff is an example, not the official ZTM tariff. |
| CO₂ | Configured emission factors | **Estimate.** |
| Distance | Entered by the user | User input. The form shows the straight-line distance between the stops only as a hint. |
| Weather | Weatherbit Current Weather API | **Current observation**, never a forecast (`is_forecast: false`). Used only for departures within about 2 hours. |

## Architecture

```
┌──────────────────────────┐      /api (Vite dev proxy)      ┌───────────────────────────────┐
│ React + TypeScript SPA   │  ─────────────────────────────▶ │ FastAPI  (/api/v1)            │
│ hooks → services (fetch) │                                 │ api → services → repositories │
└──────────────────────────┘                                 └──────┬──────────────┬─────────┘
                                                                    │              │
                                            ┌───────────────────────┘              └──────────────┐
                                            ▼                                                     ▼
                              SQLite  smartroute.db (trips)               SQLite  gtfs.db (timetable, read-only at runtime)
                                                                          ▲            filled by the GTFS import CLI
                              Weatherbit Current Weather API ◀── optional, cached, only for "now" trips
```

- **Layers:** `api → services → repositories → models`. Transport calculators, the
  recommendation engine and the weather rules are plain Python, independent of FastAPI and the
  database, so they are unit-tested in isolation.
- **Pluggable transit time:** `PublicTransportCalculator` takes a `TransitTimeProvider`. The
  GTFS provider returns the scheduled time, or falls back to the parametric estimate and records
  the reason in `assumptions`.
- **Two databases:** trips live in `smartroute.db`. The timetable lives in `gtfs.db`, which only
  the importer writes. The API never downloads data while serving a request.
- **Frontend flow:** `POST /trips` → `GET /trips/{id}/compare`, with `GET /connections` in
  parallel for the departures panel. TypeScript types in `frontend/src/types/api.ts` mirror the
  Pydantic schemas.

## Tech stack

| Area | Technologies |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn, SQLAlchemy 2.0, Pydantic v2, pydantic-settings |
| Database | SQLite (WAL mode for the timetable database) |
| Timetable | GTFS Static, parsed with the standard library (`csv`, `zipfile`, `zoneinfo` + `tzdata`) |
| Frontend | React 19, TypeScript 6, Vite 8, Tailwind CSS 4, Lucide React |
| Tests | pytest, pytest-cov, httpx/TestClient; Vitest, Testing Library, jsdom |
| Code quality | Ruff (lint + format); ESLint (typescript-eslint, react-hooks); `tsc` typecheck |

Backend dependencies are declared in [`backend/pyproject.toml`](backend/pyproject.toml).
Verified, pinned versions are in [`backend/requirements-lock.txt`](backend/requirements-lock.txt),
which `setup.ps1` applies as a constraints file. Frontend versions are pinned in
`frontend/package-lock.json`.

## Getting started

### Requirements

- **Python 3.12.x** (`pyproject.toml` requires `>=3.12,<3.13`)
- **Node.js ≥ 22.12** with npm (required by Vite 8), for the frontend only
- Git and internet access for the first installation (PyPI, npm) and the GTFS download

The helper scripts target **Windows PowerShell 5.1 or PowerShell 7+**. The
[manual commands](#manual-setup-macos--linux--without-scripts) work on any OS, but only Windows
has been tested.

### Quick start (Windows)

```powershell
git clone <repository-url> smartroute-ai
cd smartroute-ai

# 1. Backend environment: creates .venv, installs pinned dependencies, copies backend/.env.example to backend/.env
powershell -ExecutionPolicy Bypass -File .\setup.ps1

# 2. Frontend dependencies (once; versions pinned in package-lock.json)
cd frontend; npm install; cd ..

# 3. Timetable (needed for stop search in the UI): downloads the ZTM Gdańsk feed (~30 s, ~125 MB database)
powershell -ExecutionPolicy Bypass -File .\import-gtfs.ps1

# 4. Backend (http://127.0.0.1:8000, Swagger UI at /docs) and frontend (http://localhost:5173)
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Open **http://localhost:5173**. The Vite dev server proxies `/api` to `http://127.0.0.1:8000`,
so the browser only sees one origin. Press **Ctrl+C** in the same terminal to stop both servers.

`run.ps1` works from any current directory and runs both servers in one console:

- It checks the prerequisites (`.venv` with FastAPI and Uvicorn, Node.js ≥ 22.12,
  `frontend/node_modules`) and explains what to run if something is missing. It never installs
  packages itself.
- If port 8000 or 5173 already serves SmartRoute, that server is reused instead of starting a
  second instance. If the port is taken by another program, the script stops before starting
  anything.
- Ctrl+C stops both servers together with their child processes (Uvicorn's reload worker). If one
  server exits on its own, the other one is stopped too.

```powershell
.\run.ps1                                  # backend + frontend
.\run.ps1 -BackendOnly                     # API only (no Node.js needed)
.\run.ps1 -FrontendOnly                    # frontend only, against an already running backend
.\run.ps1 -Port 8001 -FrontendPort 5174    # other ports; the Vite proxy follows -Port
.\run.ps1 -NoReload                        # backend without auto-reload
.\run.ps1 -BindHost 0.0.0.0                # backend reachable from the local network
```

> `-ExecutionPolicy Bypass` applies to that single call only. To run the scripts directly
> (`.\setup.ps1`), allow local scripts for your user:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

| Script | What it does |
|---|---|
| `setup.ps1` | Creates `.venv` from Python 3.12 if it is missing. It stops with an error, and deletes nothing, if an existing `.venv` uses another Python version. Then it runs `pip install -e "backend[dev]" -c backend/requirements-lock.txt` and `pip check`, and copies `.env.example` to `.env` only if `.env` does not exist. It is idempotent. `-NoDev` installs runtime dependencies only. |
| `import-gtfs.ps1` | Runs `python -m app.cli.gtfs import` from `backend/`. `-Source <url-or-zip>` imports from another URL or a local ZIP. Re-importing replaces the timetable in one transaction. |
| `run.ps1` | Starts the backend (Uvicorn from `backend/`, where `.env` and the relative SQLite paths are resolved) and the frontend (Vite from `frontend/`) in one console; Ctrl+C stops both. Options: `-BackendOnly`, `-FrontendOnly`, `-Port`, `-FrontendPort`, `-BindHost`, `-NoReload`. |

Without an imported timetable, the API still works: comparisons use the estimate, and `/stops`
and `/connections` return `503 gtfs_not_imported`. The UI requires stop selection, though, so
import the timetable before using the dashboard.

### Docker Compose

Requires Docker with Compose v2.24+ (Docker Desktop on Windows/macOS). No local Python or Node.js
needed.

```bash
# Optional: secrets and settings (e.g. WEATHERBIT_API_KEY) are read from backend/.env at run time
cp backend/.env.example backend/.env

docker compose up -d --build      # backend http://localhost:8000, frontend http://localhost:5173
docker compose ps                 # both services should become "healthy"

# Timetable: a separate, one-off step (the app never imports it on start)
docker compose run --rm backend python -m app.cli.gtfs import
docker compose run --rm backend python -m app.cli.gtfs info

docker compose logs -f backend    # logs
docker compose down               # stop; data in the volume is kept
```

| Service | Image | Host address | Notes |
|---|---|---|---|
| `backend` | `backend/Dockerfile` (Python 3.12 slim, non-root) | http://localhost:8000 (`/docs`, `/api/v1/health`) | Uvicorn on `0.0.0.0:8000` in the container |
| `frontend` | `frontend/Dockerfile` (Vite build → nginx, non-root) | http://localhost:5173 | nginx proxies `/api` to `backend:8000` |

- **Secrets:** `backend/.env` is excluded from both images (`.dockerignore`) and passed to the
  backend only at run time through `env_file` (optional — without it the defaults apply). Do not
  share the output of `docker compose config` (without `--quiet`) or `docker inspect`, as they show
  the values.
- **Data:** both SQLite databases (`smartroute.db`, `gtfs.db`) live in the named volume
  `smartroute_smartroute-data` mounted at `/data`. `DATABASE_URL` and `GTFS_DATABASE_URL` are set
  in `compose.yaml` and take precedence over `backend/.env`. The volume survives
  `docker compose down` and rebuilds; only `docker compose down -v` removes it. The local
  `backend/*.db` files used by `run.ps1` are not mounted or modified.
- **GTFS:** the backend starts without a timetable (`/stops` and `/connections` return 503 until it
  is imported). Re-importing replaces the timetable in one transaction while the API keeps
  serving the old one. To import a local ZIP instead of downloading:
  `docker compose run --rm -v "./feed.zip:/tmp/feed.zip:ro" backend python -m app.cli.gtfs import --source /tmp/feed.zip`.
  To reuse an already imported local database instead (only when the volume has no `gtfs.db` yet;
  the host file is only read): `docker compose cp backend/gtfs.db backend:/data/gtfs.db`.
- **Healthchecks:** the backend checks `GET /api/v1/health` (status `ok`), the frontend checks that
  nginx serves the page. The frontend starts once the backend is healthy.
- **Ports** are published on `127.0.0.1` only. CORS is not involved: the browser talks to a single
  origin (`localhost:5173`) and nginx forwards `/api`.
- **Tests in a container:** `docker build --target test -t smartroute-backend:test backend` and
  `docker run --rm smartroute-backend:test`.

### Manual setup (macOS / Linux / without scripts)

```bash
python3.12 -m venv .venv
source .venv/bin/activate                  # Windows: .\.venv\Scripts\Activate.ps1
pip install -e "./backend[dev]" -c backend/requirements-lock.txt
cp backend/.env.example backend/.env       # optional, every setting has a default

cd backend
python -m app.cli.gtfs import              # optional: timetable
python -m app.cli.gtfs info                # source, import time, validity, record counts
python -m uvicorn app.main:app --reload    # http://127.0.0.1:8000

# in a second terminal
cd frontend && npm install && npm run dev  # http://localhost:5173
```

### Useful URLs

| URL | Description |
|---|---|
| http://localhost:5173 | Frontend (Vite dev server) |
| http://127.0.0.1:8000/docs | Swagger UI |
| http://127.0.0.1:8000/redoc | ReDoc |
| http://127.0.0.1:8000/api/v1/health | Health check |

### Frontend scripts

| Command | Description |
|---|---|
| `npm run dev` | Vite dev server with the `/api` → backend proxy |
| `npm run build` | Type check (`tsc -b`) and production build to `dist/` |
| `npm run preview` | Preview of the production build (port 4173, with the same proxy) |
| `npm run typecheck` | TypeScript only |
| `npm run lint` | ESLint |
| `npm test` | Vitest (jsdom, no network, no backend needed) |

## Configuration

The backend uses `pydantic-settings` ([`backend/app/core/config.py`](backend/app/core/config.py)).
Every value has a default, so `backend/.env` is optional. Environment variables take precedence
over `.env`.

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `SmartRoute` | Name shown in Swagger UI and the health check |
| `ENVIRONMENT` | `development` | `development` / `test` / `production` |
| `DEBUG` | `false` | FastAPI debug mode and SQL logging |
| `DATABASE_URL` | `sqlite:///./smartroute.db` | Trips database (relative to `backend/`) |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list of allowed origins |
| `GTFS_DATABASE_URL` | `sqlite:///./gtfs.db` | Timetable database, created by the importer |
| `GTFS_FEED_URL` | official ZTM Gdańsk feed | Default import source |
| `GTFS_SEARCH_WINDOW_MIN` | `180` | How far ahead the comparison looks for a direct trip [min] |
| `GTFS_MAX_DOWNLOAD_MB` | `200` | Download size limit for the feed ZIP |
| `WEATHERBIT_API_KEY` | empty (disabled) | Weatherbit key. Set it **only** in `backend/.env` or the environment. |
| `WEATHER_TIMEOUT_S` | `5` | HTTP timeout [s] |
| `WEATHER_CACHE_TTL_S` | `1800` | Cache lifetime per location [s] |
| `WEATHER_ERROR_COOLDOWN_S` | `300` | Pause after an error or HTTP 429 [s] |
| `WEATHER_MAX_LEAD_MIN` | `120` | Maximum time to departure for applying current weather [min] |
| `TRANSPORT__*` | see below | Model parameters, e.g. `TRANSPORT__CAR__FUEL_PRICE_PLN_PER_L=6.89` |

Frontend (optional, `frontend/.env.local`, template in
[`frontend/.env.example`](frontend/.env.example)):

- `VITE_BACKEND_PROXY_TARGET` sets the backend address for the dev proxy. The default is
  `http://127.0.0.1:8000`.
- `VITE_API_BASE_URL` sets the full API URL when the frontend is served without the proxy.
  In that case, also add the frontend origin to `CORS_ORIGINS`.

Both SQLite files are created automatically and are ignored by Git. Tables are created at
startup (`create_all`), and a small idempotent `upgrade_schema()` adds the nullable GTFS columns
to older `trips` tables. There is no Alembic. To reset saved trips, stop the server and delete
`backend/smartroute.db`.

## GTFS integration (ZTM Gdańsk)

Source: [Otwarte Dane Gdańsk — GTFS Static ZTM Gdańsk](https://ckan.multimediagdansk.pl/dataset/c24aa637-3619-4dc2-a171-a23eec8f2172/resource/30e783e4-2bec-4a7d-bb22-ee3e3b26ca96/download/gtfsgoogle.zip).
ZTM publishes a new feed daily, and each feed covers about 15 days, so re-run the import
regularly (e.g. daily via Windows Task Scheduler).

**Import**

- CSV files are streamed from the ZIP and inserted in batches, with about 50 MB peak memory for
  the full feed. Nothing is extracted to disk.
- Only known files in the archive root are read. Encrypted entries, archives over 1 GiB
  uncompressed and suspicious compression ratios are rejected. Downloads have a size limit and
  a timeout.
- The import replaces the whole timetable in a single transaction. If it fails, the previous
  timetable stays intact, and thanks to WAL mode the running server keeps reading during an
  import.
- Malformed rows (bad time format, unknown trip or stop, bad date) are skipped and counted in
  the import report.
- The importer handles the ZTM specifics: no `calendar.txt` (only `calendar_dates.txt`),
  extended `route_type` values (700 bus, 900 tram) and times past `24:00:00`.

**Connection search**

- **Direct connections only:** the trip must stop at the origin and later, with a higher
  `stop_sequence`, at the destination. Trips in the opposite direction are not returned.
- The service calendar is respected. Stops with `pickup_type=1` / `drop_off_type=1` are skipped,
  while `3` (request stop) counts as served.
- GTFS times are counted from "noon minus 12 h" of the service day in `Europe/Warsaw`, which
  handles DST changes and after-midnight trips. `departure_at` without a timezone is read as
  Gdańsk local time. Responses include the UTC offset.

**Use in the comparison.** A trip can carry `origin_stop_id`, `destination_stop_id` (from
`GET /stops`) and `departure_at`. Free-text `origin` / `destination` are never geocoded.

- If a direct trip departs within `GTFS_SEARCH_WINDOW_MIN` (180 min), the public transport option
  uses `data_source: "gtfs_schedule"`. Its time is the wait plus the ride, and the line,
  departure and arrival are listed in `assumptions`.
- Otherwise it uses `data_source: "parametric_estimate"`, and the first assumption explains why:
  no direct trip, unknown stop, missing field or timetable not imported.
- In the UI, the card, the departures panel and, when public transport is the recommended option,
  the recommendation panel state that the time is an estimate. They also say that transfers are
  not searched and that the recommendation does not guarantee an available connection.
  The option stays in the ranking.

## Weather integration (Weatherbit)

Optional, uses the free [Weatherbit Current Weather API](https://www.weatherbit.io/api/weather-current)
(`GET /v2.0/current`, `units=M`). Forecasts are not used.

1. Create a Weatherbit account and copy your API key. A new key may need some time to activate.
2. Put it **only** in `backend/.env` (ignored by Git) or in an environment variable:
   `WEATHERBIT_API_KEY=your_key`.
3. Restart the backend. Without a key the integration is disabled (`weather.status: "disabled"`)
   and comparisons are unchanged.

The key is a `SecretStr`, so it is masked in `repr`. It is never logged or returned in error
messages, and HTTP exceptions whose URL contains the key are not chained into tracebacks. The
frontend never talks to Weatherbit.

**When weather is applied.** All of the following conditions must hold. Otherwise
`weather.status` names the reason and the result is identical to a run without weather.

| Condition | Status otherwise |
|---|---|
| The bike option is available | `not_applicable` |
| `WEATHERBIT_API_KEY` is set | `disabled` |
| Departure is between 60 min ago and `WEATHER_MAX_LEAD_MIN` (120 min) from now | `out_of_time_window` |
| The trip has an `origin_stop_id` with GTFS coordinates (the location is the origin stop) | `no_location` |
| Weatherbit answered (from cache or the API); timeouts, 429, invalid key and bad payloads all degrade safely | `unavailable` |

The client keeps a 30-minute in-process cache per 0.1° grid cell and pauses requests for
5 minutes after any error. No request is made when weather cannot be applied.

**Bike comfort rules** (deterministic thresholds, which are MVP assumptions):

| Factor | `reduced` | `poor` |
|---|---|---|
| Precipitation | ≥ 0.2 mm/h | ≥ 2.5 mm/h |
| Thunderstorm, snow, freezing rain (codes 2xx, 511, 6xx) or any snowfall | — | always |
| Wind | ≥ 25 km/h (bike time +10%) | ≥ 40 km/h (bike time +20%) |
| Temperature | ≤ 3 °C or ≥ 28 °C | ≤ −5 °C or ≥ 33 °C |

The overall comfort is the worst factor. The time, cost and CO₂ weights never change.
`reduced` only adds a warning. `poor` moves the bike to the end of the ranking for every
priority, if another option is available. The explanation says so, and the bike keeps its
scores (`score.weather_demoted: true`). Car and public transport are not adjusted.

**How it was verified.** The automated tests use mocked Weatherbit responses and make no network
calls. Separately, the author ran a manual test of the comparison endpoint with a real API key:
the response contained real current weather data with `weather.status: "applied"`. This was a
one-off manual check, not an automated integration test.

## Comparison model and recommendation

Default parameters ([`backend/app/core/transport_params.py`](backend/app/core/transport_params.py)),
all overridable via `TRANSPORT__*`:

| Mode | Time | Cost | CO₂ |
|---|---|---|---|
| Car | distance ÷ 40 km/h + 5 min parking | fuel only: 7 l/100 km × 6.50 PLN/l, shared by the passengers | 0.17 kg/km per vehicle |
| Public transport | GTFS schedule, or distance ÷ 22 km/h + 8 min access and waiting | 4.40 PLN per person up to 10 km, + 0.25 PLN/km beyond (example tariff) | 0.05 kg per passenger-km |
| Bike | distance ÷ 15 km/h (+ wind adjustment) | 0 PLN | 0 kg; available up to 20 km |

The car is unavailable with `has_car=false` and the bike with `allow_bike=false` or above 20 km.
Unavailable options are shown with the reason and never recommended.

**Recommendation** ([`backend/app/services/recommendation_service.py`](backend/app/services/recommendation_service.py)).
This is plain, rule-based code with no machine learning, no LLM and no training data:

1. Only available options are considered. Values are compared as returned by the API (rounded).
2. `fastest`, `cheapest` and `greenest` order the options lexicographically by the main metric,
   then the remaining ones (e.g. fastest: time → cost → CO₂). If the main metric is tied, the
   explanation says which secondary metric decided.
3. `balanced` applies min-max normalisation per metric (0 = best, 1 = worst) and scores
   `1/3·time + 1/3·cost + 1/3·CO₂`. The lowest score wins.
4. A complete tie is resolved by the fixed order bike → public transport → car
   (`scoring.tie_break_order`), so the result is always deterministic.
5. The weather comfort rule described above is applied as a separate, explicit step.

The response includes a Polish explanation, the per-mode normalised scores and the method
description. In the UI, "best value" badges compare values at display precision and mark equal
values as "ex aequo".

## API overview

All endpoints are prefixed with `/api/v1`. The full schema is in Swagger UI (`/docs`).

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Application and database status |
| `GET` | `/trips` | List (`skip`, `limit` ≤ 100, `q` search) |
| `POST` | `/trips` | Create a trip (201) |
| `GET` / `PUT` / `PATCH` / `DELETE` | `/trips/{id}` | Read, replace, update, delete (204) |
| `GET` | `/trips/{id}/compare` | Comparison and recommendation (optional `priority` override, not saved) |
| `GET` | `/stops` | GTFS stop search (`query` ≥ 2 characters, accent-insensitive; `limit` ≤ 50) |
| `GET` | `/connections` | Direct connections (`origin_stop_id`, `destination_stop_id`, `departure_at`, `window_min`, `limit`) |

Example (PowerShell; use `curl.exe` rather than the `curl` alias):

```powershell
$api = 'http://127.0.0.1:8000/api/v1'
Invoke-RestMethod "$api/stops?query=zaspa&limit=3"

$body = @{
    name = 'Dworzec - Zaspa'; origin = 'Dworzec Główny 01'; destination = 'Zaspa 01'
    distance_km = 5.5; passengers = 1; priority = 'balanced'; has_car = $true; allow_bike = $true
    origin_stop_id = '2001'; destination_stop_id = '2089'; departure_at = '2026-11-12T07:55:00'
} | ConvertTo-Json
$trip = Invoke-RestMethod "$api/trips" -Method Post -ContentType 'application/json; charset=utf-8' `
    -Body ([Text.Encoding]::UTF8.GetBytes($body))
Invoke-RestMethod "$api/trips/$($trip.id)/compare?priority=fastest" | ConvertTo-Json -Depth 6
```

Stop IDs come from the imported feed, so check them with `/stops` first. The departure must fall
within the feed's validity period (`python -m app.cli.gtfs info`). Windows PowerShell 5.1 may
display Polish characters incorrectly, but the data itself is UTF-8 and PowerShell 7 shows it
correctly.

Error format:

```json
{ "detail": "Podróż o id=999 nie istnieje", "code": "not_found" }
```

## Testing and code quality

Backend tests use in-memory SQLite and a small synthetic GTFS ZIP
([`backend/tests/gtfs_factory.py`](backend/tests/gtfs_factory.py)). Weather tests use mocked
Weatherbit responses. The tests need no `.env`, never touch the local databases and make no
network calls.

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest                  # unit + API tests
..\.venv\Scripts\python.exe -m pytest --cov            # with coverage
..\.venv\Scripts\python.exe -m ruff check .            # lint
..\.venv\Scripts\python.exe -m ruff format --check .   # formatting

cd ..\frontend
npm test                                               # Vitest + Testing Library
npm run typecheck
npm run lint
npm run build
```

- `backend/tests/unit` covers the calculators, recommendation, weather rules and client, the
  GTFS importer and time handling, schemas and configuration.
- `backend/tests/api` covers the endpoints through `TestClient`, error codes and CORS.
- Frontend tests cover form validation and stop search, result rendering (ranking,
  unavailable options, GTFS vs estimate labels, recommendation warnings, ties), formatting
  and the API client.

Automated tests do not check visual layout. The manual check for 360 / 768 / 1024 / 1440 px is
described in [`docs/README.pl.md`](docs/README.pl.md#ręczna-weryfikacja-układu).

## Project structure

```
smartroute-ai/
├── setup.ps1 · run.ps1 · import-gtfs.ps1   # Windows helper scripts
├── compose.yaml                            # Docker Compose: backend + frontend + data volume
├── architecture-plan.md                    # original planning document (Polish, historical)
├── docs/README.pl.md                       # detailed Polish documentation
├── backend/
│   ├── pyproject.toml · requirements-lock.txt · .env.example · Dockerfile
│   ├── app/
│   │   ├── main.py                         # app factory, CORS, lifespan, routers
│   │   ├── api/v1/                         # endpoints: meta (health), trips, comparisons, gtfs
│   │   ├── cli/gtfs.py                     # python -m app.cli.gtfs import | info
│   │   ├── core/                           # settings, enums, model parameters, errors, timezone
│   │   ├── db/ · models/ · repositories/   # engines/sessions, ORM models, data access
│   │   ├── schemas/                        # Pydantic API contract
│   │   └── services/
│   │       ├── transport/                  # car, public transport, bike, GTFS time provider
│   │       ├── gtfs/                       # importer, GTFS time, connection search
│   │       ├── weather/                    # Weatherbit client, assessment and adjustment
│   │       ├── comparison_service.py
│   │       └── recommendation_service.py
│   └── tests/ (unit/, api/)
└── frontend/
    ├── vite.config.ts · eslint.config.js · .env.example · Dockerfile · nginx.conf
    └── src/
        ├── pages/DashboardPage.tsx         # layout and flow orchestration
        ├── components/                     # TripForm, StopPicker, VariantCard, RecommendationPanel,
        │                                   # SchedulePanel, WeatherPanel, HelpPanel, ui/…
        ├── hooks/                          # useComparison, useStopSearch, useBackendHealth
        ├── services/                       # fetch client (ApiError) and endpoint functions
        ├── types/api.ts                    # API contract types
        └── utils/                          # formatting, dates, validation, errors, results, GTFS status
```

## AI-assisted development

This project was built with substantial help from AI tools. The split of work was as follows:

- **The author** came up with the application concept and defined its requirements, as well as
  the scope and constraints of each development stage.
- **ChatGPT and Claude Code** were used to plan the work and to generate and modify the code.
  A significant part of the backend and frontend implementation, the automated tests and this
  documentation was generated by AI, based on the author's requirements and instructions.
- **Automated tests** (pytest, Vitest) were generated by AI. Claude Code ran them, together with
  the linters and builds, and reported the results.
- **Manual testing by the author:** selected endpoints were tested in Swagger UI, and the
  behaviour of the user interface was checked in the browser. The author also ran the manual
  Weatherbit check described in [Weather integration](#weather-integration-weatherbit).

The author has **not yet carried out a full, independent review of the entire codebase**.

## Known limitations

- **Estimates, not measurements.** Car and bike times use average speeds without traffic data.
  Prices, fares and emission factors are configured assumptions.
- **Public transport is limited to direct, scheduled trips.** There are no transfers, no
  real-time delays (no GTFS-Realtime), no walking time to and from stops, and SKM/PKM rail
  services are not included. A missing direct trip leads to an estimate, not to a confirmed
  connection. The app does **not guarantee** that a direct public transport connection exists,
  even when public transport is the recommended option.
- **The timetable must be refreshed.** A feed is valid for about 15 days, and `shapes.txt` is not
  imported.
- **Distance is entered manually.** There is no geocoding, routing or map. Stops must be picked
  explicitly. The nearest stop is not suggested.
- **Weather is current only.** It applies to departures within about 2 hours, at the origin stop
  only. Comfort thresholds are assumptions, and the wind direction relative to the route is
  unknown. The cache is in-process, so it is lost on restart and not shared between workers.
  Weather descriptions are in English (from Weatherbit).
- **Frontend:** a single page without a list of saved trips (CRUD exists only in the API). Every
  comparison with new input saves a trip. The dashboard requires an imported timetable.
  Dark theme only. The UI is in Polish.
- **Backend:** no authentication (single anonymous user), SQLite only, no Alembic migrations,
  PLN only, API messages in Polish.
- **Tooling:** the helper scripts are Windows-only. There is no Docker and no CI. `npm audit`
  reports moderate advisories in dev-only lint dependencies. Tests emit a known
  `StarletteDeprecationWarning` about `httpx` in `TestClient`.

## Possible next steps

- Trip history view in the frontend (edit and delete via the existing API)
- Connections with transfers (e.g. RAPTOR / CSA on the imported `stop_times`)
- Nearest stops by coordinates and walking time
- GTFS-Realtime delays as a separate, explicitly labelled data source
- Scheduled timetable refresh; map integration for distance and route
- Alembic migrations, Docker and CI
