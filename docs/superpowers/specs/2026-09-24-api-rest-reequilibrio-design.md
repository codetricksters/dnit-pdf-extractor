# Subprojeto A — API REST e correção do modelo do reequilíbrio

Data: 2026-09-24 · Status: aprovado em conversa, aguardando revisão da spec

## Contexto e divisão

A revisão da aplicação foi dividida em três subprojetos, cada um com spec, plano e
implementação próprios:

- **A (este documento)** — correção do modelo de domínio e uma API REST completa
  em `/api/v1`, usável por curl/CLI e pelo frontend futuro; teste ponta a ponta
  com índices reais.
- **B** — frontend novo (navegação e telas redesenhadas), consumindo a API de A.
  A escolha do framework (React ou outro) é decidida lá.
- **C** — revisão final: remoção do que ficar obsoleto (Dash, trilha de etapas),
  reorganização das rotas antigas, README e regras.

**O Dash fica congelado durante A.** Telas que quebrarem com as mudanças de modelo
ficam quebradas até B; os testes correspondentes em `tests/test_dashboard.py`
são marcados `skip` com o motivo "Dash congelado até o subprojeto B". As rotas
atuais (`/upload`, `/jobs`, `/admin`, `/reequilibrio/planilha`) continuam
funcionando sem alteração.

## Regras de domínio

1. **Contrato** tem Data Base e uma região ANP por família (CAP, EMULSOES). Ambas
   obrigatórias para o contrato estar completo. A Data Base vem sugerida pelo PDF
   e é **editável** pelo usuário.
2. **Exportação** aceita trocar a região de cada família só para aquela geração
   (simulação), sem alterar o cadastro. Não existe comparativo entre regiões numa
   mesma planilha: para comparar, exporta-se duas vezes.
3. **Catálogo** é independente de contrato. O usuário cadastra produtos
   (descrição livre + família) e associa *alguns* códigos de serviço a eles. Código
   sem associação fica fora do cálculo — não é pendência, não gera aviso, não
   bloqueia nada. A associação é retroativa: todos os itens já extraídos com
   aquele código passam a entrar no cálculo, sem reprocessar PDFs
   (`medicao_item` já guarda todos os itens).
4. **Índices** (ANP semanal e IGP-DI mensal) são globais, sem relação com
   contrato, editáveis por qualquer usuário, individualmente ou em massa por
   upload.
5. **ΔP** mantém as fórmulas atuais (`delta_p.py`), já conferidas contra a planilha
   de referência:
   - preço ANP do mês `m` = a semana cujo intervalo `[início, fim]`, **pontas
     inclusas**, contém o **dia 15** de `m − 1`; base = Data Base − 1;
   - IGP-DI do mês `m`; base = Data Base;
   - `ΔP_cap = P(m−1)/P(base) − 1`;
     `ΔP_emul = 0,75·ΔP_cap + 0,25·(IGP(m)/IGP(base) − 1)`.
6. **Semanas sobrepostas são proibidas** para o mesmo produto e região — seja por
   upload, seja por edição manual. Assim o "dia 15" nunca cai em duas semanas e não
   há desempate a escolher.
7. **Semana sem cotação** (`***` no arquivo, NULL no banco) no dia de referência
   **recusa** o cálculo com mensagem do mês e da região — o mesmo resultado da
   planilha de referência (`#VALOR!`), com mensagem legível. Não há fallback para
   outra semana nem para a coluna Brasil.
8. A **memória de cálculo** é fixa (equação do template). Não é parâmetro.

## Modelo de dados — migração `006`

**Catálogo**
- `produto` mantém `descricao_export` (única), `familia` (`CAP`/`EMULSOES`),
  `ordem`. Rótulos de exibição das famílias ficam no código:
  `CAP → "Aquisição de CAP"`, `EMULSOES → "Aquisição de Emulsões"`.
- `produto_codigo`: apagar as linhas com `confirmado = false`, depois
  `DROP COLUMN confirmado`. Linha existente = código associado.
- Os produtos já existentes (inclusive os criados pela sugestão automática, como
  "TRANSPORTE DE CAP 50/70") **são mantidos**; a limpeza é do usuário, pela API.

**Contrato**
- Sem mudança de esquema. `contratos_repo.registrar_do_pdf` continua não
  sobrescrevendo o que o usuário editou; `data_base` passa a aceitar edição pelo
  `PATCH`.

