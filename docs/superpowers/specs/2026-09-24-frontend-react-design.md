# Subprojeto B — Frontend React do reequilíbrio

Data: 2026-09-24 · Status: em revisão

## Contexto

Segundo dos três subprojetos do redesenho (ver
`2026-09-24-api-rest-reequilibrio-design.md`):

- **A (concluído)** — modelo de domínio corrigido e API REST `/api/v1`.
- **B (este documento)** — frontend novo em React, consumindo a API de A, que
  **substitui toda a interface**: upload, contratos, catálogo, índices, cálculo e
  exportação, templates e backups.
- **C** — remoção do Dash e dos arquivos Jinja, migração de `/upload`, `/jobs` e
  `/admin` para `/api/v1`, revisão final.

As regras de domínio de A valem sem alteração: região ANP obrigatória por família
no contrato e alterável só na exportação (simulação); catálogo global em que
código sem associação fica fora do cálculo sem pendência; índices globais
editáveis por qualquer usuário; memória de cálculo fixa.

## Decisões de interface

Validadas com mockups (sessão de brainstorming visual).

### Navegação

O **contrato é uma página própria**; não existe "contrato ativo" global nem a
trilha de seis etapas. Menu lateral:

| Grupo | Item | Rota |
|---|---|---|
| Trabalho | Contratos | `/` e `/contratos` |
| | Upload de PDFs | `/upload` |
| Bases globais | Catálogo de produtos | `/catalogo` |
| | Índices ANP / IGP-DI | `/indices/anp`, `/indices/igp-di` |
| Sistema | Templates | `/sistema/templates` |
| | Backups | `/sistema/backups` |

A página do contrato (`/contratos/:id`) tem cabeçalho com número e contratada e
três abas com rota própria: `cadastro`, `medicoes`, `calculo`. Catálogo e índices
nunca mostram contrato. O que falta num contrato aparece dentro dele.

### Contratos (tela inicial)

Tabela pesquisável por número: contrato, contratada, rodovia, Data Base, regiões
CAP/Emulsões, nº de medições, período, **Situação**, derivada de `faltantes`:

- vermelho — cálculo bloqueado (`data_base` ou `regiao_*` faltando), com o texto
  do que falta ("Falta região Emulsões");
- amarelo — calcula, planilha sai com aviso (só campos de cabeçalho vazios);
- verde — completo.

Clicar no número abre a aba Cadastro, ou Cálculo se o contrato estiver sem
bloqueio. Botão "Enviar PDFs" leva ao upload. Sem contratos: estado vazio que
convida a enviar PDFs.

### Aba Cadastro

Formulário **sempre editável**, em dois painéis, um botão Salvar/Descartar:

1. **Parâmetros do cálculo** (destacado): Data Base (sugerida pelo PDF,
   editável, mês/ano), Região ANP — CAP, Região ANP — Emulsões. Obrigatórios;
   status "N pendente(s) — cálculo bloqueado". Nota: "Na exportação dá para
   simular outra região sem alterar este cadastro."
2. **Cabeçalho da planilha**: Contratada, Edital, Nº do processo (só leitura,
   vem do PDF), Rodovia, Trecho, Subtrecho, Segmento, Extensão (km). Status "N
   vazio(s) — sairá com aviso".

As regiões oferecidas são as de `GET /indices/cobertura` (`regioes`). Erros do
`PATCH` aparecem no campo correspondente.

### Aba Medições (só leitura)

Itens extraídos do contrato: mês, código, descrição do PDF, valor PI líquido,
fator, reajuste líquido, **produto no catálogo**, arquivo de origem. Filtros: mês,
"só itens no cálculo" / todos, busca por código ou descrição. Código fora do
cálculo mostra "associar", que leva a `/catalogo?q=<código>`.

### Aba Cálculo e exportação

- **Barra**: Data Base (leitura), seletor de região por família (padrão = cadastro),
  "Voltar ao cadastro" (limpa a simulação), "Baixar planilha (.xlsx)".
- **Simulação**: região diferente do cadastro mostra faixa de aviso com a região
  do cadastro e o nome do arquivo que será gerado; o cadastro não muda.
