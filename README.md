# Creative Lab — Agency Finance Dashboard

Full-stack finance dashboard for a creative advertising agency, built to
`dashboard_prompt.md`. PostgreSQL star schema, FastAPI backend (polars import,
FP&A/IFRS statements, management CRUD), Redis cache, Nuxt 3 frontend, all wired
with `docker-compose`.

## Stack
- **DB** — PostgreSQL 16, star schema in `schema.sql` (mother fact
  `fact_transaction` typed `SALE`/`RECEIVABLE`/`PAYABLE` + 14 dims incl. `dim_media`).
- **Backend** — FastAPI + SQLAlchemy 2, `polars` (calamine engine) import,
  `jdatetime` for Jalali↔Gregorian, `loguru` logging, Redis cache.
- **Frontend** — Nuxt 3 (`<script setup>`), Pinia, Chart.js via `vue-chartjs`.
- **Cache** — Redis: aggregate results (TTL 300s) + import-job status.

## Run

```bash
docker compose up --build
```

- Web → http://localhost:3000
- API → http://localhost:8000 (OpenAPI docs at `/docs`)
- On first boot the API runs `schema.sql` and **seeds** from `import_template.xlsx`.

### Local dev (API only, against dockerized db/redis)
```bash
docker compose up -d db redis
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://finance:finance@localhost:5432/finance
export REDIS_URL=redis://localhost:6380/0     # compose maps redis to host 6380
uvicorn app.main:app --reload
cd web && npm install && npm run dev      # http://localhost:3000
```

## Data import
`POST /import/xlsx` (multipart) reads `Sales`/`Invoices`/`Suppliers` with polars.
Derived columns are Excel formulas with **no cached values**, so every derived
measure is recomputed from the inputs (verified: 360M @ VAT .1 / Ins .1667 →
Receivable 335,988,000). Cleaning: strip whitespace/tabs, drop thousands
separators, map `#DIV/0!`/`#N/A`/blank → NULL, normalise percentages to 0–100.
Jalali→Gregorian via `jdatetime` (missing day → 1, logged). Dimensions are
get-or-create by natural key; facts carry a `source_row` provenance so
**re-import is idempotent** (verified: 231 rows → 231 after re-upload).

## API
- Dashboard: `/kpis` `/funnel` `/revenue-by-service` `/revenue-trend`
  `/top-clients` `/top-campaigns` `/brands` `/receivables` `/payables` `/meta`
- FP&A (IFRS): `/statements/income` (IAS 1) `/statements/balance` (IAS 1)
  `/statements/cashflow` (IAS 7 indirect) `/statements/notes` (IFRS 15/7)
- Management CRUD: `/manage/{campaigns|projects|users|media}` — list + `/{id}`
  detail + `PATCH` + `DELETE` (soft-deletes rows referenced by facts).
- Import: `POST /import/xlsx`, `GET /import/status/{job_id}`

All dashboard/statement endpoints accept the same filters: `date_from`,
`date_to` (Jalali `YYYYMM`, e.g. `140401`), `client`, `brand`, `service`,
`user`, `transaction_type`. All are Redis-cached; cache is invalidated on import
and on management mutations.

## UI pages
Overview (6 KPIs, funnel, revenue-by-service, revenue-vs-cost trend, top
clients/campaigns) · Receivables · Payables · **Brands** (tick brands to compare
revenue/cost/profit/margin side-by-side + grouped bar chart) · Financials
(Income / Balance / Cash Flow tabs) · Campaigns / Projects / Users-Managers /
Media · Import (drag-drop). Palette white/grey/green; IRR thousands separators;
Jalali dates.

## Layout
```
schema.sql            star schema (idempotent DDL + seeds)
app/                  FastAPI: db, clean, jalali, importer, cache, filters, log, routers/
web/                  Nuxt 3 app
Dockerfile.api        api image
web/Dockerfile        web image
docker-compose.yml    db + redis + api + web
```

## Tests
- `python -m app.clean` — cleaning-function self-check (commas, `#DIV/0!`, `%`, whitespace).
- Verified end-to-end against Postgres+Redis: seed 79 SALE / 22 RECEIVABLE /
  130 PAYABLE, all endpoints 200, filters, prior-period comparatives, PATCH/DELETE,
  idempotent re-import.

## Notes / deferred
- `dim_media` is seeded (VOD/BTL/Studio/Digital/OOH/Social) and imported from
  Main Service (the source has no distinct media column yet).
- FP&A prior-period comparative shows when a `date_from`/`date_to` range is set
  (compared to the same window one Jalali year earlier); the seed data is a
  single year (1404), so prior is 0 until a second year is imported.