**Índices**
- `anp_preco_semanal` e `indice_mensal` ganham
  `origem TEXT NOT NULL DEFAULT 'manual'` (`'manual'` ou `'upload:<arquivo>'`) e
  `atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()`. Linhas existentes recebem
  `origem = 'seed'`.
- Sobreposição proibida no banco:
  `CREATE EXTENSION IF NOT EXISTS btree_gist` e
  `EXCLUDE USING gist (produto WITH =, regiao WITH =,
  daterange(vigencia_inicio, vigencia_fim, '[]') WITH &&)`.
  O importador também verifica antes de gravar, para dar mensagem por linha; a
  constraint é a garantia final.
- Sem histórico de versões: uma correção sobrescreve o valor anterior.

## Código removido ou alterado

- `catalogo`: saem `registrar_pendencia`, `sugerir_familia`, `listar_pendencias`,
  `confirmar_codigo`; `codigos_confirmados` vira `codigos_associados`;
  `registrar_codigo` perde o parâmetro `confirmado`; entram edição/exclusão de
  produto, desassociar código e `buscar_codigos(q, associado)`.
- Valores `origem` possíveis: `'manual'`, `'upload:<arquivo>'` e `'seed'`. Só
  `'manual'` é protegido na importação.
- `medicoes_repo.gravar_itens` deixa de registrar pendências e devolve só a
  contagem de itens; `itens_para_export` perde o filtro `pc.confirmado`.
- `file_processor` deixa de reportar pendências.
- `reequilibrio_export`: `calcular_deltas` e `exportar` recebem
  `regioes_override: dict[str, str] | None`; a mensagem "Confirme os códigos
  pendentes" vira "Nenhum código de serviço deste contrato está associado a um
  produto". `ExportacaoImpossivel` passa a carregar a lista `faltando`
  estruturada.
- `progresso`: a etapa "Códigos pendentes" deixa de bloquear. Revisão completa
  da trilha fica para B/C.
- `indices_repo`: gravações passam a registrar `origem`/`atualizado_em` e só
  regravam quando o valor muda (`IS DISTINCT FROM`); regiões comparadas sem
  diferenciar maiúsculas (`NORDESTE` = `Nordeste`), gravadas na grafia do
  arquivo ANP.

## API — `/api/v1`

Routers em `app/routers/api/`, schemas Pydantic, repositórios síncronos chamados
via `asyncio.to_thread`. Sem autenticação (uso em rede interna, como hoje).
Contratos são identificados por `id` numérico no caminho; busca por número via
`GET /contratos?numero=…`.

### Contratos — `contratos.py`

| Rota | Função |
|---|---|
| `GET /contratos[?numero=]` | lista: número, data base, regiões, nº de itens e medições, `faltantes` |
| `GET /contratos/{id}` | cadastro completo |
| `PATCH /contratos/{id}` | campos do cadastro, `data_base`, `regioes: {"CAP": …, "EMULSOES": …}`; região inexistente nos preços ANP → 422 |

### Catálogo — `catalogo.py`

| Rota | Função |
|---|---|
| `GET /produtos`, `POST /produtos` | itens customizados (descrição livre + família) |
| `PATCH /produtos/{id}`, `DELETE /produtos/{id}` | edição; exclusão remove as associações (cascade) |
| `GET /codigos?q=&associado=` | códigos distintos extraídos: código, descrição do PDF mais recente, nº de contratos e de ocorrências, produto associado. `q` filtra código **ou** descrição (`ILIKE '%q%'`) — uma caixa de texto livre, sem busca complexa |
| `PUT /codigos/{codigo}` `{"produto_id": n}` | associa ou troca; aceita código ainda não extraído |
| `DELETE /codigos/{codigo}` | desassocia |

### Índices — `indices.py`