- **Tabela única espelhando a planilha**: colunas com as letras da linha 16
  (`a` valor PI, `b` reajuste, `d` ΔP, `c = a·d`, `e = c − b`,
  `f = e·(1−5,11%)`), agrupada família → produto → meses, subtotal por produto e
  total geral; negativos em vermelho. Avisos (`avisos`) abaixo da tabela.
- **Bloqueado** (422 com `faltando`): caixa de erro listando **todos** os itens
  faltantes; campos do cadastro (`data_base`, `regiao_*`) viram link para a aba
  Cadastro, índices viram atalho para `/indices/anp` ou `/indices/igp-di`.

### Catálogo de produtos

Duas colunas: à esquerda os produtos agrupados por família (com nº de códigos);
à direita o produto selecionado — descrição, família, Editar/Excluir e a tabela
dos seus códigos (código, descrição do PDF, nº de contratos, remover). "+ Novo
produto" (descrição livre + família). "+ Adicionar códigos" abre uma busca nos
códigos extraídos (`q` sobre código ou descrição, filtro associados/todos/sem
produto) com seleção múltipla; cada linha indica "neste produto", "sem produto"
ou "em <outro produto>"; "Associar selecionados" grava em lote. `?q=` na URL
abre a busca preenchida. Exclusão de produto pede confirmação e informa que as
associações são removidas.

### Índices

Página com duas abas, `ANP semanal` e `IGP-DI mensal`, cada uma com faixa de
cobertura (período, registros, nº de valores manuais), filtros, "Exportar"
(xlsx/csv) e "Importar".

- **ANP em grade semanas × regiões** (Norte, Nordeste, Centro-Oeste, Sul,
  Sudeste), como o `.xls` da ANP. Filtros: produto (padrão CAP 50/70) e período.
  Célula clicável para editar (Enter salva, Esc cancela); célula `origem =
  manual` com marca amarela; tooltip com origem e `atualizado_em`; NULL aparece
  como "sem cotação". Menu da linha apaga a semana. "+ Semana" cria uma semana
  (início, fim, região, preço).
- **IGP-DI em grade anos × meses**, mesma edição por célula e marca de manual.
  "Baixar template" (preenchido com o banco) e "Importar".
- **Importação em dois passos**: (1) arquivo → `simular=true`; (2) prévia com
  cartões Novos / Alterados / Iguais / "Seus valores manuais em conflito", a
  tabela dos conflitos (chave, valor no banco, valor no arquivo, editado em) e os
  avisos (ex.: produto pulado); botões Cancelar, "Gravar e manter meus valores
  manuais" (`sobrescrever_manuais=false`) e "Gravar e sobrescrever os N manuais"
  (`true`). Arquivo inválido mostra a lista `erros`.

### Upload de PDFs

Área de arrastar/escolher arquivos; tabela do lote com arquivo, status
(pendente, processando, concluído, falhou — o backend não informa progresso por
página), resultado ("48 itens → 15 00716/2022", com link para o contrato), JSON,
"Tentar de novo" nos que falharam, "Baixar todos os resultados (.zip)". Lotes
anteriores recolhíveis (`GET /jobs?status=`).

### Templates e Backups

Mesmas funções de hoje, em listas com ações:

- Templates: listar, enviar, baixar, ativar, excluir (o ativo não pode ser
  excluído).
- Backups: gerar agora, listar, baixar, enviar `.dump`, restaurar (exige digitar
  o nome do backup), excluir.

## Arquitetura

### Onde o código mora

```
frontend/
├── package.json, package-lock.json, vite.config.ts, tsconfig.json
├── index.html
├── public/                 # favicons, webmanifest
├── src/
│   ├── main.tsx, App.tsx   # roteamento
│   ├── api/                # cliente HTTP, tipos das respostas, erros
│   ├── styles/             # tokens e componentes (herdados de style.css)
│   ├── fonts/              # Inter, JetBrains Mono, Material Symbols (woff2)
│   ├── components/         # casca, tabelas, formulários, badges, diálogos
│   ├── pages/              # uma pasta por tela
│   └── lib/                # formatação BR de números e datas
├── tests/                  # Vitest + Testing Library + MSW
└── e2e/                    # Playwright
```

