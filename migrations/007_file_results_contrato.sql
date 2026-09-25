-- Qual contrato cada PDF processado alimentou e quantos itens gravou, para a
-- tela de upload mostrar "48 itens → 15 00716/2022" com link para o contrato.
-- SET NULL: excluir um contrato não apaga o histórico de processamento.
ALTER TABLE file_results
    ADD COLUMN IF NOT EXISTS contrato_id BIGINT REFERENCES contrato(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS itens INTEGER;