| Rota | Função |
|---|---|
| `GET /indices/cobertura` | período e registros de cada série, regiões |
| `GET /indices/anp?produto=&regiao=&de=&ate=` | preços com `origem` e `atualizado_em`; `produto` padrão CAP 50/70 |
| `PUT /indices/anp` | grava/corrige uma semana (`produto`, `vigencia_inicio`, `vigencia_fim`, `regiao`, `preco`); `origem = 'manual'`; sobreposição → 422 indicando a semana em conflito |
| `DELETE /indices/anp/{id}` | remove uma semana |
| `POST /indices/anp/importar` | upload do `.xls` padrão da ANP (ver Importação) |
| `GET /indices/anp/exportar?produto=&regiao=&de=&ate=&formato=xlsx\|csv` | uma linha por semana e região: `produto, vigencia_inicio, vigencia_fim, regiao, preco, origem, atualizado_em` |
| `GET /indices/igp-di?de=&ate=` | valores mensais com `origem` e `atualizado_em` |
| `PUT /indices/igp-di/{AAAA-MM}` `{"valor": …}` | grava/corrige um mês; `origem = 'manual'` |
| `DELETE /indices/igp-di/{AAAA-MM}` | remove um mês |
| `GET /indices/igp-di/template` | template `.xlsx` **preenchido com os valores do banco** (vazio se não houver) |
| `POST /indices/igp-di/importar` | upload do template preenchido |
| `GET /indices/igp-di/exportar?formato=xlsx\|csv` | `xlsx` = o template preenchido (reimportável); `csv` = `mes, valor, origem, atualizado_em` |

### Cálculo e exportação — `calculo.py`

| Rota | Função |
|---|---|
| `GET /contratos/{id}/calculo?regiao_cap=&regiao_emulsoes=` | JSON: parâmetros efetivos (data base, regiões usadas, `simulacao: bool`), grupos família → produto → linhas (`mes`, `a` valor PI, `fator`, `b` reajustamento, `d` ΔP, `c`, `e`, `f`), subtotais, total, avisos |
| `GET /contratos/{id}/planilha?regiao_cap=&regiao_emulsoes=` | o `.xlsx`, mesmos parâmetros |

Cálculo JSON e planilha saem da mesma função, para não divergirem. Numa
simulação, o template não é alterado (não há célula de região no cabeçalho); a
simulação é identificada pelo nome do arquivo
(`Reequilibrio_<numero>_SIMULACAO_CAP-Sul.xlsx`) e por `X-Avisos`.

### Erros

- recurso inexistente → 404;
- cálculo impossível → 422 `{"detail": "...", "faltando": ["...", ...]}` com
  **todos** os índices ausentes;
- arquivo de importação inválido → 422 `{"detail": "...", "erros": ["linha 14: ..."]}`;
- mensagens escritas para o usuário, em português.

## Importação — `app/services/importadores.py`

Módulo puro: recebe bytes, devolve linhas validadas ou lista de erros. A gravação
fica no `indices_repo`. Seed, API e testes usam o mesmo código. Limite de upload:
20 MB.

