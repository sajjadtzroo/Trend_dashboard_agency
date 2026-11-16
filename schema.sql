-- =====================================================================
-- Creative Lab — Agency Finance Star Schema (PostgreSQL)
-- Mother fact: fact_transaction  |  Dates: Jalali + Gregorian
-- =====================================================================
--
-- ---------------------------------------------------------------------
-- REUSABLE PROMPT (paste into an LLM to regenerate/extend this schema):
-- ---------------------------------------------------------------------
-- "You are a senior data engineer. Design a PostgreSQL STAR SCHEMA for a
--  creative advertising agency's finances. One MOTHER fact table
--  `fact_transaction` at grain = one financial line item, discriminated by
--  transaction_type in (SALE, RECEIVABLE, PAYABLE):
--    - SALE       = sales-funnel / income-statement order line (revenue, cost, profit)
--    - RECEIVABLE = client invoice (VAT, insurance, receivable, paid, balance)
--    - PAYABLE    = supplier/freelancer payment (total, paid, balance)
--  Dimensions (surrogate integer *_key PKs, keep business keys as columns):
--    dim_date (JALALI year/month/day + jalali_date text + gregorian_date + quarter + fa month name),
--    dim_user (account/salesperson), dim_client (company + national_code + industry category),
--    dim_brand (belongs to client), dim_project (project_code like BEL401, belongs to client),
--    dim_campaign (order name, belongs to project), dim_service (media: VOD/BTL/Studio/Digital),
--    dim_supplier, dim_payment_status (0/1/2 -> Unpaid/Paid/Partial),
--    dim_payment_method (seeded lookup, no source data yet),
--    dim_order_status (funnel: Opportunity/Confirm/Invoice/Decline),
--    dim_invoice (invoice_number, po_number, clearance_certificate).
--  All money is IRR. Add FK indexes + composite indexes on (date,type) and (client,date).
--  Seed the small lookup dims. Output idempotent DDL (IF NOT EXISTS)."
-- ---------------------------------------------------------------------

BEGIN;

-- =====================================================================
-- DIMENSIONS
-- =====================================================================

CREATE TABLE IF NOT EXISTS dim_date (
    date_key            INTEGER      PRIMARY KEY,          -- YYYYMMDD in Jalali, e.g. 14040517
    jalali_year         SMALLINT     NOT NULL,
    jalali_month        SMALLINT     NOT NULL,
    jalali_day          SMALLINT     NOT NULL,
    jalali_date         TEXT         NOT NULL,             -- '1404-05-17'
    gregorian_date      DATE         NOT NULL,
    jalali_quarter      SMALLINT     NOT NULL,
    jalali_month_name_fa TEXT        NOT NULL,             -- فروردین ...
    weekday             SMALLINT                            -- 0=Shanbe .. 6=Jomeh (optional)
);

CREATE TABLE IF NOT EXISTS dim_user (
    user_key    SERIAL PRIMARY KEY,
    account     TEXT NOT NULL UNIQUE,                       -- Mamrez, Narges
    role        TEXT                                        -- Sales / Accounting
);

CREATE TABLE IF NOT EXISTS dim_client (
    client_key    SERIAL PRIMARY KEY,
    company_name  TEXT NOT NULL,                            -- Unilever, Bel Rouzaneh ... (canonical, one row per client)
    national_code TEXT,                                     -- tax / national id (sparse: only Sales carries it, backfilled)
    category      TEXT,                                     -- FMCG, Home Appliances, Car Industry ...
    UNIQUE (company_name)                                   -- identity is the canonical name; national_code is NULL in most sheets
);

CREATE TABLE IF NOT EXISTS dim_brand (
    brand_key   SERIAL PRIMARY KEY,
    brand_name  TEXT NOT NULL,                              -- Rouzaneh, Clear, Lux ...
    client_key  INTEGER REFERENCES dim_client(client_key),
    UNIQUE (brand_name, client_key)
);

CREATE TABLE IF NOT EXISTS dim_project (
    project_key  SERIAL PRIMARY KEY,
    project_code TEXT NOT NULL UNIQUE,                      -- BEL401, PKS401, ARN401 ...
    project_name TEXT,
    client_key   INTEGER REFERENCES dim_client(client_key)
);