- **Stack**: Vite, React 19, TypeScript, React Router, TanStack Query,
  react-hook-form. Sem biblioteca de componentes; tabelas e grades são
  componentes próprios.
- **Design system**: tokens de `app/static/css/style.css` (`--surface-*`,
  `--text-*`, `--primary*`, `--tertiary*`, `--error*`/`--critical*`,
  `--success*`, `--border-*`, `--row-height*`, raios, espaçamentos) portados
  para `frontend/src/styles/`. Fontes auto-hospedadas via `@font-face`. **Sem
  CDN e sem emoji**; ícones Material Symbols sempre com rótulo.
- **Node 24** só para desenvolvimento e build.

### Como é servido

- **Produção**: `npm run build` gera `frontend/dist/` (fora do git). O FastAPI
  monta `dist/assets` e responde `index.html` para qualquer rota não reservada
  (`/api`, `/jobs`, `/upload` POST, `/admin`, `/reequilibrio`, `/static`,
  `/dashboard`, `/docs`, `/openapi.json`). Sem `dist/`, `/` responde uma página
  simples orientando a rodar o build — a suíte pytest não depende do frontend.
- **Conflito de rota `/upload`**: `GET /upload` passa a ser a tela do SPA;
  `POST /upload` continua sendo o endpoint de envio.
- **Docker**: estágio `node:24` que roda `npm ci && npm run build`; a imagem
  Python copia só `frontend/dist/`.
- **Desenvolvimento**: `npm run dev` (Vite, porta 5173) com proxy para o
  FastAPI; porta do backend por variável (`VITE_BACKEND_URL`, padrão
  `http://localhost:8000`).

### O que sai e o que fica

- A página Jinja `GET /` deixa de ser servida (o SPA assume `/`); os arquivos
  Jinja e `script.js` são removidos em C.
- O Dash continua montado em `/dashboard`, congelado e fora do menu, até C.
- `/upload`, `/jobs` e `/admin/*` são consumidos como estão.

### Adições no backend

| Rota | Função |
|---|---|
| `GET /api/v1/contratos/{id}/medicoes?mes=&no_calculo=&q=` | itens do contrato com produto associado (ou nulo); 404 se o contrato não existe |
| `GET /api/v1/codigos?produto_id=` | novo filtro: códigos associados a um produto |
| `PUT /api/v1/produtos/{id}/codigos` `{"codigos": [...]}` | associa vários códigos ao produto numa transação; 404 produto inexistente |
| `GET /api/v1/indices/anp/produtos` | produtos ANP distintos no banco, para o filtro da grade ANP |
| `GET /api/v1/indices/cobertura` | cada série ganha `manuais`: quantos valores foram corrigidos à mão |
| JSON do cálculo | ganha `arquivo`: o nome que a planilha baixada teria, com `SIMULACAO` quando há override |
| `GET /jobs/{id}/status` | cada arquivo ganha `contrato_id` e `itens` depois de persistido (migração 007, `file_results.contrato_id`/`itens`), para a tela de upload levar ao contrato |

## Fluxo de dados

- **Leitura** via TanStack Query por chave (`['contratos']`, `['contrato', id]`,
  `['calculo', id, regioes]`, `['medicoes', id, filtros]`, `['produtos']`,
  `['codigos', filtros]`, `['anp', produto, de, ate]`, `['igp-di', de, ate]`,
  `['cobertura']`).
- **Gravação** invalida as chaves afetadas e a tela relê do banco: salvar o
  cadastro invalida contrato, lista e cálculo; associar/desassociar código ou
  editar produto invalida catálogo, medições e todos os cálculos; editar/importar
  índice invalida índices, cobertura e todos os cálculos.
- **Simulação na URL**: `/contratos/:id/calculo?regiao_cap=Sul&regiao_emulsoes=…`
  — compartilhável e estável ao recarregar. O download usa os mesmos parâmetros
  em `GET /api/v1/contratos/{id}/planilha`; JSON e arquivo saem da mesma função.
- **Grade ANP** montada no cliente a partir de `GET /indices/anp` (uma linha por
  semana e região). Edição → `PUT /indices/anp` daquele valor; recusa do backend
  (semana sobreposta, preço ≤ 0) devolve a célula ao valor anterior e mostra a
  mensagem.
