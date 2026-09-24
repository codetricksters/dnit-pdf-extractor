-- Catálogo sem pendências e índices com origem e sem sobreposição.
--
-- 1. Um código de serviço está associado a um produto ou não está no catálogo.
--    O estado "sugerido, aguardando confirmação" deixa de existir: as sugestões
--    automáticas não confirmadas são apagadas, e a linha existente passa a
--    significar "associado".
DELETE FROM produto_codigo WHERE NOT confirmado;
ALTER TABLE produto_codigo DROP COLUMN confirmado;

-- 2. Origem e data da última gravação de cada índice, para a importação
--    preservar o que o usuário corrigiu à mão. O que já está no banco veio do
--    seed; o padrão das próximas linhas é 'manual'.
ALTER TABLE anp_preco_semanal
    ADD COLUMN origem TEXT NOT NULL DEFAULT 'seed',
    ADD COLUMN atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE anp_preco_semanal ALTER COLUMN origem SET DEFAULT 'manual';

ALTER TABLE indice_mensal
    ADD COLUMN origem TEXT NOT NULL DEFAULT 'seed',
    ADD COLUMN atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE indice_mensal ALTER COLUMN origem SET DEFAULT 'manual';

-- 3. Semanas sobrepostas proibidas para o mesmo produto e região: o "dia 15"
--    de um mês nunca cai em duas semanas, então não há desempate a escolher.
--    Pontas inclusas ('[]'), como na regra de consulta.
CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE anp_preco_semanal
    ADD CONSTRAINT anp_vigencia_ordenada CHECK (vigencia_fim >= vigencia_inicio);

ALTER TABLE anp_preco_semanal
    ADD CONSTRAINT anp_sem_sobreposicao EXCLUDE USING gist (
        produto WITH =,
        regiao WITH =,
        daterange(vigencia_inicio, vigencia_fim, '[]') WITH &&
    );
