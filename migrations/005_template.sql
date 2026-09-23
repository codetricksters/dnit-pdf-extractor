-- Export templates, stored as bytes inside the database.
--
-- Keeping them here rather than on a volume means one backup artefact covers
-- both the data and the template the spreadsheet is generated from.

CREATE TABLE IF NOT EXISTS template (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome       TEXT NOT NULL,
    arquivo    BYTEA NOT NULL,
    tamanho    INT NOT NULL,
    sha256     TEXT NOT NULL,
    ativo      BOOLEAN NOT NULL DEFAULT FALSE,
    criado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    observacao TEXT
);

-- At most one active template at a time; the export always knows which to use.
CREATE UNIQUE INDEX IF NOT EXISTS idx_template_unico_ativo
    ON template (ativo) WHERE ativo;
