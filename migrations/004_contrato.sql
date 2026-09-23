-- Contract registration (the B3:C13 header block of the export) and the
-- measurement items extracted from the PDFs.

CREATE TABLE IF NOT EXISTS contrato (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero          TEXT NOT NULL UNIQUE,
    -- From the PDF header, written once and never overwritten afterwards.
    data_base       DATE,
    numero_processo TEXT,
    -- Registered by the user; absent from every PDF.
    edital          TEXT,
    rodovia         TEXT,
    trecho          TEXT,
    subtrecho       TEXT,
    segmento        TEXT,
    extensao        NUMERIC,
    contratada      TEXT,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Each family gets its own ANP region, chosen independently by the user.
CREATE TABLE IF NOT EXISTS contrato_familia_regiao (
    contrato_id BIGINT NOT NULL REFERENCES contrato(id) ON DELETE CASCADE,
    familia     TEXT NOT NULL CHECK (familia IN ('CAP', 'EMULSOES')),
    regiao      TEXT NOT NULL,
    PRIMARY KEY (contrato_id, familia)
);

CREATE TABLE IF NOT EXISTS medicao_item (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contrato_id    BIGINT NOT NULL REFERENCES contrato(id) ON DELETE CASCADE,
    codigo_servico TEXT NOT NULL,
    descricao_pdf  TEXT,
    mes_medicao    DATE NOT NULL,
    valor_pi       NUMERIC NOT NULL,
    fator          NUMERIC NOT NULL,
    source_file    TEXT NOT NULL,
    job_id         TEXT,
    -- Makes reprocessing the same PDF idempotent via ON CONFLICT DO UPDATE.
    UNIQUE (contrato_id, codigo_servico, mes_medicao, source_file)
);

CREATE INDEX IF NOT EXISTS idx_medicao_item_contrato
    ON medicao_item (contrato_id, mes_medicao);
