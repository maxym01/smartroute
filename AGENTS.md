# AGENTS.md — instructions for AI coding agents

Guidance for AI coding agents (Claude Code, Codex and similar) working in this repository.
Human contributors may find it useful as a summary of the project conventions.

> **Provenance.** This file was added on 2026-11-15, after the MVP was finished. During
> development there was **no** repository instruction file. Instructions were given to the
> agent separately for each development stage, in the prompt, and from stage 1 onward those
> prompts pointed the agent to [`architecture-plan.md`](architecture-plan.md) and the existing
> code. This file collects the rules that were repeated across those stage prompts and the
> conventions visible in the code. It is not a record of an earlier configuration.

## Project in one paragraph

SmartRoute compares car, public transport and bike for a trip in Gdańsk by time, cost and
estimated CO₂, and recommends one option for a chosen priority (`fastest`, `cheapest`,
`greenest`, `balanced`). The recommendation is a **deterministic, rule-based** algorithm, not
ML or an LLM. Public transport can use the official ZTM Gdańsk GTFS Static timetable (direct
trips only); the bike option can be adjusted by current Weatherbit weather. Everything else is
a parametric estimate. See [`README.md`](README.md) for the full description.

## Repository layout

| Path | Contents |
|---|---|
| `backend/` | FastAPI app (Python 3.12), package `app`, tests in `backend/tests` |
| `frontend/` | React + TypeScript + Vite + Tailwind CSS 4 single-page dashboard |
| `compose.yaml`, `*/Dockerfile` | Docker Compose setup (backend + nginx-served frontend) |
| `setup.ps1`, `run.ps1`, `import-gtfs.ps1` | Windows helper scripts (setup, run both servers, GTFS import) |
| `architecture-plan.md` | Original planning document (Polish, historical; the README describes the current state) |
| `demo/` | Demo video |

## Commands

Backend (from `backend/`, using the repository `.venv`; on macOS/Linux use `../.venv/bin/python`):

```powershell
..\.venv\Scripts\python.exe -m pytest                  # unit + API tests (offline)
..\.venv\Scripts\python.exe -m pytest --cov            # with coverage
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m ruff format --check .
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
..\.venv\Scripts\python.exe -m app.cli.gtfs import     # downloads the GTFS feed into gtfs.db (~125 MB)
..\.venv\Scripts\python.exe -m app.cli.gtfs info
```

Frontend (from `frontend/`):

```powershell
npm test            # Vitest (jsdom, no backend needed)
npm run typecheck
npm run lint
npm run build       # tsc -b + vite build
npm run dev         # http://localhost:5173, proxies /api to http://127.0.0.1:8000
```

Whole app: `.\run.ps1` (Windows) or `docker compose up -d --build`
(backend `localhost:8000`, frontend `localhost:5173`).

Environment setup: `.\setup.ps1` (creates `.venv` from Python 3.12, installs
`backend[dev]` with `-c backend/requirements-lock.txt`) and `npm install` in `frontend/`.
Do not install another Python version; use the existing `.venv`.

## Architecture conventions

**Backend** (`backend/app/`):

- Layers: `api/v1/` (routers, HTTP only) → `services/` (domain logic) → `repositories/`
  (data access) → `models/` (SQLAlchemy 2.0). Pydantic v2 request/response schemas live in
  `schemas/`. Keep business logic out of routers.
- All routes are under `/api/v1` (`API_V1_PREFIX`). Errors use one format,
  `{"detail": ..., "code": ...}`, produced by the handlers in `core/exceptions.py`
  (`not_found`, `validation_error`, `gtfs_not_imported`, …).
- Settings: `core/config.py` (pydantic-settings, env vars or `backend/.env`). Model parameters
  (speeds, prices, emission factors) live in `core/transport_params.py` with units and are
  overridable via `TRANSPORT__<MODE>__<FIELD>`. They are **assumptions**, not current prices or
  official fares — never present them as measurements.
- Transport calculators are in `services/transport/`; the public transport time comes from a
  `TransitTimeProvider` (GTFS when a direct trip exists, otherwise the parametric estimate).
  Every variant carries a `data_source` (`gtfs_schedule` or `parametric_estimate`).
