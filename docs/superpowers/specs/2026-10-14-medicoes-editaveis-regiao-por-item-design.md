# Edição de registros de medição e região ANP por item

## Context
Hoje as medições extraídas de um contrato só podem ser lidas. A aba *Medições* não permite incluir, alterar nem excluir um registro, e reenviar o PDF sobrescreve tudo (`medicoes_repo.gravar_itens`, `ON CONFLICT … DO UPDATE`). O ΔP também não vê os registros um a um: ele sai da região da família (`contrato_familia_regiao`), que pode ser substituída para uma geração pela simulação `?regiao_cap=`/`?regiao_emulsoes=`.

O que o usuário quer:
1. Incluir, alterar e excluir um registro de medição (código × mês) por vez.
2. Definir a região ANP de CAP e/ou de Emulsões **num registro**. Esse registro passa a ser calculado pela região própria, que **prevalece** sobre a do cadastro e sobre a simulação da exportação.
3. Ao reenviar o PDF, o trabalho manual fica preservado: registros editados ou incluídos à mão não são sobrescritos, e os excluídos não voltam.
4. Na planilha, o registro com região própria vira uma linha separada, com `*` na descrição, fundo colorido e uma nota indicando a região. A tela marca do mesmo jeito.

## Banco — `migrations/008_medicao_manual.sql`
- `medicao_item` ganha colunas novas:
  - `origem TEXT NOT NULL DEFAULT 'pdf' CHECK (origem IN ('pdf','editado','manual'))`
  - `excluido BOOLEAN NOT NULL DEFAULT false` (exclusão lógica de um registro vindo do PDF, para o reprocessamento não trazê-lo de volta; um registro `manual` é apagado de fato)
  - `regiao_cap TEXT NULL` e `regiao_emulsoes TEXT NULL`
  - `atualizado_em TIMESTAMPTZ`
- A `UNIQUE (contrato_id, codigo_servico, mes_medicao, source_file)` dá lugar a um índice único parcial `WHERE origem <> 'manual'`. Um registro manual usa `source_file = 'manual'` e não entra em conflito com o PDF.

## Backend
**`app/services/medicoes_repo.py`**
- `gravar_itens`: `ON CONFLICT … DO UPDATE … WHERE medicao_item.origem = 'pdf' AND NOT medicao_item.excluido`. O contador de retorno continua igual.
- Funções novas, que validam tudo antes de abrir a transação, no padrão de `contratos_repo.atualizar`, e recusam com `MedicaoInvalida`:
  - `incluir_item(contrato_id, dados)` → `origem='manual'`
  - `atualizar_item(contrato_id, item_id, dados)`: os campos são mês, código, descrição, valor_pi, fator, regiao_cap e regiao_emulsoes. Um registro `pdf` passa a `editado`.
  - `excluir_item(contrato_id, item_id)`: apaga um `manual`; num `pdf`/`editado`, marca `excluido=true`.
- Regiões normalizadas com `indices_repo.normalizar_regiao` e validadas contra `cobertura()["regioes"]`. Vazio → NULL, e o registro volta a seguir o contrato.
- `listar_itens` e `itens_para_export` passam a ignorar `excluido` e a devolver `origem`, `regiao_cap` e `regiao_emulsoes`.

**`app/services/reequilibrio_export.py`**
- Região de cada item: `regiao_<familia do produto>` do item; se não houver, a região efetiva da família (cadastro ou simulação).
- `_deltas` passa a usar a chave `(familia, mes, regiao)`, e `faltando` relata também os índices que faltam nas regiões manuais.
- `montar_grupos`: a agregação fica produto × mês × fator × `regiao_manual` (None quando segue o contrato). `Linha` ganha `regiao_manual`.
- `serializar`: inclui `regiao_manual` em cada linha.
- `gerar`:
  - Nas linhas com `regiao_manual`, a descrição recebe `*` e o fundo fica colorido (uma `PatternFill` única).
  - Depois do total entra uma nota por região/família: `* Região ANP definida no item: CAP – Sul`.
  - Endereços e texto ficam em `reequilibrio_layout.py`.
  - As fórmulas vivas não mudam, e a coluna G continua literal.
- `avisos`: avisar quantos registros usam região própria.

**`app/routers/api/contratos.py` e `schemas.py`**
- Rotas novas, que respondem 404 quando o contrato ou o item não existe e convertem `MedicaoInvalida` em `ErroApi(422)`:
  - `POST /contratos/{id}/medicoes` → 201
  - `PATCH /contratos/{id}/medicoes/{item_id}`
  - `DELETE /contratos/{id}/medicoes/{item_id}` → 204
- `ItemMedicao` ganha `origem`, `regiao_cap` e `regiao_emulsoes`; os esquemas de entrada são `MedicaoEntrada`/`MedicaoAlteracao`, com Decimal em texto.
- A linha do cálculo ganha `regiao_manual`.

## Frontend
- `api/medicoes.ts` (incluir/alterar/excluir), `api/tipos.ts`, e `api/invalidar.ts` com `aposMedicao`, que invalida medições, cálculo e lista de contratos.
- `pages/contrato/AbaMedicoes.tsx`:
  - Um botão *Incluir registro* e, em cada linha, *Editar* e *Excluir*. Excluir pede confirmação com `ConfirmarDialogo`.
  - Um diálogo `DialogoMedicao` com react-hook-form. O mês usa o campo de mês/ano que já existe. As regiões são seletores com as regiões de `cobertura`, mais a opção "Seguir o contrato". Os erros 422 aparecem no campo.
  - Colunas novas: *Origem* (badge `manual`/`editado`) e *Região* (badge com `*`).
- Aba *Cálculo*: `*` com badge e classe de linha destacada quando a linha tem `regiao_manual`, mais uma nota abaixo da tabela.
- Token novo em `styles/tokens.css` (`--row-regiao-manual`) e classe em `telas.css`, sem `style` inline.
- A *Situação* e o ΔP continuam vindo do backend; o frontend não calcula nada.

## Documentação (mesma alteração)
- `architecture.md`: migração 008 no layout.
- `backend.md`: regras de `medicoes_repo` (preservação do manual, exclusão lógica), precedência da região (item > simulação > cadastro) e a nova chave de agregação/ΔP.
- `frontend.md`: ações da aba *Medições* e `aposMedicao`.
- `README.md`, em *O que a aplicação faz*.

## Verificação
- **pytest** (`uv run pytest -q`):
  - repo: incluir, editar e excluir; reprocessar o mesmo PDF preserva os registros editados e manuais e não traz de volta os excluídos;
  - `delta_p`/export: item com região própria → linha separada, ΔP da região dele mesmo sob simulação; índice faltante na região manual aparece em `faltando`;
  - planilha: `*`, fill e nota presentes, fórmulas intactas, equação preservada;
  - API: 201/204/404/422.
- **Vitest**: diálogo de inclusão/edição, confirmação de exclusão, erro 422 no campo, marcação na aba Cálculo.
- **Playwright**: um cenário que edita a região de um registro e confere a linha marcada no Cálculo.
- **Manual**: `npm run build`, `uvicorn`, editar um registro, baixar a planilha e conferir no Excel.
