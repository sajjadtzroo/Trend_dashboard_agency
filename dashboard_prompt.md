# Build Prompt — Creative Lab Agency Finance Dashboard

Copy everything below into your coding agent. It has the full spec, stack, schema reference, cleaning rules, and a coverage checklist.

---

You are a senior full-stack engineer. Build an **agency finance dashboard** for a creative advertising agency ("Creative Lab").

## Stack
- **Frontend:** Nuxt 3 (Vue 3, `<script setup>`), Pinia, Chart.js (via `vue-chartjs`).
- **Backend:** FastAPI (Python 3.11), SQLAlchemy 2.x, `psycopg`, `polars` (`read_excel` with the `calamine` engine) + `openpyxl` for import, `jdatetime` for Jalali↔Gregorian.
- **DB:** PostgreSQL — use the star schema in `schema.sql` (mother fact `fact_transaction`, typed `SALE`/`RECEIVABLE`/`PAYABLE`, dims: date, user, client, brand, project, campaign, service, media, supplier, payment_status, payment_method, order_status, invoice). Run `schema.sql` as the migration.
- **Cache:** Redis — cache aggregate query results (keyed by endpoint + filter params, TTL 300s) and hold import-job status.
- **Deploy:** `docker-compose.yml` with `db` (postgres:16), `redis`, `api`, `web`.

## Data & Import
Data comes from `import_template.xlsx` (sheets: `Sales`, `Invoices`, `Suppliers`, plus `_Reference`, `_README`). **Derived columns are Excel formulas** (Sales: Total Revenue/Cost, Operational Profit, Profit Margin %; Invoices: VAT Amount, Final Amount, Insurance Amount, Receivable, Balance; Suppliers: Balance) — read their **cached computed values** (`polars.read_excel(..., engine="calamine")` returns them when the file was saved by Excel/LibreOffice); if a cached value is missing, **recompute from the input columns** using the same arithmetic. Build `POST /import/xlsx` (multipart upload) that:
1. Reads each data sheet with `polars` (calamine engine). **Data rows start at row 2 (real data, no example row)** — do NOT skip row 2; only skip fully-blank spacer rows.
2. **Cleans** every cell:
   - strip leading/trailing whitespace and tab characters from all text;
   - strip thousands separators from numbers (`"10,000,000,000"` → `10000000000`);
   - map `#DIV/0!`, `#N/A`, empty → `NULL` (esp. Profit Margin);
   - coerce percentages (`"90%"`, `90`, `0.9`) consistently (store fulfillment/margin as 0–100 numeric).
3. **Converts Jalali → Gregorian** with `jdatetime` from the Year/Month/Day columns; upsert `dim_date` (store both jalali fields and `gregorian_date`). Handle missing Day (default 1) — log it.
4. **Upserts dimensions** (get-or-create by natural key): user(Account), client(Company+National Code+Category), brand(→client), project(Project ID→client), campaign(Order Name→project), supplier, invoice(Invoice/PO Number), and resolves seeded lookups (service, payment_status 0/1/2, order_status, payment_method).
5. **Inserts `fact_transaction`** rows:
   - `Sales` → `SALE` (revenue, cost, operational_profit, profit_margin, fulfillment_pct, order_status, service, campaign);
   - `Invoices` → `RECEIVABLE` (amount, vat_*, final_amount, insurance_*, receivable, amount_paid, balance, payment_status, invoice);
   - `Suppliers` → `PAYABLE` (amount=Total, amount_paid, balance, payment_status, supplier, service).
6. Returns a summary: rows inserted per type + list of skipped/invalid rows. Store job status in Redis.
7. Idempotent re-import (a stable `source_row` provenance or natural-key upsert avoids duplicates).

## API (all Jalali-aware, all Redis-cached, all accept filters: date range in Jalali, client, brand, service, user, transaction_type)
- `GET /kpis` — total revenue, total cost, operational profit, avg profit margin, AR outstanding (Σ RECEIVABLE balance), AP outstanding (Σ PAYABLE balance).
- `GET /funnel` — count + revenue by `order_status` (Opportuinity→Confirm→Invoice/Decline).
- `GET /revenue-by-service` — revenue/cost/profit grouped by service (VOD/BTL/Studio/Digital).
- `GET /revenue-trend` — monthly (Jalali) revenue vs cost line series.
- `GET /top-clients` and `GET /top-campaigns` — by revenue, with profit margin.
- `GET /receivables` and `GET /payables` — outstanding balances by client / supplier.

