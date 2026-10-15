-- A escolha "Atualizar registros já importados" do envio, guardada no lote para
-- que "tentar de novo" um arquivo que falhou grave do mesmo jeito que o envio.
-- limpar_regioes só tem efeito junto com atualizar.
ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS atualizar BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS limpar_regioes BOOLEAN NOT NULL DEFAULT false;