CREATE TABLE IF NOT EXISTS dim_campaign (
    campaign_key SERIAL PRIMARY KEY,
    order_name   TEXT NOT NULL,                             -- "Legends Campaign", "Mid-Roll 10"
    project_key  INTEGER REFERENCES dim_project(project_key),
    UNIQUE (order_name, project_key)
);

CREATE TABLE IF NOT EXISTS dim_service (
    service_key  SERIAL PRIMARY KEY,
    service_name TEXT NOT NULL UNIQUE                       -- VOD, BTL, Studio, Digital, Social, ATL
);

CREATE TABLE IF NOT EXISTS dim_supplier (
    supplier_key  SERIAL PRIMARY KEY,
    supplier_name TEXT NOT NULL UNIQUE,
    main_service  TEXT
);

CREATE TABLE IF NOT EXISTS dim_media (
    media_key  SERIAL PRIMARY KEY,
    media_name TEXT NOT NULL UNIQUE                       -- VOD, BTL, Studio, Digital, OOH, Social
);

CREATE TABLE IF NOT EXISTS dim_payment_status (
    payment_status_key SMALLINT PRIMARY KEY,                -- source code 0/1/2
    label              TEXT NOT NULL                        -- Unpaid / Paid / Partial
);

CREATE TABLE IF NOT EXISTS dim_payment_method (
    payment_method_key SERIAL PRIMARY KEY,
    label              TEXT NOT NULL UNIQUE
);  -- ponytail: seeded, no source data yet — populate as real payment methods appear

CREATE TABLE IF NOT EXISTS dim_order_status (
    order_status_key SERIAL PRIMARY KEY,
    label            TEXT NOT NULL UNIQUE,                  -- funnel stage
    funnel_rank      SMALLINT                               -- 1..n ordering
);

CREATE TABLE IF NOT EXISTS dim_invoice (
    invoice_key          SERIAL PRIMARY KEY,
    invoice_number       TEXT,
    po_number            TEXT,
    clearance_certificate TEXT,
    UNIQUE (invoice_number, po_number)
);

-- =====================================================================
-- MOTHER FACT
-- =====================================================================

