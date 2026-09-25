# Frontend

A interface é um **SPA React** em `frontend/`, construído por Vite e servido pelo
próprio FastAPI a partir de `frontend/dist/` (`app/spa.py`). Ele consome
`/api/v1`, `POST /upload`, `/jobs` e `/admin` como estão — nenhuma regra de
negócio mora no navegador.

A interface anterior (Jinja em `app/templates/`, `app/static/js/script.js` e o
Dash em `/dashboard`) continua no repositório, **congelada**: `GET /` não é mais
dela, o Dash fica fora do menu, e nada novo entra ali. A remoção é um passo
posterior.

## Estrutura

```
frontend/
├── package.json, package-lock.json, tsconfig.json, vite.config.ts, playwright.config.ts, index.html
├── public/                # favicons, site.webmanifest, logo.svg
├── src/
│   ├── main.tsx, App.tsx  # QueryClient, BrowserRouter, as rotas
│   ├── styles/            # fontes, tokens, casca, componentes, upload, telas (index.css importa todos)
│   ├── fonts/             # Inter, JetBrains Mono, Material Symbols Outlined (woff2)
│   ├── api/               # client, erros, tipos, chaves, invalidar e um módulo por recurso
│   ├── lib/formato.ts     # formatação brasileira de números, meses, datas e tamanhos
│   ├── components/        # Shell, Cabecalho, Dialogo, ConfirmarDialogo, MensagemErro, Icone, …
│   └── pages/             # uma pasta por tela: contratos, contrato, catalogo, indices, upload, sistema
├── tests/                 # Vitest + Testing Library + MSW
└── e2e/                   # Playwright contra o FastAPI real
```

Componentes de tela exportam função nomeada (`export function PaginaUpload()`),
nunca `default`.

## Rotas

| Rota | Tela |
|---|---|
| `/`, `/contratos` | Lista de contratos com a situação |
| `/contratos/:id/{cadastro,medicoes,calculo}` | Página do contrato, uma aba por rota; `calculo` aceita `?regiao_cap=&regiao_emulsoes=` (simulação) |
| `/upload` | Envio de PDFs e acompanhamento do lote |
| `/catalogo` | Produtos e códigos; `?produto=<id>` seleciona, `?q=<código>` abre *Adicionar códigos* já buscando |
| `/indices/anp`, `/indices/igp-di` | Grades de índices, importação e exportação |
| `/sistema/templates`, `/sistema/backups` | Templates e backups |

`/contratos/:id` sozinho não bate com nenhuma sub-rota: um `useEffect` em
`PaginaContrato.tsx` redireciona para `cadastro` assim que a página monta, sem
esperar o contrato carregar.

O que a tela mostra de estado compartilhável (simulação, produto selecionado,
busca) fica na **URL**, não em estado local: recarregar ou mandar o link
reproduz a tela.

`GET /upload` é a tela e `POST /upload` é o envio: o `app/spa.py` só atende GET,
e o proxy do Vite desvia para `index.html` o GET que pede `text/html`.

## Camada de API

- `api/client.ts` — `pedir<T>(caminho, { metodo, params, json, form, sinal })` é
  a única função que faz `fetch`. `montarUrl` descarta parâmetros `undefined`,
  `null` e `''`; `false` vai como `"false"`. `caminhoCom(caminho, params)` monta
  os links de download (`href`), que não passam por `fetch`.
- `api/erros.ts` — toda resposta não-2xx vira `ErroApi(status, detail, { campos,
  faltando, erros })`, normalizando os **dois formatos de 422** descritos em
  `backend.md`: o do Pydantic (lista em `detail`, vira `campos`) e o do `ErroApi`
  do backend (texto em `detail`, com `faltando` ou `erros`). Falha de rede vira
  `ErroConexao`, que o `BannerConexao` mostra uma vez para a aplicação inteira.
- `api/tipos.ts` — os tipos das respostas. **`Decimal` é `string`**: o valor
  chega como veio do `NUMERIC` e nunca vira `number`.
