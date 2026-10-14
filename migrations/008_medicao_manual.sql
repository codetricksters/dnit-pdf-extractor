-- Registros de medição editáveis à mão, e a região ANP fixada num registro.
--
-- origem: 'pdf' veio da extração e o reprocessamento ainda o atualiza;
-- 'editado' veio do PDF e foi alterado pelo usuário (o reprocessamento não o
-- toca mais); 'manual' foi incluído pelo usuário.
-- excluido: exclusão lógica de um registro do PDF — se fosse apagado, o
-- reprocessamento o traria de volta. Um registro 'manual' é apagado de fato.
-- regiao_cap / regiao_emulsoes: quando preenchidas, prevalecem sobre a região
-- do contrato e sobre a simulação da exportação para este registro.

ALTER TABLE medicao_item
    ADD COLUMN origem TEXT NOT NULL DEFAULT 'pdf'
        CHECK (origem IN ('pdf', 'editado', 'manual')),
    ADD COLUMN excluido BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN regiao_cap TEXT,
    ADD COLUMN regiao_emulsoes TEXT,
    ADD COLUMN atualizado_em TIMESTAMPTZ;

-- A UNIQUE de 004 tem nome gerado pelo Postgres; procura-se pelo catálogo.
DO $$
DECLARE
    nome text;
BEGIN
    SELECT conname INTO nome FROM pg_constraint
     WHERE conrelid = 'medicao_item'::regclass AND contype = 'u';
    IF nome IS NOT NULL THEN
        EXECUTE format('ALTER TABLE medicao_item DROP CONSTRAINT %I', nome);
    END IF;
END $$;

-- Só os registros do PDF precisam da chave de idempotência; vários registros
-- manuais podem ter o mesmo código e mês.
CREATE UNIQUE INDEX uq_medicao_item_pdf
    ON medicao_item (contrato_id, codigo_servico, mes_medicao, source_file)
    WHERE origem <> 'manual';