- Recommendation (`services/recommendation_service.py`): lexicographic order for single-metric
  priorities, min–max normalisation with equal weights for `balanced`, fixed tie-break order.
  Results must stay deterministic; unavailable variants are never recommended.
- Databases: SQLite. `smartroute.db` (trips) is created at startup (`create_all` plus the
  idempotent, additive `db/migrations.py`; there is no Alembic). `gtfs.db` is a separate file
  written **only** by the importer, in one transaction; the API only reads it and returns
  `503 gtfs_not_imported` when it is missing.
- Weather (`services/weather/`): optional. Missing key, timeouts, HTTP 429 or no network must
  never break a comparison — fall back to the unadjusted result.
- API changes must stay backward compatible (new fields optional) unless a breaking change is
  explicitly requested.

**Frontend** (`frontend/src/`):

- `pages/` (layout and flow), `components/`, `hooks/`, `services/` (fetch client
  `apiClient.ts` with `ApiError`, endpoint functions in `smartrouteApi.ts`), `types/api.ts`,
  `utils/`.
- `types/api.ts` must match the real backend schemas — check the Pydantic models, do not
  assume fields.
- The UI never computes its own recommendation and contains no demo data; everything comes from
  the API. It must clearly distinguish GTFS timetable times from estimates.
- The API base URL is relative (`/api/v1`); the Vite dev server (and nginx in Docker) proxies
  `/api` to the backend.

**Language:** user-facing UI text and API messages are in Polish. Code, comments, docstrings,
commit messages and documentation are in English. The product name is **SmartRoute**; the
technical identifiers `smartroute-ai` (directory, package name) are intentionally unchanged.

**PowerShell scripts** must work in Windows PowerShell 5.1 and keep their UTF-8 BOM encoding.

## Testing rules

- Tests must run offline: no network calls, no real API keys. GTFS tests use the synthetic ZIP
  from `backend/tests/gtfs_factory.py`; weather tests use mocked responses
  (`backend/tests/weather_factory.py`); databases are in-memory SQLite.
- Tests must never touch the local `backend/*.db` files or need `backend/.env`.
- Add or update tests with every behaviour change, including edge cases. Do not delete or
  weaken existing tests to make a change pass.
- Before reporting a task as done, run the backend tests, `ruff check`, `ruff format --check`
  and, for frontend changes, `npm test`, `npm run typecheck`, `npm run lint` and
  `npm run build`. Report the actual results, including failures and warnings.

## AI workflow guidelines

These rules were repeated in the stage prompts used during development:

1. **Read first.** Before changing anything, read `README.md`, the relevant code and, for design
   questions, `architecture-plan.md`. Do not assume something is missing before checking.
2. **Stay in scope.** Implement only the requested stage or task. Do not add features, refactor
   unrelated code or change business logic, endpoints, algorithms or API contracts unless the
   task requires it. If a wider change seems necessary, describe the problem first.
3. **Plan before large changes.** For new features or redesigns, present a short plan first.
4. **Data honesty.** Label estimates as estimates. Do not imply real-time data, live delays or
   traffic. Do not treat a free-text place name as a stop ID or as coordinates. A missing direct
   GTFS trip does not mean public transport is impossible (transfers are not searched).
5. **Secrets.** `WEATHERBIT_API_KEY` and other secrets come only from `backend/.env` or
   environment variables. Never put them in code, logs, tests, Docker images or Git, and never
   print their values (use `docker compose config --quiet`, not plain `config`).
6. **Protect local data.** Do not delete or overwrite the local SQLite databases, `.env` files
   or other user data.
7. **Git.** Do not commit or push without explicit approval. Stage files selectively and check
   `git status` / `git diff` first. Never commit `.env`, keys, `*.db`, `.venv`,
   `node_modules`, `dist` or temporary files. Do not use `git reset --hard`, `git clean -fd` or
   `git push --force`, and do not create commits that misrepresent their content. Commit
   messages follow Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`).
8. **Report.** Finish with a short summary: changed files, test and lint results, and any open
   problems or decisions for the maintainer. Do not claim checks or reviews that did not happen.

## Documentation

`README.md` is the single project README (English). Keep it consistent with the code when you
change commands, endpoints, configuration or behaviour, and keep the "AI-assisted
development" section accurate.