CREATE TABLE IF NOT EXISTS fact_transaction (
    transaction_id    BIGSERIAL PRIMARY KEY,
    transaction_type  TEXT NOT NULL CHECK (transaction_type IN ('SALE','RECEIVABLE','PAYABLE')),

    -- dimension foreign keys (nullable where a type doesn't use them)
    date_key            INTEGER  REFERENCES dim_date(date_key),
    user_key            INTEGER  REFERENCES dim_user(user_key),
    client_key          INTEGER  REFERENCES dim_client(client_key),
    brand_key           INTEGER  REFERENCES dim_brand(brand_key),
    project_key         INTEGER  REFERENCES dim_project(project_key),
    campaign_key        INTEGER  REFERENCES dim_campaign(campaign_key),
    service_key         INTEGER  REFERENCES dim_service(service_key),
    media_key           INTEGER  REFERENCES dim_media(media_key),              -- SALE media channel
    supplier_key        INTEGER  REFERENCES dim_supplier(supplier_key),        -- PAYABLE only
    invoice_key         INTEGER  REFERENCES dim_invoice(invoice_key),          -- RECEIVABLE / PAYABLE
    payment_status_key  SMALLINT REFERENCES dim_payment_status(payment_status_key),
    payment_method_key  INTEGER  REFERENCES dim_payment_method(payment_method_key),
    order_status_key    INTEGER  REFERENCES dim_order_status(order_status_key), -- SALE funnel

    -- measures (all IRR unless noted)
    currency            TEXT NOT NULL DEFAULT 'IRR',
    amount              NUMERIC(20,2),   -- gross / invoice / supplier total
    vat_rate            NUMERIC(6,4),
    vat_amount          NUMERIC(20,2),
    final_amount        NUMERIC(20,2),
    insurance_rate      NUMERIC(6,4),
    insurance_amount    NUMERIC(20,2),
    receivable          NUMERIC(20,2),
    amount_paid         NUMERIC(20,2),
    balance             NUMERIC(20,2),
    revenue             NUMERIC(20,2),   -- SALE
    cost                NUMERIC(20,2),   -- SALE (total: invested + external)
    invested_cost       NUMERIC(20,2),   -- SALE: the invested part of cost (VOD media buy)
    operational_profit  NUMERIC(20,2),   -- SALE
    profit_margin       NUMERIC(7,4),    -- SALE (null when source was #DIV/0!)
    fulfillment_pct     NUMERIC(5,2),    -- SALE (0..100)

    source_row          TEXT,            -- optional provenance: 'Sales!R12'
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Sales Funnel sheet now carries per-channel columns: one SALE fact per channel
-- (source_row 'Sales!R12#VOD'), so an order spanning channels is several rows.
ALTER TABLE fact_transaction ADD COLUMN IF NOT EXISTS invested_cost NUMERIC(20,2);

-- =====================================================================
-- INDEXES
-- =====================================================================
CREATE INDEX IF NOT EXISTS ix_ft_type        ON fact_transaction(transaction_type);
CREATE INDEX IF NOT EXISTS ix_ft_date        ON fact_transaction(date_key);
CREATE INDEX IF NOT EXISTS ix_ft_user        ON fact_transaction(user_key);
CREATE INDEX IF NOT EXISTS ix_ft_client      ON fact_transaction(client_key);
CREATE INDEX IF NOT EXISTS ix_ft_brand       ON fact_transaction(brand_key);
CREATE INDEX IF NOT EXISTS ix_ft_project     ON fact_transaction(project_key);
CREATE INDEX IF NOT EXISTS ix_ft_campaign    ON fact_transaction(campaign_key);
CREATE INDEX IF NOT EXISTS ix_ft_service     ON fact_transaction(service_key);
CREATE INDEX IF NOT EXISTS ix_ft_media       ON fact_transaction(media_key);
CREATE INDEX IF NOT EXISTS ix_ft_supplier    ON fact_transaction(supplier_key);
CREATE INDEX IF NOT EXISTS ix_ft_orderstatus ON fact_transaction(order_status_key);
-- composite indexes for common dashboard filters
CREATE INDEX IF NOT EXISTS ix_ft_type_date   ON fact_transaction(transaction_type, date_key);
CREATE INDEX IF NOT EXISTS ix_ft_client_date ON fact_transaction(client_key, date_key);

-- =====================================================================
-- PAYMENTS — itemized payments recorded in-app against a RECEIVABLE invoice.
-- The imported fact_transaction.amount_paid/balance stay the live source of
-- truth (each recorded payment bumps them), so grids/status need no changes.
-- This table is the itemized history behind that number.
-- ponytail: a full re-import resets the aggregate to source truth; these rows
-- survive here. Re-fold them into amount_paid only if that ever matters.
-- =====================================================================
CREATE TABLE IF NOT EXISTS payment (
    payment_id     BIGSERIAL PRIMARY KEY,
    transaction_id BIGINT NOT NULL REFERENCES fact_transaction(transaction_id) ON DELETE CASCADE,
    amount         NUMERIC(20,2) NOT NULL CHECK (amount > 0),
    paid_on        DATE NOT NULL,
    method         TEXT,                                   -- a dim_payment_method label
    note           TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_payment_txn ON payment(transaction_id);

-- =====================================================================
-- SOFT-DELETE FLAGS (management CRUD never hard-deletes referenced dims)
-- =====================================================================
ALTER TABLE dim_campaign ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE dim_project  ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE dim_user     ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE dim_media    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
-- user role for the manager view
ALTER TABLE dim_user     ADD COLUMN IF NOT EXISTS role TEXT;

-- =====================================================================
-- SEED LOOKUPS
-- =====================================================================
INSERT INTO dim_service (service_name) VALUES ('VOD'),('BTL'),('Studio'),('Digital'),('Social'),('ATL')
    ON CONFLICT (service_name) DO NOTHING;

INSERT INTO dim_media (media_name) VALUES ('VOD'),('BTL'),('Studio'),('Digital'),('OOH'),('Social'),('ATL')
    ON CONFLICT (media_name) DO NOTHING;

INSERT INTO dim_payment_status (payment_status_key, label)
    VALUES (0,'Unpaid'),(1,'Paid'),(2,'Partial')
    ON CONFLICT (payment_status_key) DO NOTHING;

INSERT INTO dim_payment_method (label)
    VALUES ('Bank Transfer'),('Cash'),('Cheque'),('POS'),('Unknown')
    ON CONFLICT (label) DO NOTHING;

INSERT INTO dim_order_status (label, funnel_rank)
    VALUES ('Opportuinity',1),('Proposal',2),('Confirm',3),('Invoice',4),('Suspend',8),('Decline',9)
    ON CONFLICT (label) DO NOTHING;

-- =====================================================================
-- AUTH — dashboard login accounts (separate from dim_user salespeople)
-- =====================================================================
CREATE TABLE IF NOT EXISTS app_user (
    id            BIGSERIAL PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    token_version INTEGER NOT NULL DEFAULT 0,   -- bump to revoke every session at once
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;

-- =====================================================================
-- RAG CHATBOT — Phase 0: pgvector + lexical extensions, read-only SQL role
-- (Runs after COMMIT; init_schema() executes the file in AUTOCOMMIT.)
-- Requires the pgvector/pgvector image — plain postgres:16 lacks `vector`.
-- =====================================================================
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- Persian-friendly fuzzy lexical (no FA FTS dict)

-- Read-only role for the free-form SQL branch. NOLOGIN by design: exec_sql does
-- `SET LOCAL ROLE bot_ro` inside its transaction on the existing connection, so
-- there's no second credential to manage and the timeout/row-cap wrapper still applies.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'bot_ro') THEN
        CREATE ROLE bot_ro NOLOGIN;
    END IF;
END $$;
GRANT USAGE ON SCHEMA public TO bot_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO bot_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO bot_ro;  -- future chunk/document tables

-- =====================================================================
-- RAG CHATBOT — Phase 2: document corpus for dense retrieval
-- Store content_raw (original, for citations) AND content_norm (embedding/lexical).
-- embedding dims = EMBED_DIMS (default 1024, Qwen3 MRL); the P0 probe may switch this
-- to 3072 (Gemini native) -> ALTER COLUMN + reindex (the documented migration path).
-- =====================================================================
CREATE TABLE IF NOT EXISTS document (
    document_id    BIGSERIAL PRIMARY KEY,
    source_uri     TEXT NOT NULL,
    title_raw      TEXT,
    doc_type       TEXT,
    lang           TEXT,
    doc_tags       TEXT[] DEFAULT '{}',
    jalali_yyyymm  INTEGER,
    gregorian_date DATE,
    content_hash   TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_uri, content_hash)
);

CREATE TABLE IF NOT EXISTS chunk (
    chunk_id        BIGSERIAL PRIMARY KEY,
    document_id     BIGINT NOT NULL REFERENCES document(document_id) ON DELETE CASCADE,
    ord             INTEGER NOT NULL,
    content_raw     TEXT NOT NULL,
    content_norm    TEXT NOT NULL,
    token_count     INTEGER,
    embedding_model TEXT NOT NULL,
    embedding       halfvec(1024),
    UNIQUE (document_id, ord, embedding_model)
);
-- ponytail: prod had a pre-existing `chunk` without these columns; CREATE IF NOT EXISTS
-- skipped it and the hnsw index below crashed boot. Backfill columns idempotently.
ALTER TABLE chunk ADD COLUMN IF NOT EXISTS embedding_model TEXT;
ALTER TABLE chunk ADD COLUMN IF NOT EXISTS embedding halfvec(1024);

CREATE INDEX IF NOT EXISTS ix_chunk_embedding
    ON chunk USING hnsw (embedding halfvec_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX IF NOT EXISTS ix_chunk_norm_trgm
    ON chunk USING gin (content_norm gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_doc_yyyymm ON document(jalali_yyyymm);
CREATE INDEX IF NOT EXISTS ix_doc_tags   ON document USING gin (doc_tags);

GRANT SELECT ON document, chunk TO bot_ro;  -- explicit for existing DBs (default-priv only covers future tables)
