-- Product catalogue: maps service codes found in the PDFs to the export
-- descriptions the user expects, grouped into calculation families.
--
-- The service *code* is the key, never the description: OCR corrupts
-- descriptions but not numeric codes, and several codes denote the same
-- material across contracts.

CREATE TABLE IF NOT EXISTS produto (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    descricao_export TEXT NOT NULL UNIQUE,
    familia         TEXT NOT NULL CHECK (familia IN ('CAP', 'EMULSOES')),
    ordem           INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS produto_codigo (
    codigo_servico TEXT PRIMARY KEY,
    produto_id     BIGINT NOT NULL REFERENCES produto(id) ON DELETE CASCADE,
    descricao_pdf  TEXT,
    -- FALSE = family was guessed from the description and awaits review.
    -- Unconfirmed codes are excluded from the calculation so that a new
    -- material cannot silently contaminate the result.
    confirmado     BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_produto_codigo_produto ON produto_codigo(produto_id);

INSERT INTO produto (descricao_export, familia, ordem) VALUES
    ('AQUISIÇÃO DE CAP 50/70', 'CAP', 1),
    ('AQUISIÇÃO DE EMULSÃO ASFÁLTICA RR-1C', 'EMULSOES', 2),
    ('AQUISIÇÃO DE EMULSÃO ASFÁLTICA PARA IMPRIMAÇÃO', 'EMULSOES', 3),
    ('AQUISIÇÃO DE RR-2C COM POLÍMERO', 'EMULSOES', 4)
ON CONFLICT (descricao_export) DO NOTHING;

INSERT INTO produto_codigo (codigo_servico, produto_id, confirmado)
SELECT c.codigo, p.id, TRUE
FROM (VALUES
    ('60112',   'AQUISIÇÃO DE CAP 50/70'),
    ('92704',   'AQUISIÇÃO DE CAP 50/70'),
    ('8300980', 'AQUISIÇÃO DE CAP 50/70'),
    ('29083',   'AQUISIÇÃO DE EMULSÃO ASFÁLTICA RR-1C'),
    ('5471',    'AQUISIÇÃO DE EMULSÃO ASFÁLTICA RR-1C'),
    ('60107',   'AQUISIÇÃO DE EMULSÃO ASFÁLTICA RR-1C'),
    ('51796',   'AQUISIÇÃO DE EMULSÃO ASFÁLTICA PARA IMPRIMAÇÃO'),
    ('91815',   'AQUISIÇÃO DE EMULSÃO ASFÁLTICA PARA IMPRIMAÇÃO'),
    ('133004',  'AQUISIÇÃO DE RR-2C COM POLÍMERO')
) AS c(codigo, descricao)
JOIN produto p ON p.descricao_export = c.descricao
ON CONFLICT (codigo_servico) DO NOTHING;