### FP&A / Financial Statements (IFRS-aligned)
All statements are period-scoped (Jalali date range → maps to a fiscal period), Redis-cached, and computed from `fact_transaction` (no separate ledger — derive line items from typed rows).
- `GET /statements/income` — **Statement of Profit or Loss** (IAS 1): Revenue (Σ SALE revenue) → Cost of Sales (Σ SALE cost) → Gross Profit → Operating Expenses → Operating Profit (Σ operational_profit) → VAT/tax (IAS 12, from Invoices vat/tax) → Net Profit. Return each line with current-period and prior-period comparatives (IAS 1 requires comparatives) plus % change.
- `GET /statements/balance` — **Statement of Financial Position** (IAS 1): Assets (Trade Receivables = Σ RECEIVABLE balance, incl. insurance retention as a separate line), Liabilities (Trade Payables = Σ PAYABLE balance, VAT payable), and derived Equity (Assets − Liabilities). As-at date, with comparative prior date.
- `GET /statements/cashflow` — **Statement of Cash Flows** (IAS 7), indirect method, operating activities: Net Profit adjusted for ΔReceivables and ΔPayables over the period → Net Cash from Operations.
- `GET /statements/notes` — supporting note breakdowns (revenue disaggregated by service per IFRS 15, ageing of receivables/payables per IFRS 7).
- All monetary lines in IRR; label the reporting currency and period explicitly (IAS 1 presentation). Flag any period with incomplete data rather than silently zeroing.

### Management (CRUD on dimensions + roll-up metrics)
Each resource: `GET /{resource}` (list + per-row roll-ups), `GET /{resource}/{id}` (detail + linked transactions), `POST`/`PATCH`/`DELETE` (validate natural keys; soft-delete, never hard-delete rows referenced by `fact_transaction`).
- `campaigns` — campaign ↔ project ↔ client, with revenue / cost / margin and order-status funnel per campaign.
- `projects` — project ↔ client, budget vs actual (Σ revenue, Σ cost), open receivables, campaign count.
- `users` / **managers** — team members (dim_user, Account); role field (`user` / `manager`); manager view rolls up the campaigns/projects owned by their reports.
- `media` — media channel/type (add `dim_media`: e.g. VOD, BTL, Studio, Digital, OOH, Social; distinct from `service`), linked to campaigns; revenue and spend by media channel. Importer resolves/get-or-creates `dim_media` from the media/channel column and links it on SALE rows.

## UI — palette: **white / grey / green**
- Tokens: background `#FFFFFF`, surface/cards `#F5F7F8`, borders/muted text `#B0BEC5`/`#607D8B`, primary green `#2E7D32`, accent green `#43A047`, positive `#2E7D32`, negative `#C62828`. Text `#263238`. Rounded cards, soft shadow, generous whitespace.
- **Layout:** left sidebar (grey) + top filter bar (Jalali date-range picker, client/service/user dropdowns).
- **Overview page:** 6 KPI cards → funnel chart (horizontal bars) → revenue-by-service grouped bars → revenue-vs-cost trend line → top-clients & top-campaigns tables.
- **Receivables/Payables page:** tables with outstanding balance, aging, payment status chips (green=Paid, grey=Unpaid, amber=Partial).
- **Financials page (FP&A):** three tabs — Income Statement, Balance Sheet, Cash Flow — rendered as classic statement tables (line item, current period, prior period, % change), IFRS/IAS reference in a footnote per statement, currency + period header. Notes accordion for the disaggregation breakdowns.
- **Management pages:** `Campaigns`, `Projects`, `Users/Managers`, `Media` — sortable tables with roll-up metrics, drill-in detail showing linked transactions, and create/edit forms (soft-delete only).
- **Import page:** drag-drop `import_template.xlsx`, show per-type inserted counts and skipped rows.
- Format IRR with thousands separators; show Jalali dates as `1404/05/17`.
- Responsive; accessible (labels, focus states, aria on charts’ data tables).

## Deliverables
`docker-compose.yml`, `schema.sql`, FastAPI app (`app/` with import, models, routers, redis cache dep), Nuxt app (`web/` with pages, components, Pinia store, api client), and a `README.md` with run steps. Seed by importing the provided `import_template.xlsx`.

## Coverage checklist (the build MUST satisfy all)
- [ ] Every dim table in `schema.sql` is populated by the importer.
- [ ] `fact_transaction` rows land with correct `transaction_type` per sheet.
- [ ] Cleaning handles: `#DIV/0!` → NULL, comma numbers, whitespace/tabs, blank spacer rows skipped (row 2 is real data, not skipped).
- [ ] Jalali→Gregorian conversion stored in `dim_date` (both calendars); UI shows Jalali.
- [ ] Redis caches aggregates and holds import-job status.
- [ ] UI uses only the white/grey/green tokens above.
- [ ] Re-importing the same file does not duplicate rows.
- [ ] FP&A statements (Income/Balance/Cash Flow) compute from `fact_transaction` with prior-period comparatives and cite the IFRS/IAS standard.
- [ ] Management CRUD for campaigns, projects, users/managers, media works with soft-delete and blocks deletion of referenced dims.
- [ ] `dim_media` added to `schema.sql`, populated by the importer, and linked on SALE rows.
- [ ] Import uses `polars` (calamine engine); no `pandas` dependency remains.