**ANP (`.xls` padrão, lido com `xlrd`, que passa a ser dependência de runtime)**
- layout conferido antes da leitura: aba `Preços Produtor e Importador`; linha 8
  com `Produto | Período | Região`; linha 9 com `Norte, Nordeste, Centro-Oeste,
  Sul, Sudeste` e `Brasil` na coluna I. Divergência → recusa ("este não é o
  arquivo de preços semanais da ANP");
- dados da linha 10 até a primeira linha sem produto ou sem data serial (rodapé);
  datas seriais do Excel; `***` → NULL; valores quantizados em 5 casas;
- **todos os produtos** do arquivo são importados (≈ 69 mil linhas); o cálculo
  consulta só o CAP 50/70.

**IGP-DI (template próprio, gerado por `openpyxl`)**
- aba `IGP-DI`: `A1 = Mês`, `B1 = Valor`; mês como célula de data (formato
  `mmm/aaaa`) ou texto `MM/AAAA`; valor numérico;
- aba `Instruções` com o formato e a base (ago/1994 = 100);
- validação: mês legível, valor > 0, mês não repetido no arquivo; linhas em branco
  ignoradas.

**Regras comuns**
- **Tudo ou nada**: qualquer linha inválida (inclusive semana sobreposta) recusa o
  arquivo inteiro com a lista de erros; nada é gravado.
- **Prévia**: `?simular=true` valida e devolve o que aconteceria, sem gravar:
  `inseridos`, `atualizados` (com valor antigo e novo), `inalterados`,
  `conflitos_manuais` (chave, valor no banco, valor no arquivo, `atualizado_em`),
  período coberto.
- **Gravação**: `?sobrescrever_manuais=false` (padrão) grava o que não conflita e
  **preserva** os valores `origem = 'manual'`, listando-os na resposta;
  `true` faz o arquivo vencer e grava `origem = 'upload:<arquivo>'`.
- A pergunta "Deseja sobrescrever as N alterações manuais?" é o fluxo prévia →
  gravação; a tela fica para B, a API já o suporta.

**Seed** — `scripts/seed_indices.py` passa a usar os importadores: ANP de
`data/precos-medios-ponderados-semanais-2013.xls`; IGP-DI apenas com
`--igp-di <arquivo no formato do template>`. A planilha
`Reequilíbrio - 26 - Contrato 716-22.xlsx` **não** é usada pelo seed.

## Testes

**Fixtures** em `tests/fixtures/`, geradas uma vez e versionadas:
- `anp_semanal.xls` — o arquivo oficial completo (≈ 2 MB, dado público);
- `igp_di.xlsx` — no formato do template, com valores reais: aba `IGP - DI`
  (jan/2023–jul/2026) mais jan–dez/2022 da coluna "IGP-D-MM" da aba
  `CÁLCULO DA VARIAÇÃO DE PREÇOS` da planilha do usuário;
- `delta_p_referencia.csv` — mês, ΔP CAP e ΔP Emulsões da aba
  `CÁLCULO DA VARIAÇÃO DE PREÇOS` (contrato 716-22, Data Base jan/2022,
  Nordeste): o oráculo, calculado de forma independente no Excel;
- `contrato_ficticio.json` — itens reais de um resultado de extração já
  processado (meses a partir de jan/2023), cabeçalho fictício (número
  `99 99999/2099`, rodovia e contratada inventadas), Data Base real jan/2022.

**Ponta a ponta** — `tests/test_e2e_reequilibrio.py`, só pela API, banco real:
1. importa ANP e IGP-DI pelos endpoints;
2. cria o contrato processando o JSON pelo `file_processor`; completa o cadastro
   e define Nordeste nas duas famílias via `PATCH`;
3. cria "Aquisição de CAP 50/70" e "Aquisição de Emulsão RR-1C", associa **só
   alguns** códigos; confere que os demais ficam fora sem bloquear;
4. `GET /calculo`: cada ΔP confere com o oráculo (tolerância 1e-9); colunas c, e,
   f conferem com as fórmulas do art. 16 recalculadas no teste;
5. `GET /planilha`: fórmulas vivas em F, H, I, J; ΔP em G; equação da memória de
   cálculo presente no drawing;
6. `?regiao_cap=Sul`: ΔP muda, nome do arquivo contém `SIMULACAO`, cadastro
   continua Nordeste.

Se o passo 4 falhar, trata-se de divergência de regra a levar ao usuário — o
oráculo não é ajustado para passar.

**Unitários e de rota**: importadores (layout errado, linha inválida, tudo ou
nada, contagens, prévia, conflito manual preservado/sobrescrito, sobreposição),
exportação CSV/XLSX, reimportação do template exportado, constraint de
sobreposição na edição manual, catálogo (filtro `q`, associar/desassociar,
retroatividade), `PATCH` de contrato (região inexistente → 422), 404 e 422 com
`faltando`, semana sem cotação → recusa.

## Documentação

Na mesma alteração, conforme `.claude/rules/documentation.md`:
- `README.md` — funcionalidades (catálogo, importação/exportação de índices,
  simulação de região), a API (`/api/v1`, `/docs`), setup (novo seed), testes;
- `.claude/rules/backend.md` e `architecture.md` — catálogo sem pendências,
  importadores, API, migração 006, `xlrd` em runtime;
- `.claude/rules/deployment.md` e `requirements.txt` — `xlrd`, extensão
  `btree_gist`.

A documentação do Dash não é reescrita em A (fica para C), mas o que deixar de
ser verdade sobre pendências é removido.

## Fora do escopo

- frontend novo e redesenho da navegação (B);
- remoção do Dash e reorganização das rotas antigas (C);
- autenticação;
- importação automática a partir de sites da ANP/FGV;
- CLI próprio (curl + OpenAPI atendem);
- comparativo entre regiões numa mesma planilha;
- histórico de versões dos índices.
