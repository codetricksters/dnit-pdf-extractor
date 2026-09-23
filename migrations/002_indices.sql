-- Price indices fed by the users.
--
-- NUMERIC, not double precision: these values feed a calculation the user
-- audits cell by cell against a spreadsheet, so float drift is unacceptable.
--
-- Long format (one row per region) rather than one column per region: querying
-- by region needs no dynamic SQL, and a new region is a row, not a migration.

CREATE TABLE IF NOT EXISTS anp_preco_semanal (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    produto         TEXT NOT NULL,
    vigencia_inicio DATE NOT NULL,
    vigencia_fim    DATE NOT NULL,
    regiao          TEXT NOT NULL,
    -- NULL when the source publishes '***' (no quotation that week).
    preco           NUMERIC,
    UNIQUE (produto, vigencia_inicio, regiao)
);

CREATE INDEX IF NOT EXISTS idx_anp_lookup
    ON anp_preco_semanal (produto, regiao, vigencia_inicio);

CREATE TABLE IF NOT EXISTS indice_mensal (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    indice     TEXT NOT NULL,
    base_label TEXT,
    -- Stored as the first day of the month so that comparisons and interval
    -- arithmetic work; a 'YYYY-MM' text column would support neither.
    mes_ref    DATE NOT NULL,
    valor      NUMERIC NOT NULL,
    UNIQUE (indice, mes_ref)
);

CREATE INDEX IF NOT EXISTS idx_indice_mensal_lookup
    ON indice_mensal (indice, mes_ref);