- `api/chaves.ts` — todas as chaves do TanStack Query, num lugar só.
- `api/invalidar.ts` — o que cada gravação invalida (`aposCadastro`,
  `aposCatalogo`, `aposIndices`, `aposUpload`). Gravar nunca atualiza o cache à
  mão: invalida e a tela relê do banco. Restaurar um backup invalida **tudo**.

## Regras de tela

- **O frontend nunca calcula.** ΔP, subtotais, total, situação do contrato: tudo
  vem do backend. `lib/formato.ts` só formata — `numero(v, casas)`, `exato(v)`
  (mantém as casas do banco), `mesAno` (`jan/2023`), `data` (`15/01/2022`),
  `semana`, `dataHora` (fuso `America/Sao_Paulo`), `tamanho` — e `paraDecimal`
  converte a digitação brasileira (`1.234,56`) no texto que a API espera.
  Mês e data da API nunca passam por `new Date()`; só `dataHora` usa `Date`.
- **Mensagens de negócio são as do backend**, mostradas como vieram por
  `MensagemErro` (o `detail` e a lista `erros`). O frontend só redige mensagens
  que o backend não tem (campo ilegível antes de enviar, arquivo que não é PDF).
- **Ações destrutivas pedem confirmação** com `ConfirmarDialogo`: excluir
  produto, apagar semana ou mês (ANP e IGP-DI, na grade ou na célula), excluir
  template ou backup. Restaurar backup exige ainda digitar o nome
  (`textoExigido`).
- **Sem emoji; sem CDN.** Ícones são Material Symbols Outlined da fonte
  auto-hospedada, via `<Icone nome="…" />` (`aria-hidden="true"`), sempre ao lado
  de um rótulo em texto.
- **Sem `style` inline.** Cores e medidas novas entram como tokens em
  `styles/tokens.css` (os mesmos nomes de `app/static/css/style.css`:
  `--surface-*`, `--text-*`, `--primary*`, `--tertiary*`, `--error*`/`--critical*`,
  `--success*`, `--border-*`, `--row-height*`, raios, espaçamentos); os
  componentes usam as classes de `componentes.css` e `telas.css` (`panel`,
  `btn btn-primary`, `badge badge-ok`, `data-table`, `field`, `notice`,
  `cartao`, `celula`, …).
- Formulários de cadastro usam react-hook-form; o erro de um campo vindo do 422
  do Pydantic aparece **no campo** (`aria-invalid`, `.erro-campo`).

## Testes

- **Vitest + Testing Library + MSW** (`npm run test`). `tests/render.tsx` tem
  `renderApp(rota, opcoesUsuario?)`, que monta a aplicação inteira numa rota com
  um `QueryClient` novo e devolve `{ usuario, qc, … }`; o elemento
  `data-testid="local"` mostra a URL atual. `tests/servidor.ts` é o servidor MSW,
  com `onUnhandledRequest: 'error'`: requisição sem handler falha o teste.
  `tests/fabricas.ts` monta respostas típicas (`umContrato`, `umaCobertura`, …).
  `tests/setup.ts` troca `File`/`Blob`/`FormData`/`fetch`/`Headers`/`Request`/
  `Response` do jsdom pelas classes de `node:buffer`/`undici` (devDependency em
  `package.json`): o `FormData` do jsdom só reconhece um arquivo se ele for
  instância do *seu* `Blob`, então sem essa troca um upload real
  (`input[type=file]` → `FormData` → `fetch`) chega ao handler do MSW
  corrompido. Um teste novo de upload já encontra isso pronto, sem precisar
  repetir o ajuste.
- **Playwright** (`npm run e2e`) roda os cenários de `e2e/` contra o FastAPI na
  porta 8765 e o banco `dnit_test`, preparado a cada execução por
  `scripts/preparar_e2e.py` (ver `deployment.md`). Os specs rodam em série e em
  ordem de arquivo.
- `uv run pytest` não depende de Node nem de `frontend/dist/`: `tests/test_spa.py`
  cria um `dist` falso.