- **Importação**: o arquivo fica em memória no navegador entre prévia e
  gravação; o backend não guarda estado.
- **Upload**: `POST /upload` → `EventSource` em `/jobs/{id}/events`, com
  polling de `/jobs/{id}/status` se o SSE falhar.
- **O frontend nunca calcula**: `Decimal` chega como string e só é formatado
  (padrão brasileiro). Mês `jan/2023`, data `15/01/2022`; entrada numérica
  aceita vírgula decimal.

## Erros e estados

- `api/` normaliza os dois formatos de 422: `detail` string (com `faltando` ou
  `erros` quando houver) é exibido como veio; `detail` lista (validação
  Pydantic) vira mensagens por campo.
- 404 → página "não encontrado" (contrato, produto). 413 → "arquivo maior que 20
  MB".
- Falha de rede → aviso fixo "Sem conexão com o servidor" com "Tentar de novo".
- Mensagens de regra de negócio são as do backend, em português; o frontend não
  as reescreve.
- Estados vazios: sem contratos, sem índices, catálogo vazio (explica que só
  códigos associados entram no cálculo), produto sem códigos.
- Ações destrutivas (excluir produto, apagar semana/mês, restaurar backup,
  excluir template/backup) pedem confirmação.

## Testes

- **Backend (pytest)**: os três endpoints novos (sucesso, filtros, 404, 422);
  serviço do SPA (`/contratos/12` e `GET /upload` devolvem `index.html` quando há
  `dist/`; `/api/v1/...`, `POST /upload`, `/jobs`, `/docs` não são capturados;
  sem `dist/`, página de orientação).
- **Frontend (Vitest + Testing Library + MSW)**: formatação BR; normalização dos
  dois 422; montagem da grade ANP (inclusive "sem cotação" e marca manual);
  cadastro (pendências, salvar, erro no campo, descartar); simulação refletida na
  URL, na faixa e no link de download; bloqueio com `faltando` e seus links;
  prévia de importação e os dois botões; busca e associação em lote no catálogo.
- **Ponta a ponta (Playwright)** contra FastAPI real + `dnit_test`, com as
  fixtures de A (`tests/fixtures/`):
  1. completar o cadastro, abrir o cálculo, baixar a planilha; simular
     `regiao_cap=Sul` → nome com `SIMULACAO`, cadastro continua Nordeste;
  2. criar produto, associar 60112 e ver a linha no cálculo;
  3. importar IGP-DI com prévia e um valor manual em conflito, gravar mantendo o
     manual.

  Comando separado (`npm run e2e`); `uv run pytest` continua sem Node.

## Ordem de entrega

1. Esqueleto: Vite/React/TS, tokens e fontes, casca com menu, FastAPI servindo
   `dist/`, estágio Node no Dockerfile.
2. Endpoints novos no backend.
3. Contratos (lista) e aba Cadastro.
4. Aba Cálculo e exportação com simulação.
5. Aba Medições.
6. Catálogo.
7. Índices: grade ANP, grade IGP-DI, importação com prévia, exportação.
8. Upload de PDFs com SSE.
9. Templates e Backups.
10. Ponta a ponta Playwright e documentação final.

## Documentação

Na mesma alteração, conforme `.claude/rules/documentation.md`:

- `README.md` — *O que a aplicação faz* e *Telas* (rotas novas), *Requisitos*
  (Node 24 para build), *Setup* (`npm ci`, `npm run build`), *Testes* (Vitest,
  Playwright), *Estrutura* (`frontend/`).
- `.claude/rules/frontend.md` reescrito para o React (estrutura, tokens, camada
  de API, padrões de tela); Dash descrito só como "congelado até C".
- `.claude/rules/architecture.md` e `deployment.md` — pasta `frontend/`, serviço
  do SPA, estágio Node no Dockerfile, `VITE_BACKEND_URL`.

## Fora do escopo

- remoção do Dash, de `app/templates/` e de `script.js` (C);
- mover `/upload`, `/jobs`, `/admin` para `/api/v1` (C);
- progresso de OCR por página;
- autenticação;
- comparativo de regiões numa mesma tela ou planilha;
- tema claro.
