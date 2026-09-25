# Frontend React do reequilíbrio — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um frontend React (Vite + TypeScript) em `frontend/` que substitui toda a interface — contratos, cadastro, cálculo com simulação, medições, catálogo, índices com importação em dois passos, upload, templates e backups — consumindo `/api/v1`, `/upload`, `/jobs` e `/admin`, servido pelo próprio FastAPI a partir de `frontend/dist/`.

**Architecture:** O SPA é construído por Vite em `frontend/dist/`; um roteador catch-all do FastAPI (`app/spa.py`, registrado por último) devolve `index.html` para qualquer GET fora dos prefixos do backend. Toda leitura passa por TanStack Query com chaves fixas (`src/api/chaves.ts`) e toda gravação invalida as chaves afetadas (`src/api/invalidar.ts`). O frontend nunca calcula: `Decimal` chega como string e só é formatado com `Intl.NumberFormat('pt-BR')`, que formata strings decimais exatamente.

**Tech Stack:** Node 24 / npm 11, Vite, React 19, TypeScript, react-router 7, @tanstack/react-query 5, react-hook-form 7; Vitest + jsdom + Testing Library + MSW 2; Playwright. Backend: FastAPI + psycopg 3 (existente).

**Spec:** `docs/superpowers/specs/2026-09-24-frontend-react-design.md`

## Global Constraints

- Documentação, textos da interface e mensagens de commit em **português**.
- Todo commit termina com a linha `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Nunca `git add -A` nem `git add .`: sempre caminhos explícitos.
- **Sem CDN e sem emoji** na interface; ícones Material Symbols Outlined (fonte auto-hospedada), sempre acompanhados de rótulo em texto e com `aria-hidden="true"`.
- Cores e tamanhos novos entram como tokens em `frontend/src/styles/tokens.css`, nunca inline; prefira classe a `style`.
- O frontend **nunca calcula** valores do reequilíbrio: `Decimal` chega como string e só é formatado (padrão brasileiro). Mês `jan/2023`, data `15/01/2022`; entrada numérica aceita vírgula decimal.
- Mensagens de regra de negócio são as do backend, exibidas como vieram; o frontend não as reescreve.
- Ações destrutivas (excluir produto, apagar semana/mês, restaurar backup, excluir template/backup) pedem confirmação.
- `uv run pytest` continua funcionando **sem Node** e sem `frontend/dist/`.
- Não usar `Reequilíbrio - 26 - Contrato 716-22.xlsx` em seed, fixture ou teste; os testes usam só `tests/fixtures/`.
- Postgres de teste: `docker compose up -d postgres` (porta 5433, banco `dnit_test`). O e2e do Playwright e o pytest usam o mesmo `dnit_test`: **não rodar os dois ao mesmo tempo**.
- README e regras (`.claude/rules/*.md`) atualizados na mesma entrega (Tarefa 14), conforme `.claude/rules/documentation.md`.
- A porta 8000 pode estar ocupada na máquina de desenvolvimento; `VITE_BACKEND_URL` aponta o proxy do Vite para outra (ex.: `http://localhost:8001`).

## Mapa de arquivos

```
app/spa.py                                  # novo: serve frontend/dist (Tarefa 2)
app/main.py                                 # inclui spa.router por último (Tarefa 2)
app/routers/upload.py                       # remove GET / (Tarefa 2)
app/routers/jobs.py                         # contrato_id/itens no status (Tarefa 3)
app/routers/api/{contratos,catalogo,indices,calculo,schemas}.py   # endpoints novos (Tarefa 3)
app/services/{medicoes_repo,catalogo,indices_repo,file_processor,job_manager}.py  # (Tarefa 3)
migrations/007_file_results_contrato.sql    # novo (Tarefa 3)
scripts/preparar_e2e.py                     # novo (Tarefa 13)
tests/test_spa.py                           # novo; substitui tests/test_index.py (Tarefa 2)
tests/test_api_medicoes.py, tests/test_api_adicoes_frontend.py   # novos (Tarefa 3)
Dockerfile, .dockerignore, .gitignore       # (Tarefas 1 e 2)
frontend/
├── package.json, package-lock.json, tsconfig.json, vite.config.ts, playwright.config.ts, index.html
├── public/                  # favicons, site.webmanifest, logo.svg
├── src/
│   ├── main.tsx, App.tsx
│   ├── styles/              # fontes.css, tokens.css, casca.css, componentes.css, upload.css, telas.css, index.css
│   ├── fonts/               # *.woff2 copiados de app/static/fonts
│   ├── api/                 # client, erros, conexao, queryClient, tipos, chaves, invalidar, contratos, catalogo, indices, jobs, sistema
│   ├── lib/formato.ts
│   ├── components/          # Shell, Icone, Cabecalho, Dialogo, ConfirmarDialogo, MensagemErro, BannerConexao, NaoEncontrado, Carregando, CelulaEditavel
│   └── pages/
│       ├── contratos/       # ListaContratos, situacao.ts
│       ├── contrato/        # PaginaContrato, AbaCadastro, cadastro.ts, AbaCalculo, TabelaCalculo, bloqueio.ts, AbaMedicoes
│       ├── catalogo/        # PaginaCatalogo, ProdutoDialogo, AdicionarCodigos
│       ├── indices/         # PaginaIndices, FaixaCobertura, GradeAnp, GradeIgpDi, grade.ts, NovaSemana, ImportarIndices
│       ├── upload/          # PaginaUpload, AreaArquivos, TabelaLote, LotesAnteriores (acompanhamento em api/jobs.ts)
│       └── sistema/         # PaginaTemplates, PaginaBackups, EnviarArquivo
├── tests/                   # setup.ts, servidor.ts, render.tsx, fabricas.ts, *.test.ts(x)
└── e2e/                     # 01-cadastro-calculo, 02-catalogo, 03-importacao-igp (.spec.ts)
```

Convenções usadas em todas as tarefas de frontend:

- Rodar comandos npm **de dentro de `frontend/`** (`cd frontend && npm run test`), a menos que o passo diga outra coisa.
- Componentes de tela exportam uma função nomeada (`export function ListaContratos()`), nunca `default`.
- Datas/meses vindos da API são strings ISO (`2022-01-01`, `2023-01`); nunca passam por `new Date()` para formatação de mês/data (evita fuso). Só `dataHora()` usa `Date`.
- Testes de componente usam `renderApp(rota)` de `tests/render.tsx` e MSW (`servidor.use(...)`); requisição sem handler **falha o teste** (`onUnhandledRequest: 'error'`).

---
### Tarefa 1: Esqueleto do frontend — Vite, tokens, fontes e casca com menu

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/index.html`
- Create: `frontend/public/` (favicons, `site.webmanifest`, `logo.svg` — copiados)
- Create: `frontend/src/fonts/*.woff2` (copiados), `frontend/src/styles/{fontes,tokens,casca,componentes,upload,telas,index}.css`
- Create: `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/api/queryClient.ts`
- Create: `frontend/src/components/{Shell,Icone,Cabecalho,NaoEncontrado,Carregando}.tsx`
- Create: `frontend/tests/{setup.ts,servidor.ts,render.tsx,shell.test.tsx}`
- Modify: `.gitignore` (fim do arquivo)

**Interfaces:**
- Produces:
  - `AppRoutes()` (`src/App.tsx`) — todas as rotas dentro de `<Route element={<Shell />}>`; as tarefas seguintes acrescentam rotas **antes** de `path="*"`.
  - `Shell()` — casca com `<aside className="sidebar">` e `<main className="main-content"><Outlet/></main>`; `itemAtivo(prefixos: string[], pathname: string): boolean`.
  - `Icone({ nome })`, `Cabecalho({ titulo, subtitulo?, trilha?, acoes? })`, `NaoEncontrado({ mensagem? })`, `Carregando()`.
  - `criarQueryClient(): QueryClient` (`retry: false`, `refetchOnWindowFocus: false`).
  - Testes: `servidor` (MSW `setupServer()` sem handlers), `renderApp(rota: string, opcoesUsuario?) → { usuario, qc, ...render }` (`opcoesUsuario` vai para `userEvent.setup`); `screen.getByTestId('local')` mostra `pathname + search` atual.

- [ ] **Step 1: Criar `package.json` e instalar as dependências**

`frontend/package.json`:

```json
{
  "name": "dnit-reequilibrio-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "engines": { "node": ">=24" },
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "e2e": "npm run build && playwright test"
  }
}
```

Run (de dentro de `frontend/`):

```bash
npm install react react-dom react-router @tanstack/react-query react-hook-form
npm install -D vite @vitejs/plugin-react typescript @types/react @types/react-dom @types/node \
  vitest jsdom @testing-library/react @testing-library/dom @testing-library/user-event \
  @testing-library/jest-dom msw @playwright/test
```

Expected: `package-lock.json` criado, `node_modules/` presente, sem erro de peer dependency.

- [ ] **Step 2: `tsconfig.json`, `vite.config.ts` e `index.html`**

`frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2023",
    "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "resolveJsonModule": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "types": ["vite/client", "node"]
  },
  "include": ["src", "tests", "e2e", "vite.config.ts", "playwright.config.ts"]
}
```

`frontend/vite.config.ts`:

```ts
import react from '@vitejs/plugin-react'
import type { ProxyOptions } from 'vite'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'

// Prefixos que pertencem ao FastAPI. Em produção o próprio FastAPI serve o
// SPA; em desenvolvimento o Vite repassa estes caminhos para ele.
const PREFIXOS = ['/api', '/jobs', '/admin', '/reequilibrio', '/static', '/dashboard', '/docs', '/redoc', '/openapi.json']

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const alvo = env.VITE_BACKEND_URL || 'http://localhost:8000'
  const proxy: Record<string, ProxyOptions> = Object.fromEntries(
    PREFIXOS.map((prefixo) => [prefixo, { target: alvo, changeOrigin: true }]),
  )
  // GET /upload no navegador é a tela do SPA; POST /upload é o envio dos PDFs.
  proxy['/upload'] = {
    target: alvo,
    changeOrigin: true,
    bypass: (req) =>
      req.method === 'GET' && req.headers.accept?.includes('text/html') ? '/index.html' : undefined,
  }
  return {
    plugins: [react()],
    server: { port: 5173, proxy },
    test: {
      environment: 'jsdom',
      setupFiles: ['./tests/setup.ts'],
      include: ['tests/**/*.test.{ts,tsx}'],
    },
  }
})
```

`frontend/index.html`:

```html
<!doctype html>
<html lang="pt-BR" class="dark">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="icon" href="/favicon.ico" sizes="any" />
    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png" />
    <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png" />
    <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
    <link rel="manifest" href="/site.webmanifest" />
    <title>DNIT · Reequilíbrio</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 3: Copiar fontes, favicons e logo; portar os estilos**

Run (da raiz do repositório):

```bash
mkdir -p frontend/public frontend/src/fonts frontend/src/styles
cp app/static/fonts/*.woff2 frontend/src/fonts/
cp app/static/favicon.ico app/static/favicon-16x16.png app/static/favicon-32x32.png \
   app/static/apple-touch-icon.png app/static/android-chrome-192x192.png \
   app/static/android-chrome-512x512.png app/static/site.webmanifest frontend/public/
cp app/static/images/logo.svg frontend/public/logo.svg

CSS=app/static/css/style.css
DEST=frontend/src/styles
cabecalho() { printf '/* Portado de app/static/css/style.css (%s). Cores e tamanhos\n * novos vão em tokens.css, nunca inline. */\n\n' "$1"; }

{ cabecalho "fontes, linhas 17-42"; sed -n 17,42p $CSS; } > $DEST/fontes.css
{ cabecalho "tokens, reset e utilitários, linhas 44-171"; sed -n 44,171p $CSS; } > $DEST/tokens.css
{ cabecalho "casca, linhas 173-284 e 948-962; .main-content adaptado"; sed -n 173,284p $CSS; } > $DEST/casca.css
{ cabecalho "blocos, linhas 380-760, e .alert, linhas 942-946"; sed -n 380,760p $CSS; sed -n 942,946p $CSS; } > $DEST/componentes.css
{ cabecalho "upload, linhas 762-851"; sed -n 762,851p $CSS; } > $DEST/upload.css
```

Conferir que cada arquivo começa e termina numa regra completa:

```bash
for f in frontend/src/styles/*.css; do echo "== $f"; head -5 "$f" | tail -2; tail -2 "$f"; done
```

Expected: `fontes.css` termina em `}` do `@font-face` do Material Symbols; `tokens.css` termina com `.neg {…}`; `casca.css` termina com a regra `.sidebar-footer .num`; `componentes.css` termina com `.alert-secondary, .alert-dark {…}`; `upload.css` termina com `.status-message.success {…}`. Se um corte cair no meio de uma regra, ajuste as linhas pelo número exibido em `grep -n '^/\* ---' app/static/css/style.css`.

O `url('../fonts/…')` de `fontes.css` continua válido: `src/styles/` → `src/fonts/`.

Acrescentar ao fim de `casca.css` (a casca nova não tem a barra de etapas, então o `main` não reserva a altura do topo):

```css

/* Sem a barra de etapas do Jinja: o conteúdo começa logo no topo. */
.main-content {
  margin-left: var(--sidebar-width);
  padding: var(--space-lg) var(--gutter) var(--space-xl);
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
  min-width: 0;
}

@media (max-width: 1024px) {
  :root { --sidebar-width: 0px; }
  .sidebar { position: static; width: 100%; height: auto; }
  .sidebar-nav { flex-direction: row; flex-wrap: wrap; overflow: visible; }
  .main-content { margin-left: 0; }
}
```

Acrescentar ao fim de `tokens.css`:

```css

/* Tokens novos do frontend React. */
:root {
  --scrim: rgb(0 0 0 / 0.6);
  --dialog-width: 36rem;
  --cell-min-width: 7rem;
}
```

`frontend/src/styles/telas.css` (estilos novos das telas; só tokens):

```css
/* Estilos das telas React que não existiam no style.css do Jinja.
 * Só tokens de tokens.css; nada de cor ou tamanho solto. */

/* Abas com rota própria (contrato, índices). */
.tabs { display: flex; gap: var(--space-lg); border-bottom: 1px solid var(--border-subtle); }
.tab {
  padding: var(--space-sm) 0;
  margin-bottom: -1px;
  color: var(--text-secondary);
  border-bottom: 2px solid transparent;
}
.tab:hover { color: var(--text-primary); }
.tab.active { color: var(--primary); border-bottom-color: var(--primary); font-weight: 500; }

/* Avisos: .notice sem modificador já é o amarelo; .warn deixa isso explícito. */
.notice.warn { border-left-color: var(--tertiary); }
.banner-conexao { position: sticky; top: 0; z-index: 40; }

/* Barra de filtros e ações acima das tabelas. */
.barra { display: flex; flex-wrap: wrap; align-items: flex-end; gap: var(--space-md); }
.barra .espaco { flex: 1; }
.contagem { font-size: 13px; color: var(--text-secondary); }

/* Faixa de cobertura dos índices. */
.faixa {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-lg);
  padding: var(--space-sm) var(--space-md);
  background: var(--surface-container-low);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  font-size: 13px;
  color: var(--text-secondary);
}
.faixa strong { color: var(--text-primary); }

/* Células editáveis das grades de índices. */
.celula { cursor: pointer; }
.celula:hover { background: var(--surface-container-high); }
.celula.manual { box-shadow: inset 3px 0 0 var(--tertiary); }
.celula.vazia { color: var(--text-disabled); }
.celula .input { width: 100%; min-width: var(--cell-min-width); text-align: right; font-family: var(--font-data); }
.celula-erro { display: block; color: var(--error); font-size: 12px; white-space: normal; text-align: left; }
.marca-manual {
  display: inline-block;
  width: 3px;
  height: 1em;
  margin-right: var(--space-xs);
  vertical-align: middle;
  background: var(--tertiary);
}

/* Diálogo modal. */
.dialogo-fundo {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--scrim);
}
.dialogo {
  width: min(var(--dialog-width), 92vw);
  max-height: 90vh;
  overflow: auto;
  display: flex;
  flex-direction: column;
  background: var(--surface-container-low);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xl);
}
.dialogo-titulo { padding: var(--space-md); font-size: 18px; font-weight: 600; border-bottom: 1px solid var(--border-subtle); }
.dialogo-corpo { padding: var(--space-md); display: flex; flex-direction: column; gap: var(--space-md); }
.dialogo-acoes {
  padding: var(--space-md);
  display: flex;
  justify-content: flex-end;
  gap: var(--space-sm);
  border-top: 1px solid var(--border-subtle);
}

/* Catálogo: lista de produtos à esquerda, produto à direita. */
.duas-colunas { display: grid; grid-template-columns: minmax(16rem, 1fr) 3fr; gap: var(--space-lg); align-items: start; }
.lista-produtos { display: flex; flex-direction: column; gap: 2px; }

/* Importação em dois passos. */
.passos { display: flex; gap: var(--space-sm); }
.passo {
  padding: 2px var(--space-sm);
  border-radius: var(--radius-full);
  background: var(--surface-container-high);
  color: var(--text-secondary);
  font-size: 12px;
}
.passo.active { background: var(--primary-container); color: var(--on-primary-container); }
.cartoes { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-sm); }
.cartao {
  padding: var(--space-sm) var(--space-md);
  background: var(--surface-container);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  font-size: 13px;
  color: var(--text-secondary);
}
.cartao strong { display: block; font-family: var(--font-data); font-size: 22px; color: var(--text-primary); }
.cartao.warn strong { color: var(--tertiary); }

/* Mensagens de erro. */
.erro-campo { color: var(--error); font-size: 12px; }
.lista-erros { margin: var(--space-xs) 0 0 var(--space-md); padding: 0; font-size: 13px; }
.pre-linha { white-space: pre-line; }

select.input { appearance: auto; }
details.lotes > summary { cursor: pointer; color: var(--text-secondary); }

@media (max-width: 1024px) {
  .duas-colunas { grid-template-columns: 1fr; }
  .cartoes { grid-template-columns: repeat(2, 1fr); }
}
```

`frontend/src/styles/index.css`:

```css
@import './fontes.css';
@import './tokens.css';
@import './casca.css';
@import './componentes.css';
@import './upload.css';
@import './telas.css';
```

- [ ] **Step 4: Escrever o teste da casca (falha: nada existe ainda)**

`frontend/tests/servidor.ts`:

```ts
import { setupServer } from 'msw/node'

// Sem handlers globais: cada teste declara o que o backend responde, e
// qualquer requisição não declarada falha o teste (setup.ts).
export const servidor = setupServer()
```

`frontend/tests/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { servidor } from './servidor'

process.env.TZ = 'UTC'

beforeAll(() => servidor.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  servidor.resetHandlers()
})
afterAll(() => servidor.close())
```

`frontend/tests/render.tsx`:

```tsx
import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router'
import { AppRoutes } from '../src/App'
import { criarQueryClient } from '../src/api/queryClient'

function LocalAtual() {
  const local = useLocation()
  return <output data-testid="local">{local.pathname + local.search}</output>
}

// A aplicação inteira numa rota, com um QueryClient novo por teste.
export function renderApp(rota = '/', opcoesUsuario?: Parameters<typeof userEvent.setup>[0]) {
  const qc = criarQueryClient()
  const usuario = userEvent.setup(opcoesUsuario)
  const resultado = render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[rota]}>
        <AppRoutes />
        <LocalAtual />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { ...resultado, usuario, qc }
}
```

`frontend/tests/shell.test.tsx`:

```tsx
import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { itemAtivo } from '../src/components/Shell'
import { renderApp } from './render'

describe('casca', () => {
  it('mostra os itens dos três grupos do menu', () => {
    renderApp('/rota-que-nao-existe')
    for (const nome of ['Contratos', 'Upload de PDFs', 'Catálogo de produtos', 'Índices ANP / IGP-DI', 'Templates', 'Backups']) {
      expect(screen.getByRole('link', { name: nome })).toBeInTheDocument()
    }
    expect(screen.getByText('Trabalho')).toBeInTheDocument()
    expect(screen.getByText('Bases globais')).toBeInTheDocument()
    expect(screen.getByText('Sistema')).toBeInTheDocument()
  })

  it('rota desconhecida mostra "Não encontrado" dentro da casca', () => {
    renderApp('/rota-que-nao-existe')
    expect(screen.getByRole('heading', { name: 'Não encontrado' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Menu principal' })).toBeInTheDocument()
  })

  it('marca o item ativo pelo prefixo da rota', () => {
    expect(itemAtivo(['/', '/contratos'], '/')).toBe(true)
    expect(itemAtivo(['/', '/contratos'], '/contratos/12/calculo')).toBe(true)
    expect(itemAtivo(['/', '/contratos'], '/catalogo')).toBe(false)
    expect(itemAtivo(['/indices'], '/indices/igp-di')).toBe(true)
    expect(itemAtivo(['/sistema/templates'], '/sistema/backups')).toBe(false)
  })
})
```

Run: `npm run test`
Expected: FAIL — `Failed to resolve import "../src/components/Shell"`.

- [ ] **Step 5: Implementar casca, componentes base e rotas**

`frontend/src/api/queryClient.ts`:

```ts
import { QueryClient } from '@tanstack/react-query'

// Sem retentativa: erro de regra (4xx) não muda repetindo, e falta de conexão
// vira o aviso fixo com "Tentar de novo" (BannerConexao).
export function criarQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false, staleTime: 30_000 },
      mutations: { retry: false },
    },
  })
}
```

`frontend/src/components/Icone.tsx`:

```tsx
// Material Symbols é decorativo: o texto ao lado é o rótulo acessível.
export function Icone({ nome }: { nome: string }) {
  return (
    <span className="material-symbols-outlined" aria-hidden="true">
      {nome}
    </span>
  )
}
```

`frontend/src/components/Cabecalho.tsx`:

```tsx
import type { ReactNode } from 'react'

interface Props {
  titulo: ReactNode
  subtitulo?: ReactNode
  trilha?: ReactNode
  acoes?: ReactNode
}

export function Cabecalho({ titulo, subtitulo, trilha, acoes }: Props) {
  return (
    <div className="page-head">
      <div>
        {trilha && <div className="page-crumb">{trilha}</div>}
        <h1 className="page-title">{titulo}</h1>
        {subtitulo && <p className="page-subtitle">{subtitulo}</p>}
      </div>
      {acoes && <div className="page-actions">{acoes}</div>}
    </div>
  )
}
```

`frontend/src/components/NaoEncontrado.tsx`:

```tsx
import { Link } from 'react-router'
import { Cabecalho } from './Cabecalho'

export function NaoEncontrado({ mensagem = 'A página pedida não existe.' }: { mensagem?: string }) {
  return (
    <>
      <Cabecalho titulo="Não encontrado" />
      <div className="panel">
        <div className="empty-state">
          <p>{mensagem}</p>
          <p className="mt-md">
            <Link to="/contratos" className="btn btn-sm">
              Voltar aos contratos
            </Link>
          </p>
        </div>
      </div>
    </>
  )
}
```

`frontend/src/components/Carregando.tsx`:

```tsx
export function Carregando() {
  return (
    <p className="muted" role="status">
      Carregando…
    </p>
  )
}
```

`frontend/src/components/Shell.tsx`:

```tsx
import { Link, Outlet, useLocation } from 'react-router'
import { Icone } from './Icone'

interface Item {
  para: string
  prefixos: string[]
  icone: string
  rotulo: string
}

const GRUPOS: { titulo: string; itens: Item[] }[] = [
  {
    titulo: 'Trabalho',
    itens: [
      { para: '/contratos', prefixos: ['/', '/contratos'], icone: 'description', rotulo: 'Contratos' },
      { para: '/upload', prefixos: ['/upload'], icone: 'upload_file', rotulo: 'Upload de PDFs' },
    ],
  },
  {
    titulo: 'Bases globais',
    itens: [
      { para: '/catalogo', prefixos: ['/catalogo'], icone: 'inventory_2', rotulo: 'Catálogo de produtos' },
      { para: '/indices/anp', prefixos: ['/indices'], icone: 'monitoring', rotulo: 'Índices ANP / IGP-DI' },
    ],
  },
  {
    titulo: 'Sistema',
    itens: [
      { para: '/sistema/templates', prefixos: ['/sistema/templates'], icone: 'table_view', rotulo: 'Templates' },
      { para: '/sistema/backups', prefixos: ['/sistema/backups'], icone: 'backup', rotulo: 'Backups' },
    ],
  },
]

// "/" só casa com a raiz; os demais prefixos casam com as sub-rotas.
export function itemAtivo(prefixos: string[], pathname: string): boolean {
  return prefixos.some((p) => (p === '/' ? pathname === '/' : pathname === p || pathname.startsWith(`${p}/`)))
}

export function Shell() {
  const { pathname } = useLocation()
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <img className="brand-mark" src="/logo.svg" alt="" />
          <div>
            <p className="brand-title">DNIT</p>
            <p className="brand-sub">Reequilíbrio · art. 16</p>
          </div>
        </div>
        <nav className="sidebar-nav" aria-label="Menu principal">
          {GRUPOS.map((grupo) => (
            <div className="nav-group" key={grupo.titulo}>
              <p className="nav-group-title">{grupo.titulo}</p>
              {grupo.itens.map((item) => {
                const ativo = itemAtivo(item.prefixos, pathname)
                return (
                  <Link
                    key={item.para}
                    to={item.para}
                    className={ativo ? 'nav-item active' : 'nav-item'}
                    aria-current={ativo ? 'page' : undefined}
                  >
                    <Icone nome={item.icone} />
                    <span>{item.rotulo}</span>
                  </Link>
                )
              })}
            </div>
          ))}
        </nav>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
```

`frontend/src/App.tsx`:

```tsx
import { Route, Routes } from 'react-router'
import { NaoEncontrado } from './components/NaoEncontrado'
import { Shell } from './components/Shell'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route path="*" element={<NaoEncontrado />} />
      </Route>
    </Routes>
  )
}
```

`frontend/src/main.tsx`:

```tsx
import { QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { AppRoutes } from './App'
import { criarQueryClient } from './api/queryClient'
import './styles/index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={criarQueryClient()}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
```

- [ ] **Step 6: Rodar os testes e o build**

Run: `npm run test`
Expected: PASS — 3 testes em `tests/shell.test.tsx`.

Run: `npm run build`
Expected: `tsc` sem erros; `dist/index.html`, `dist/assets/*.js`, `dist/assets/*.css`, os três `.woff2` em `dist/assets/` e os favicons na raiz de `dist/`.

Run: `grep -c "fonts.googleapis\|cdn" dist/index.html dist/assets/*.css`
Expected: `0` em todos (sem CDN).

- [ ] **Step 7: `.gitignore`**

Acrescentar ao **fim** de `.gitignore` (a negação precisa vir depois das regras `lib/` e `[Ll]ib`, que ignorariam `frontend/src/lib/`):

```gitignore

# Frontend React
node_modules/
frontend/test-results/
frontend/playwright-report/
# As regras "lib/" e "[Ll]ib" acima são de pacotes Python; esta pasta é código-fonte.
!/frontend/src/lib/

# Rascunhos das skills (brainstorm, planos em execução)
.superpowers/
```

`frontend/dist/` já é coberto pela regra `dist/`.

Run: `git status --short frontend | head -20 && git check-ignore -v frontend/dist frontend/node_modules`
Expected: `frontend/dist` e `frontend/node_modules` aparecem como ignorados; `frontend/src/...` e `frontend/package-lock.json` aparecem como não rastreados.

- [ ] **Step 8: Commit**

```bash
git add .gitignore frontend/package.json frontend/package-lock.json frontend/tsconfig.json \
  frontend/vite.config.ts frontend/index.html frontend/public frontend/src frontend/tests
git commit -m "$(cat <<'EOF'
feat(frontend): esqueleto React com tokens, fontes e casca com menu

Vite + React 19 + TypeScript em frontend/, estilos portados do style.css
(tokens, casca, componentes, upload) e fontes auto-hospedadas. Vitest com
MSW falhando em requisição não declarada.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarefa 2: FastAPI serve o SPA; estágio Node no Dockerfile

**Files:**
- Create: `app/spa.py`
- Modify: `app/main.py` (incluir `spa.router` por último)
- Modify: `app/routers/upload.py` (remover `GET /`, `templates`, `progresso`)
- Create: `tests/test_spa.py`
- Delete: `tests/test_index.py`
- Modify: `Dockerfile`, `.dockerignore`

**Interfaces:**
- Consumes: `frontend/dist/` gerado por `npm run build` (Tarefa 1) — só em produção; os testes criam um `dist` falso.
- Produces: `app.spa.DIST: Path` (lido a cada requisição, os testes o trocam com `monkeypatch`), `app.spa.RESERVADOS: frozenset[str]`, `app.spa.router`.

- [ ] **Step 1: Escrever os testes do SPA**

`tests/test_spa.py`:

```python
"""O FastAPI serve o build do frontend sem capturar as rotas do backend."""

import pytest

from app import spa

INDEX = "<!doctype html><div id=root></div><!-- spa -->"


@pytest.fixture
def dist(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text(INDEX, encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    monkeypatch.setattr(spa, "DIST", tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    "rota", ["/", "/contratos", "/contratos/12", "/contratos/12/calculo", "/upload", "/indices/anp"]
)
async def test_rotas_do_spa_devolvem_o_index(client, dist, rota):
    resposta = await client.get(rota)
    assert resposta.status_code == 200
    assert "<!-- spa -->" in resposta.text
    assert resposta.headers["cache-control"] == "no-cache"


async def test_arquivo_do_build_e_servido_como_esta(client, dist):
    resposta = await client.get("/assets/app.js")
    assert resposta.status_code == 200
    assert resposta.text == "console.log('ok')"


async def test_caminho_para_fora_do_dist_cai_no_index(client, dist):
    resposta = await client.get("/assets/..%2F..%2Fpyproject.toml")
    assert resposta.status_code == 200
    assert "<!-- spa -->" in resposta.text


@pytest.mark.parametrize(
    "rota",
    ["/api/v1/nao-existe", "/jobs/a/b/c/d", "/admin/nada", "/reequilibrio/nada", "/static/nada.css"],
)
async def test_prefixos_do_backend_nao_sao_capturados(client, dist, rota):
    resposta = await client.get(rota)
    assert resposta.status_code == 404
    assert "<!-- spa -->" not in resposta.text


async def test_backend_continua_respondendo(client, dist):
    assert (await client.get("/api/v1/contratos")).json() == []
    assert (await client.get("/jobs?status=active")).status_code == 200
    assert (await client.get("/openapi.json")).status_code == 200
    assert (await client.get("/docs")).status_code == 200
    # POST /upload continua sendo o envio: sem arquivos, a validação recusa.
    assert (await client.post("/upload")).status_code == 422


async def test_rota_do_spa_fica_fora_do_openapi(client, dist):
    caminhos = (await client.get("/openapi.json")).json()["paths"]
    assert not any("caminho" in c for c in caminhos)


async def test_sem_build_mostra_como_gerar(client, tmp_path, monkeypatch):
    monkeypatch.setattr(spa, "DIST", tmp_path / "nao-existe")
    resposta = await client.get("/contratos/12")
    assert resposta.status_code == 200
    assert "npm run build" in resposta.text
```

Run: `uv run pytest tests/test_spa.py -q`
Expected: FAIL — `ImportError: cannot import name 'spa' from 'app'`.

- [ ] **Step 2: Implementar `app/spa.py`**

```python
"""Serve o frontend React construído em ``frontend/dist``.

Qualquer GET que nenhuma rota do backend atendeu chega aqui: um arquivo real do
build é devolvido como está, e o resto recebe ``index.html`` para o roteador do
React decidir a tela. Os prefixos do backend nunca caem no SPA — um caminho
errado em ``/api`` tem de ser 404, não uma página HTML.

Sem ``dist/`` (checkout novo, suíte de testes), ``/`` responde uma página que
explica como gerar o build: o backend não depende de Node para subir.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

RESERVADOS = frozenset(
    {"api", "jobs", "admin", "reequilibrio", "static", "dashboard", "docs", "redoc", "openapi.json"}
)

SEM_BUILD = """<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>DNIT · frontend não construído</title></head>
<body>
<h1>Frontend não construído</h1>
<p>Gere o build do frontend e recarregue a página:</p>
<pre>cd frontend
npm ci
npm run build</pre>
<p>A API continua disponível em <a href="/docs">/docs</a>.</p>
</body>
</html>
"""

router = APIRouter(include_in_schema=False)


@router.get("/{caminho:path}")
async def spa(caminho: str):
    if caminho.split("/", 1)[0] in RESERVADOS:
        raise HTTPException(404)
    dist = DIST.resolve()
    indice = dist / "index.html"
    if not indice.is_file():
        return HTMLResponse(SEM_BUILD)
    if caminho:
        alvo = (dist / caminho).resolve()
        if alvo.is_relative_to(dist) and alvo.is_file():
            return FileResponse(alvo)
    # index.html não pode ficar em cache: é ele que aponta para os assets com
    # hash do build atual.
    return FileResponse(indice, headers={"Cache-Control": "no-cache"})
```

- [ ] **Step 3: Registrar por último em `app/main.py` e tirar `GET /` do upload**

Em `app/main.py`, trocar o bloco de imports de routers e o fim do arquivo:

```python
from . import spa
from .routers import admin
```

```python
app.mount("/dashboard", create_dash_app())

# Por último: o catch-all do SPA só recebe o que nenhuma rota acima atendeu.
app.include_router(spa.router)
```

Em `app/routers/upload.py`, remover a função `index` inteira (o decorator `@router.get("/", include_in_schema=False)` e o corpo), a linha `templates = Jinja2Templates(...)` e os imports que ficam sem uso: `from fastapi.templating import Jinja2Templates`, `from pathlib import Path` e `from ..services import progresso`. O topo fica:

```python
import asyncio
from typing import List

from fastapi import APIRouter, File, Request, UploadFile

from ..models.job import FileStatus
from ..services.file_processor import classify_file, process_ocr_pdf, process_text_pdf
from ..services.job_manager import (
    create_job,
    check_job_completed,
    mark_job_completed,
    notify_change,
    update_file_status,
)
from ..services.storage import save_upload

router = APIRouter()
```

Remover `tests/test_index.py` (testava a página Jinja que deixou de ser servida; `tests/test_spa.py` cobre `/`):

```bash
git rm tests/test_index.py
```

- [ ] **Step 4: Rodar os testes**

Run: `uv run pytest tests/test_spa.py -q`
Expected: PASS (17 testes, contando os parametrizados).

Run: `uv run pytest -q`
Expected: PASS em toda a suíte. Se algum teste ainda fizer `GET /` esperando o HTML do Jinja (`grep -rn 'get("/")' tests`), ele pertence à página removida: apague-o e registre no commit.

- [ ] **Step 5: Dockerfile e `.dockerignore`**

No topo do `Dockerfile`, antes de `FROM python:3.12-slim`:

```dockerfile
# Estágio 1: o build do frontend React. Só frontend/dist vai para a imagem
# final; Node não é dependência de execução.
FROM node:24-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

```

Depois de `COPY . .`:

```dockerfile
# O SPA construído no estágio 1 (app/spa.py serve frontend/dist).
COPY --from=frontend /frontend/dist ./frontend/dist
```

Acrescentar ao fim de `.dockerignore` (os padrões do `.dockerignore` são relativos à raiz: `dist/` lá em cima não cobre `frontend/dist`):

```
# Frontend: dependências e build locais; a imagem gera os seus
frontend/node_modules/
frontend/dist/
frontend/test-results/
frontend/playwright-report/
```

Run: `docker build -t dnit-spa-teste .`
Expected: os dois estágios concluem; `docker run --rm dnit-spa-teste ls frontend/dist` lista `index.html` e `assets`. Sem Docker disponível na máquina, registrar no relatório que este passo não foi executado.

- [ ] **Step 6: Commit**

```bash
git add app/spa.py app/main.py app/routers/upload.py tests/test_spa.py Dockerfile .dockerignore
git commit -m "$(cat <<'EOF'
feat: FastAPI serve o build do frontend React

app/spa.py devolve index.html para qualquer GET fora dos prefixos do backend
e os arquivos reais de frontend/dist; sem build, uma página explica como
gerá-lo. GET / do Jinja sai (o SPA assume /), POST /upload continua. O
Dockerfile ganha o estágio node:24 que roda npm ci e npm run build.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarefa 3: Adições no backend para o frontend

**Files:**
- Create: `migrations/007_file_results_contrato.sql`
- Modify: `app/services/medicoes_repo.py` (nova `listar_itens`)
- Modify: `app/services/catalogo.py` (`buscar_codigos` ganha `produto_id`; nova `associar_codigos`)
- Modify: `app/services/indices_repo.py` (`cobertura` com `manuais`; nova `produtos_anp`)
- Modify: `app/services/job_manager.py` (nova `vincular_contrato`; `reset_file_for_retry` limpa os campos novos)
- Modify: `app/services/file_processor.py` (`_persistir` vincula o contrato ao arquivo)
- Modify: `app/routers/jobs.py` (`_job_status_dict` com `contrato_id` e `itens`)
- Modify: `app/routers/api/schemas.py`, `contratos.py`, `catalogo.py`, `indices.py`, `calculo.py`
- Create: `tests/test_api_medicoes.py`, `tests/test_api_adicoes_frontend.py`

**Interfaces:**
- Produces (HTTP, consumido pelas Tarefas 5–11):
  - `GET /api/v1/contratos/{id}/medicoes?mes=AAAA-MM&no_calculo=true|false&q=` → `ItemMedicao[]`:
    `{id, mes: "AAAA-MM-01", codigo, descricao_pdf|null, valor_pi, fator, reajuste, arquivo, produto_id|null, produto|null, familia|null}`
    (decimais como string; `reajuste = trunc(valor_pi·fator, 2)`, a mesma regra da coluna F da planilha). 404 `"Contrato N não encontrado."`, 422 mês fora do padrão.
  - `GET /api/v1/codigos?produto_id=N` — filtro novo, combinável com `q`/`associado`.
  - `PUT /api/v1/produtos/{id}/codigos` `{"codigos": ["60112", …]}` → `Produto` (com `codigos` atualizado); 404 `"Produto N não encontrado."` sem gravar nada.
  - `GET /api/v1/indices/anp/produtos` → `string[]` (produtos com semana gravada, em ordem alfabética).
  - `GET /api/v1/indices/cobertura` → `anp` e `igp_di` ganham `manuais: int`.
  - `GET /api/v1/contratos/{id}/calculo` → ganha `arquivo: string` (o mesmo nome do `Content-Disposition` da planilha).
  - `GET /jobs/{id}/status` → cada arquivo ganha `contrato_id: int|null` e `itens: int|null`.
- Produces (Python): `medicoes_repo.listar_itens(contrato_id, *, mes=None, no_calculo=None, q=None) -> list[dict]`; `catalogo.associar_codigos(produto_id, codigos) -> bool`; `indices_repo.produtos_anp() -> list[str]`; `job_manager.vincular_contrato(job_id, filename, contrato_id, itens) -> None` (síncrona).

- [ ] **Step 1: Testes das medições do contrato**

`tests/test_api_medicoes.py`:

```python
"""Itens extraídos de um contrato, com o produto do catálogo (ou nenhum)."""

from app.services import catalogo, contratos_repo, medicoes_repo

HEADER = {"Contrato": "15 00716/2022 - HWN ENGENHARIA LTDA", "Data Base": "01/01/2022"}
FEV = "01/02/2023 - 28/02/2023"
MAR = "01/03/2023 - 31/03/2023"


def _item(codigo, descricao, valor, fator, periodo, arquivo="1ª MP.pdf") -> dict:
    return {"Serviço": codigo, "Descrição": descricao, "Valor a PI Líquido": valor,
            "Fator": fator, "Período Líquido": periodo, "Source_File": arquivo}


def _contrato() -> int:
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(
        contrato_id,
        [
            _item("60112", "Fornecimento de CAP 50/70", 412300.0, 0.148, FEV),
            _item("40210", "Escavação de material de 1ª categoria", 10.0, 0.12399, FEV),
            _item("60112", "Fornecimento de CAP 50/70", 100.0, -0.1839, MAR, "2ª MP.pdf"),
        ],
    )
    produto_id = catalogo.novo_produto("Aquisição de CAP 50/70", "CAP")
    catalogo.registrar_codigo("60112", produto_id)
    return contrato_id


async def _medicoes(client, contrato_id, **params):
    resposta = await client.get(f"/api/v1/contratos/{contrato_id}/medicoes", params=params)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


async def test_lista_itens_com_produto_e_reajuste_truncado(client):
    contrato_id = _contrato()
    itens = await _medicoes(client, contrato_id)
    assert [(i["mes"], i["codigo"]) for i in itens] == [
        ("2023-02-01", "40210"), ("2023-02-01", "60112"), ("2023-03-01", "60112"),
    ]
    escavacao, cap_fev, cap_mar = itens
    assert cap_fev["produto"] == "Aquisição de CAP 50/70" and cap_fev["familia"] == "CAP"
    assert cap_fev["valor_pi"] == "412300.00" and cap_fev["reajuste"] == "61020.40"
    assert cap_fev["arquivo"] == "1ª MP.pdf"
    # 10 · 0,12399 = 1,2399 → 1,23: trunca, não arredonda (coluna F da planilha).
    assert escavacao["reajuste"] == "1.23"
    assert escavacao["produto_id"] is None and escavacao["produto"] is None
    assert escavacao["familia"] is None
    assert cap_mar["reajuste"] == "-18.39" and cap_mar["arquivo"] == "2ª MP.pdf"


async def test_filtros_de_mes_calculo_e_busca(client):
    contrato_id = _contrato()
    assert [i["codigo"] for i in await _medicoes(client, contrato_id, mes="2023-03")] == ["60112"]
    no_calculo = await _medicoes(client, contrato_id, no_calculo="true")
    assert {i["codigo"] for i in no_calculo} == {"60112"} and len(no_calculo) == 2
    assert [i["codigo"] for i in await _medicoes(client, contrato_id, no_calculo="false")] == ["40210"]
    assert [i["codigo"] for i in await _medicoes(client, contrato_id, q="escava")] == ["40210"]
    assert len(await _medicoes(client, contrato_id, q="601")) == 2
    assert await _medicoes(client, contrato_id, mes="2023-03", no_calculo="false") == []


async def test_mes_invalido_e_contrato_inexistente(client):
    contrato_id = _contrato()
    resposta = await client.get(f"/api/v1/contratos/{contrato_id}/medicoes", params={"mes": "2023-13"})
    assert resposta.status_code == 422
    assert isinstance(resposta.json()["detail"], list)
    resposta = await client.get("/api/v1/contratos/999/medicoes")
    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "Contrato 999 não encontrado."
```

Run: `uv run pytest tests/test_api_medicoes.py -q`
Expected: FAIL — 404 `Not Found` nas três (a rota não existe).

- [ ] **Step 2: Implementar `listar_itens` e a rota**

Acrescentar a `app/services/medicoes_repo.py`, depois de `itens_para_export`, e o import no topo (`from datetime import date` e `from .catalogo import _padrao_ilike` — `catalogo` só importa `psycopg`, `db` e `delta_p`, então não há ciclo):

```python
def listar_itens(
    contrato_id: int,
    *,
    mes: date | None = None,
    no_calculo: bool | None = None,
    q: str | None = None,
) -> list[dict]:
    """Every extracted item of a contract, with its catalogue product or None.

    The read-only view of the measurements: unlike ``itens_para_export`` it keeps
    the codes without a product, which is how the user finds what to associate.
    ``reajuste`` truncates like column F of the spreadsheet.
    """
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT m.id, m.mes_medicao AS mes, m.codigo_servico AS codigo, "
            "       m.descricao_pdf, m.valor_pi, m.fator, "
            "       trunc(m.valor_pi * m.fator, 2) AS reajuste, "
            "       m.source_file AS arquivo, p.id AS produto_id, "
            "       p.descricao_export AS produto, p.familia "
            "FROM medicao_item m "
            "LEFT JOIN produto_codigo pc ON pc.codigo_servico = m.codigo_servico "
            "LEFT JOIN produto p ON p.id = pc.produto_id "
            "WHERE m.contrato_id = %(contrato)s "
            "  AND (%(mes)s::date IS NULL OR m.mes_medicao = %(mes)s) "
            "  AND (%(no_calculo)s::boolean IS NULL "
            "       OR (p.id IS NOT NULL) = %(no_calculo)s) "
            "  AND (%(padrao)s::text IS NULL "
            "       OR m.codigo_servico ILIKE %(padrao)s "
            "       OR m.descricao_pdf ILIKE %(padrao)s) "
            "ORDER BY m.mes_medicao, m.codigo_servico, m.id",
            {"contrato": contrato_id, "mes": mes, "no_calculo": no_calculo,
             "padrao": _padrao_ilike(q)},
        )
        return [dict(r) for r in cur.fetchall()]
```

Em `app/routers/api/schemas.py`, depois de `class Codigo`:

```python
class ItemMedicao(BaseModel):
    id: int
    mes: date
    codigo: str
    descricao_pdf: str | None
    valor_pi: Decimal
    fator: Decimal
    reajuste: Decimal
    arquivo: str
    produto_id: int | None
    produto: str | None
    familia: Familia | None
```

Em `app/routers/api/contratos.py`, imports e rota nova (depois de `detalhar`):

```python
import asyncio
from datetime import date

from fastapi import APIRouter, Query

from ...services import contratos_repo, medicoes_repo
from .erros import ErroApi
from .indices import MES
from .schemas import Contrato, ContratoPatch, ContratoResumo, ItemMedicao
```

```python
def _medicoes(contrato_id: int, mes: str | None, no_calculo: bool | None, q: str | None) -> list[dict]:
    if contratos_repo.buscar_por_id(contrato_id) is None:
        raise ErroApi(404, f"Contrato {contrato_id} não encontrado.")
    mes_ref = date(int(mes[:4]), int(mes[5:7]), 1) if mes else None
    return medicoes_repo.listar_itens(contrato_id, mes=mes_ref, no_calculo=no_calculo, q=q)


@router.get("/{contrato_id}/medicoes", response_model=list[ItemMedicao])
async def medicoes(
    contrato_id: int,
    mes: str | None = Query(None, pattern=MES, description="AAAA-MM"),
    no_calculo: bool | None = Query(None, description="Só itens com produto (true) ou sem (false)"),
    q: str | None = Query(None, description="Trecho do código ou da descrição"),
):
    return await asyncio.to_thread(_medicoes, contrato_id, mes, no_calculo, q)
```

Run: `uv run pytest tests/test_api_medicoes.py -q`
Expected: PASS (3 testes).

- [ ] **Step 3: Testes das demais adições**

`tests/test_api_adicoes_frontend.py`:

```python
"""Pequenas adições da API pedidas pelo frontend React."""

import asyncio
from datetime import date

from app.models.job import FileStatus
from app.routers.api.calculo import nome_do_arquivo
from app.services import catalogo, contratos_repo, file_processor, indices_repo, job_manager, medicoes_repo
from app.services.delta_p import ANP_PRODUTO_CAP

from .indices_factory import mes_igp, semana
from .test_api_calculo import _contrato as contrato_calculavel

HEADER = {"Contrato": "15 00716/2022 - HWN ENGENHARIA LTDA", "Data Base": "01/01/2022"}
DIESEL = "Óleo Diesel (R$/l)"


def _extrair(*codigos: str) -> int:
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    medicoes_repo.gravar_itens(
        contrato_id,
        [{"Serviço": c, "Descrição": f"Item {c}", "Valor a PI Líquido": 10.0, "Fator": 0.1,
          "Período Líquido": "01/02/2023 - 28/02/2023", "Source_File": "1ª MP.pdf"}
         for c in codigos],
    )
    return contrato_id


# ── Catálogo ────────────────────────────────────────────────────────────────


async def test_codigos_filtrados_por_produto(client):
    _extrair("60112", "60113", "40210")
    cap = catalogo.novo_produto("CAP 50/70", "CAP")
    emul = catalogo.novo_produto("Emulsão RR-1C", "EMULSOES")
    catalogo.registrar_codigo("60112", cap)
    catalogo.registrar_codigo("60113", emul)
    resposta = await client.get("/api/v1/codigos", params={"produto_id": cap})
    assert [c["codigo"] for c in resposta.json()] == ["60112"]
    resposta = await client.get("/api/v1/codigos", params={"produto_id": cap, "q": "40210"})
    assert resposta.json() == []


async def test_associar_codigos_em_lote(client):
    _extrair("60112", "60113", "40210")
    cap = catalogo.novo_produto("CAP 50/70", "CAP")
    emul = catalogo.novo_produto("Emulsão RR-1C", "EMULSOES")
    catalogo.registrar_codigo("60113", emul)

    resposta = await client.put(
        f"/api/v1/produtos/{cap}/codigos",
        # 60113 muda de produto, 99999 ainda não foi extraído, 60112 repetido.
        json={"codigos": ["60112", "60113", "99999", "60112"]},
    )
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["id"] == cap and resposta.json()["codigos"] == 3
    assert catalogo.buscar_produto(emul)["codigos"] == 0
    codigos = await client.get("/api/v1/codigos", params={"produto_id": cap})
    assert [c["codigo"] for c in codigos.json()] == ["60112", "60113", "99999"]


async def test_associar_em_lote_produto_inexistente_nao_grava(client):
    _extrair("60112")
    resposta = await client.put("/api/v1/produtos/999/codigos", json={"codigos": ["60112"]})
    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "Produto 999 não encontrado."
    assert catalogo.buscar_por_codigo("60112") is None


async def test_associar_em_lote_valida_o_corpo(client):
    cap = catalogo.novo_produto("CAP 50/70", "CAP")
    for corpo in ({"codigos": []}, {"codigos": ["12"]}, {"codigos": ["60112"], "extra": 1}):
        resposta = await client.put(f"/api/v1/produtos/{cap}/codigos", json=corpo)
        assert resposta.status_code == 422, corpo
        assert isinstance(resposta.json()["detail"], list)


# ── Índices ─────────────────────────────────────────────────────────────────


async def test_produtos_anp(client):
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.2")])
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "6.1", produto=DIESEL)])
    resposta = await client.get("/api/v1/indices/anp/produtos")
    assert resposta.status_code == 200
    assert resposta.json() == [ANP_PRODUTO_CAP, DIESEL]


async def test_cobertura_conta_os_valores_manuais(client):
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 2), "3.1")], origem="seed")
    indices_repo.gravar_indices_mensais([mes_igp(date(2022, 12, 1), "1100.5")], origem="seed")
    resposta = await client.put(
        "/api/v1/indices/anp",
        json={"vigencia_inicio": "2023-01-09", "vigencia_fim": "2023-01-15",
              "regiao": "Nordeste", "preco": "3.2"},
    )
    assert resposta.status_code == 200, resposta.text
    resposta = await client.put("/api/v1/indices/igp-di/2023-01", json={"valor": "1110.4"})
    assert resposta.status_code == 200, resposta.text

    corpo = (await client.get("/api/v1/indices/cobertura")).json()
    assert corpo["anp"]["registros"] == 2 and corpo["anp"]["manuais"] == 1
    assert corpo["igp_di"]["registros"] == 2 and corpo["igp_di"]["manuais"] == 1


# ── Cálculo ─────────────────────────────────────────────────────────────────


async def test_calculo_informa_o_nome_do_arquivo(client):
    contrato_id = contrato_calculavel()
    url = f"/api/v1/contratos/{contrato_id}"
    corpo = (await client.get(f"{url}/calculo")).json()
    assert corpo["arquivo"] == "Reequilibrio_15-00716-2022.xlsx"

    params = {"regiao_cap": "Sul"}
    corpo = (await client.get(f"{url}/calculo", params=params)).json()
    assert corpo["arquivo"] == nome_do_arquivo("15 00716/2022", {"CAP": "Sul"})
    planilha = await client.get(f"{url}/planilha", params=params)
    assert corpo["arquivo"] in planilha.headers["content-disposition"]


# ── Jobs ────────────────────────────────────────────────────────────────────

RESULTADO = {
    "header": HEADER,
    "rows": [{"Serviço": "60112", "Descrição": "CAP", "Valor a PI Líquido": "10,00",
              "Fator": "0,1", "Período Líquido": "01/02/2023 - 28/02/2023",
              "Source_File": "a.pdf"},
             {"Serviço": "60113", "Descrição": "Emulsão", "Valor a PI Líquido": "5,00",
              "Fator": "0,1", "Período Líquido": "01/02/2023 - 28/02/2023",
              "Source_File": "a.pdf"}],
}


async def test_status_do_job_liga_o_arquivo_ao_contrato(client):
    job_id = await job_manager.create_job(["a.pdf", "b.pdf"])
    await asyncio.to_thread(file_processor._persistir, RESULTADO, "a.pdf", job_id)

    arquivos = (await client.get(f"/jobs/{job_id}/status")).json()["files"]
    contrato = contratos_repo.buscar("15 00716/2022")
    assert arquivos["a.pdf"]["contrato_id"] == contrato["id"]
    assert arquivos["a.pdf"]["itens"] == 2
    assert arquivos["b.pdf"]["contrato_id"] is None and arquivos["b.pdf"]["itens"] is None


async def test_tentar_de_novo_limpa_o_vinculo(client):
    job_id = await job_manager.create_job(["a.pdf"])
    await asyncio.to_thread(file_processor._persistir, RESULTADO, "a.pdf", job_id)
    await job_manager.update_file_status(job_id, "a.pdf", FileStatus.FAILED, error="x")
    await job_manager.reset_file_for_retry(job_id, "a.pdf")

    arquivo = (await client.get(f"/jobs/{job_id}/status")).json()["files"]["a.pdf"]
    assert arquivo["contrato_id"] is None and arquivo["itens"] is None
```

Run: `uv run pytest tests/test_api_adicoes_frontend.py -q`
Expected: FAIL — `produto_id` ignorado, 405 no `PUT /produtos/{id}/codigos`, 422 em `/indices/anp/produtos` (casado por outra rota ou 404), `KeyError: 'manuais'`, `KeyError: 'arquivo'`, `KeyError: 'contrato_id'`.

- [ ] **Step 4: Migração 007 e vínculo arquivo → contrato**

`migrations/007_file_results_contrato.sql`:

```sql
-- Qual contrato cada PDF processado alimentou e quantos itens gravou, para a
-- tela de upload mostrar "48 itens → 15 00716/2022" com link para o contrato.
-- SET NULL: excluir um contrato não apaga o histórico de processamento.
ALTER TABLE file_results
    ADD COLUMN IF NOT EXISTS contrato_id BIGINT REFERENCES contrato(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS itens INTEGER;
```

Em `app/services/job_manager.py`, trocar `from ..db import acquire` por `from ..db import acquire, acquire_sync` e acrescentar, depois de `update_file_status`:

```python
def vincular_contrato(job_id: str, filename: str, contrato_id: int, itens: int) -> None:
    """Record which contract a processed file fed and how many items it stored.

    Synchronous: it is called from ``file_processor._persistir``, which runs in
    the executor thread alongside the synchronous repositories.
    """
    with acquire_sync() as conn:
        conn.execute(
            "UPDATE file_results SET contrato_id = %s, itens = %s "
            "WHERE job_id = %s AND filename = %s",
            (contrato_id, itens, job_id, filename),
        )
```

Em `reset_file_for_retry`, a primeira instrução passa a limpar também o vínculo:

```python
            "UPDATE file_results SET status = %s, error = NULL, result_path = NULL, "
            "started_at = NULL, completed_at = NULL, contrato_id = NULL, itens = NULL "
            "WHERE job_id = %s AND filename = %s AND status = %s",
```

Em `app/services/file_processor.py`, `from . import contratos_repo, job_manager, medicoes_repo` e, dentro do `try` de `_persistir`, logo depois de `gravar_itens`:

```python
        itens = medicoes_repo.gravar_itens(
            contrato_id, result.get("rows") or [], job_id=job_id
        )
        job_manager.vincular_contrato(job_id, filename, contrato_id, itens)
        logger.info("'%s': %d item(ns) gravado(s) no banco.", filename, itens)
```

Em `app/routers/jobs.py`, `_job_status_dict`:

```python
        "files": {
            fname: {
                "status": fr["status"],
                "error": fr.get("error"),
                "contrato_id": fr.get("contrato_id"),
                "itens": fr.get("itens"),
            }
            for fname, fr in job["files"].items()
        },
```

- [ ] **Step 5: Catálogo — filtro por produto e associação em lote**

Em `app/services/catalogo.py`, `buscar_codigos` ganha o parâmetro e a condição:

```python
def buscar_codigos(
    q: str | None = None,
    associado: bool | None = None,
    limite: int = 500,
    produto_id: int | None = None,
) -> list[dict]:
    """Códigos distintos extraídos ou associados, para localizar e associar.

    *q* filtra código **ou** descrição do PDF, sem diferenciar maiúsculas — uma
    caixa de texto livre. *associado* restringe a associados (True) ou livres
    (False); *produto_id*, aos códigos de um produto.
    """
```

Na consulta, antes de `"ORDER BY c.codigo_servico LIMIT %(limite)s"`:

```python
            "  AND (%(produto_id)s::bigint IS NULL OR p.id = %(produto_id)s) "
```

e no dicionário de parâmetros: `{"padrao": _padrao_ilike(q), "associado": associado, "produto_id": produto_id, "limite": limite}`.

Acrescentar depois de `registrar_codigo`:

```python
def associar_codigos(produto_id: int, codigos: list[str]) -> bool:
    """Point several codes at one product in a single transaction.

    Codes already on another product are re-pointed, like ``registrar_codigo``.
    Returns False — and writes nothing — when the product does not exist.
    """
    unicos = list(dict.fromkeys(codigos))
    with acquire_sync() as conn, conn.transaction():
        if conn.execute(
            "SELECT 1 FROM produto WHERE id = %s FOR UPDATE", (produto_id,)
        ).fetchone() is None:
            return False
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO produto_codigo (codigo_servico, produto_id) VALUES (%s, %s) "
                "ON CONFLICT (codigo_servico) DO UPDATE SET produto_id = EXCLUDED.produto_id",
                [(codigo, produto_id) for codigo in unicos],
            )
    return True
```

Em `app/routers/api/schemas.py`, imports `from typing import Annotated, Literal` e `from pydantic import BaseModel, ConfigDict, Field, StringConstraints`, e depois de `class Associacao`:

```python
class CodigosDoProduto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigos: list[Annotated[str, StringConstraints(pattern=CODIGO_SERVICO)]] = Field(min_length=1)
```

Em `app/routers/api/catalogo.py`, importar `CodigosDoProduto`; `listar_codigos` ganha o parâmetro:

```python
@router.get("/codigos", response_model=list[Codigo])
async def listar_codigos(
    q: str | None = Query(None, description="Trecho do código ou da descrição"),
    associado: bool | None = None,
    produto_id: int | None = Query(None, description="Só os códigos deste produto"),
    limite: int = Query(500, ge=1, le=5000),
):
    return await asyncio.to_thread(
        lambda: catalogo.buscar_codigos(q, associado, limite, produto_id=produto_id)
    )
```

e, depois de `excluir_produto`:

```python
@router.put("/produtos/{produto_id}/codigos", response_model=Produto)
async def associar_codigos(produto_id: int, corpo: CodigosDoProduto):
    if not await asyncio.to_thread(catalogo.associar_codigos, produto_id, corpo.codigos):
        raise ErroApi(404, f"Produto {produto_id} não encontrado.")
    return await asyncio.to_thread(catalogo.buscar_produto, produto_id)
```

- [ ] **Step 6: Índices — produtos da ANP e valores manuais na cobertura**

Em `app/services/indices_repo.py`, em `cobertura()` acrescentar `COUNT(*) FILTER (WHERE origem = %s) AS manuais` às duas consultas:

```python
        anp = conn.execute(
            "SELECT MIN(vigencia_inicio) AS de, MAX(vigencia_fim) AS ate, "
            "COUNT(*) AS registros, "
            "COUNT(*) FILTER (WHERE origem = %s) AS manuais "
            "FROM anp_preco_semanal WHERE produto = %s",
            (ORIGEM_MANUAL, ANP_PRODUTO_CAP),
        ).fetchone()
        igp = conn.execute(
            "SELECT MIN(mes_ref) AS de, MAX(mes_ref) AS ate, COUNT(*) AS registros, "
            "COUNT(*) FILTER (WHERE origem = %s) AS manuais "
            "FROM indice_mensal WHERE indice = %s",
            (ORIGEM_MANUAL, INDICE_IGP_DI),
        ).fetchone()
```

(`ORIGEM_MANUAL` é a constante já usada como default de `gravar_precos_anp`.) E, depois de `regioes_disponiveis`:

```python
def produtos_anp() -> list[str]:
    """Products with at least one stored week, for the ANP screen's selector."""
    with acquire_sync() as conn:
        cur = conn.execute("SELECT DISTINCT produto FROM anp_preco_semanal ORDER BY produto")
        return [r["produto"] for r in cur.fetchall()]
```

Em `schemas.py`, `PeriodoCoberto` ganha `manuais: int`.

Em `app/routers/api/indices.py`, **antes** de `@router.get("/anp", …)` (a ordem não importa para o casamento exato, mas deixa a rota junto das outras do ANP):

```python
@router.get("/anp/produtos", response_model=list[str])
async def produtos_anp():
    return await asyncio.to_thread(indices_repo.produtos_anp)
```

- [ ] **Step 7: Cálculo — nome do arquivo no JSON**

Em `schemas.py`, `CalculoResposta` ganha `arquivo: str` (depois de `avisos`).

Em `app/routers/api/calculo.py`:

```python
@router.get("/{contrato_id}/calculo", response_model=CalculoResposta)
async def calculo(
    contrato_id: int, regiao_cap: str | None = None, regiao_emulsoes: str | None = None
):
    resultado = await asyncio.to_thread(_calcular, contrato_id, regiao_cap, regiao_emulsoes)
    resposta = reequilibrio_export.serializar(resultado)
    # O nome que a planilha terá: a tela mostra qual arquivo a simulação gera.
    resposta["arquivo"] = nome_do_arquivo(resultado.contrato["numero"], resultado.simuladas)
    return resposta
```

- [ ] **Step 8: Rodar tudo**

Run: `uv run pytest tests/test_api_medicoes.py tests/test_api_adicoes_frontend.py -q`
Expected: PASS (3 + 10 testes).

Run: `uv run pytest -q`
Expected: PASS na suíte inteira (as respostas de `/jobs/.../status`, cobertura e cálculo só ganharam campos).

- [ ] **Step 9: Commit**

```bash
git add migrations/007_file_results_contrato.sql app/services/medicoes_repo.py app/services/catalogo.py \
  app/services/indices_repo.py app/services/job_manager.py app/services/file_processor.py \
  app/routers/jobs.py app/routers/api/schemas.py app/routers/api/contratos.py \
  app/routers/api/catalogo.py app/routers/api/indices.py app/routers/api/calculo.py \
  tests/test_api_medicoes.py tests/test_api_adicoes_frontend.py
git commit -m "$(cat <<'EOF'
feat(api): adições para o frontend React

Medições do contrato com o produto do catálogo, filtro de códigos por
produto, associação em lote, produtos da ANP, contagem de valores manuais
na cobertura, nome do arquivo no JSON do cálculo e, pela migração 007, o
contrato e os itens gravados por arquivo no status do job.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarefa 4: Camada de API, formatação BR e componentes compartilhados

**Files:**
- Create: `frontend/src/lib/formato.ts`
- Create: `frontend/src/api/{client,erros,conexao,tipos,chaves,invalidar}.ts`
- Create: `frontend/src/components/{BannerConexao,Dialogo,ConfirmarDialogo,MensagemErro}.tsx`
- Modify: `frontend/src/components/Shell.tsx` (banner acima do `<Outlet/>`)
- Modify: `frontend/tests/setup.ts` (`reiniciarConexao` depois de cada teste)
- Create: `frontend/tests/{formato,erros,client,componentes}.test.ts(x)`

**Interfaces:**
- Consumes: `Shell`, `renderApp`, `servidor` (Tarefa 1).
- Produces — `src/lib/formato.ts` (toda entrada decimal é **string**, como vem da API; `null`/`undefined`/`''` viram `'—'`):
  - `numero(v, casas): string`, `dinheiro(v)` (2 casas), `fator(v)` (4), `deltaP(v)` (6), `exato(v)` (as casas que a string tiver), `percentual(v, casas = 2)` (`'0.0511'` → `'5,11%'`)
  - `negativo(v): boolean` (verdadeiro só para valor < 0; `'-0.00'` não é negativo)
  - `mesAno('2023-01' | '2023-01-01'): 'jan/2023'`, `data('2022-01-15'): '15/01/2022'`, `semana(inicio, fim): '09/01 – 15/01/2022'` (anos diferentes: `'26/12/2022 – 01/01/2023'`), `dataHora(isoDatetime): '24/09/2026 07:02'` (fuso `America/Sao_Paulo`)
  - `paraDecimal(texto): string | null` — entrada do usuário (`'1.234,56'`, `'4,02073'`, `'4.02073'`) para o formato da API (`'1234.56'`); `null` se ilegível ou vazio.
- Produces — `src/api/`:
  - `pedir<T>(caminho, { metodo?, params?, json?, form?, sinal? }?): Promise<T>`; `caminhoCom(caminho, params?): string` (caminho relativo com query, para `href` de download); `class ErroConexao`.
  - `class ErroApi { status; detail: string; campos: Record<string, string>; faltando: string[]; erros: string[] }`; `normalizarErro(status, corpo): ErroApi`.
  - `useOffline(): boolean`, `marcarOffline()`, `marcarOnline()`, `reiniciarConexao()`.
  - `tipos.ts` — interfaces de todas as respostas (lista abaixo), `Decimal = string`, `Familia = 'CAP' | 'EMULSOES'`, `FAMILIAS`, `ROTULO_FAMILIA`.
  - `chaves.ts` — objeto `chaves` com as chaves do TanStack Query.
  - `invalidar.ts` — `aposCadastro(qc, id)`, `aposCatalogo(qc)`, `aposIndices(qc)`, `aposUpload(qc)`.
- Produces — componentes: `BannerConexao()`; `Dialogo({ titulo, aoFechar, acoes, children })`; `ConfirmarDialogo({ titulo, mensagem, rotuloConfirmar, textoExigido?, perigoso?, pendente?, erro?, aoConfirmar, aoCancelar })`; `MensagemErro({ erro })`.

- [ ] **Step 1: Testes da formatação**

`frontend/tests/formato.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import {
  data, dataHora, deltaP, dinheiro, exato, fator, mesAno, negativo, paraDecimal, percentual, semana,
} from '../src/lib/formato'

describe('números', () => {
  it('formata no padrão brasileiro com casas fixas', () => {
    expect(dinheiro('208133.17')).toBe('208.133,17')
    expect(dinheiro('-38275.68')).toBe('-38.275,68')
    expect(dinheiro('0')).toBe('0,00')
    expect(fator('-0.1839')).toBe('-0,1839')
    expect(deltaP('-0.182815')).toBe('-0,182815')
  })

  it('não passa por float: string grande sai exata', () => {
    expect(dinheiro('12345678901234567.89')).toBe('12.345.678.901.234.567,89')
    expect(exato('0.12345678901234567890')).toBe('0,12345678901234567890')
  })

  it('exato mantém as casas da string', () => {
    expect(exato('4.02073')).toBe('4,02073')
    expect(exato('1110.398')).toBe('1.110,398')
    expect(exato('3')).toBe('3')
  })

  it('percentual', () => {
    expect(percentual('0.0511')).toBe('5,11%')
  })

  it('vazio vira travessão', () => {
    expect(dinheiro(null)).toBe('—')
    expect(exato(undefined)).toBe('—')
    expect(fator('')).toBe('—')
  })

  it('negativo', () => {
    expect(negativo('-0.01')).toBe(true)
    expect(negativo('-0.00')).toBe(false)
    expect(negativo('12')).toBe(false)
    expect(negativo(null)).toBe(false)
  })
})

describe('datas', () => {
  it('mês e data sem passar por Date', () => {
    expect(mesAno('2023-01')).toBe('jan/2023')
    expect(mesAno('2023-12-01')).toBe('dez/2023')
    expect(data('2022-01-15')).toBe('15/01/2022')
    expect(mesAno(null)).toBe('—')
  })

  it('semana', () => {
    expect(semana('2022-01-09', '2022-01-15')).toBe('09/01 – 15/01/2022')
    expect(semana('2022-12-26', '2023-01-01')).toBe('26/12/2022 – 01/01/2023')
  })

  it('data e hora no fuso de Brasília', () => {
    expect(dataHora('2026-09-24T10:02:00+00:00')).toBe('24/09/2026 07:02')
  })
})

describe('entrada do usuário', () => {
  it('aceita vírgula decimal e pontos de milhar', () => {
    expect(paraDecimal('1.234,56')).toBe('1234.56')
    expect(paraDecimal('4,02073')).toBe('4.02073')
    expect(paraDecimal(' -0,5 ')).toBe('-0.5')
    expect(paraDecimal('1110')).toBe('1110')
  })

  it('um ponto sozinho é separador decimal (valor colado da planilha)', () => {
    expect(paraDecimal('4.02073')).toBe('4.02073')
    expect(paraDecimal('1.234.567')).toBe('1234567')
  })

  it('ilegível ou vazio é null', () => {
    for (const texto of ['', '  ', 'abc', '1,2,3', '1.234,5.6', '--1']) {
      expect(paraDecimal(texto)).toBeNull()
    }
  })
})
```

Run: `npm run test -- formato`
Expected: FAIL — `Failed to resolve import "../src/lib/formato"`.

- [ ] **Step 2: Implementar `formato.ts`**

`frontend/src/lib/formato.ts`:

```ts
// Formatação no padrão brasileiro. Valores decimais chegam da API como string
// e são formatados como string: Intl.NumberFormat formata a string decimal
// exatamente, sem passar por float — o usuário confere estes números contra a
// planilha.

type Entrada = string | null | undefined

const VAZIO = '—'
const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']

const formatadores = new Map<string, Intl.NumberFormat>()

function formatador(casas: number, estilo: 'decimal' | 'percent' = 'decimal') {
  const chave = `${estilo}:${casas}`
  let f = formatadores.get(chave)
  if (!f) {
    f = new Intl.NumberFormat('pt-BR', {
      style: estilo,
      minimumFractionDigits: casas,
      maximumFractionDigits: casas,
    })
    formatadores.set(chave, f)
  }
  return f
}

// A tipagem de format() só lista number/bigint/StringNumericLiteral; a string
// decimal é aceita e formatada exatamente (Intl.NumberFormat v3).
function formatar(v: string, f: Intl.NumberFormat) {
  return f.format(v as `${number}`)
}

export function numero(v: Entrada, casas: number): string {
  if (v === null || v === undefined || v.trim() === '') return VAZIO
  return formatar(v.trim(), formatador(casas))
}

export const dinheiro = (v: Entrada) => numero(v, 2)
export const fator = (v: Entrada) => numero(v, 4)
export const deltaP = (v: Entrada) => numero(v, 6)

export function exato(v: Entrada): string {
  if (v === null || v === undefined || v.trim() === '') return VAZIO
  const casas = (v.trim().split('.')[1] ?? '').length
  return numero(v, casas)
}

export function percentual(v: Entrada, casas = 2): string {
  if (v === null || v === undefined || v.trim() === '') return VAZIO
  return formatar(v.trim(), formatador(casas, 'percent'))
}

export function negativo(v: Entrada): boolean {
  return !!v && v.trim().startsWith('-') && /[1-9]/.test(v)
}

export function mesAno(iso: Entrada): string {
  if (!iso) return VAZIO
  const [ano, mes] = iso.split('-')
  return `${MESES[Number(mes) - 1]}/${ano}`
}

export function data(iso: Entrada): string {
  if (!iso) return VAZIO
  const [ano, mes, dia] = iso.slice(0, 10).split('-')
  return `${dia}/${mes}/${ano}`
}

export function semana(inicio: string, fim: string): string {
  const [ai, mi, di] = inicio.split('-')
  const [af, mf, df] = fim.split('-')
  const comeco = ai === af ? `${di}/${mi}` : `${di}/${mi}/${ai}`
  return `${comeco} – ${df}/${mf}/${af}`
}

const DATA_HORA = new Intl.DateTimeFormat('pt-BR', {
  dateStyle: 'short',
  timeStyle: 'short',
  timeZone: 'America/Sao_Paulo',
})

export function dataHora(iso: Entrada): string {
  if (!iso) return VAZIO
  return DATA_HORA.format(new Date(iso)).replace(',', '')
}

// O que o usuário digitou → decimal da API ("1234.56"). Com vírgula, pontos são
// milhar; sem vírgula, um ponto só é o separador decimal (valor colado de uma
// planilha em inglês) e mais de um ponto é milhar.
export function paraDecimal(texto: string): string | null {
  let t = texto.trim().replace(/\s/g, '')
  if (!t) return null
  if (t.includes(',')) {
    t = t.replace(/\./g, '').replace(',', '.')
  } else if ((t.match(/\./g) ?? []).length > 1) {
    t = t.replace(/\./g, '')
  }
  return /^-?\d+(\.\d+)?$/.test(t) ? t : null
}
```

Run: `npm run test -- formato`
Expected: PASS.

- [ ] **Step 3: Testes de erros e do cliente HTTP**

`frontend/tests/erros.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { normalizarErro } from '../src/api/erros'

describe('normalizarErro', () => {
  it('detail string do ErroApi vem como está, com faltando e erros', () => {
    const e = normalizarErro(422, {
      detail: 'Não é possível calcular:\n- data_base',
      faltando: ['data_base', 'Sem valor de IGP - DI para 02/2023 (mês da medição).'],
    })
    expect(e.status).toBe(422)
    expect(e.detail).toBe('Não é possível calcular:\n- data_base')
    expect(e.faltando).toHaveLength(2)
    expect(e.erros).toEqual([])
    expect(e.campos).toEqual({})

    const i = normalizarErro(422, { detail: 'Arquivo inválido.', erros: ['linha 3: mês ilegível'] })
    expect(i.erros).toEqual(['linha 3: mês ilegível'])
  })

  it('detail lista do Pydantic vira mensagem por campo', () => {
    const e = normalizarErro(422, {
      detail: [
        { loc: ['body', 'extensao'], msg: 'Input should be a valid decimal', type: 'decimal_parsing' },
        { loc: ['query', 'mes'], msg: "String should match pattern", type: 'string_pattern_mismatch' },
        { loc: ['body'], msg: 'Field required', type: 'missing' },
      ],
    })
    expect(e.campos).toEqual({
      extensao: 'Input should be a valid decimal',
      mes: 'String should match pattern',
      geral: 'Field required',
    })
    expect(e.detail).toContain('extensao: Input should be a valid decimal')
  })

  it('sem corpo útil usa a mensagem do status', () => {
    expect(normalizarErro(404, null).detail).toBe('Não encontrado.')
    expect(normalizarErro(413, 'x').detail).toBe('Arquivo maior que 20 MB.')
    expect(normalizarErro(500, {}).detail).toBe('O servidor respondeu com erro 500.')
  })
})
```

`frontend/tests/client.test.ts`:

```ts
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { caminhoCom, ErroConexao, pedir } from '../src/api/client'
import { useOffline } from '../src/api/conexao'
import { ErroApi } from '../src/api/erros'
import { renderHook } from '@testing-library/react'
import { servidor } from './servidor'

describe('pedir', () => {
  it('monta a query sem parâmetros vazios e devolve o JSON', async () => {
    let url = ''
    servidor.use(
      http.get('/api/v1/contratos/1/calculo', ({ request }) => {
        url = request.url
        return HttpResponse.json({ ok: true })
      }),
    )
    const corpo = await pedir<{ ok: boolean }>('/api/v1/contratos/1/calculo', {
      params: { regiao_cap: 'Sul', regiao_emulsoes: undefined, vazio: '' },
    })
    expect(corpo).toEqual({ ok: true })
    expect(new URL(url).search).toBe('?regiao_cap=Sul')
  })

  it('envia JSON e trata 204', async () => {
    let recebido: unknown
    servidor.use(
      http.patch('/api/v1/contratos/1', async ({ request }) => {
        recebido = await request.json()
        return new HttpResponse(null, { status: 204 })
      }),
    )
    expect(await pedir('/api/v1/contratos/1', { metodo: 'PATCH', json: { edital: 'X' } })).toBeUndefined()
    expect(recebido).toEqual({ edital: 'X' })
  })

  it('4xx vira ErroApi', async () => {
    servidor.use(http.get('/api/v1/x', () => HttpResponse.json({ detail: 'Contrato 9 não encontrado.' }, { status: 404 })))
    await expect(pedir('/api/v1/x')).rejects.toMatchObject({ status: 404, detail: 'Contrato 9 não encontrado.' })
    await expect(pedir('/api/v1/x')).rejects.toBeInstanceOf(ErroApi)
  })

  it('falha de rede e 502 marcam offline; resposta boa volta a online', async () => {
    const { result, rerender } = renderHook(() => useOffline())
    servidor.use(http.get('/api/v1/rede', () => HttpResponse.error()))
    await expect(pedir('/api/v1/rede')).rejects.toBeInstanceOf(ErroConexao)
    rerender()
    expect(result.current).toBe(true)

    servidor.use(http.get('/api/v1/ok', () => HttpResponse.json([])))
    await pedir('/api/v1/ok')
    rerender()
    expect(result.current).toBe(false)

    servidor.use(http.get('/api/v1/gateway', () => new HttpResponse('Bad Gateway', { status: 502 })))
    await expect(pedir('/api/v1/gateway')).rejects.toBeInstanceOf(ErroConexao)
    rerender()
    expect(result.current).toBe(true)
  })

  it('caminhoCom devolve caminho relativo para links de download', () => {
    expect(caminhoCom('/api/v1/contratos/1/planilha', { regiao_cap: 'Centro-Oeste', regiao_emulsoes: null }))
      .toBe('/api/v1/contratos/1/planilha?regiao_cap=Centro-Oeste')
  })
})
```

Run: `npm run test -- erros client`
Expected: FAIL — módulos não existem.

- [ ] **Step 4: Implementar `erros.ts`, `conexao.ts` e `client.ts`**

`frontend/src/api/erros.ts`:

```ts
// Os dois formatos de 422 do backend numa forma só. detail string (ErroApi do
// backend) é exibido como veio; detail lista (validação do Pydantic) vira uma
// mensagem por campo.

export class ErroApi extends Error {
  status: number
  detail: string
  campos: Record<string, string>
  faltando: string[]
  erros: string[]

  constructor(
    status: number,
    detail: string,
    { campos = {}, faltando = [], erros = [] }: { campos?: Record<string, string>; faltando?: string[]; erros?: string[] } = {},
  ) {
    super(detail)
    this.name = 'ErroApi'
    this.status = status
    this.detail = detail
    this.campos = campos
    this.faltando = faltando
    this.erros = erros
  }
}

const PADRAO: Record<number, string> = {
  404: 'Não encontrado.',
  413: 'Arquivo maior que 20 MB.',
}

const PREFIXOS_LOC = new Set(['body', 'query', 'path'])

interface ItemPydantic {
  loc?: (string | number)[]
  msg?: string
}

function listaDeTextos(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []
}

export function normalizarErro(status: number, corpo: unknown): ErroApi {
  const c = (corpo && typeof corpo === 'object' ? corpo : {}) as Record<string, unknown>
  if (typeof c.detail === 'string') {
    return new ErroApi(status, c.detail, { faltando: listaDeTextos(c.faltando), erros: listaDeTextos(c.erros) })
  }
  if (Array.isArray(c.detail)) {
    const campos: Record<string, string> = {}
    for (const item of c.detail as ItemPydantic[]) {
      const campo = (item.loc ?? []).filter((p) => !PREFIXOS_LOC.has(String(p))).join('.') || 'geral'
      campos[campo] = item.msg ?? 'Valor inválido.'
    }
    const detail = Object.entries(campos).map(([campo, msg]) => `${campo}: ${msg}`).join('\n')
    return new ErroApi(status, detail, { campos })
  }
  return new ErroApi(status, PADRAO[status] ?? `O servidor respondeu com erro ${status}.`)
}
```

`frontend/src/api/conexao.ts`:

```ts
import { useSyncExternalStore } from 'react'

// Estado "sem conexão com o servidor", compartilhado por toda a aplicação:
// qualquer requisição que falhe por rede liga o aviso, e a primeira que
// responder desliga.

let offline = false
const ouvintes = new Set<() => void>()

function avisar() {
  for (const ouvinte of ouvintes) ouvinte()
}

function assinar(ouvinte: () => void) {
  ouvintes.add(ouvinte)
  return () => ouvintes.delete(ouvinte)
}

export function marcarOffline() {
  if (!offline) {
    offline = true
    avisar()
  }
}

export function marcarOnline() {
  if (offline) {
    offline = false
    avisar()
  }
}

// Para os testes: cada teste começa online.
export function reiniciarConexao() {
  offline = false
  avisar()
}

export function useOffline(): boolean {
  return useSyncExternalStore(assinar, () => offline)
}
```

`frontend/src/api/client.ts`:

```ts
import { marcarOffline, marcarOnline } from './conexao'
import { normalizarErro } from './erros'

export class ErroConexao extends Error {
  constructor() {
    super('Sem conexão com o servidor.')
    this.name = 'ErroConexao'
  }
}

export type Params = Record<string, string | number | boolean | null | undefined>

interface Opcoes {
  metodo?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  params?: Params
  json?: unknown
  form?: FormData
  sinal?: AbortSignal
}

function montarUrl(caminho: string, params?: Params): URL {
  const url = new URL(caminho, window.location.origin)
  for (const [chave, valor] of Object.entries(params ?? {})) {
    if (valor !== undefined && valor !== null && valor !== '') url.searchParams.set(chave, String(valor))
  }
  return url
}

// Caminho relativo com a query: é o que vai no href dos downloads.
export function caminhoCom(caminho: string, params?: Params): string {
  const url = montarUrl(caminho, params)
  return url.pathname + url.search
}

const SEM_SERVIDOR = new Set([502, 503, 504])

export async function pedir<T>(caminho: string, opcoes: Opcoes = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  let body: BodyInit | undefined
  if (opcoes.json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(opcoes.json)
  } else if (opcoes.form) {
    body = opcoes.form
  }

  let resposta: Response
  try {
    resposta = await fetch(montarUrl(caminho, opcoes.params), {
      method: opcoes.metodo ?? 'GET',
      headers,
      body,
      signal: opcoes.sinal,
    })
  } catch (e) {
    if ((e as Error)?.name === 'AbortError') throw e
    marcarOffline()
    throw new ErroConexao()
  }

  // O proxy (Vite em desenvolvimento, nginx em produção) responde 502/503/504
  // quando o FastAPI está fora do ar: para o usuário é a mesma falta de conexão.
  if (SEM_SERVIDOR.has(resposta.status)) {
    marcarOffline()
    throw new ErroConexao()
  }
  marcarOnline()

  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => null)
    throw normalizarErro(resposta.status, corpo)
  }
  if (resposta.status === 204) return undefined as T
  return (await resposta.json()) as T
}
```

Em `frontend/tests/setup.ts`, importar `reiniciarConexao` de `'../src/api/conexao'` e chamá-lo no `afterEach`, depois de `servidor.resetHandlers()`.

Run: `npm run test -- erros client`
Expected: PASS.

- [ ] **Step 5: Tipos, chaves e invalidação**

`frontend/src/api/tipos.ts` (espelha `app/routers/api/schemas.py`, `app/routers/jobs.py` e `app/routers/admin.py`):

```ts
// Respostas da API. Decimal chega como string (Pydantic 2) e nunca vira
// number: é só formatado (lib/formato.ts). Datas são strings ISO.

export type Decimal = string
export type Familia = 'CAP' | 'EMULSOES'
export const FAMILIAS: Familia[] = ['CAP', 'EMULSOES']
export const ROTULO_FAMILIA: Record<Familia, string> = { CAP: 'CAP', EMULSOES: 'Emulsões' }

export interface ContratoResumo {
  id: number
  numero: string
  data_base: string | null
  contratada: string | null
  rodovia: string | null
  regioes: Partial<Record<Familia, string>>
  itens: number
  medicoes: number
  primeiro_mes: string | null
  ultimo_mes: string | null
  faltantes: string[]
}

export interface Contrato {
  id: number
  numero: string
  numero_processo: string | null
  data_base: string | null
  edital: string | null
  rodovia: string | null
  trecho: string | null
  subtrecho: string | null
  segmento: string | null
  extensao: Decimal | null
  contratada: string | null
  regioes: Partial<Record<Familia, string>>
  faltantes: string[]
  atualizado_em: string
}

export type CampoCadastro = 'edital' | 'rodovia' | 'trecho' | 'subtrecho' | 'segmento' | 'extensao' | 'contratada'

export interface ContratoPatch {
  edital?: string | null
  rodovia?: string | null
  trecho?: string | null
  subtrecho?: string | null
  segmento?: string | null
  extensao?: string | null
  contratada?: string | null
  data_base?: string
  regioes?: Partial<Record<Familia, string>>
}

export interface ItemMedicao {
  id: number
  mes: string
  codigo: string
  descricao_pdf: string | null
  valor_pi: Decimal
  fator: Decimal
  reajuste: Decimal
  arquivo: string
  produto_id: number | null
  produto: string | null
  familia: Familia | null
}

export interface LinhaCalculo {
  mes: string
  a: Decimal
  fator: Decimal
  b: Decimal
  d: Decimal
  c: Decimal
  e: Decimal
  f: Decimal
}

export interface ProdutoCalculo {
  descricao: string
  subtotal: Decimal
  linhas: LinhaCalculo[]
}

export interface FamiliaCalculo {
  familia: Familia
  rotulo: string
  subtotal: Decimal
  produtos: ProdutoCalculo[]
}

export interface Calculo {
  contrato: { id: number; numero: string }
  parametros: { data_base: string; regioes: Partial<Record<Familia, string>>; simulacao: boolean; lucro: Decimal }
  familias: FamiliaCalculo[]
  total: Decimal
  avisos: string[]
  arquivo: string
}

export interface Produto {
  id: number
  descricao_export: string
  familia: Familia
  ordem: number
  codigos: number
}

export interface Codigo {
  codigo: string
  descricao_pdf: string | null
  contratos: number
  ocorrencias: number
  produto_id: number | null
  descricao_export: string | null
  familia: Familia | null
}

export interface SemanaAnp {
  id: number
  produto: string
  regiao: string
  vigencia_inicio: string
  vigencia_fim: string
  preco: Decimal | null
  origem: string
  atualizado_em: string
}

export interface SemanaAnpEntrada {
  produto?: string
  vigencia_inicio: string
  vigencia_fim: string
  regiao: string
  preco: Decimal | null
}

export interface IndiceMensal {
  mes: string
  valor: Decimal
  origem: string
  atualizado_em: string
}

export interface PeriodoCoberto {
  de: string | null
  ate: string | null
  registros: number
  manuais: number
}

export interface Cobertura {
  anp: PeriodoCoberto
  igp_di: PeriodoCoberto
  regioes: string[]
}

export interface ResultadoImportacao {
  arquivo: string
  simulacao: boolean
  periodo: { de: string | null; ate: string | null }
  inseridos: number
  atualizados: { chave: Record<string, string>; antes: Decimal | null; depois: Decimal | null }[]
  inalterados: number
  conflitos_manuais: {
    chave: Record<string, string>
    valor_banco: Decimal | null
    valor_arquivo: Decimal | null
    atualizado_em: string
  }[]
  manuais_preservados: number
  avisos: string[]
}

export type StatusArquivo = 'pending' | 'processing' | 'completed' | 'failed'

export interface ArquivoDoJob {
  status: StatusArquivo
  error: string | null
  contrato_id: number | null
  itens: number | null
}

export interface StatusJob {
  job_id: string
  completed: boolean
  files: Record<string, ArquivoDoJob>
}

export interface ResumoJob {
  job_id: string
  created_at: string
  completed: boolean
  file_count: number
  completed_count: number
  failed_count: number
  processing_count: number
  pending_count: number
}

export interface Template {
  id: number
  nome: string
  tamanho: number
  sha256: string
  ativo: boolean
  criado_em: string
  observacao: string | null
}

export interface Backup {
  nome: string
  tamanho: number
  criado_em: string
}
```

Os tipos de job, template e backup espelham `FileStatus` (`app/models/job.py`), `list_jobs` (`app/services/job_manager.py`), `_job_status_dict` (`app/routers/jobs.py`, já com `contrato_id`/`itens` da Tarefa 3), `template_repo.listar` e `backup.listar`.

`frontend/src/api/chaves.ts`:

```ts
// Chaves do TanStack Query. Os prefixos (todos*, calculos) existem para a
// invalidação em invalidar.ts: invalidar ['calculo'] atinge todo cálculo em
// cache, de qualquer contrato e simulação.

export interface RegioesSimuladas {
  cap?: string
  emulsoes?: string
}

export interface FiltrosMedicoes {
  mes?: string
  noCalculo?: boolean
  q?: string
}

export interface FiltrosCodigos {
  q?: string
  associado?: boolean
  produtoId?: number
}

export const chaves = {
  contratos: ['contratos'] as const,
  contrato: (id: number) => ['contrato', id] as const,
  calculos: ['calculo'] as const,
  calculo: (id: number, regioes: RegioesSimuladas) => ['calculo', id, regioes] as const,
  todasMedicoes: ['medicoes'] as const,
  medicoes: (id: number, filtros: FiltrosMedicoes) => ['medicoes', id, filtros] as const,
  produtos: ['produtos'] as const,
  todosCodigos: ['codigos'] as const,
  codigos: (filtros: FiltrosCodigos) => ['codigos', filtros] as const,
  todosAnp: ['anp'] as const,
  anp: (produto: string, de?: string, ate?: string) => ['anp', produto, de, ate] as const,
  produtosAnp: ['anp-produtos'] as const,
  todosIgpDi: ['igp-di'] as const,
  igpDi: (de?: string, ate?: string) => ['igp-di', de, ate] as const,
  cobertura: ['cobertura'] as const,
  jobs: (status: 'active' | 'completed') => ['jobs', status] as const,
  templates: ['templates'] as const,
  backups: ['backups'] as const,
}
```

`frontend/src/api/invalidar.ts`:

```ts
import type { QueryClient } from '@tanstack/react-query'
import { chaves } from './chaves'

// Depois de cada gravação, as telas releem do banco o que ela pode ter mudado.

export function aposCadastro(qc: QueryClient, contratoId: number) {
  return Promise.all([
    qc.invalidateQueries({ queryKey: chaves.contrato(contratoId) }),
    qc.invalidateQueries({ queryKey: chaves.contratos }),
    qc.invalidateQueries({ queryKey: chaves.calculos }),
  ])
}

// Produto ou associação de código: muda o que entra em qualquer cálculo.
export function aposCatalogo(qc: QueryClient) {
  return Promise.all([
    qc.invalidateQueries({ queryKey: chaves.produtos }),
    qc.invalidateQueries({ queryKey: chaves.todosCodigos }),
    qc.invalidateQueries({ queryKey: chaves.todasMedicoes }),
    qc.invalidateQueries({ queryKey: chaves.calculos }),
  ])
}

// Índices são globais: todo cálculo em cache pode ter mudado.
export function aposIndices(qc: QueryClient) {
  return Promise.all([
    qc.invalidateQueries({ queryKey: chaves.todosAnp }),
    qc.invalidateQueries({ queryKey: chaves.produtosAnp }),
    qc.invalidateQueries({ queryKey: chaves.todosIgpDi }),
    qc.invalidateQueries({ queryKey: chaves.cobertura }),
    qc.invalidateQueries({ queryKey: chaves.calculos }),
  ])
}

// PDF processado: contrato novo ou itens novos.
export function aposUpload(qc: QueryClient) {
  return Promise.all([
    qc.invalidateQueries({ queryKey: chaves.contratos }),
    qc.invalidateQueries({ queryKey: ['contrato'] }),
    qc.invalidateQueries({ queryKey: chaves.todasMedicoes }),
    qc.invalidateQueries({ queryKey: chaves.todosCodigos }),
    qc.invalidateQueries({ queryKey: chaves.calculos }),
  ])
}
```

- [ ] **Step 6: Testes dos componentes compartilhados**

`frontend/tests/componentes.test.tsx`:

```tsx
import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { chaves } from '../src/api/chaves'
import { marcarOffline } from '../src/api/conexao'
import { ErroApi } from '../src/api/erros'
import { aposCatalogo } from '../src/api/invalidar'
import { criarQueryClient } from '../src/api/queryClient'
import { BannerConexao } from '../src/components/BannerConexao'
import { ConfirmarDialogo } from '../src/components/ConfirmarDialogo'
import { MensagemErro } from '../src/components/MensagemErro'
import { servidor } from './servidor'

describe('ConfirmarDialogo', () => {
  it('só confirma depois de digitar o texto exigido', async () => {
    const usuario = userEvent.setup()
    const aoConfirmar = vi.fn()
    render(
      <ConfirmarDialogo
        titulo="Restaurar backup"
        mensagem="O banco atual será substituído."
        rotuloConfirmar="Restaurar"
        textoExigido="dnit_20260924.dump"
        perigoso
        aoConfirmar={aoConfirmar}
        aoCancelar={() => {}}
      />,
    )
    const botao = screen.getByRole('button', { name: 'Restaurar' })
    expect(botao).toBeDisabled()
    await usuario.type(screen.getByLabelText('Digite dnit_20260924.dump para confirmar'), 'dnit_2026')
    expect(botao).toBeDisabled()
    await usuario.type(screen.getByLabelText('Digite dnit_20260924.dump para confirmar'), '0924.dump')
    await usuario.click(botao)
    expect(aoConfirmar).toHaveBeenCalledOnce()
  })

  it('Esc cancela', async () => {
    const usuario = userEvent.setup()
    const aoCancelar = vi.fn()
    render(
      <ConfirmarDialogo titulo="Excluir" mensagem="Certeza?" rotuloConfirmar="Excluir"
        aoConfirmar={() => {}} aoCancelar={aoCancelar} />,
    )
    await usuario.keyboard('{Escape}')
    expect(aoCancelar).toHaveBeenCalledOnce()
  })
})

describe('MensagemErro', () => {
  it('mostra o detail como veio e a lista de erros', () => {
    render(<MensagemErro erro={new ErroApi(422, 'Arquivo inválido.', { erros: ['linha 3: mês ilegível'] })} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Arquivo inválido.')
    expect(screen.getByText('linha 3: mês ilegível')).toBeInTheDocument()
  })

  it('sem erro não renderiza nada', () => {
    const { container } = render(<MensagemErro erro={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('BannerConexao', () => {
  it('aparece sem conexão e "Tentar de novo" refaz as consultas ativas', async () => {
    const usuario = userEvent.setup()
    const qc = criarQueryClient()
    const refazer = vi.spyOn(qc, 'refetchQueries')
    render(
      <QueryClientProvider client={qc}>
        <BannerConexao />
      </QueryClientProvider>,
    )
    expect(screen.queryByText('Sem conexão com o servidor.')).not.toBeInTheDocument()
    marcarOffline()
    expect(await screen.findByText('Sem conexão com o servidor.')).toBeInTheDocument()
    await usuario.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    expect(refazer).toHaveBeenCalledWith({ type: 'active' })
  })
})

describe('invalidação', () => {
  it('aposCatalogo invalida produtos, códigos, medições e cálculos', async () => {
    servidor.use(http.get('*', () => HttpResponse.json([])))
    const qc = criarQueryClient()
    for (const chave of [chaves.produtos, chaves.codigos({}), chaves.medicoes(1, {}), chaves.calculo(1, {}), chaves.cobertura]) {
      qc.setQueryData(chave, [])
    }
    await aposCatalogo(qc)
    const invalida = (chave: readonly unknown[]) => qc.getQueryState(chave)?.isInvalidated
    expect(invalida(chaves.produtos)).toBe(true)
    expect(invalida(chaves.codigos({}))).toBe(true)
    expect(invalida(chaves.medicoes(1, {}))).toBe(true)
    expect(invalida(chaves.calculo(1, {}))).toBe(true)
    expect(invalida(chaves.cobertura)).toBe(false)
  })
})
```

Run: `npm run test -- componentes`
Expected: FAIL — componentes não existem.

- [ ] **Step 7: Implementar os componentes**

`frontend/src/components/Dialogo.tsx`:

```tsx
import { useEffect, useId, useRef, type ReactNode } from 'react'

interface Props {
  titulo: string
  aoFechar: () => void
  acoes: ReactNode
  children: ReactNode
}

// Modal simples: Esc e o fundo fecham; o foco entra no diálogo ao abrir.
export function Dialogo({ titulo, aoFechar, acoes, children }: Props) {
  const idTitulo = useId()
  const caixa = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const primeiro = caixa.current?.querySelector<HTMLElement>('input, select, textarea')
    ;(primeiro ?? caixa.current)?.focus()
  }, [])

  return (
    <div
      className="dialogo-fundo"
      onMouseDown={(e) => e.target === e.currentTarget && aoFechar()}
      onKeyDown={(e) => e.key === 'Escape' && aoFechar()}
    >
      <div ref={caixa} className="dialogo" role="dialog" aria-modal="true" aria-labelledby={idTitulo} tabIndex={-1}>
        <h2 id={idTitulo} className="dialogo-titulo">
          {titulo}
        </h2>
        <div className="dialogo-corpo">{children}</div>
        <div className="dialogo-acoes">{acoes}</div>
      </div>
    </div>
  )
}
```

`frontend/src/components/ConfirmarDialogo.tsx`:

```tsx
import { useId, useState, type ReactNode } from 'react'
import { Dialogo } from './Dialogo'
import { MensagemErro } from './MensagemErro'

interface Props {
  titulo: string
  mensagem: ReactNode
  rotuloConfirmar: string
  // Ações irreversíveis (restaurar backup) exigem digitar este texto.
  textoExigido?: string
  perigoso?: boolean
  pendente?: boolean
  erro?: unknown
  aoConfirmar: () => void
  aoCancelar: () => void
}

export function ConfirmarDialogo({
  titulo, mensagem, rotuloConfirmar, textoExigido, perigoso, pendente, erro, aoConfirmar, aoCancelar,
}: Props) {
  const [digitado, setDigitado] = useState('')
  const idCampo = useId()
  const liberado = !pendente && (!textoExigido || digitado === textoExigido)
  return (
    <Dialogo
      titulo={titulo}
      aoFechar={aoCancelar}
      acoes={
        <>
          <button type="button" className="btn" onClick={aoCancelar}>
            Cancelar
          </button>
          <button
            type="button"
            className={perigoso ? 'btn btn-danger' : 'btn btn-primary'}
            disabled={!liberado}
            onClick={aoConfirmar}
          >
            {rotuloConfirmar}
          </button>
        </>
      }
    >
      <div>{mensagem}</div>
      {textoExigido && (
        <div className="field">
          <label className="field-label" htmlFor={idCampo}>
            Digite {textoExigido} para confirmar
          </label>
          <input id={idCampo} className="input" value={digitado} onChange={(e) => setDigitado(e.target.value)} autoComplete="off" />
        </div>
      )}
      <MensagemErro erro={erro} />
    </Dialogo>
  )
}
```

`frontend/src/components/MensagemErro.tsx`:

```tsx
import { ErroConexao } from '../api/client'
import { ErroApi } from '../api/erros'

// Mensagem de regra de negócio exatamente como o backend a escreveu. Falta de
// conexão não aparece aqui: o aviso fixo (BannerConexao) já cobre.
export function MensagemErro({ erro }: { erro: unknown }) {
  if (!erro || erro instanceof ErroConexao) return null
  const detail = erro instanceof ErroApi ? erro.detail : erro instanceof Error ? erro.message : String(erro)
  const erros = erro instanceof ErroApi ? erro.erros : []
  return (
    <div className="notice danger" role="alert">
      <div>
        <p className="notice-text pre-linha">{detail}</p>
        {erros.length > 0 && (
          <ul className="lista-erros">
            {erros.map((texto) => (
              <li key={texto}>{texto}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
```

`frontend/src/components/BannerConexao.tsx`:

```tsx
import { useQueryClient } from '@tanstack/react-query'
import { useOffline } from '../api/conexao'
import { Icone } from './Icone'

export function BannerConexao() {
  const offline = useOffline()
  const qc = useQueryClient()
  if (!offline) return null
  return (
    <div className="notice warn banner-conexao" role="alert">
      <div className="notice-icon">
        <Icone nome="cloud_off" />
      </div>
      <div>
        <p className="notice-title">Sem conexão com o servidor.</p>
        <p className="notice-text">Confira se o servidor está rodando e tente de novo.</p>
        <div className="notice-actions">
          <button type="button" className="btn btn-sm" onClick={() => qc.refetchQueries({ type: 'active' })}>
            Tentar de novo
          </button>
        </div>
      </div>
    </div>
  )
}
```

Em `Shell.tsx`, importar `BannerConexao` e renderizá-lo como primeiro filho de `<main className="main-content">`, antes de `<Outlet />`.

- [ ] **Step 8: Rodar tudo**

Run: `npm run test && npm run build`
Expected: todos os testes passam (shell, formato, erros, client, componentes); build sem erro de tipo.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib frontend/src/api frontend/src/components frontend/tests
git commit -m "$(cat <<'EOF'
feat(frontend): camada de API, formatação BR e componentes base

Cliente HTTP que normaliza os dois formatos de 422 e liga o aviso de falta
de conexão; tipos das respostas, chaves e invalidação do TanStack Query;
formatação de decimais como string (sem float), meses e datas; diálogo,
confirmação com texto exigido e mensagem de erro.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarefa 5: Lista de contratos, página do contrato e aba Cadastro

**Files:**
- Create: `frontend/src/api/contratos.ts`, `frontend/src/api/indices.ts` (só `buscarCobertura` nesta tarefa; a Tarefa 9 completa)
- Create: `frontend/src/pages/contratos/{ListaContratos.tsx,situacao.ts}`
- Create: `frontend/src/pages/contrato/{PaginaContrato.tsx,AbaCadastro.tsx,cadastro.ts}`
- Modify: `frontend/src/App.tsx` (rotas)
- Create: `frontend/tests/{fabricas.ts,situacao.test.ts,contratos.test.tsx,cadastro.test.tsx}`

**Interfaces:**
- Consumes: `pedir`, `ErroApi`, `chaves`, `aposCadastro`, `tipos` (Tarefa 4); `Cabecalho`, `NaoEncontrado`, `Carregando`, `Icone`, `MensagemErro` (Tarefas 1 e 4); `renderApp`, `servidor`.
- Produces:
  - `src/api/contratos.ts`: `listarContratos(): Promise<ContratoResumo[]>`, `buscarContrato(id): Promise<Contrato>`, `atualizarContrato(id, patch: ContratoPatch): Promise<Contrato>`, `calcular(id, regioes: RegioesSimuladas): Promise<Calculo>`, `urlPlanilha(id, regioes): string`, `listarMedicoes(id, filtros: FiltrosMedicoes): Promise<ItemMedicao[]>`.
  - `src/api/indices.ts`: `buscarCobertura(): Promise<Cobertura>`.
  - `situacao(faltantes: string[]): { nivel: 'bloqueado' | 'aviso' | 'completo'; texto: string }`; `bloqueado(faltantes): boolean`; `ROTULO_BLOQUEIO: Record<'data_base' | 'regiao_cap' | 'regiao_emulsoes', string>`.
  - `PaginaContrato` passa o `Contrato` às abas por `useOutletContext<Contrato>()`; rotas `/contratos/:id/cadastro|medicoes|calculo` (`/contratos/:id` redireciona para `cadastro`).
  - Testes: `tests/fabricas.ts` com `umContrato(parcial?)`, `umResumo(parcial?)`, `umaCobertura(parcial?)` — usados pelas Tarefas 6 a 8.

- [ ] **Step 1: Fábricas de dados para os testes**

`frontend/tests/fabricas.ts`:

```ts
import type { Cobertura, Contrato, ContratoResumo } from '../src/api/tipos'

export function umContrato(parcial: Partial<Contrato> = {}): Contrato {
  return {
    id: 1,
    numero: '15 00716/2022',
    numero_processo: '50600.000123/2021-11',
    data_base: '2022-01-01',
    edital: '0123/2021-15',
    rodovia: 'BR-230',
    trecho: 'Div. PB/PE',
    subtrecho: 'Entr. BR-104',
    segmento: 'km 10,0 ao km 55,7',
    extensao: '45.7',
    contratada: 'HWN ENGENHARIA LTDA',
    regioes: { CAP: 'Nordeste', EMULSOES: 'Nordeste' },
    faltantes: [],
    atualizado_em: '2026-09-24T10:02:00+00:00',
    ...parcial,
  }
}

export function umResumo(parcial: Partial<ContratoResumo> = {}): ContratoResumo {
  return {
    id: 1,
    numero: '15 00716/2022',
    data_base: '2022-01-01',
    contratada: 'HWN ENGENHARIA LTDA',
    rodovia: 'BR-230',
    regioes: { CAP: 'Nordeste', EMULSOES: 'Nordeste' },
    itens: 48,
    medicoes: 2,
    primeiro_mes: '2023-02-01',
    ultimo_mes: '2023-03-01',
    faltantes: [],
    ...parcial,
  }
}

export function umaCobertura(parcial: Partial<Cobertura> = {}): Cobertura {
  return {
    anp: { de: '2013-01-06', ate: '2026-09-19', registros: 60114, manuais: 0 },
    igp_di: { de: '2022-01-01', ate: '2026-08-01', registros: 56, manuais: 1 },
    regioes: ['Centro-Oeste', 'Nordeste', 'Norte', 'Sudeste', 'Sul'],
    ...parcial,
  }
}
```

- [ ] **Step 2: Testes da situação do contrato**

`frontend/tests/situacao.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { bloqueado, situacao } from '../src/pages/contratos/situacao'

describe('situacao', () => {
  it('Data Base ou região faltando bloqueia o cálculo', () => {
    expect(situacao(['regiao_emulsoes'])).toEqual({ nivel: 'bloqueado', texto: 'Falta região Emulsões' })
    expect(situacao(['edital', 'data_base', 'regiao_cap'])).toEqual({
      nivel: 'bloqueado',
      texto: 'Falta Data Base e região CAP',
    })
    expect(bloqueado(['regiao_cap'])).toBe(true)
  })

  it('só campos de cabeçalho vazios: calcula, com aviso', () => {
    expect(situacao(['edital', 'trecho'])).toEqual({ nivel: 'aviso', texto: '2 campos do cabeçalho vazios' })
    expect(situacao(['edital'])).toEqual({ nivel: 'aviso', texto: '1 campo do cabeçalho vazio' })
    expect(bloqueado(['edital'])).toBe(false)
  })

  it('nada faltando: completo', () => {
    expect(situacao([])).toEqual({ nivel: 'completo', texto: 'Completo' })
  })
})
```

Run: `npm run test -- situacao`
Expected: FAIL — `Failed to resolve import "../src/pages/contratos/situacao"`.

- [ ] **Step 3: Implementar `situacao.ts` e a camada `contratos.ts`**

`frontend/src/pages/contratos/situacao.ts`:

```ts
// Situação de um contrato a partir de `faltantes` (GET /contratos): Data Base e
// regiões bloqueiam o cálculo; campos de cabeçalho vazios só geram aviso na
// planilha.

export const ROTULO_BLOQUEIO = {
  data_base: 'Data Base',
  regiao_cap: 'região CAP',
  regiao_emulsoes: 'região Emulsões',
} as const

type CodigoBloqueio = keyof typeof ROTULO_BLOQUEIO

function ehBloqueio(campo: string): campo is CodigoBloqueio {
  return campo in ROTULO_BLOQUEIO
}

export type Nivel = 'bloqueado' | 'aviso' | 'completo'

export function bloqueado(faltantes: string[]): boolean {
  return faltantes.some(ehBloqueio)
}

export function situacao(faltantes: string[]): { nivel: Nivel; texto: string } {
  const bloqueios = faltantes.filter(ehBloqueio).map((c) => ROTULO_BLOQUEIO[c])
  if (bloqueios.length) return { nivel: 'bloqueado', texto: `Falta ${bloqueios.join(' e ')}` }
  const n = faltantes.length
  if (n === 1) return { nivel: 'aviso', texto: '1 campo do cabeçalho vazio' }
  if (n > 1) return { nivel: 'aviso', texto: `${n} campos do cabeçalho vazios` }
  return { nivel: 'completo', texto: 'Completo' }
}

export const BADGE_NIVEL: Record<Nivel, string> = {
  bloqueado: 'badge badge-danger',
  aviso: 'badge badge-warn',
  completo: 'badge badge-ok',
}
```

`frontend/src/api/contratos.ts`:

```ts
import type { FiltrosMedicoes, RegioesSimuladas } from './chaves'
import { caminhoCom, pedir } from './client'
import type { Calculo, Contrato, ContratoPatch, ContratoResumo, ItemMedicao } from './tipos'

const BASE = '/api/v1/contratos'

export const listarContratos = () => pedir<ContratoResumo[]>(BASE)

export const buscarContrato = (id: number) => pedir<Contrato>(`${BASE}/${id}`)

export const atualizarContrato = (id: number, patch: ContratoPatch) =>
  pedir<Contrato>(`${BASE}/${id}`, { metodo: 'PATCH', json: patch })

function paramsRegioes(regioes: RegioesSimuladas) {
  return { regiao_cap: regioes.cap, regiao_emulsoes: regioes.emulsoes }
}

export const calcular = (id: number, regioes: RegioesSimuladas) =>
  pedir<Calculo>(`${BASE}/${id}/calculo`, { params: paramsRegioes(regioes) })

// O JSON e o arquivo saem da mesma função no backend; os mesmos parâmetros
// garantem que a planilha baixada é a tabela da tela.
export const urlPlanilha = (id: number, regioes: RegioesSimuladas) =>
  caminhoCom(`${BASE}/${id}/planilha`, paramsRegioes(regioes))

export const listarMedicoes = (id: number, filtros: FiltrosMedicoes) =>
  pedir<ItemMedicao[]>(`${BASE}/${id}/medicoes`, {
    params: { mes: filtros.mes, no_calculo: filtros.noCalculo, q: filtros.q },
  })
```

`frontend/src/api/indices.ts`:

```ts
import { pedir } from './client'
import type { Cobertura } from './tipos'

const BASE = '/api/v1/indices'

export const buscarCobertura = () => pedir<Cobertura>(`${BASE}/cobertura`)
```

Run: `npm run test -- situacao`
Expected: PASS.

- [ ] **Step 4: Testes da lista de contratos e da página do contrato**

`frontend/tests/contratos.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { umContrato, umaCobertura, umResumo } from './fabricas'
import { renderApp } from './render'
import { servidor } from './servidor'

function comContratos(lista: unknown[]) {
  servidor.use(http.get('/api/v1/contratos', () => HttpResponse.json(lista)))
}

describe('Lista de contratos', () => {
  it('mostra a situação e aponta o número para cadastro ou cálculo', async () => {
    comContratos([
      umResumo({ id: 1, numero: '15 00716/2022' }),
      umResumo({ id: 2, numero: '15 00800/2023', faltantes: ['regiao_emulsoes'], regioes: { CAP: 'Sul' } }),
      umResumo({ id: 3, numero: '15 00900/2024', faltantes: ['edital'] }),
    ])
    renderApp('/')
    const linha1 = (await screen.findByText('15 00716/2022')).closest('tr')!
    expect(within(linha1).getByText('Completo')).toHaveClass('badge-ok')
    expect(within(linha1).getByRole('link', { name: '15 00716/2022' })).toHaveAttribute('href', '/contratos/1/calculo')
    expect(within(linha1).getByText('jan/2022')).toBeInTheDocument()
    expect(within(linha1).getByText('fev/2023 – mar/2023')).toBeInTheDocument()

    const linha2 = screen.getByText('15 00800/2023').closest('tr')!
    expect(within(linha2).getByText('Falta região Emulsões')).toHaveClass('badge-danger')
    expect(within(linha2).getByRole('link', { name: '15 00800/2023' })).toHaveAttribute('href', '/contratos/2/cadastro')

    const linha3 = screen.getByText('15 00900/2024').closest('tr')!
    expect(within(linha3).getByText('1 campo do cabeçalho vazio')).toHaveClass('badge-warn')
  })

  it('pesquisa por número', async () => {
    comContratos([umResumo({ id: 1, numero: '15 00716/2022' }), umResumo({ id: 2, numero: '15 00800/2023' })])
    const { usuario } = renderApp('/contratos')
    await screen.findByText('15 00716/2022')
    await usuario.type(screen.getByLabelText('Pesquisar contrato'), '800')
    expect(screen.queryByText('15 00716/2022')).not.toBeInTheDocument()
    expect(screen.getByText('15 00800/2023')).toBeInTheDocument()
  })

  it('sem contratos convida a enviar PDFs', async () => {
    comContratos([])
    renderApp('/')
    expect(await screen.findByText('Nenhum contrato ainda.')).toBeInTheDocument()
    for (const link of screen.getAllByRole('link', { name: 'Enviar PDFs' })) {
      expect(link).toHaveAttribute('href', '/upload')
    }
  })
})

describe('Página do contrato', () => {
  it('404 mostra "não encontrado"', async () => {
    servidor.use(
      http.get('/api/v1/contratos/9', () => HttpResponse.json({ detail: 'Contrato 9 não encontrado.' }, { status: 404 })),
    )
    renderApp('/contratos/9/cadastro')
    expect(await screen.findByText('Contrato 9 não encontrado.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Voltar aos contratos' })).toBeInTheDocument()
  })

  it('/contratos/:id abre a aba Cadastro', async () => {
    servidor.use(
      http.get('/api/v1/contratos/1', () => HttpResponse.json(umContrato())),
      http.get('/api/v1/indices/cobertura', () => HttpResponse.json(umaCobertura())),
    )
    renderApp('/contratos/1')
    expect(await screen.findByRole('heading', { name: '15 00716/2022' })).toBeInTheDocument()
    expect(screen.getByTestId('local')).toHaveTextContent('/contratos/1/cadastro')
    expect(screen.getByRole('link', { name: 'Cadastro' })).toHaveAttribute('aria-current', 'page')
  })
})
```

Run: `npm run test -- contratos`
Expected: FAIL — as rotas não existem ("Não encontrado").

- [ ] **Step 5: Implementar a lista e a página do contrato**

`frontend/src/pages/contratos/ListaContratos.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'
import { chaves } from '../../api/chaves'
import { listarContratos } from '../../api/contratos'
import type { ContratoResumo } from '../../api/tipos'
import { Cabecalho } from '../../components/Cabecalho'
import { Carregando } from '../../components/Carregando'
import { Icone } from '../../components/Icone'
import { MensagemErro } from '../../components/MensagemErro'
import { mesAno } from '../../lib/formato'
import { BADGE_NIVEL, bloqueado, situacao } from './situacao'

function periodo(c: ContratoResumo) {
  if (!c.primeiro_mes) return '—'
  if (c.primeiro_mes === c.ultimo_mes) return mesAno(c.primeiro_mes)
  return `${mesAno(c.primeiro_mes)} – ${mesAno(c.ultimo_mes)}`
}

function BotaoEnviar() {
  return (
    <Link to="/upload" className="btn btn-primary">
      <Icone nome="upload_file" />
      <span>Enviar PDFs</span>
    </Link>
  )
}

export function ListaContratos() {
  const [busca, setBusca] = useState('')
  const consulta = useQuery({ queryKey: chaves.contratos, queryFn: listarContratos })
  const termo = busca.trim().toLowerCase()
  const lista = (consulta.data ?? []).filter((c) => c.numero.toLowerCase().includes(termo))

  return (
    <>
      <Cabecalho
        titulo="Contratos"
        subtitulo="Contratos extraídos dos PDFs de medição. Abra um para completar o cadastro, conferir as medições e gerar a planilha."
        acoes={<BotaoEnviar />}
      />
      <MensagemErro erro={consulta.error} />
      {consulta.isPending && <Carregando />}
      {consulta.data?.length === 0 && (
        <div className="panel">
          <div className="empty-state">
            <p className="headline-sm">Nenhum contrato ainda.</p>
            <p className="muted">Os contratos aparecem aqui depois que os PDFs do Resumo da Medição são processados.</p>
            <BotaoEnviar />
          </div>
        </div>
      )}
      {!!consulta.data?.length && (
        <div className="panel">
          <div className="panel-head">
            <div className="inline-form">
              <label className="field-label" htmlFor="busca-contrato">
                Pesquisar contrato
              </label>
              <input
                id="busca-contrato"
                className="input"
                placeholder="Número do contrato"
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
              />
            </div>
          </div>
          <div className="panel-body flush table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Contrato</th>
                  <th>Contratada</th>
                  <th>Rodovia</th>
                  <th>Data Base</th>
                  <th>Região CAP</th>
                  <th>Região Emulsões</th>
                  <th className="num">Medições</th>
                  <th>Período</th>
                  <th>Situação</th>
                </tr>
              </thead>
              <tbody>
                {lista.map((c) => {
                  const s = situacao(c.faltantes)
                  const aba = bloqueado(c.faltantes) ? 'cadastro' : 'calculo'
                  return (
                    <tr key={c.id}>
                      <td>
                        <Link className="cell-title" to={`/contratos/${c.id}/${aba}`}>
                          {c.numero}
                        </Link>
                      </td>
                      <td>{c.contratada ?? '—'}</td>
                      <td>{c.rodovia ?? '—'}</td>
                      <td>{mesAno(c.data_base)}</td>
                      <td>{c.regioes.CAP ?? '—'}</td>
                      <td>{c.regioes.EMULSOES ?? '—'}</td>
                      <td className="num">{c.medicoes}</td>
                      <td>{periodo(c)}</td>
                      <td>
                        <span className={BADGE_NIVEL[s.nivel]}>{s.texto}</span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {lista.length === 0 && <p className="empty-state muted">Nenhum contrato com “{busca}”.</p>}
          </div>
        </div>
      )}
    </>
  )
}
```

`frontend/src/pages/contrato/PaginaContrato.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query'
import { Link, NavLink, Outlet, useParams } from 'react-router'
import { chaves } from '../../api/chaves'
import { buscarContrato } from '../../api/contratos'
import { ErroApi } from '../../api/erros'
import { Cabecalho } from '../../components/Cabecalho'
import { Carregando } from '../../components/Carregando'
import { MensagemErro } from '../../components/MensagemErro'
import { NaoEncontrado } from '../../components/NaoEncontrado'

const ABAS = [
  { para: 'cadastro', rotulo: 'Cadastro' },
  { para: 'medicoes', rotulo: 'Medições' },
  { para: 'calculo', rotulo: 'Cálculo e exportação' },
]

export function PaginaContrato() {
  const id = Number(useParams().id)
  const valido = Number.isInteger(id) && id > 0
  const consulta = useQuery({ queryKey: chaves.contrato(id), queryFn: () => buscarContrato(id), enabled: valido })

  if (!valido) return <NaoEncontrado mensagem="Contrato não encontrado." />
  if (consulta.error instanceof ErroApi && consulta.error.status === 404) {
    return <NaoEncontrado mensagem={consulta.error.detail} />
  }
  if (consulta.error) return <MensagemErro erro={consulta.error} />
  if (!consulta.data) return <Carregando />

  const contrato = consulta.data
  return (
    <>
      <Cabecalho
        trilha={<Link to="/contratos">Contratos</Link>}
        titulo={contrato.numero}
        subtitulo={contrato.contratada ?? 'Contratada não informada'}
      />
      <nav className="tabs" aria-label="Seções do contrato">
        {ABAS.map((aba) => (
          <NavLink key={aba.para} to={aba.para} className={({ isActive }) => (isActive ? 'tab active' : 'tab')}>
            {aba.rotulo}
          </NavLink>
        ))}
      </nav>
      <Outlet context={contrato} />
    </>
  )
}
```

`NavLink` já põe `aria-current="page"` no ativo.

Rotas em `frontend/src/App.tsx` (as abas Medições e Cálculo entram nas Tarefas 6 e 7; até lá o `*` responde):

```tsx
import { Navigate, Route, Routes } from 'react-router'
import { NaoEncontrado } from './components/NaoEncontrado'
import { Shell } from './components/Shell'
import { AbaCadastro } from './pages/contrato/AbaCadastro'
import { PaginaContrato } from './pages/contrato/PaginaContrato'
import { ListaContratos } from './pages/contratos/ListaContratos'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<ListaContratos />} />
        <Route path="contratos" element={<ListaContratos />} />
        <Route path="contratos/:id" element={<PaginaContrato />}>
          <Route index element={<Navigate to="cadastro" replace />} />
          <Route path="cadastro" element={<AbaCadastro />} />
        </Route>
        <Route path="*" element={<NaoEncontrado />} />
      </Route>
    </Routes>
  )
}
```

Para o teste de rota rodar antes da aba existir de verdade, crie já `AbaCadastro` como `export function AbaCadastro() { return null }`; o Step 7 a implementa.

Run: `npm run test -- contratos`
Expected: PASS (5 testes).

- [ ] **Step 6: Testes da aba Cadastro**

`frontend/tests/cadastro.test.tsx`:

```tsx
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Contrato } from '../src/api/tipos'
import { umContrato, umaCobertura } from './fabricas'
import { renderApp } from './render'
import { servidor } from './servidor'

function preparar(contrato: Contrato) {
  let atual = contrato
  const recebidos: unknown[] = []
  servidor.use(
    http.get('/api/v1/contratos/1', () => HttpResponse.json(atual)),
    http.get('/api/v1/indices/cobertura', () => HttpResponse.json(umaCobertura())),
    http.patch('/api/v1/contratos/1', async ({ request }) => {
      const corpo = (await request.json()) as Record<string, unknown>
      recebidos.push(corpo)
      const regioes = { ...atual.regioes, ...(corpo.regioes as object) }
      atual = { ...atual, ...corpo, regioes, faltantes: [] } as Contrato
      return HttpResponse.json(atual)
    }),
  )
  return recebidos
}

describe('Aba Cadastro', () => {
  it('mostra pendências dos parâmetros e dos campos de cabeçalho', async () => {
    preparar(umContrato({ regioes: { CAP: 'Nordeste' }, edital: null, trecho: null, faltantes: ['edital', 'trecho', 'regiao_emulsoes'] }))
    renderApp('/contratos/1/cadastro')
    expect(await screen.findByText('1 pendente — cálculo bloqueado')).toBeInTheDocument()
    expect(screen.getByText('2 vazios — sairá com aviso')).toBeInTheDocument()
    expect(screen.getByLabelText('Nº do processo')).toHaveAttribute('readonly')
    expect(screen.getByLabelText('Data Base')).toHaveValue('2022-01')
    expect(screen.getByLabelText('Extensão (km)')).toHaveValue('45,7')
  })

  it('salva só o que mudou e volta a mostrar completo', async () => {
    const recebidos = preparar(umContrato({ regioes: { CAP: 'Nordeste' }, faltantes: ['regiao_emulsoes'] }))
    const { usuario } = renderApp('/contratos/1/cadastro')
    await usuario.selectOptions(await screen.findByLabelText('Região ANP — Emulsões'), 'Sul')
    await usuario.clear(screen.getByLabelText('Trecho'))
    await usuario.click(screen.getByRole('button', { name: 'Salvar' }))
    await waitFor(() => expect(recebidos).toHaveLength(1))
    expect(recebidos[0]).toEqual({ trecho: null, regioes: { EMULSOES: 'Sul' } })
    expect(await screen.findByText('Cadastro salvo.')).toBeInTheDocument()
    expect(screen.getByText('Parâmetros completos')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled()
  })

  it('erro do backend aparece no campo', async () => {
    preparar(umContrato())
    servidor.use(
      http.patch('/api/v1/contratos/1', () =>
        HttpResponse.json(
          { detail: "Região 'Sul' sem preços ANP do CAP 50/70. Regiões disponíveis: Nordeste." },
          { status: 422 },
        ),
      ),
    )
    const { usuario } = renderApp('/contratos/1/cadastro')
    await usuario.selectOptions(await screen.findByLabelText('Região ANP — CAP'), 'Sul')
    await usuario.click(screen.getByRole('button', { name: 'Salvar' }))
    const erro = await screen.findByText(/sem preços ANP do CAP 50\/70/)
    expect(erro).toHaveClass('erro-campo')
    expect(screen.getByLabelText('Região ANP — CAP')).toHaveAttribute('aria-invalid', 'true')
  })

  it('descartar volta ao que está gravado', async () => {
    preparar(umContrato())
    const { usuario } = renderApp('/contratos/1/cadastro')
    const rodovia = await screen.findByLabelText('Rodovia')
    await usuario.clear(rodovia)
    await usuario.type(rodovia, 'BR-999')
    await usuario.click(screen.getByRole('button', { name: 'Descartar' }))
    expect(rodovia).toHaveValue('BR-230')
    expect(screen.getByRole('button', { name: 'Descartar' })).toBeDisabled()
  })
})
```

Run: `npm run test -- cadastro`
Expected: FAIL — `AbaCadastro` ainda é o esboço que devolve `null`.

- [ ] **Step 7: Implementar `cadastro.ts` e `AbaCadastro.tsx`**

`frontend/src/pages/contrato/cadastro.ts`:

```ts
import { ErroApi } from '../../api/erros'
import type { CampoCadastro, Contrato, ContratoPatch, Familia } from '../../api/tipos'
import { exato } from '../../lib/formato'

// O formulário do cadastro como strings; a API recebe só o que mudou.

export interface ValoresCadastro {
  data_base: string // AAAA-MM, do <input type="month">
  regiao_CAP: string
  regiao_EMULSOES: string
  contratada: string
  edital: string
  rodovia: string
  trecho: string
  subtrecho: string
  segmento: string
  extensao: string // como o usuário digita: "45,7"
}

export type CampoForm = keyof ValoresCadastro

export const PARAMETROS: { campo: CampoForm; rotulo: string }[] = [
  { campo: 'data_base', rotulo: 'Data Base' },
  { campo: 'regiao_CAP', rotulo: 'Região ANP — CAP' },
  { campo: 'regiao_EMULSOES', rotulo: 'Região ANP — Emulsões' },
]

export const CABECALHO: { campo: CampoCadastro; rotulo: string }[] = [
  { campo: 'contratada', rotulo: 'Contratada' },
  { campo: 'edital', rotulo: 'Edital' },
  { campo: 'rodovia', rotulo: 'Rodovia' },
  { campo: 'trecho', rotulo: 'Trecho' },
  { campo: 'subtrecho', rotulo: 'Subtrecho' },
  { campo: 'segmento', rotulo: 'Segmento' },
  { campo: 'extensao', rotulo: 'Extensão (km)' },
]

export function valoresIniciais(c: Contrato): ValoresCadastro {
  return {
    data_base: c.data_base ? c.data_base.slice(0, 7) : '',
    regiao_CAP: c.regioes.CAP ?? '',
    regiao_EMULSOES: c.regioes.EMULSOES ?? '',
    contratada: c.contratada ?? '',
    edital: c.edital ?? '',
    rodovia: c.rodovia ?? '',
    trecho: c.trecho ?? '',
    subtrecho: c.subtrecho ?? '',
    segmento: c.segmento ?? '',
    extensao: c.extensao ? exato(c.extensao).replace(/\./g, '') : '',
  }
}

export function montarPatch(v: ValoresCadastro, sujos: Partial<Record<CampoForm, unknown>>): ContratoPatch {
  const patch: ContratoPatch = {}
  for (const { campo } of CABECALHO) {
    if (sujos[campo]) patch[campo] = v[campo].trim() || null
  }
  if (sujos.data_base) patch.data_base = v.data_base
  const regioes: Partial<Record<Familia, string>> = {}
  if (sujos.regiao_CAP && v.regiao_CAP) regioes.CAP = v.regiao_CAP
  if (sujos.regiao_EMULSOES && v.regiao_EMULSOES) regioes.EMULSOES = v.regiao_EMULSOES
  if (Object.keys(regioes).length) patch.regioes = regioes
  return patch
}

export function pendenciasParametros(v: ValoresCadastro): number {
  return PARAMETROS.filter(({ campo }) => !v[campo]).length
}

export function vaziosCabecalho(v: ValoresCadastro): number {
  return CABECALHO.filter(({ campo }) => !v[campo].trim()).length
}

// A recusa do PATCH é uma frase só (CadastroInvalido); este mapa decide em qual
// campo mostrá-la. A validação do Pydantic já vem por campo.
export function campoDoErro(erro: ErroApi, v: ValoresCadastro): Partial<Record<CampoForm | 'geral', string>> {
  if (Object.keys(erro.campos).length) {
    const saida: Partial<Record<CampoForm | 'geral', string>> = {}
    for (const [loc, msg] of Object.entries(erro.campos)) {
      const campo = loc.replace(/^regioes\./, 'regiao_') as CampoForm
      saida[campo in v ? campo : 'geral'] = msg
    }
    return saida
  }
  if (/Data Base/.test(erro.detail)) return { data_base: erro.detail }
  if (/Região/.test(erro.detail)) {
    const familia = (['CAP', 'EMULSOES'] as const).find((f) => {
      const valor = v[`regiao_${f}`]
      return valor && erro.detail.includes(`'${valor}'`)
    })
    if (familia) return { [`regiao_${familia}`]: erro.detail }
  }
  return { geral: erro.detail }
}
```

`frontend/src/pages/contrato/AbaCadastro.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useOutletContext } from 'react-router'
import { chaves } from '../../api/chaves'
import { atualizarContrato } from '../../api/contratos'
import { ErroApi } from '../../api/erros'
import { buscarCobertura } from '../../api/indices'
import { aposCadastro } from '../../api/invalidar'
import type { Contrato } from '../../api/tipos'
import { MensagemErro } from '../../components/MensagemErro'
import {
  CABECALHO, campoDoErro, montarPatch, PARAMETROS, pendenciasParametros, vaziosCabecalho,
  valoresIniciais, type CampoForm, type ValoresCadastro,
} from './cadastro'

function plural(n: number, um: string, varios: string) {
  return `${n} ${n === 1 ? um : varios}`
}

export function AbaCadastro() {
  const contrato = useOutletContext<Contrato>()
  const qc = useQueryClient()
  const cobertura = useQuery({ queryKey: chaves.cobertura, queryFn: buscarCobertura })
  const form = useForm<ValoresCadastro>({ defaultValues: valoresIniciais(contrato) })
  const { register, handleSubmit, reset, watch, setError, formState } = form
  const [erroGeral, setErroGeral] = useState<unknown>(null)
  const [salvo, setSalvo] = useState(false)

  // Contrato relido do banco (depois de salvar ou de outra aba): o formulário
  // passa a partir dele.
  useEffect(() => reset(valoresIniciais(contrato)), [contrato, reset])

  const salvar = useMutation({
    mutationFn: (v: ValoresCadastro) => atualizarContrato(contrato.id, montarPatch(v, formState.dirtyFields)),
    onSuccess: async (atualizado) => {
      qc.setQueryData(chaves.contrato(contrato.id), atualizado)
      reset(valoresIniciais(atualizado))
      setSalvo(true)
      await aposCadastro(qc, contrato.id)
    },
    onError: (erro, v) => {
      if (!(erro instanceof ErroApi)) return setErroGeral(erro)
      for (const [campo, msg] of Object.entries(campoDoErro(erro, v))) {
        if (campo === 'geral') setErroGeral(new ErroApi(erro.status, msg!))
        else setError(campo as CampoForm, { type: 'servidor', message: msg })
      }
    },
  })

  const valores = watch()
  const pendentes = pendenciasParametros(valores)
  const vazios = vaziosCabecalho(valores)
  const regioes = cobertura.data?.regioes ?? []

  function opcoesRegiao(atual: string) {
    const lista = atual && !regioes.includes(atual) ? [atual, ...regioes] : regioes
    return lista.map((r) => (
      <option key={r} value={r}>
        {r}
      </option>
    ))
  }

  function erroDo(campo: CampoForm) {
    const msg = formState.errors[campo]?.message
    return msg ? (
      <p className="erro-campo" id={`erro-${campo}`}>
        {msg}
      </p>
    ) : null
  }

  function atributosDeErro(campo: CampoForm) {
    const tem = !!formState.errors[campo]
    return { 'aria-invalid': tem || undefined, 'aria-describedby': tem ? `erro-${campo}` : undefined }
  }

  return (
    <form
      onSubmit={handleSubmit((v) => {
        setErroGeral(null)
        setSalvo(false)
        salvar.mutate(v)
      })}
    >
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2 className="panel-title">Parâmetros do cálculo</h2>
            <p className="panel-subtitle">Na exportação dá para simular outra região sem alterar este cadastro.</p>
          </div>
          <span className={pendentes ? 'badge badge-danger' : 'badge badge-ok'}>
            {pendentes ? `${plural(pendentes, 'pendente', 'pendentes')} — cálculo bloqueado` : 'Parâmetros completos'}
          </span>
        </div>
        <div className="panel-body field-grid">
          <div className="field">
            <label className="field-label" htmlFor="data_base">
              Data Base <span className="field-required">*</span>
            </label>
            <input id="data_base" type="month" className="input" {...register('data_base')} {...atributosDeErro('data_base')} />
            <p className="field-hint">Sugerida pelo PDF; mês e ano.</p>
            {erroDo('data_base')}
          </div>
          {PARAMETROS.slice(1).map(({ campo, rotulo }) => (
            <div className="field" key={campo}>
              <label className="field-label" htmlFor={campo}>
                {rotulo} <span className="field-required">*</span>
              </label>
              <select id={campo} className="input" {...register(campo)} {...atributosDeErro(campo)}>
                <option value="">Escolha a região</option>
                {opcoesRegiao(valores[campo])}
              </select>
              {erroDo(campo)}
            </div>
          ))}
        </div>
      </section>

      <section className="panel mt-md">
        <div className="panel-head">
          <div>
            <h2 className="panel-title">Cabeçalho da planilha</h2>
            <p className="panel-subtitle">Campos impressos no bloco de identificação do Reequilíbrio.</p>
          </div>
          <span className={vazios ? 'badge badge-warn' : 'badge badge-ok'}>
            {vazios ? `${plural(vazios, 'vazio', 'vazios')} — sairá com aviso` : 'Cabeçalho completo'}
          </span>
        </div>
        <div className="panel-body field-grid">
          <div className="field">
            <label className="field-label" htmlFor="numero_processo">
              Nº do processo
            </label>
            <input id="numero_processo" className="input" readOnly value={contrato.numero_processo ?? ''} />
            <p className="field-hint">Vem do PDF.</p>
          </div>
          {CABECALHO.map(({ campo, rotulo }) => (
            <div className="field" key={campo}>
              <label className="field-label" htmlFor={campo}>
                {rotulo}
              </label>
              <input
                id={campo}
                className="input"
                inputMode={campo === 'extensao' ? 'decimal' : undefined}
                {...register(campo)}
                {...atributosDeErro(campo)}
              />
              {erroDo(campo)}
            </div>
          ))}
        </div>
      </section>

      <MensagemErro erro={erroGeral} />
      <div className="barra mt-md">
        {salvo && !formState.isDirty && (
          <p className="status-message" role="status">
            Cadastro salvo.
          </p>
        )}
        <span className="espaco" />
        <button type="button" className="btn" disabled={!formState.isDirty || salvar.isPending} onClick={() => reset()}>
          Descartar
        </button>
        <button type="submit" className="btn btn-primary" disabled={!formState.isDirty || salvar.isPending}>
          Salvar
        </button>
      </div>
    </form>
  )
}
```

`reset()` sem argumento volta aos últimos `defaultValues` — os do contrato gravado, porque cada `reset(valoresIniciais(...))` os redefine.

Run: `npm run test -- cadastro contratos situacao`
Expected: PASS.

- [ ] **Step 8: Rodar tudo e commitar**

Run: `npm run test && npm run build`
Expected: todos os testes passam; build sem erro de tipo.

```bash
git add frontend/src/App.tsx frontend/src/api/contratos.ts frontend/src/api/indices.ts \
  frontend/src/pages/contratos frontend/src/pages/contrato frontend/tests
git commit -m "$(cat <<'EOF'
feat(frontend): lista de contratos e aba Cadastro

Lista pesquisável com a situação derivada de faltantes (bloqueado, aviso,
completo) e o número apontando para cadastro ou cálculo. Página do contrato
com abas por rota; cadastro sempre editável, que grava só o que mudou e
mostra a recusa do backend no campo correspondente.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarefa 6: Aba Cálculo e exportação, com simulação na URL

**Files:**
- Create: `frontend/src/pages/contrato/{AbaCalculo.tsx,TabelaCalculo.tsx,bloqueio.ts}`
- Modify: `frontend/src/App.tsx` (rota `calculo`)
- Modify: `frontend/src/styles/telas.css` (linhas de grupo, subtotal e total da tabela)
- Create: `frontend/tests/{bloqueio.test.ts,calculo.test.tsx}`

**Interfaces:**
- Consumes: `calcular`, `urlPlanilha` (Tarefa 5); `buscarCobertura`; `chaves.calculo(id, regioes)`, `RegioesSimuladas`; `ErroApi.faltando`; `useOutletContext<Contrato>()`; `umContrato`, `umaCobertura` (fábricas).
- Produces:
  - `regioesDaUrl(busca: URLSearchParams): RegioesSimuladas` e `destinoDoFaltante(item: string, contratoId: number): { texto: string; para: string | null; rotulo: string | null }` (`bloqueio.ts`).
  - `TabelaCalculo({ calculo })` — reutilizável; `AbaCalculo()`.
  - Parâmetros de URL `regiao_cap` e `regiao_emulsoes` (os mesmos nomes da API).

- [ ] **Step 1: Testes do mapeamento de `faltando`**

`frontend/tests/bloqueio.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { destinoDoFaltante, regioesDaUrl } from '../src/pages/contrato/bloqueio'

describe('destinoDoFaltante', () => {
  it('campos do cadastro levam à aba Cadastro', () => {
    expect(destinoDoFaltante('data_base', 7)).toEqual({
      texto: 'Falta a Data Base do contrato.',
      para: '/contratos/7/cadastro',
      rotulo: 'Abrir cadastro',
    })
    expect(destinoDoFaltante('regiao_emulsoes', 7).texto).toBe('Falta a região ANP das Emulsões.')
    expect(destinoDoFaltante('regiao_cap', 7).para).toBe('/contratos/7/cadastro')
  })

  it('índices levam à tela de índices, com o texto do backend', () => {
    const anp = 'Sem preço ANP de Cimento Asfáltico de Petróleo 50 70 (R$/kg) para a região Sul em 01/2023 (mês anterior à medição).'
    expect(destinoDoFaltante(anp, 7)).toEqual({ texto: anp, para: '/indices/anp', rotulo: 'Abrir índices ANP' })
    const igp = 'Sem valor de IGP - DI para 02/2023 (mês da medição).'
    expect(destinoDoFaltante(igp, 7)).toEqual({ texto: igp, para: '/indices/igp-di', rotulo: 'Abrir IGP-DI' })
    expect(destinoDoFaltante("regiao_cap: região 'Marte' sem preços ANP", 7).para).toBe('/indices/anp')
  })

  it('o resto aparece sem link', () => {
    expect(destinoDoFaltante('Família desconhecida: X', 7)).toEqual({
      texto: 'Família desconhecida: X',
      para: null,
      rotulo: null,
    })
  })
})

describe('regioesDaUrl', () => {
  it('lê só os parâmetros preenchidos', () => {
    expect(regioesDaUrl(new URLSearchParams('regiao_cap=Sul'))).toEqual({ cap: 'Sul' })
    expect(regioesDaUrl(new URLSearchParams('regiao_cap=&regiao_emulsoes=Norte'))).toEqual({ emulsoes: 'Norte' })
  })
})
```

Run: `npm run test -- bloqueio`
Expected: FAIL — módulo não existe.

- [ ] **Step 2: Implementar `bloqueio.ts`**

`frontend/src/pages/contrato/bloqueio.ts`:

```ts
import type { RegioesSimuladas } from '../../api/chaves'

// O 422 do cálculo traz em `faltando` códigos de campo do cadastro e frases
// sobre índices. Aqui cada item vira texto e atalho para onde se resolve.

const CAMPOS: Record<string, string> = {
  data_base: 'Falta a Data Base do contrato.',
  regiao_cap: 'Falta a região ANP do CAP.',
  regiao_emulsoes: 'Falta a região ANP das Emulsões.',
}

export function destinoDoFaltante(item: string, contratoId: number) {
  if (item in CAMPOS) {
    return { texto: CAMPOS[item], para: `/contratos/${contratoId}/cadastro`, rotulo: 'Abrir cadastro' }
  }
  if (/ANP/.test(item)) return { texto: item, para: '/indices/anp', rotulo: 'Abrir índices ANP' }
  if (/IGP/.test(item)) return { texto: item, para: '/indices/igp-di', rotulo: 'Abrir IGP-DI' }
  return { texto: item, para: null, rotulo: null }
}

export function regioesDaUrl(busca: URLSearchParams): RegioesSimuladas {
  const regioes: RegioesSimuladas = {}
  const cap = busca.get('regiao_cap')
  const emulsoes = busca.get('regiao_emulsoes')
  if (cap) regioes.cap = cap
  if (emulsoes) regioes.emulsoes = emulsoes
  return regioes
}
```

Run: `npm run test -- bloqueio`
Expected: PASS.

- [ ] **Step 3: Testes da aba Cálculo**

`frontend/tests/calculo.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Calculo } from '../src/api/tipos'
import { umContrato, umaCobertura } from './fabricas'
import { renderApp } from './render'
import { servidor } from './servidor'

function umCalculo(parcial: Partial<Calculo> = {}): Calculo {
  return {
    contrato: { id: 1, numero: '15 00716/2022' },
    parametros: { data_base: '2022-01-01', regioes: { CAP: 'Nordeste', EMULSOES: 'Nordeste' }, simulacao: false, lucro: '0.0511' },
    familias: [
      {
        familia: 'CAP',
        rotulo: 'CAP',
        subtotal: '-38275.68',
        produtos: [
          {
            descricao: 'Aquisição de CAP 50/70',
            subtotal: '-38275.68',
            linhas: [
              { mes: '2023-02-01', a: '412300.00', fator: '0.1480', b: '61020.40', d: '0.049812',
                c: '20537.4876', e: '-40482.9124', f: '-38275.68' },
            ],
          },
        ],
      },
    ],
    total: '-38275.68',
    avisos: ['Campo(s) do cadastro vazio(s): edital.'],
    arquivo: 'Reequilibrio_15_00716-2022.xlsx',
    ...parcial,
  }
}

function preparar(resposta: (url: URL) => Response) {
  const pedidos: URL[] = []
  servidor.use(
    http.get('/api/v1/contratos/1', () => HttpResponse.json(umContrato())),
    http.get('/api/v1/indices/cobertura', () => HttpResponse.json(umaCobertura())),
    http.get('/api/v1/contratos/1/calculo', ({ request }) => {
      const url = new URL(request.url)
      pedidos.push(url)
      return resposta(url)
    }),
  )
  return pedidos
}

describe('Aba Cálculo', () => {
  it('tabela espelha a planilha: letras, grupos, subtotal, total e negativos', async () => {
    preparar(() => HttpResponse.json(umCalculo()))
    renderApp('/contratos/1/calculo')
    const tabela = await screen.findByRole('table')
    for (const letra of ['a', 'b', 'd', 'c = a·d', 'e = c − b', 'f = e·(1 − 5,11%)']) {
      expect(within(tabela).getByText(letra)).toBeInTheDocument()
    }
    expect(within(tabela).getByText('Aquisição de CAP 50/70')).toBeInTheDocument()
    const linha = within(tabela).getByText('fev/2023').closest('tr')!
    expect(within(linha).getByText('412.300,00')).toBeInTheDocument()
    expect(within(linha).getByText('0,049812')).toBeInTheDocument()
    expect(within(linha).getByText('-40.482,91')).toHaveClass('neg')
    expect(within(tabela).getByText('Total geral').closest('tr')).toHaveTextContent('-38.275,68')
    expect(screen.getByText('Campo(s) do cadastro vazio(s): edital.')).toBeInTheDocument()
    expect(screen.getByText('Data Base: jan/2022')).toBeInTheDocument()
  })

  it('simulação vai para a URL, mostra o aviso e muda o link de download', async () => {
    const pedidos = preparar((url) =>
      HttpResponse.json(
        url.searchParams.get('regiao_cap')
          ? umCalculo({
              parametros: { data_base: '2022-01-01', regioes: { CAP: 'Sul', EMULSOES: 'Nordeste' }, simulacao: true, lucro: '0.0511' },
              arquivo: 'Reequilibrio_15_00716-2022_SIMULACAO_CAP-Sul.xlsx',
            })
          : umCalculo(),
      ),
    )
    const { usuario } = renderApp('/contratos/1/calculo')
    const baixar = await screen.findByRole('link', { name: 'Baixar planilha (.xlsx)' })
    expect(baixar).toHaveAttribute('href', '/api/v1/contratos/1/planilha')

    await usuario.selectOptions(screen.getByLabelText('Região CAP'), 'Sul')
    expect(screen.getByTestId('local')).toHaveTextContent('/contratos/1/calculo?regiao_cap=Sul')
    const faixa = await screen.findByText(/Simulação/)
    expect(faixa.closest('.notice')).toHaveTextContent('CAP em Sul (cadastro: Nordeste)')
    expect(faixa.closest('.notice')).toHaveTextContent('Reequilibrio_15_00716-2022_SIMULACAO_CAP-Sul.xlsx')
    expect(baixar).toHaveAttribute('href', '/api/v1/contratos/1/planilha?regiao_cap=Sul')
    expect(pedidos.at(-1)!.searchParams.get('regiao_cap')).toBe('Sul')

    await usuario.click(screen.getByRole('button', { name: 'Voltar ao cadastro' }))
    expect(screen.getByTestId('local')).toHaveTextContent(/^\/contratos\/1\/calculo$/)
    expect(screen.queryByText(/Simulação/)).not.toBeInTheDocument()
  })

  it('escolher a região do cadastro tira o parâmetro da URL', async () => {
    preparar(() => HttpResponse.json(umCalculo()))
    const { usuario } = renderApp('/contratos/1/calculo?regiao_cap=Sul')
    await usuario.selectOptions(await screen.findByLabelText('Região CAP'), 'Nordeste')
    expect(screen.getByTestId('local')).toHaveTextContent(/^\/contratos\/1\/calculo$/)
  })

  it('bloqueado lista todos os faltantes com atalhos', async () => {
    preparar(() =>
      HttpResponse.json(
        {
          detail: 'Não é possível calcular:\n- regiao_emulsoes\n- Sem valor de IGP - DI para 02/2023 (mês da medição).',
          faltando: ['regiao_emulsoes', 'Sem valor de IGP - DI para 02/2023 (mês da medição).'],
        },
        { status: 422 },
      ),
    )
    renderApp('/contratos/1/calculo')
    const caixa = (await screen.findByText('Cálculo bloqueado')).closest('.notice')!
    expect(within(caixa as HTMLElement).getByText('Falta a região ANP das Emulsões.')).toBeInTheDocument()
    expect(within(caixa as HTMLElement).getByRole('link', { name: 'Abrir cadastro' })).toHaveAttribute('href', '/contratos/1/cadastro')
    expect(within(caixa as HTMLElement).getByRole('link', { name: 'Abrir IGP-DI' })).toHaveAttribute('href', '/indices/igp-di')
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Baixar planilha (.xlsx)' })).not.toBeInTheDocument()
  })
})
```

Run: `npm run test -- calculo`
Expected: FAIL — rota `calculo` não existe.

- [ ] **Step 4: Implementar a tabela e a aba**

Acrescentar ao fim de `frontend/src/styles/telas.css`:

```css
/* Tabela do cálculo: grupos família → produto, subtotal e total, como na planilha. */
.data-table tr.linha-familia td {
  background: var(--surface-container-high);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.data-table tr.linha-produto td {
  background: var(--surface-container);
  font-weight: 600;
}

.data-table tr.linha-subtotal td {
  height: var(--row-height-subtotal);
  border-top: 1px solid var(--border-strong);
  font-weight: 600;
}

.data-table tr.linha-total td {
  height: var(--row-height-total);
  border-top: 2px solid var(--border-structural);
  background: var(--surface-container-high);
  font-weight: 700;
}

.data-table th .letra {
  display: block;
  font-family: var(--font-data);
  color: var(--text-secondary);
  font-weight: 400;
}
```

`frontend/src/pages/contrato/TabelaCalculo.tsx`:

```tsx
import { Fragment } from 'react'
import type { Calculo, Decimal } from '../../api/tipos'
import { deltaP, dinheiro, fator, mesAno, negativo, percentual } from '../../lib/formato'

function Num({ v, formatar, forte }: { v: Decimal; formatar: (v: Decimal) => string; forte?: boolean }) {
  const classes = ['num', forte ? 'num-strong' : '', negativo(v) ? 'neg' : ''].filter(Boolean).join(' ')
  return <td className={classes}>{formatar(v)}</td>
}

// Colunas com as letras da linha 16 do template. O frontend só formata: todos
// os valores vêm prontos da API (as mesmas fórmulas que a planilha grava).
export function TabelaCalculo({ calculo }: { calculo: Calculo }) {
  const lucro = percentual(calculo.parametros.lucro)
  const colunas: [string, string][] = [
    ['Valor PI líquido', 'a'],
    ['Fator', ''],
    ['Reajuste líquido', 'b'],
    ['ΔP', 'd'],
    ['Reajuste pelo ΔP', 'c = a·d'],
    ['Diferença', 'e = c − b'],
    ['Diferença sem lucro', `f = e·(1 − ${lucro})`],
  ]
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th>Mês</th>
            {colunas.map(([nome, letra]) => (
              <th key={nome} className="num">
                {nome}
                {letra && <span className="letra">{letra}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {calculo.familias.map((familia) => (
            <Fragment key={familia.familia}>
              <tr className="linha-familia">
                <td colSpan={8}>{familia.rotulo}</td>
              </tr>
              {familia.produtos.map((produto) => (
                <Fragment key={produto.descricao}>
                  <tr className="linha-produto">
                    <td colSpan={8}>{produto.descricao}</td>
                  </tr>
                  {produto.linhas.map((l) => (
                    <tr key={l.mes}>
                      <td>{mesAno(l.mes)}</td>
                      <Num v={l.a} formatar={dinheiro} />
                      <Num v={l.fator} formatar={fator} />
                      <Num v={l.b} formatar={dinheiro} />
                      <Num v={l.d} formatar={deltaP} />
                      <Num v={l.c} formatar={dinheiro} />
                      <Num v={l.e} formatar={dinheiro} />
                      <Num v={l.f} formatar={dinheiro} />
                    </tr>
                  ))}
                  <tr className="linha-subtotal">
                    <td colSpan={7}>Subtotal — {produto.descricao}</td>
                    <Num v={produto.subtotal} formatar={dinheiro} forte />
                  </tr>
                </Fragment>
              ))}
            </Fragment>
          ))}
          <tr className="linha-total">
            <td colSpan={7}>Total geral</td>
            <Num v={calculo.total} formatar={dinheiro} forte />
          </tr>
        </tbody>
      </table>
    </div>
  )
}
```

`frontend/src/pages/contrato/AbaCalculo.tsx`:

```tsx
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link, useOutletContext, useSearchParams } from 'react-router'
import { chaves } from '../../api/chaves'
import { calcular, urlPlanilha } from '../../api/contratos'
import { ErroApi } from '../../api/erros'
import { buscarCobertura } from '../../api/indices'
import { FAMILIAS, ROTULO_FAMILIA, type Contrato, type Familia } from '../../api/tipos'
import { Carregando } from '../../components/Carregando'
import { Icone } from '../../components/Icone'
import { MensagemErro } from '../../components/MensagemErro'
import { mesAno } from '../../lib/formato'
import { destinoDoFaltante, regioesDaUrl } from './bloqueio'
import { TabelaCalculo } from './TabelaCalculo'

const PARAMETRO: Record<Familia, 'regiao_cap' | 'regiao_emulsoes'> = {
  CAP: 'regiao_cap',
  EMULSOES: 'regiao_emulsoes',
}

export function AbaCalculo() {
  const contrato = useOutletContext<Contrato>()
  const [busca, setBusca] = useSearchParams()
  const regioes = regioesDaUrl(busca)
  const cobertura = useQuery({ queryKey: chaves.cobertura, queryFn: buscarCobertura })
  const calculo = useQuery({
    queryKey: chaves.calculo(contrato.id, regioes),
    queryFn: () => calcular(contrato.id, regioes),
    placeholderData: keepPreviousData,
  })

  const simuladas = FAMILIAS.filter((f) => busca.get(PARAMETRO[f]))
  const opcoes = cobertura.data?.regioes ?? []

  function escolher(familia: Familia, regiao: string) {
    const proxima = new URLSearchParams(busca)
    // A região do cadastro não é simulação: sai da URL.
    if (!regiao || regiao === contrato.regioes[familia]) proxima.delete(PARAMETRO[familia])
    else proxima.set(PARAMETRO[familia], regiao)
    setBusca(proxima)
  }

  const erro = calculo.error
  const bloqueio = erro instanceof ErroApi && erro.status === 422 && erro.faltando.length > 0

  return (
    <>
      <div className="panel">
        <div className="panel-body barra">
          <span className="badge badge-mono">Data Base: {mesAno(contrato.data_base)}</span>
          {FAMILIAS.map((familia) => {
            const atual = busca.get(PARAMETRO[familia]) ?? contrato.regioes[familia] ?? ''
            const lista = atual && !opcoes.includes(atual) ? [atual, ...opcoes] : opcoes
            return (
              <div className="inline-form" key={familia}>
                <label className="field-label" htmlFor={`regiao-${familia}`}>
                  Região {ROTULO_FAMILIA[familia]}
                </label>
                <select
                  id={`regiao-${familia}`}
                  className="input"
                  value={atual}
                  onChange={(e) => escolher(familia, e.target.value)}
                >
                  {!atual && <option value="">Sem região</option>}
                  {lista.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </div>
            )
          })}
          <span className="espaco" />
          {simuladas.length > 0 && (
            <button type="button" className="btn" onClick={() => setBusca(new URLSearchParams())}>
              Voltar ao cadastro
            </button>
          )}
          {calculo.data && !bloqueio && (
            <a className="btn btn-primary" href={urlPlanilha(contrato.id, regioes)} download>
              <Icone nome="download" />
              <span>Baixar planilha (.xlsx)</span>
            </a>
          )}
        </div>
      </div>

      {simuladas.length > 0 && calculo.data && !calculo.isPlaceholderData && !bloqueio && (
        <div className="notice info mt-md" role="status">
          <div>
            <p className="notice-title">Simulação — o cadastro não muda.</p>
            <p className="notice-text">
              {simuladas
                .map((f) => `${ROTULO_FAMILIA[f]} em ${busca.get(PARAMETRO[f])} (cadastro: ${contrato.regioes[f] ?? 'sem região'})`)
                .join('; ')}
              . Arquivo: {calculo.data.arquivo}
            </p>
          </div>
        </div>
      )}

      {bloqueio && (
        <div className="notice danger mt-md" role="alert">
          <div className="notice-icon">
            <Icone nome="block" />
          </div>
          <div>
            <p className="notice-title">Cálculo bloqueado</p>
            <ul className="lista-erros">
              {erro.faltando.map((item) => {
                const destino = destinoDoFaltante(item, contrato.id)
                return (
                  <li key={item}>
                    {destino.texto}{' '}
                    {destino.para && (
                      <Link to={destino.para} className="btn btn-sm">
                        {destino.rotulo}
                      </Link>
                    )}
                  </li>
                )
              })}
            </ul>
          </div>
        </div>
      )}
      {!bloqueio && <MensagemErro erro={erro} />}
      {calculo.isPending && <Carregando />}

      {calculo.data && !bloqueio && (
        <>
          <section className="panel mt-md">
            <div className="panel-body flush">
              <TabelaCalculo calculo={calculo.data} />
            </div>
          </section>
          {calculo.data.avisos.length > 0 && (
            <div className="notice warn mt-md">
              <div>
                <p className="notice-title">Avisos da planilha</p>
                <ul className="lista-erros">
                  {calculo.data.avisos.map((aviso) => (
                    <li key={aviso}>{aviso}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </>
      )}
    </>
  )
}
```

`keepPreviousData` mantém a tabela anterior na tela enquanto a simulação nova carrega (o aviso da simulação espera `isPlaceholderData` cair, para não mostrar o nome de arquivo antigo); `calculo.error` só existe quando a última resposta falhou, e aí nada da tabela anterior aparece (`!bloqueio`).

Em `frontend/src/App.tsx`, dentro de `contratos/:id`, depois de `cadastro`:

```tsx
          <Route path="calculo" element={<AbaCalculo />} />
```

com `import { AbaCalculo } from './pages/contrato/AbaCalculo'`.

Run: `npm run test -- calculo bloqueio`
Expected: PASS.

- [ ] **Step 5: Rodar tudo e commitar**

Run: `npm run test && npm run build`
Expected: todos passam; build sem erro.

```bash
git add frontend/src/App.tsx frontend/src/pages/contrato frontend/src/styles/telas.css frontend/tests
git commit -m "$(cat <<'EOF'
feat(frontend): aba Cálculo com simulação de região e download

Tabela única com as letras da linha 16, agrupada família → produto → mês,
com subtotais, total e negativos em vermelho. Região simulada vai para a
URL e para o link da planilha, com faixa de aviso e o nome do arquivo; 422
com faltando lista tudo o que falta, com atalhos para cadastro e índices.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarefa 7: Aba Medições

**Files:**
- Create: `frontend/src/pages/contrato/AbaMedicoes.tsx`
- Modify: `frontend/src/App.tsx` (rota `medicoes`)
- Create: `frontend/tests/medicoes.test.tsx`

**Interfaces:**
- Consumes: `listarMedicoes(id, filtros: FiltrosMedicoes)` (Tarefa 5); `chaves.medicoes(id, filtros)`; `ItemMedicao`; `dinheiro`, `fator`, `mesAno`, `negativo`; `useOutletContext<Contrato>()`.
- Produces: `AbaMedicoes()`; o link `/catalogo?q=<código>` que a Tarefa 8 abre direto na busca de códigos.

- [ ] **Step 1: Testes**

`frontend/tests/medicoes.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import type { ItemMedicao } from '../src/api/tipos'
import { umContrato } from './fabricas'
import { renderApp } from './render'
import { servidor } from './servidor'

function umItem(parcial: Partial<ItemMedicao> = {}): ItemMedicao {
  return {
    id: 1,
    mes: '2023-02-01',
    codigo: '60112',
    descricao_pdf: 'Fornecimento de CAP 50/70',
    valor_pi: '412300.00',
    fator: '0.1480',
    reajuste: '61020.40',
    arquivo: 'medicao_fev.pdf',
    produto_id: 3,
    produto: 'Aquisição de CAP 50/70',
    familia: 'CAP',
    ...parcial,
  }
}

function preparar(itens: ItemMedicao[]) {
  const pedidos: URLSearchParams[] = []
  servidor.use(
    http.get('/api/v1/contratos/1', () => HttpResponse.json(umContrato())),
    http.get('/api/v1/contratos/1/medicoes', ({ request }) => {
      pedidos.push(new URL(request.url).searchParams)
      return HttpResponse.json(itens)
    }),
  )
  return pedidos
}

describe('Aba Medições', () => {
  it('lista os itens com o produto, ou o atalho para associar', async () => {
    preparar([
      umItem(),
      umItem({ id: 2, codigo: '40210', descricao_pdf: 'Escavação', produto_id: null, produto: null, familia: null }),
    ])
    renderApp('/contratos/1/medicoes')
    const linha = (await screen.findByText('60112')).closest('tr')!
    expect(within(linha).getByText('fev/2023')).toBeInTheDocument()
    expect(within(linha).getByText('412.300,00')).toBeInTheDocument()
    expect(within(linha).getByText('0,1480')).toBeInTheDocument()
    expect(within(linha).getByText('Aquisição de CAP 50/70')).toBeInTheDocument()
    expect(within(linha).getByText('medicao_fev.pdf')).toBeInTheDocument()

    const fora = screen.getByText('40210').closest('tr')!
    expect(within(fora).getByText('Fora do cálculo')).toBeInTheDocument()
    expect(within(fora).getByRole('link', { name: 'Associar' })).toHaveAttribute('href', '/catalogo?q=40210')
    expect(screen.getByText('2 itens')).toBeInTheDocument()
  })

  it('filtros viram parâmetros da API', async () => {
    const pedidos = preparar([umItem()])
    const { usuario } = renderApp('/contratos/1/medicoes')
    await screen.findByText('60112')

    await usuario.type(screen.getByLabelText('Mês'), '2023-02')
    await usuario.selectOptions(screen.getByLabelText('Situação'), 'Só no cálculo')
    await usuario.type(screen.getByLabelText('Código ou descrição'), 'cap')
    await usuario.click(screen.getByRole('button', { name: 'Filtrar' }))

    const ultimo = pedidos.at(-1)!
    expect(ultimo.get('mes')).toBe('2023-02')
    expect(ultimo.get('no_calculo')).toBe('true')
    expect(ultimo.get('q')).toBe('cap')
  })

  it('sem itens mostra o estado vazio', async () => {
    preparar([])
    renderApp('/contratos/1/medicoes')
    expect(await screen.findByText('Nenhum item com esses filtros.')).toBeInTheDocument()
  })
})
```

`usuario.type` num `input type="month"` do jsdom aceita o texto `2023-02` como valor; se a versão do jsdom recusar, troque por `fireEvent.change(campo, { target: { value: '2023-02' } })` — o comportamento testado é o mesmo.

Run: `npm run test -- medicoes`
Expected: FAIL — rota `medicoes` não existe.

- [ ] **Step 2: Implementar**

`frontend/src/pages/contrato/AbaMedicoes.tsx`:

```tsx
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useOutletContext } from 'react-router'
import { chaves, type FiltrosMedicoes } from '../../api/chaves'
import { listarMedicoes } from '../../api/contratos'
import type { Contrato } from '../../api/tipos'
import { Carregando } from '../../components/Carregando'
import { MensagemErro } from '../../components/MensagemErro'
import { dinheiro, fator, mesAno, negativo } from '../../lib/formato'

type Situacao = '' | 'true' | 'false'

// Os itens como o PDF os trouxe. Um código sem produto não é pendência: fica
// fora do cálculo, e o atalho leva ao catálogo para associá-lo se for material.
export function AbaMedicoes() {
  const contrato = useOutletContext<Contrato>()
  const [mes, setMes] = useState('')
  const [situacao, setSituacao] = useState<Situacao>('')
  const [q, setQ] = useState('')
  const [filtros, setFiltros] = useState<FiltrosMedicoes>({})

  const itens = useQuery({
    queryKey: chaves.medicoes(contrato.id, filtros),
    queryFn: () => listarMedicoes(contrato.id, filtros),
    placeholderData: keepPreviousData,
  })

  function filtrar(e: FormEvent) {
    e.preventDefault()
    setFiltros({
      mes: mes || undefined,
      noCalculo: situacao === '' ? undefined : situacao === 'true',
      q: q.trim() || undefined,
    })
  }

  return (
    <>
      <form className="barra" onSubmit={filtrar}>
        <div className="field">
          <label className="field-label" htmlFor="filtro-mes">Mês</label>
          <input id="filtro-mes" type="month" className="input" value={mes} onChange={(e) => setMes(e.target.value)} />
        </div>
        <div className="field">
          <label className="field-label" htmlFor="filtro-situacao">Situação</label>
          <select
            id="filtro-situacao"
            className="input"
            value={situacao}
            onChange={(e) => setSituacao(e.target.value as Situacao)}
          >
            <option value="">Todos</option>
            <option value="true">Só no cálculo</option>
            <option value="false">Fora do cálculo</option>
          </select>
        </div>
        <div className="field">
          <label className="field-label" htmlFor="filtro-q">Código ou descrição</label>
          <input id="filtro-q" className="input" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <button type="submit" className="btn">Filtrar</button>
        <span className="espaco" />
        {itens.data && <span className="contagem">{itens.data.length} {itens.data.length === 1 ? 'item' : 'itens'}</span>}
      </form>

      <MensagemErro erro={itens.error} />
      {itens.isPending && <Carregando />}

      {itens.data && itens.data.length === 0 && <p className="contagem mt-md">Nenhum item com esses filtros.</p>}
      {itens.data && itens.data.length > 0 && (
        <section className="panel mt-md">
          <div className="panel-body flush table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Mês</th>
                  <th>Código</th>
                  <th>Descrição no PDF</th>
                  <th className="num">Valor PI líquido</th>
                  <th className="num">Fator</th>
                  <th className="num">Reajuste líquido</th>
                  <th>Produto</th>
                  <th>Arquivo</th>
                </tr>
              </thead>
              <tbody>
                {itens.data.map((item) => (
                  <tr key={item.id}>
                    <td>{mesAno(item.mes)}</td>
                    <td className="num">{item.codigo}</td>
                    <td>{item.descricao_pdf ?? '—'}</td>
                    <td className={negativo(item.valor_pi) ? 'num neg' : 'num'}>{dinheiro(item.valor_pi)}</td>
                    <td className="num">{fator(item.fator)}</td>
                    <td className={negativo(item.reajuste) ? 'num neg' : 'num'}>{dinheiro(item.reajuste)}</td>
                    <td>
                      {item.produto ?? (
                        <>
                          <span className="badge">Fora do cálculo</span>{' '}
                          <Link className="btn btn-sm" to={`/catalogo?q=${encodeURIComponent(item.codigo)}`}>
                            Associar
                          </Link>
                        </>
                      )}
                    </td>
                    <td>{item.arquivo}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  )
}
```

Em `frontend/src/App.tsx`, dentro de `contratos/:id`, entre `cadastro` e `calculo`:

```tsx
          <Route path="medicoes" element={<AbaMedicoes />} />
```

com `import { AbaMedicoes } from './pages/contrato/AbaMedicoes'`.

Run: `npm run test -- medicoes`
Expected: PASS.

- [ ] **Step 3: Rodar tudo e commitar**

Run: `npm run test && npm run build`
Expected: todos passam; build sem erro.

```bash
git add frontend/src/App.tsx frontend/src/pages/contrato/AbaMedicoes.tsx frontend/tests/medicoes.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): aba Medições do contrato

Itens extraídos dos PDFs com filtros de mês, situação e busca, que vão
como parâmetros da API. Código sem produto aparece como fora do cálculo,
com atalho para o catálogo já filtrado por ele.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarefa 8: Catálogo de produtos e códigos

**Files:**
- Create: `frontend/src/api/catalogo.ts`
- Create: `frontend/src/pages/catalogo/{PaginaCatalogo.tsx,ProdutoDialogo.tsx,AdicionarCodigos.tsx}`
- Modify: `frontend/src/App.tsx` (rota `catalogo`)
- Create: `frontend/tests/catalogo.test.tsx`

**Interfaces:**
- Consumes: `pedir` (Tarefa 4); `chaves.produtos`, `chaves.codigos(f)`, `FiltrosCodigos`; `aposCatalogo(qc)`; `Produto`, `Codigo`, `Familia`, `FAMILIAS`, `ROTULO_FAMILIA`; `Dialogo`, `ConfirmarDialogo`, `MensagemErro`, `Cabecalho`, `Carregando`, `Icone`.
- Produces:
  - `src/api/catalogo.ts`: `listarProdutos(): Promise<Produto[]>`, `criarProduto(p: ProdutoNovo): Promise<Produto>`, `atualizarProduto(id, p: Partial<ProdutoNovo>): Promise<Produto>`, `excluirProduto(id): Promise<void>`, `listarCodigos(f: FiltrosCodigos): Promise<Codigo[]>`, `associarCodigos(produtoId, codigos: string[]): Promise<Produto>`, `desassociarCodigo(codigo): Promise<void>`; tipo `ProdutoNovo { descricao_export: string; familia: Familia }`.
  - Rota `/catalogo`, com `?produto=<id>` (produto selecionado) e `?q=<código>` (abre *Adicionar códigos* já buscando — é o link da aba Medições).

- [ ] **Step 1: Cliente do catálogo**

`frontend/src/api/catalogo.ts`:

```ts
import type { FiltrosCodigos } from './chaves'
import { pedir } from './client'
import type { Codigo, Familia, Produto } from './tipos'

const BASE = '/api/v1'

export interface ProdutoNovo {
  descricao_export: string
  familia: Familia
}

export const listarProdutos = () => pedir<Produto[]>(`${BASE}/produtos`)

export const criarProduto = (produto: ProdutoNovo) =>
  pedir<Produto>(`${BASE}/produtos`, { metodo: 'POST', json: produto })

export const atualizarProduto = (id: number, produto: Partial<ProdutoNovo>) =>
  pedir<Produto>(`${BASE}/produtos/${id}`, { metodo: 'PATCH', json: produto })

export const excluirProduto = (id: number) => pedir<void>(`${BASE}/produtos/${id}`, { metodo: 'DELETE' })

export const listarCodigos = (filtros: FiltrosCodigos) =>
  pedir<Codigo[]>(`${BASE}/codigos`, {
    params: { q: filtros.q, associado: filtros.associado, produto_id: filtros.produtoId, limite: 500 },
  })

// Um PUT só para vários códigos: ou todos são associados, ou nenhum.
export const associarCodigos = (produtoId: number, codigos: string[]) =>
  pedir<Produto>(`${BASE}/produtos/${produtoId}/codigos`, { metodo: 'PUT', json: { codigos } })

export const desassociarCodigo = (codigo: string) =>
  pedir<void>(`${BASE}/codigos/${encodeURIComponent(codigo)}`, { metodo: 'DELETE' })
```

- [ ] **Step 2: Testes da tela**

`frontend/tests/catalogo.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Codigo, Produto } from '../src/api/tipos'
import { renderApp } from './render'
import { servidor } from './servidor'

const CAP: Produto = { id: 3, descricao_export: 'Aquisição de CAP 50/70', familia: 'CAP', ordem: 0, codigos: 1 }
const RR: Produto = { id: 4, descricao_export: 'Emulsão RR-1C', familia: 'EMULSOES', ordem: 0, codigos: 0 }

function umCodigo(parcial: Partial<Codigo> = {}): Codigo {
  return {
    codigo: '60112',
    descricao_pdf: 'Fornecimento de CAP 50/70',
    contratos: 1,
    ocorrencias: 2,
    produto_id: 3,
    descricao_export: CAP.descricao_export,
    familia: 'CAP',
    ...parcial,
  }
}

const SEM_PRODUTO = umCodigo({ codigo: '40210', descricao_pdf: 'Escavação', produto_id: null, descricao_export: null, familia: null })
const EM_RR = umCodigo({ codigo: '60113', descricao_pdf: 'Emulsão RR', produto_id: 4, descricao_export: RR.descricao_export, familia: 'EMULSOES' })

function preparar(produtos: Produto[] = [CAP, RR]) {
  const escritas: { metodo: string; url: string; corpo: unknown }[] = []
  servidor.use(
    http.get('/api/v1/produtos', () => HttpResponse.json(produtos)),
    http.get('/api/v1/codigos', ({ request }) => {
      const p = new URL(request.url).searchParams
      if (p.get('produto_id') === '3') return HttpResponse.json([umCodigo()])
      if (p.get('produto_id')) return HttpResponse.json([])
      return HttpResponse.json([umCodigo(), SEM_PRODUTO, EM_RR])
    }),
    http.post('/api/v1/produtos', async ({ request }) => {
      const corpo = await request.json()
      escritas.push({ metodo: 'POST', url: request.url, corpo })
      return HttpResponse.json({ ...RR, id: 9, ...(corpo as object) }, { status: 201 })
    }),
    http.delete('/api/v1/produtos/:id', ({ request }) => {
      escritas.push({ metodo: 'DELETE', url: request.url, corpo: null })
      return new HttpResponse(null, { status: 204 })
    }),
    http.delete('/api/v1/codigos/:codigo', ({ request }) => {
      escritas.push({ metodo: 'DELETE', url: request.url, corpo: null })
      return new HttpResponse(null, { status: 204 })
    }),
    http.put('/api/v1/produtos/:id/codigos', async ({ request }) => {
      escritas.push({ metodo: 'PUT', url: request.url, corpo: await request.json() })
      return HttpResponse.json({ ...CAP, codigos: 3 })
    }),
  )
  return escritas
}

describe('Catálogo', () => {
  it('lista os produtos por família e mostra os códigos do selecionado', async () => {
    preparar()
    renderApp('/catalogo')
    const lista = await screen.findByRole('navigation', { name: 'Produtos' })
    expect(within(lista).getByText('CAP')).toBeInTheDocument()
    expect(within(lista).getByText('Emulsões')).toBeInTheDocument()
    // O primeiro produto fica selecionado.
    expect(await screen.findByRole('heading', { name: 'Aquisição de CAP 50/70' })).toBeInTheDocument()
    const linha = (await screen.findByText('60112')).closest('tr')!
    expect(within(linha).getByText('Fornecimento de CAP 50/70')).toBeInTheDocument()
  })

  it('sem produtos explica o que fazer', async () => {
    preparar([])
    renderApp('/catalogo')
    expect(await screen.findByText(/Nenhum produto ainda/)).toBeInTheDocument()
  })

  it('cria um produto', async () => {
    const escritas = preparar()
    const { usuario } = renderApp('/catalogo')
    await usuario.click(await screen.findByRole('button', { name: 'Novo produto' }))
    const dialogo = screen.getByRole('dialog')
    await usuario.type(within(dialogo).getByLabelText('Descrição na planilha'), 'Emulsão RL-1C')
    await usuario.selectOptions(within(dialogo).getByLabelText('Família'), 'Emulsões')
    await usuario.click(within(dialogo).getByRole('button', { name: 'Salvar' }))
    expect(escritas[0]).toMatchObject({ metodo: 'POST', corpo: { descricao_export: 'Emulsão RL-1C', familia: 'EMULSOES' } })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByTestId('local')).toHaveTextContent('/catalogo?produto=9')
  })

  it('duplicado mostra o erro dentro do diálogo', async () => {
    preparar()
    servidor.use(
      http.post('/api/v1/produtos', () =>
        HttpResponse.json({ detail: "Já existe o produto 'Emulsão RR-1C'." }, { status: 409 }),
      ),
    )
    const { usuario } = renderApp('/catalogo')
    await usuario.click(await screen.findByRole('button', { name: 'Novo produto' }))
    const dialogo = screen.getByRole('dialog')
    await usuario.type(within(dialogo).getByLabelText('Descrição na planilha'), 'Emulsão RR-1C')
    await usuario.click(within(dialogo).getByRole('button', { name: 'Salvar' }))
    expect(await within(dialogo).findByText("Já existe o produto 'Emulsão RR-1C'.")).toBeInTheDocument()
  })

  it('excluir pede confirmação e explica o efeito', async () => {
    const escritas = preparar()
    const { usuario } = renderApp('/catalogo?produto=3')
    await usuario.click(await screen.findByRole('button', { name: 'Excluir produto' }))
    const dialogo = screen.getByRole('dialog')
    expect(dialogo).toHaveTextContent('1 código deixa o cálculo')
    await usuario.click(within(dialogo).getByRole('button', { name: 'Excluir' }))
    expect(escritas).toContainEqual(expect.objectContaining({ metodo: 'DELETE', url: expect.stringContaining('/produtos/3') }))
  })

  it('remove um código do produto sem confirmação', async () => {
    const escritas = preparar()
    const { usuario } = renderApp('/catalogo?produto=3')
    const linha = (await screen.findByText('60112')).closest('tr')!
    await usuario.click(within(linha).getByRole('button', { name: 'Remover 60112' }))
    expect(escritas).toContainEqual(expect.objectContaining({ metodo: 'DELETE', url: expect.stringContaining('/codigos/60112') }))
  })

  it('adicionar códigos: status de cada um e associação em lote', async () => {
    const escritas = preparar()
    const { usuario } = renderApp('/catalogo?produto=3&q=60')
    const dialogo = await screen.findByRole('dialog')
    expect(within(dialogo).getByLabelText('Buscar código ou descrição')).toHaveValue('60')
    const linha = (texto: string) => within(dialogo).getByText(texto).closest('tr')!
    expect(await within(dialogo).findByText('40210')).toBeInTheDocument()
    expect(linha('60112')).toHaveTextContent('neste produto')
    expect(linha('40210')).toHaveTextContent('sem produto')
    expect(linha('60113')).toHaveTextContent('em Emulsão RR-1C')

    await usuario.click(within(linha('40210')).getByRole('checkbox'))
    await usuario.click(within(linha('60113')).getByRole('checkbox'))
    await usuario.click(within(dialogo).getByRole('button', { name: 'Associar selecionados (2)' }))
    expect(escritas.at(-1)).toMatchObject({ metodo: 'PUT', corpo: { codigos: ['40210', '60113'] } })
    expect(escritas.at(-1)!.url).toContain('/produtos/3/codigos')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByTestId('local')).toHaveTextContent(/^\/catalogo\?produto=3$/)
  })
})
```

Run: `npm run test -- catalogo`
Expected: FAIL — rota `catalogo` não existe.

- [ ] **Step 3: Diálogo de produto**

`frontend/src/pages/catalogo/ProdutoDialogo.tsx`:

```tsx
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { atualizarProduto, criarProduto, type ProdutoNovo } from '../../api/catalogo'
import { aposCatalogo } from '../../api/invalidar'
import { FAMILIAS, ROTULO_FAMILIA, type Familia, type Produto } from '../../api/tipos'
import { Dialogo } from '../../components/Dialogo'
import { MensagemErro } from '../../components/MensagemErro'

interface Props {
  produto?: Produto
  aoFechar: () => void
  aoSalvar: (produto: Produto) => void
}

// Criar e editar são o mesmo formulário: descrição livre (é o texto que sai na
// planilha) e a família, que decide a fórmula do ΔP.
export function ProdutoDialogo({ produto, aoFechar, aoSalvar }: Props) {
  const qc = useQueryClient()
  const [descricao, setDescricao] = useState(produto?.descricao_export ?? '')
  const [familia, setFamilia] = useState<Familia>(produto?.familia ?? 'CAP')
  const salvar = useMutation({
    mutationFn: (dados: ProdutoNovo) => (produto ? atualizarProduto(produto.id, dados) : criarProduto(dados)),
    onSuccess: async (salvo) => {
      await aposCatalogo(qc)
      aoSalvar(salvo)
    },
  })

  function enviar(e: FormEvent) {
    e.preventDefault()
    salvar.mutate({ descricao_export: descricao.trim(), familia })
  }

  return (
    <Dialogo
      titulo={produto ? 'Editar produto' : 'Novo produto'}
      aoFechar={aoFechar}
      acoes={
        <>
          <button type="button" className="btn" onClick={aoFechar}>Cancelar</button>
          <button type="submit" form="form-produto" className="btn btn-primary" disabled={!descricao.trim() || salvar.isPending}>
            Salvar
          </button>
        </>
      }
    >
      <form id="form-produto" onSubmit={enviar}>
        <div className="field">
          <label className="field-label" htmlFor="produto-descricao">Descrição na planilha</label>
          <input id="produto-descricao" className="input" value={descricao} onChange={(e) => setDescricao(e.target.value)} />
        </div>
        <div className="field mt-md">
          <label className="field-label" htmlFor="produto-familia">Família</label>
          <select id="produto-familia" className="input" value={familia} onChange={(e) => setFamilia(e.target.value as Familia)}>
            {FAMILIAS.map((f) => (
              <option key={f} value={f}>{ROTULO_FAMILIA[f]}</option>
            ))}
          </select>
        </div>
        <MensagemErro erro={salvar.error} />
      </form>
    </Dialogo>
  )
}
```

`Dialogo` (Tarefa 4) já renderiza `role="dialog"`, o título, o corpo (`.dialogo-corpo`) e as `acoes` no rodapé; o botão Salvar fica fora do `<form>` e o submete por `form="form-produto"`.

- [ ] **Step 4: Diálogo de adicionar códigos**

`frontend/src/pages/catalogo/AdicionarCodigos.tsx`:

```tsx
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { associarCodigos, listarCodigos } from '../../api/catalogo'
import { chaves, type FiltrosCodigos } from '../../api/chaves'
import { aposCatalogo } from '../../api/invalidar'
import type { Codigo, Produto } from '../../api/tipos'
import { Carregando } from '../../components/Carregando'
import { Dialogo } from '../../components/Dialogo'
import { MensagemErro } from '../../components/MensagemErro'

type Filtro = 'todos' | 'sem' | 'associados'

const ASSOCIADO: Record<Filtro, boolean | undefined> = { todos: undefined, sem: false, associados: true }

interface Props {
  produtos: Produto[]
  produtoInicial: number
  buscaInicial: string
  aoFechar: () => void
}

function situacaoDoCodigo(codigo: Codigo, alvo: number): string {
  if (codigo.produto_id === alvo) return 'neste produto'
  if (codigo.produto_id === null) return 'sem produto'
  return `em ${codigo.descricao_export}`
}

// Busca entre os códigos já extraídos e associa vários de uma vez. Um código
// em outro produto pode ser marcado: o PUT o reaponta, como no backend.
export function AdicionarCodigos({ produtos, produtoInicial, buscaInicial, aoFechar }: Props) {
  const qc = useQueryClient()
  const [texto, setTexto] = useState(buscaInicial)
  const [filtro, setFiltro] = useState<Filtro>('todos')
  const [filtros, setFiltros] = useState<FiltrosCodigos>({ q: buscaInicial || undefined })
  const [alvo, setAlvo] = useState(produtoInicial)
  const [marcados, setMarcados] = useState<string[]>([])

  const codigos = useQuery({
    queryKey: chaves.codigos(filtros),
    queryFn: () => listarCodigos(filtros),
    placeholderData: keepPreviousData,
  })
  const associar = useMutation({
    mutationFn: () => associarCodigos(alvo, marcados),
    onSuccess: async () => {
      await aposCatalogo(qc)
      aoFechar()
    },
  })

  function buscar(e: FormEvent) {
    e.preventDefault()
    setFiltros({ q: texto.trim() || undefined, associado: ASSOCIADO[filtro] })
  }

  function alternar(codigo: string) {
    setMarcados((atual) => (atual.includes(codigo) ? atual.filter((c) => c !== codigo) : [...atual, codigo]))
  }

  return (
    <Dialogo
      titulo="Adicionar códigos"
      aoFechar={aoFechar}
      acoes={
        <>
          <button type="button" className="btn" onClick={aoFechar}>Cancelar</button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={marcados.length === 0 || associar.isPending}
            onClick={() => associar.mutate()}
          >
            Associar selecionados ({marcados.length})
          </button>
        </>
      }
    >
      <form className="barra" onSubmit={buscar}>
        <div className="field">
          <label className="field-label" htmlFor="busca-codigo">Buscar código ou descrição</label>
          <input id="busca-codigo" className="input" value={texto} onChange={(e) => setTexto(e.target.value)} />
        </div>
        <div className="field">
          <label className="field-label" htmlFor="filtro-associado">Mostrar</label>
          <select id="filtro-associado" className="input" value={filtro} onChange={(e) => setFiltro(e.target.value as Filtro)}>
            <option value="todos">Todos</option>
            <option value="sem">Sem produto</option>
            <option value="associados">Já associados</option>
          </select>
        </div>
        <button type="submit" className="btn">Buscar</button>
        <span className="espaco" />
        <div className="field">
          <label className="field-label" htmlFor="alvo-produto">Associar a</label>
          <select id="alvo-produto" className="input" value={alvo} onChange={(e) => setAlvo(Number(e.target.value))}>
            {produtos.map((p) => (
              <option key={p.id} value={p.id}>{p.descricao_export}</option>
            ))}
          </select>
        </div>
      </form>

      <MensagemErro erro={codigos.error ?? associar.error} />
      {codigos.isPending && <Carregando />}
      {codigos.data && codigos.data.length === 0 && <p className="contagem">Nenhum código encontrado.</p>}
      {codigos.data && codigos.data.length > 0 && (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th />
                <th>Código</th>
                <th>Descrição no PDF</th>
                <th className="num">Contratos</th>
                <th>Situação</th>
              </tr>
            </thead>
            <tbody>
              {codigos.data.map((c) => {
                const noAlvo = c.produto_id === alvo
                return (
                  <tr key={c.codigo}>
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`Selecionar ${c.codigo}`}
                        checked={marcados.includes(c.codigo)}
                        disabled={noAlvo}
                        onChange={() => alternar(c.codigo)}
                      />
                    </td>
                    <td className="num">{c.codigo}</td>
                    <td>{c.descricao_pdf ?? '—'}</td>
                    <td className="num">{c.contratos}</td>
                    <td>
                      <span className={noAlvo ? 'badge badge-ok' : c.produto_id === null ? 'badge' : 'badge badge-info'}>
                        {situacaoDoCodigo(c, alvo)}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </Dialogo>
  )
}
```

- [ ] **Step 5: Página do catálogo**

`frontend/src/pages/catalogo/PaginaCatalogo.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { desassociarCodigo, excluirProduto, listarCodigos, listarProdutos } from '../../api/catalogo'
import { chaves } from '../../api/chaves'
import { aposCatalogo } from '../../api/invalidar'
import { FAMILIAS, ROTULO_FAMILIA, type Produto } from '../../api/tipos'
import { Cabecalho } from '../../components/Cabecalho'
import { Carregando } from '../../components/Carregando'
import { ConfirmarDialogo } from '../../components/ConfirmarDialogo'
import { Icone } from '../../components/Icone'
import { MensagemErro } from '../../components/MensagemErro'
import { AdicionarCodigos } from './AdicionarCodigos'
import { ProdutoDialogo } from './ProdutoDialogo'

type Dialogo = { tipo: 'novo' } | { tipo: 'editar'; produto: Produto } | { tipo: 'excluir'; produto: Produto } | null

const plural = (n: number, um: string, varios: string) => `${n} ${n === 1 ? um : varios}`

export function PaginaCatalogo() {
  const qc = useQueryClient()
  const [busca, setBusca] = useSearchParams()
  const [dialogo, setDialogo] = useState<Dialogo>(null)
  const produtos = useQuery({ queryKey: chaves.produtos, queryFn: listarProdutos })

  const lista = produtos.data ?? []
  const idUrl = Number(busca.get('produto'))
  const selecionado = lista.find((p) => p.id === idUrl) ?? lista[0]
  const buscaCodigo = busca.get('q')

  const codigos = useQuery({
    queryKey: chaves.codigos({ produtoId: selecionado?.id }),
    queryFn: () => listarCodigos({ produtoId: selecionado!.id }),
    enabled: selecionado !== undefined,
  })
  const remover = useMutation({
    mutationFn: desassociarCodigo,
    onSuccess: () => aposCatalogo(qc),
  })
  const excluir = useMutation({
    mutationFn: (id: number) => excluirProduto(id),
    onSuccess: async () => {
      await aposCatalogo(qc)
      setDialogo(null)
      setBusca(new URLSearchParams())
    },
  })

  function selecionar(id: number) {
    setBusca(new URLSearchParams({ produto: String(id) }))
  }

  function fecharAdicionar() {
    const proxima = new URLSearchParams(busca)
    proxima.delete('q')
    setBusca(proxima)
  }

  function abrirAdicionar() {
    const proxima = new URLSearchParams(busca)
    proxima.set('q', '')
    setBusca(proxima)
  }

  return (
    <>
      <Cabecalho
        titulo="Catálogo"
        subtitulo="Produtos da planilha e os códigos de serviço que entram em cada um. Código sem produto fica fora do cálculo."
        acoes={
          <button type="button" className="btn btn-primary" onClick={() => setDialogo({ tipo: 'novo' })}>
            <Icone nome="add" />
            <span>Novo produto</span>
          </button>
        }
      />
      <MensagemErro erro={produtos.error} />
      {produtos.isPending && <Carregando />}

      {produtos.data && lista.length === 0 && (
        <div className="notice info">
          <div>
            <p className="notice-title">Nenhum produto ainda.</p>
            <p className="notice-text">
              Crie um produto para cada material que entra no reequilíbrio (CAP ou emulsão) e associe a ele os
              códigos de serviço dos PDFs.
            </p>
          </div>
        </div>
      )}

      {selecionado && (
        <div className="duas-colunas">
          <nav className="panel lista-produtos" aria-label="Produtos">
            {FAMILIAS.map((familia) => {
              const daFamilia = lista.filter((p) => p.familia === familia)
              if (daFamilia.length === 0) return null
              return (
                <div key={familia} className="panel-body">
                  <p className="field-label">{ROTULO_FAMILIA[familia]}</p>
                  {daFamilia.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      className={p.id === selecionado.id ? 'nav-item active' : 'nav-item'}
                      aria-current={p.id === selecionado.id ? 'true' : undefined}
                      onClick={() => selecionar(p.id)}
                    >
                      <span>{p.descricao_export}</span>
                      <span className="nav-item-badge">{p.codigos}</span>
                    </button>
                  ))}
                </div>
              )
            })}
          </nav>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2 className="panel-title">{selecionado.descricao_export}</h2>
                <p className="contagem">
                  {ROTULO_FAMILIA[selecionado.familia]} · {plural(selecionado.codigos, 'código', 'códigos')}
                </p>
              </div>
              <div className="barra">
                <button type="button" className="btn" onClick={() => setDialogo({ tipo: 'editar', produto: selecionado })}>
                  Editar
                </button>
                <button type="button" className="btn" onClick={() => setDialogo({ tipo: 'excluir', produto: selecionado })}>
                  Excluir produto
                </button>
                <button type="button" className="btn btn-primary" onClick={abrirAdicionar}>
                  Adicionar códigos
                </button>
              </div>
            </div>
            <div className="panel-body flush">
              <MensagemErro erro={codigos.error ?? remover.error} />
              {codigos.data && codigos.data.length === 0 && (
                <p className="panel-body contagem">Nenhum código neste produto. Use Adicionar códigos.</p>
              )}
              {codigos.data && codigos.data.length > 0 && (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Código</th>
                      <th>Descrição no PDF</th>
                      <th className="num">Contratos</th>
                      <th className="num">Ocorrências</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {codigos.data.map((c) => (
                      <tr key={c.codigo}>
                        <td className="num">{c.codigo}</td>
                        <td>{c.descricao_pdf ?? 'Ainda não extraído'}</td>
                        <td className="num">{c.contratos}</td>
                        <td className="num">{c.ocorrencias}</td>
                        <td>
                          <button
                            type="button"
                            className="btn btn-sm"
                            aria-label={`Remover ${c.codigo}`}
                            disabled={remover.isPending}
                            onClick={() => remover.mutate(c.codigo)}
                          >
                            Remover
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>
        </div>
      )}

      {dialogo?.tipo === 'novo' && (
        <ProdutoDialogo aoFechar={() => setDialogo(null)} aoSalvar={(p) => { setDialogo(null); selecionar(p.id) }} />
      )}
      {dialogo?.tipo === 'editar' && (
        <ProdutoDialogo produto={dialogo.produto} aoFechar={() => setDialogo(null)} aoSalvar={() => setDialogo(null)} />
      )}
      {dialogo?.tipo === 'excluir' && (
        <ConfirmarDialogo
          titulo={`Excluir ${dialogo.produto.descricao_export}?`}
          mensagem={`As associações são removidas: ${plural(dialogo.produto.codigos, 'código deixa', 'códigos deixam')} o cálculo. Os itens extraídos continuam nas medições.`}
          rotuloConfirmar="Excluir"
          perigoso
          pendente={excluir.isPending}
          erro={excluir.error}
          aoCancelar={() => setDialogo(null)}
          aoConfirmar={() => excluir.mutate(dialogo.produto.id)}
        />
      )}
      {buscaCodigo !== null && selecionado && (
        <AdicionarCodigos
          produtos={lista}
          produtoInicial={selecionado.id}
          buscaInicial={buscaCodigo}
          aoFechar={fecharAdicionar}
        />
      )}
    </>
  )
}
```

`ConfirmarDialogo` é o da Tarefa 4 (`titulo`, `mensagem`, `rotuloConfirmar`, `perigoso`, `pendente`, `erro`, `aoConfirmar`, `aoCancelar`, `textoExigido?`). `nav-item`, `nav-item-badge`, `panel-head` e `panel-title` são classes do `style.css` existente (sidebar e painéis).

Em `frontend/src/App.tsx`, no nível de `contratos`:

```tsx
        <Route path="catalogo" element={<PaginaCatalogo />} />
```

com `import { PaginaCatalogo } from './pages/catalogo/PaginaCatalogo'`.

Run: `npm run test -- catalogo`
Expected: PASS.

- [ ] **Step 6: Rodar tudo e commitar**

Run: `npm run test && npm run build`
Expected: todos passam; build sem erro.

```bash
git add frontend/src/App.tsx frontend/src/api/catalogo.ts frontend/src/pages/catalogo frontend/tests/catalogo.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): catálogo de produtos e associação de códigos

Produtos por família com a contagem de códigos; criar, editar e excluir
(com confirmação que diz quantos códigos deixam o cálculo). Os códigos do
produto saem de GET /codigos?produto_id; o diálogo de adicionar busca os
códigos extraídos, mostra onde cada um está e associa em lote num único
PUT. ?q= na URL abre o diálogo já buscando, a partir das Medições.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarefa 9: Índices — grades editáveis do ANP e do IGP-DI

**Files:**
- Modify: `frontend/src/api/indices.ts` (leitura, edição, exclusão e links de exportação)
- Create: `frontend/src/components/CelulaEditavel.tsx`
- Create: `frontend/src/pages/indices/{grade.ts,PaginaIndices.tsx,FaixaCobertura.tsx,GradeAnp.tsx,NovaSemana.tsx,GradeIgpDi.tsx}`
- Modify: `frontend/src/App.tsx` (rotas `indices`, `indices/anp`, `indices/igp-di`)
- Create: `frontend/tests/{grade.test.ts,celula.test.tsx,indices.test.tsx}`

**Interfaces:**
- Consumes: `pedir`, `caminhoCom` (Tarefa 4); `chaves.anp(produto, de, ate)`, `chaves.produtosAnp`, `chaves.igpDi()`, `chaves.cobertura`; `aposIndices(qc)`; `SemanaAnp`, `SemanaAnpEntrada`, `IndiceMensal`, `Cobertura`; `paraDecimal`, `exato`, `data`, `semana`, `mesAno`, `dataHora`, `numero`; `Dialogo`, `ConfirmarDialogo`, `MensagemErro`, `Cabecalho`, `Carregando`, `Icone`; `buscarCobertura` e `umaCobertura` (Tarefa 5).
- Produces:
  - `src/api/indices.ts`: `ANP_PRODUTO_CAP`, `REGIOES_ANP`, `listarAnp(f: { produto: string; de?: string; ate?: string }): Promise<SemanaAnp[]>`, `listarProdutosAnp(): Promise<string[]>`, `gravarSemanaAnp(e: SemanaAnpEntrada): Promise<SemanaAnp>`, `excluirSemanaAnp(id): Promise<void>`, `urlExportarAnp(f & { formato }): string`, `listarIgpDi(): Promise<IndiceMensal[]>`, `gravarIgpDi(mes: 'AAAA-MM', valor: string): Promise<IndiceMensal>`, `excluirIgpDi(mes): Promise<void>`, `URL_TEMPLATE_IGP_DI`, `urlExportarIgpDi(formato): string`.
  - `CelulaEditavel({ rotulo, valor, formatar, vazio?, manual?, titulo?, permiteVazio?, aoSalvar, aoApagar? })`.
  - `montarGradeAnp(semanas): GradeAnp`, `montarGradeIgpDi(indices, anoAtual): GradeIgpDi`, `REGIOES_FIXAS`.
  - `PaginaIndices` com as abas; `GradeAnp` e `GradeIgpDi` recebem na Tarefa 10 o botão **Importar**.

- [ ] **Step 1: Testes da montagem das grades**

`frontend/tests/grade.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import type { IndiceMensal, SemanaAnp } from '../src/api/tipos'
import { montarGradeAnp, montarGradeIgpDi } from '../src/pages/indices/grade'

let proximoId = 1
function umaSemana(inicio: string, fim: string, regiao: string, preco: string | null = '3.5'): SemanaAnp {
  return {
    id: proximoId++,
    produto: 'Cimento Asfáltico de Petróleo 50 70 (R$/kg)',
    regiao,
    vigencia_inicio: inicio,
    vigencia_fim: fim,
    preco,
    origem: 'seed',
    atualizado_em: '2026-09-24T10:00:00+00:00',
  }
}

describe('montarGradeAnp', () => {
  it('uma linha por semana, da mais recente, e as cinco regiões fixas antes das extras', () => {
    const grade = montarGradeAnp([
      umaSemana('2023-01-01', '2023-01-07', 'Sul'),
      umaSemana('2023-01-08', '2023-01-14', 'Brasil'),
      umaSemana('2023-01-08', '2023-01-14', 'Nordeste'),
      umaSemana('2023-01-01', '2023-01-07', 'Nordeste'),
    ])
    expect(grade.regioes).toEqual(['Norte', 'Nordeste', 'Centro-Oeste', 'Sudeste', 'Sul', 'Brasil'])
    expect(grade.linhas.map((l) => l.inicio)).toEqual(['2023-01-08', '2023-01-01'])
    expect(grade.linhas[0].celulas.Nordeste?.regiao).toBe('Nordeste')
    expect(grade.linhas[0].celulas.Sul).toBeUndefined()
    expect(grade.linhas[1].celulas.Sul?.vigencia_fim).toBe('2023-01-07')
  })

  it('sem extras, só as cinco fixas', () => {
    expect(montarGradeAnp([]).regioes).toEqual(['Norte', 'Nordeste', 'Centro-Oeste', 'Sudeste', 'Sul'])
  })
})

describe('montarGradeIgpDi', () => {
  const indice = (mes: string): IndiceMensal => ({ mes, valor: '1000.5', origem: 'seed', atualizado_em: '2026-09-24T10:00:00+00:00' })

  it('anos do mais antigo ao atual, do mais recente para trás', () => {
    const grade = montarGradeIgpDi([indice('2022-01'), indice('2023-12')], 2025)
    expect(grade.anos).toEqual([2025, 2024, 2023, 2022])
    expect(grade.valores.get('2023-12')?.valor).toBe('1000.5')
    expect(grade.valores.has('2024-01')).toBe(false)
  })

  it('sem dados, só o ano atual', () => {
    expect(montarGradeIgpDi([], 2026).anos).toEqual([2026])
  })
})
```

Run: `npm run test -- grade`
Expected: FAIL — módulo não existe.

- [ ] **Step 2: Implementar `grade.ts`**

`frontend/src/pages/indices/grade.ts`:

```ts
import type { IndiceMensal, SemanaAnp } from '../../api/tipos'

// As cinco regiões que os contratos usam ficam sempre na grade, na ordem do
// mapa; outras (Brasil, por exemplo) entram depois, só se tiverem dados.
export const REGIOES_FIXAS = ['Norte', 'Nordeste', 'Centro-Oeste', 'Sudeste', 'Sul']

export interface LinhaAnp {
  inicio: string
  fim: string
  celulas: Record<string, SemanaAnp | undefined>
}

export interface GradeAnp {
  regioes: string[]
  linhas: LinhaAnp[]
}

export function montarGradeAnp(semanas: SemanaAnp[]): GradeAnp {
  const extras = new Set<string>()
  const porSemana = new Map<string, LinhaAnp>()
  for (const s of semanas) {
    if (!REGIOES_FIXAS.includes(s.regiao)) extras.add(s.regiao)
    const chave = `${s.vigencia_inicio}|${s.vigencia_fim}`
    let linha = porSemana.get(chave)
    if (!linha) {
      linha = { inicio: s.vigencia_inicio, fim: s.vigencia_fim, celulas: {} }
      porSemana.set(chave, linha)
    }
    linha.celulas[s.regiao] = s
  }
  const linhas = [...porSemana.values()].sort((a, b) => b.inicio.localeCompare(a.inicio))
  return { regioes: [...REGIOES_FIXAS, ...[...extras].sort()], linhas }
}

export interface GradeIgpDi {
  anos: number[]
  valores: Map<string, IndiceMensal>
}

// Do ano mais antigo com dado até o ano atual, para que o mês novo tenha
// célula onde ser digitado.
export function montarGradeIgpDi(indices: IndiceMensal[], anoAtual: number): GradeIgpDi {
  const valores = new Map(indices.map((i) => [i.mes, i]))
  const primeiro = Math.min(anoAtual, ...indices.map((i) => Number(i.mes.slice(0, 4))))
  const anos: number[] = []
  for (let ano = anoAtual; ano >= primeiro; ano--) anos.push(ano)
  return { anos, valores }
}
```

Run: `npm run test -- grade`
Expected: PASS.

- [ ] **Step 3: Testes da célula editável**

`frontend/tests/celula.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ErroApi } from '../src/api/erros'
import { CelulaEditavel } from '../src/components/CelulaEditavel'
import { exato } from '../src/lib/formato'

function montar(props: Partial<Parameters<typeof CelulaEditavel>[0]> = {}) {
  const aoSalvar = vi.fn().mockResolvedValue(undefined)
  render(
    <table>
      <tbody>
        <tr>
          <CelulaEditavel rotulo="IGP-DI fev/2023" valor="1000.5" formatar={exato} aoSalvar={aoSalvar} {...props} />
        </tr>
      </tbody>
    </table>,
  )
  return { aoSalvar, usuario: userEvent.setup() }
}

describe('CelulaEditavel', () => {
  it('mostra o valor formatado e, ao clicar, um campo com ele', async () => {
    const { usuario } = montar()
    await usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' }))
    expect(screen.getByLabelText('IGP-DI fev/2023')).toHaveValue('1.000,5')
  })

  it('Enter grava o número no formato da API', async () => {
    const { usuario, aoSalvar } = montar()
    await usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' }))
    await usuario.clear(screen.getByLabelText('IGP-DI fev/2023'))
    await usuario.type(screen.getByLabelText('IGP-DI fev/2023'), '1.234,56{Enter}')
    expect(aoSalvar).toHaveBeenCalledWith('1234.56')
    expect(screen.queryByLabelText('IGP-DI fev/2023')).not.toBeInTheDocument()
  })

  it('Esc cancela sem gravar', async () => {
    const { usuario, aoSalvar } = montar()
    await usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' }))
    await usuario.type(screen.getByLabelText('IGP-DI fev/2023'), '9{Escape}')
    expect(aoSalvar).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' })).toHaveTextContent('1.000,5')
  })

  it('texto ilegível não chega à API', async () => {
    const { usuario, aoSalvar } = montar()
    await usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' }))
    await usuario.clear(screen.getByLabelText('IGP-DI fev/2023'))
    await usuario.type(screen.getByLabelText('IGP-DI fev/2023'), 'abc{Enter}')
    expect(aoSalvar).not.toHaveBeenCalled()
    expect(screen.getByText('Número ilegível; use vírgula decimal, como 1.234,56.')).toBeInTheDocument()
  })

  it('recusa da API volta ao valor anterior e mostra o motivo', async () => {
    const aoSalvar = vi.fn().mockRejectedValue(new ErroApi(422, 'O IGP-DI deve ser positivo.'))
    const { usuario } = montar({ aoSalvar })
    await usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' }))
    await usuario.clear(screen.getByLabelText('IGP-DI fev/2023'))
    await usuario.type(screen.getByLabelText('IGP-DI fev/2023'), '-1{Enter}')
    expect(await screen.findByText('O IGP-DI deve ser positivo.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' })).toHaveTextContent('1.000,5')
  })

  it('vazio apaga quando há aoApagar', async () => {
    const aoApagar = vi.fn().mockResolvedValue(undefined)
    const primeiro = montar({ aoApagar })
    await primeiro.usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' }))
    await primeiro.usuario.clear(screen.getByLabelText('IGP-DI fev/2023'))
    await primeiro.usuario.keyboard('{Enter}')
    expect(aoApagar).toHaveBeenCalled()
    expect(primeiro.aoSalvar).not.toHaveBeenCalled()
  })

  it('vazio com permiteVazio grava nulo', async () => {
    const { usuario, aoSalvar } = montar({ permiteVazio: true })
    await usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' }))
    await usuario.clear(screen.getByLabelText('IGP-DI fev/2023'))
    await usuario.keyboard('{Enter}')
    expect(aoSalvar).toHaveBeenCalledWith(null)
  })
})
```

`exato('1000.5')` é `'1.000,5'`: mantém as casas que o banco tem e agrupa milhares, e `paraDecimal` lê de volta esse mesmo texto.

Run: `npm run test -- celula`
Expected: FAIL — componente não existe.

- [ ] **Step 4: Implementar `CelulaEditavel`**

`frontend/src/components/CelulaEditavel.tsx`:

```tsx
import { useState, type KeyboardEvent } from 'react'
import { ErroApi } from '../api/erros'
import type { Decimal } from '../api/tipos'
import { exato, paraDecimal } from '../lib/formato'

interface Props {
  rotulo: string
  valor: Decimal | null | undefined
  formatar: (v: Decimal) => string
  // Texto quando não há valor; o ANP distingue "sem registro" de "sem cotação".
  vazio?: string
  manual?: boolean
  titulo?: string
  // Vazio grava nulo (semana ANP sem cotação) em vez de ser ignorado.
  permiteVazio?: boolean
  aoSalvar: (valor: Decimal | null) => Promise<unknown>
  // Vazio numa célula com valor apaga o registro (IGP-DI).
  aoApagar?: () => Promise<unknown>
}

const ILEGIVEL = 'Número ilegível; use vírgula decimal, como 1.234,56.'

// Célula de grade editável no lugar: clique abre o campo, Enter grava, Esc
// cancela. Se a API recusar, a célula volta ao valor do banco e mostra o motivo.
export function CelulaEditavel({ rotulo, valor, formatar, vazio = '—', manual, titulo, permiteVazio, aoSalvar, aoApagar }: Props) {
  const [editando, setEditando] = useState(false)
  const [texto, setTexto] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [gravando, setGravando] = useState(false)

  function abrir() {
    setTexto(valor ? exato(valor) : '')
    setErro(null)
    setEditando(true)
  }

  async function executar(acao: () => Promise<unknown>) {
    setGravando(true)
    try {
      await acao()
      setEditando(false)
    } catch (e) {
      setEditando(false)
      setErro(e instanceof ErroApi ? e.detail : 'Não foi possível gravar.')
    } finally {
      setGravando(false)
    }
  }

  function confirmar() {
    const limpo = texto.trim()
    if (!limpo) {
      if (valor && aoApagar) return executar(aoApagar)
      if (permiteVazio) return executar(() => aoSalvar(null))
      setEditando(false)
      return
    }
    const decimal = paraDecimal(limpo)
    if (decimal === null) {
      setErro(ILEGIVEL)
      return
    }
    return executar(() => aoSalvar(decimal))
  }

  function tecla(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault()
      void confirmar()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      e.stopPropagation()
      setErro(null)
      setEditando(false)
    }
  }

  const classes = ['celula', 'num', manual ? 'manual' : '', valor ? '' : 'vazia'].filter(Boolean).join(' ')
  return (
    <td className={classes} title={titulo}>
      {editando ? (
        <input
          className="input"
          aria-label={rotulo}
          value={texto}
          disabled={gravando}
          autoFocus
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={tecla}
          onBlur={() => !gravando && setEditando(false)}
        />
      ) : (
        <button type="button" className="celula-botao" aria-label={`Editar ${rotulo}`} onClick={abrir}>
          {valor ? formatar(valor) : vazio}
        </button>
      )}
      {erro && <span className="celula-erro" role="alert">{erro}</span>}
    </td>
  )
}
```

O texto ilegível mantém o campo aberto (o usuário corrige ali); a recusa da API fecha o campo, porque o valor exibido tem de ser o do banco.

Acrescentar ao fim de `frontend/src/styles/telas.css`:

```css
.celula-botao {
  width: 100%;
  padding: 0;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  text-align: right;
  cursor: pointer;
}
```

Run: `npm run test -- celula`
Expected: PASS.

- [ ] **Step 5: Cliente dos índices**

Substituir `frontend/src/api/indices.ts` por:

```ts
import { caminhoCom, pedir } from './client'
import type { Cobertura, IndiceMensal, SemanaAnp, SemanaAnpEntrada } from './tipos'

const BASE = '/api/v1/indices'

// O produto padrão do backend (indices_repo.ANP_PRODUTO_CAP).
export const ANP_PRODUTO_CAP = 'Cimento Asfáltico de Petróleo 50 70 (R$/kg)'
// indices_repo.REGIOES: as que o backend aceita numa semana digitada.
export const REGIOES_ANP = ['Norte', 'Nordeste', 'Centro-Oeste', 'Sudeste', 'Sul', 'Brasil']

export type Formato = 'xlsx' | 'csv'

export interface FiltrosAnp {
  produto: string
  de?: string
  ate?: string
}

export const buscarCobertura = () => pedir<Cobertura>(`${BASE}/cobertura`)

// A grade precisa de todas as semanas do filtro: o limite padrão da API (500)
// cortaria o histórico sem aviso.
export const listarAnp = (f: FiltrosAnp) =>
  pedir<SemanaAnp[]>(`${BASE}/anp`, { params: { produto: f.produto, de: f.de, ate: f.ate, limite: 100000 } })

export const listarProdutosAnp = () => pedir<string[]>(`${BASE}/anp/produtos`)

export const gravarSemanaAnp = (entrada: SemanaAnpEntrada) =>
  pedir<SemanaAnp>(`${BASE}/anp`, { metodo: 'PUT', json: entrada })

export const excluirSemanaAnp = (id: number) => pedir<void>(`${BASE}/anp/${id}`, { metodo: 'DELETE' })

export const urlExportarAnp = (f: FiltrosAnp & { formato: Formato }) =>
  caminhoCom(`${BASE}/anp/exportar`, { produto: f.produto, de: f.de, ate: f.ate, formato: f.formato })

export const listarIgpDi = () => pedir<IndiceMensal[]>(`${BASE}/igp-di`)

export const gravarIgpDi = (mes: string, valor: string) =>
  pedir<IndiceMensal>(`${BASE}/igp-di/${mes}`, { metodo: 'PUT', json: { valor } })

export const excluirIgpDi = (mes: string) => pedir<void>(`${BASE}/igp-di/${mes}`, { metodo: 'DELETE' })

export const URL_TEMPLATE_IGP_DI = `${BASE}/igp-di/template`

export const urlExportarIgpDi = (formato: Formato) => caminhoCom(`${BASE}/igp-di/exportar`, { formato })
```

- [ ] **Step 6: Testes da tela de índices**

`frontend/tests/indices.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import type { IndiceMensal, SemanaAnp } from '../src/api/tipos'
import { umaCobertura } from './fabricas'
import { renderApp } from './render'
import { servidor } from './servidor'

const CAP = 'Cimento Asfáltico de Petróleo 50 70 (R$/kg)'

function umaSemana(parcial: Partial<SemanaAnp>): SemanaAnp {
  return {
    id: 1,
    produto: CAP,
    regiao: 'Nordeste',
    vigencia_inicio: '2023-01-08',
    vigencia_fim: '2023-01-14',
    preco: '3.61475',
    origem: 'seed',
    atualizado_em: '2026-09-24T10:02:00+00:00',
    ...parcial,
  }
}

const SEMANAS = [
  umaSemana({ id: 1 }),
  umaSemana({ id: 2, regiao: 'Sul', preco: null }),
  umaSemana({ id: 3, regiao: 'Norte', preco: '3.9', origem: 'manual' }),
]

function preparar() {
  const escritas: { metodo: string; url: string; corpo: unknown }[] = []
  const registrar = async (request: Request) => {
    escritas.push({ metodo: request.method, url: request.url, corpo: request.method === 'DELETE' ? null : await request.json() })
  }
  servidor.use(
    http.get('/api/v1/indices/cobertura', () => HttpResponse.json(umaCobertura())),
    http.get('/api/v1/indices/anp/produtos', () => HttpResponse.json([CAP, 'Óleo Diesel (R$/l)'])),
    http.get('/api/v1/indices/anp', () => HttpResponse.json(SEMANAS)),
    http.put('/api/v1/indices/anp', async ({ request }) => {
      await registrar(request)
      return HttpResponse.json(umaSemana({ id: 9 }))
    }),
    http.delete('/api/v1/indices/anp/:id', async ({ request }) => {
      await registrar(request)
      return new HttpResponse(null, { status: 204 })
    }),
    http.get('/api/v1/indices/igp-di', () =>
      HttpResponse.json<IndiceMensal[]>([
        { mes: '2023-02', valor: '1085.3', origem: 'manual', atualizado_em: '2026-09-24T10:02:00+00:00' },
      ]),
    ),
    http.put('/api/v1/indices/igp-di/:mes', async ({ request }) => {
      await registrar(request)
      return HttpResponse.json({ mes: '2023-03', valor: '1090.1', origem: 'manual', atualizado_em: '2026-09-24T10:02:00+00:00' })
    }),
    http.delete('/api/v1/indices/igp-di/:mes', async ({ request }) => {
      await registrar(request)
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return escritas
}

describe('Índices', () => {
  it('/indices abre o ANP, com a cobertura', async () => {
    preparar()
    renderApp('/indices')
    expect(screen.getByTestId('local')).toHaveTextContent('/indices/anp')
    expect(await screen.findByText(/60\.114 registros/)).toBeInTheDocument()
  })

  it('grade do ANP: preço, sem cotação, célula vazia e marca de manual', async () => {
    preparar()
    renderApp('/indices/anp')
    const linha = (await screen.findByText('08/01 – 14/01/2023')).closest('tr')!
    expect(within(linha).getByRole('button', { name: 'Editar Nordeste 08/01 – 14/01/2023' })).toHaveTextContent('3,61475')
    expect(within(linha).getByRole('button', { name: 'Editar Sul 08/01 – 14/01/2023' })).toHaveTextContent('sem cotação')
    expect(within(linha).getByRole('button', { name: 'Editar Sudeste 08/01 – 14/01/2023' })).toHaveTextContent('—')
    const norte = within(linha).getByRole('button', { name: 'Editar Norte 08/01 – 14/01/2023' }).closest('td')!
    expect(norte).toHaveClass('manual')
    expect(norte).toHaveAttribute('title', 'manual · 24/09/2026 07:02')
    const exportar = new URL(screen.getByRole('link', { name: 'Exportar .xlsx' }).getAttribute('href')!, 'http://x')
    expect(exportar.pathname).toBe('/api/v1/indices/anp/exportar')
    expect(Object.fromEntries(exportar.searchParams)).toEqual({ produto: CAP, formato: 'xlsx' })
  })

  it('editar uma célula do ANP grava a semana inteira da região', async () => {
    const escritas = preparar()
    const { usuario } = renderApp('/indices/anp')
    await usuario.click(await screen.findByRole('button', { name: 'Editar Sudeste 08/01 – 14/01/2023' }))
    await usuario.type(screen.getByLabelText('Sudeste 08/01 – 14/01/2023'), '3,7{Enter}')
    expect(escritas[0]).toMatchObject({
      metodo: 'PUT',
      corpo: { produto: CAP, regiao: 'Sudeste', vigencia_inicio: '2023-01-08', vigencia_fim: '2023-01-14', preco: '3.7' },
    })
  })

  it('apagar a semana confirma e exclui todas as regiões dela', async () => {
    const escritas = preparar()
    const { usuario } = renderApp('/indices/anp')
    const linha = (await screen.findByText('08/01 – 14/01/2023')).closest('tr')!
    await usuario.click(within(linha).getByRole('button', { name: 'Apagar semana 08/01 – 14/01/2023' }))
    await usuario.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Apagar' }))
    const apagadas = escritas.filter((e) => e.metodo === 'DELETE').map((e) => e.url.split('/').at(-1))
    expect(apagadas.sort()).toEqual(['1', '2', '3'])
  })

  it('nova semana grava pelo diálogo', async () => {
    const escritas = preparar()
    const { usuario } = renderApp('/indices/anp')
    await usuario.click(await screen.findByRole('button', { name: 'Nova semana' }))
    const dialogo = screen.getByRole('dialog')
    await usuario.type(within(dialogo).getByLabelText('Início da vigência'), '2023-01-15')
    await usuario.type(within(dialogo).getByLabelText('Fim da vigência'), '2023-01-21')
    await usuario.selectOptions(within(dialogo).getByLabelText('Região'), 'Sul')
    await usuario.type(within(dialogo).getByLabelText('Preço (R$)'), '3,65')
    await usuario.click(within(dialogo).getByRole('button', { name: 'Gravar' }))
    expect(escritas[0]).toMatchObject({
      metodo: 'PUT',
      corpo: { produto: CAP, regiao: 'Sul', vigencia_inicio: '2023-01-15', vigencia_fim: '2023-01-21', preco: '3.65' },
    })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('grade do IGP-DI: grava um mês novo e apaga um existente', async () => {
    const escritas = preparar()
    const { usuario } = renderApp('/indices/igp-di')
    const fev = await screen.findByRole('button', { name: 'Editar IGP-DI fev/2023' })
    expect(fev.closest('td')).toHaveClass('manual')

    await usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI mar/2023' }))
    await usuario.type(screen.getByLabelText('IGP-DI mar/2023'), '1090,1{Enter}')
    expect(escritas.at(-1)).toMatchObject({ metodo: 'PUT', corpo: { valor: '1090.1' } })
    expect(escritas.at(-1)!.url).toContain('/igp-di/2023-03')

    await usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' }))
    await usuario.clear(screen.getByLabelText('IGP-DI fev/2023'))
    await usuario.keyboard('{Enter}')
    expect(escritas.at(-1)).toMatchObject({ metodo: 'DELETE' })
    expect(escritas.at(-1)!.url).toContain('/igp-di/2023-02')
    expect(screen.getByRole('link', { name: 'Baixar template' })).toHaveAttribute('href', '/api/v1/indices/igp-di/template')
  })
})
```

A região `Sudeste` sem registro na semana mostra `—` e grava ao ser editada: é assim que o usuário completa uma semana que a ANP publicou pela metade.

Run: `npm run test -- indices`
Expected: FAIL — rota `indices` não existe.

- [ ] **Step 7: Página, faixa e rotas**

`frontend/src/pages/indices/FaixaCobertura.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query'
import { chaves } from '../../api/chaves'
import { buscarCobertura } from '../../api/indices'
import { data, mesAno, numero } from '../../lib/formato'

// O que há no banco para a série da aba: período, quantidade e quantos valores
// foram digitados à mão (esses a importação preserva).
export function FaixaCobertura({ serie }: { serie: 'anp' | 'igp_di' }) {
  const cobertura = useQuery({ queryKey: chaves.cobertura, queryFn: buscarCobertura })
  const periodo = cobertura.data?.[serie]
  if (!periodo) return null
  const formatar = serie === 'anp' ? data : mesAno
  return (
    <div className="faixa">
      <span>
        Período: <strong>{periodo.de ? `${formatar(periodo.de)} a ${formatar(periodo.ate)}` : 'sem dados'}</strong>
      </span>
      <span>
        <strong>{numero(String(periodo.registros), 0)}</strong> registros
      </span>
      <span>
        <span className="marca-manual" />
        <strong>{periodo.manuais}</strong> {periodo.manuais === 1 ? 'valor manual' : 'valores manuais'}
      </span>
    </div>
  )
}
```

`frontend/src/pages/indices/PaginaIndices.tsx`:

```tsx
import { NavLink, Outlet } from 'react-router'
import { Cabecalho } from '../../components/Cabecalho'

export function PaginaIndices() {
  return (
    <>
      <Cabecalho
        titulo="Índices"
        subtitulo="Preços semanais da ANP e IGP-DI, comuns a todos os contratos. Clique numa célula para editar."
      />
      <nav className="tabs" aria-label="Séries">
        <NavLink to="/indices/anp" className="tab">ANP semanal</NavLink>
        <NavLink to="/indices/igp-di" className="tab">IGP-DI mensal</NavLink>
      </nav>
      <div className="mt-md">
        <Outlet />
      </div>
    </>
  )
}
```

`NavLink` já aplica a classe `active` à aba da rota atual.

Em `frontend/src/App.tsx`, no nível de `contratos`:

```tsx
        <Route path="indices" element={<PaginaIndices />}>
          <Route index element={<Navigate to="anp" replace />} />
          <Route path="anp" element={<GradeAnp />} />
          <Route path="igp-di" element={<GradeIgpDi />} />
        </Route>
```

com os imports de `PaginaIndices`, `GradeAnp` e `GradeIgpDi` (de `./pages/indices/…`); `Navigate` já é importado de `'react-router'` pela Tarefa 5.

- [ ] **Step 8: Grade do ANP e diálogo de nova semana**

`frontend/src/pages/indices/NovaSemana.tsx`:

```tsx
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { gravarSemanaAnp, REGIOES_ANP } from '../../api/indices'
import { aposIndices } from '../../api/invalidar'
import { Dialogo } from '../../components/Dialogo'
import { MensagemErro } from '../../components/MensagemErro'
import { paraDecimal } from '../../lib/formato'

// Uma semana digitada. Preço vazio = semana sem cotação; a sobreposição com
// outra semana da mesma região é recusada pelo backend e aparece aqui.
export function NovaSemana({ produto, aoFechar }: { produto: string; aoFechar: () => void }) {
  const qc = useQueryClient()
  const [inicio, setInicio] = useState('')
  const [fim, setFim] = useState('')
  const [regiao, setRegiao] = useState('Nordeste')
  const [preco, setPreco] = useState('')
  const [ilegivel, setIlegivel] = useState(false)
  const gravar = useMutation({
    mutationFn: gravarSemanaAnp,
    onSuccess: async () => {
      await aposIndices(qc)
      aoFechar()
    },
  })

  function enviar(e: FormEvent) {
    e.preventDefault()
    const valor = preco.trim() ? paraDecimal(preco) : null
    setIlegivel(preco.trim() !== '' && valor === null)
    if (preco.trim() !== '' && valor === null) return
    gravar.mutate({ produto, vigencia_inicio: inicio, vigencia_fim: fim, regiao, preco: valor })
  }

  return (
    <Dialogo
      titulo="Nova semana"
      aoFechar={aoFechar}
      acoes={
        <>
          <button type="button" className="btn" onClick={aoFechar}>Cancelar</button>
          <button type="submit" form="form-semana" className="btn btn-primary" disabled={!inicio || !fim || gravar.isPending}>
            Gravar
          </button>
        </>
      }
    >
      <p className="contagem">{produto}</p>
      <form id="form-semana" className="field-grid" onSubmit={enviar}>
        <div className="field">
          <label className="field-label" htmlFor="semana-inicio">Início da vigência</label>
          <input id="semana-inicio" type="date" className="input" value={inicio} onChange={(e) => setInicio(e.target.value)} />
        </div>
        <div className="field">
          <label className="field-label" htmlFor="semana-fim">Fim da vigência</label>
          <input id="semana-fim" type="date" className="input" value={fim} onChange={(e) => setFim(e.target.value)} />
        </div>
        <div className="field">
          <label className="field-label" htmlFor="semana-regiao">Região</label>
          <select id="semana-regiao" className="input" value={regiao} onChange={(e) => setRegiao(e.target.value)}>
            {REGIOES_ANP.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label className="field-label" htmlFor="semana-preco">Preço (R$)</label>
          <input id="semana-preco" className="input" value={preco} placeholder="vazio = sem cotação" onChange={(e) => setPreco(e.target.value)} />
          {ilegivel && <p className="erro-campo">Número ilegível; use vírgula decimal, como 3,61475.</p>}
        </div>
      </form>
      <MensagemErro erro={gravar.error} />
    </Dialogo>
  )
}
```

`usuario.type` num `input type="date"` do jsdom aceita `2023-01-15`; se a versão do jsdom recusar, use `fireEvent.change(campo, { target: { value: '2023-01-15' } })` no teste.

`frontend/src/pages/indices/GradeAnp.tsx`:

```tsx
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState, type FormEvent } from 'react'
import { chaves } from '../../api/chaves'
import {
  ANP_PRODUTO_CAP, excluirSemanaAnp, gravarSemanaAnp, listarAnp, listarProdutosAnp, urlExportarAnp,
} from '../../api/indices'
import { aposIndices } from '../../api/invalidar'
import { CelulaEditavel } from '../../components/CelulaEditavel'
import { Carregando } from '../../components/Carregando'
import { ConfirmarDialogo } from '../../components/ConfirmarDialogo'
import { Icone } from '../../components/Icone'
import { MensagemErro } from '../../components/MensagemErro'
import { dataHora, exato, semana } from '../../lib/formato'
import { FaixaCobertura } from './FaixaCobertura'
import { montarGradeAnp, type LinhaAnp } from './grade'
import { NovaSemana } from './NovaSemana'

export function GradeAnp() {
  const qc = useQueryClient()
  const [produto, setProduto] = useState(ANP_PRODUTO_CAP)
  const [de, setDe] = useState('')
  const [ate, setAte] = useState('')
  const [periodo, setPeriodo] = useState<{ de?: string; ate?: string }>({})
  const [novaSemana, setNovaSemana] = useState(false)
  const [apagando, setApagando] = useState<LinhaAnp | null>(null)

  const produtos = useQuery({ queryKey: chaves.produtosAnp, queryFn: listarProdutosAnp })
  const semanas = useQuery({
    queryKey: chaves.anp(produto, periodo.de, periodo.ate),
    queryFn: () => listarAnp({ produto, ...periodo }),
    placeholderData: keepPreviousData,
  })
  const grade = useMemo(() => montarGradeAnp(semanas.data ?? []), [semanas.data])

  const apagar = useMutation({
    mutationFn: async (linha: LinhaAnp) => {
      for (const s of Object.values(linha.celulas)) if (s) await excluirSemanaAnp(s.id)
    },
    onSuccess: async () => {
      await aposIndices(qc)
      setApagando(null)
    },
  })

  async function gravar(linha: LinhaAnp, regiao: string, preco: string | null) {
    await gravarSemanaAnp({ produto, regiao, vigencia_inicio: linha.inicio, vigencia_fim: linha.fim, preco })
    await aposIndices(qc)
  }

  function filtrar(e: FormEvent) {
    e.preventDefault()
    setPeriodo({ de: de || undefined, ate: ate || undefined })
  }

  const opcoes = produtos.data?.length ? produtos.data : [ANP_PRODUTO_CAP]
  return (
    <>
      <FaixaCobertura serie="anp" />
      <form className="barra mt-md" onSubmit={filtrar}>
        <div className="field">
          <label className="field-label" htmlFor="anp-produto">Produto</label>
          <select id="anp-produto" className="input" value={produto} onChange={(e) => setProduto(e.target.value)}>
            {opcoes.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label className="field-label" htmlFor="anp-de">De</label>
          <input id="anp-de" type="date" className="input" value={de} onChange={(e) => setDe(e.target.value)} />
        </div>
        <div className="field">
          <label className="field-label" htmlFor="anp-ate">Até</label>
          <input id="anp-ate" type="date" className="input" value={ate} onChange={(e) => setAte(e.target.value)} />
        </div>
        <button type="submit" className="btn">Filtrar</button>
        <span className="espaco" />
        <a className="btn" href={urlExportarAnp({ produto, ...periodo, formato: 'xlsx' })} download>Exportar .xlsx</a>
        <a className="btn" href={urlExportarAnp({ produto, ...periodo, formato: 'csv' })} download>Exportar .csv</a>
        <button type="button" className="btn btn-primary" onClick={() => setNovaSemana(true)}>
          <Icone nome="add" />
          <span>Nova semana</span>
        </button>
      </form>

      <MensagemErro erro={semanas.error} />
      {semanas.isPending && <Carregando />}
      {semanas.data && grade.linhas.length === 0 && <p className="contagem mt-md">Nenhuma semana gravada para este produto e período.</p>}
      {grade.linhas.length > 0 && (
        <section className="panel mt-md">
          <div className="panel-body flush table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Semana</th>
                  {grade.regioes.map((r) => (
                    <th key={r} className="num">{r}</th>
                  ))}
                  <th />
                </tr>
              </thead>
              <tbody>
                {grade.linhas.map((linha) => {
                  const rotuloSemana = semana(linha.inicio, linha.fim)
                  return (
                    <tr key={`${linha.inicio}|${linha.fim}`}>
                      <td className="num">{rotuloSemana}</td>
                      {grade.regioes.map((regiao) => {
                        const s = linha.celulas[regiao]
                        return (
                          <CelulaEditavel
                            key={regiao}
                            rotulo={`${regiao} ${rotuloSemana}`}
                            valor={s?.preco}
                            formatar={exato}
                            vazio={s ? 'sem cotação' : '—'}
                            manual={s?.origem === 'manual'}
                            titulo={s ? `${s.origem} · ${dataHora(s.atualizado_em)}` : undefined}
                            permiteVazio
                            aoSalvar={(preco) => gravar(linha, regiao, preco)}
                          />
                        )
                      })}
                      <td>
                        <button
                          type="button"
                          className="btn btn-sm"
                          aria-label={`Apagar semana ${rotuloSemana}`}
                          onClick={() => setApagando(linha)}
                        >
                          Apagar
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {novaSemana && <NovaSemana produto={produto} aoFechar={() => setNovaSemana(false)} />}
      {apagando && (
        <ConfirmarDialogo
          titulo={`Apagar a semana ${semana(apagando.inicio, apagando.fim)}?`}
          mensagem="Os preços de todas as regiões desta semana saem do banco. Cálculos que dependem dela ficam bloqueados até a semana voltar."
          rotuloConfirmar="Apagar"
          perigoso
          pendente={apagar.isPending}
          erro={apagar.error}
          aoCancelar={() => setApagando(null)}
          aoConfirmar={() => apagar.mutate(apagando)}
        />
      )}
    </>
  )
}
```

- [ ] **Step 9: Grade do IGP-DI**

`frontend/src/pages/indices/GradeIgpDi.tsx`:

```tsx
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo } from 'react'
import { chaves } from '../../api/chaves'
import { excluirIgpDi, gravarIgpDi, listarIgpDi, URL_TEMPLATE_IGP_DI, urlExportarIgpDi } from '../../api/indices'
import { aposIndices } from '../../api/invalidar'
import { CelulaEditavel } from '../../components/CelulaEditavel'
import { Carregando } from '../../components/Carregando'
import { MensagemErro } from '../../components/MensagemErro'
import { dataHora, exato, mesAno } from '../../lib/formato'
import { FaixaCobertura } from './FaixaCobertura'
import { montarGradeIgpDi } from './grade'

const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']

export function GradeIgpDi() {
  const qc = useQueryClient()
  const indices = useQuery({ queryKey: chaves.igpDi(), queryFn: listarIgpDi })
  const grade = useMemo(() => montarGradeIgpDi(indices.data ?? [], new Date().getFullYear()), [indices.data])

  async function depois<T>(acao: Promise<T>) {
    await acao
    await aposIndices(qc)
  }

  return (
    <>
      <FaixaCobertura serie="igp_di" />
      <div className="barra mt-md">
        <span className="espaco" />
        <a className="btn" href={URL_TEMPLATE_IGP_DI} download>Baixar template</a>
        <a className="btn" href={urlExportarIgpDi('xlsx')} download>Exportar .xlsx</a>
        <a className="btn" href={urlExportarIgpDi('csv')} download>Exportar .csv</a>
      </div>

      <MensagemErro erro={indices.error} />
      {indices.isPending && <Carregando />}
      {indices.data && (
        <section className="panel mt-md">
          <div className="panel-body flush table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Ano</th>
                  {MESES.map((m) => (
                    <th key={m} className="num">{m}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {grade.anos.map((ano) => (
                  <tr key={ano}>
                    <td className="num">{ano}</td>
                    {MESES.map((_, i) => {
                      const mes = `${ano}-${String(i + 1).padStart(2, '0')}`
                      const indice = grade.valores.get(mes)
                      return (
                        <CelulaEditavel
                          key={mes}
                          rotulo={`IGP-DI ${mesAno(mes)}`}
                          valor={indice?.valor}
                          formatar={exato}
                          manual={indice?.origem === 'manual'}
                          titulo={indice ? `${indice.origem} · ${dataHora(indice.atualizado_em)}` : undefined}
                          aoSalvar={(valor) => depois(gravarIgpDi(mes, valor!))}
                          aoApagar={() => depois(excluirIgpDi(mes))}
                        />
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  )
}
```

Sem `permiteVazio`, `aoSalvar` só recebe número (vazio vai para `aoApagar` ou é ignorado), por isso o `valor!`.

Run: `npm run test -- grade celula indices`
Expected: PASS.

- [ ] **Step 10: Rodar tudo e commitar**

Run: `npm run test && npm run build`
Expected: todos passam; build sem erro.

```bash
git add frontend/src/App.tsx frontend/src/api/indices.ts frontend/src/components/CelulaEditavel.tsx \
  frontend/src/pages/indices frontend/src/styles/telas.css frontend/tests
git commit -m "$(cat <<'EOF'
feat(frontend): grades editáveis de preços ANP e IGP-DI

Semanas × regiões (as cinco fixas e as extras com dados) e anos × meses,
com edição na célula: Enter grava, Esc cancela, recusa da API volta ao
valor do banco com o motivo. Valores manuais marcados, origem e data no
title, faixa de cobertura, nova semana, apagar semana com confirmação e
links de exportação e do template do IGP-DI.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarefa 10: Importação de índices em dois passos

**Files:**
- Modify: `frontend/src/api/indices.ts` (`importarIndices`)
- Create: `frontend/src/pages/indices/ImportarIndices.tsx`
- Modify: `frontend/src/pages/indices/GradeAnp.tsx`, `frontend/src/pages/indices/GradeIgpDi.tsx` (botão **Importar**)
- Create: `frontend/tests/importar.test.tsx`

**Interfaces:**
- Consumes: `pedir` com `form` e `params` (Tarefa 4); `ResultadoImportacao`, `ErroApi` (com `erros`); `aposIndices(qc)`; `Dialogo`, `MensagemErro`; `exato`, `mesAno`, `semana`, `dataHora`, `data`; `GradeAnp` e `GradeIgpDi` (Tarefa 9).
- Produces:
  - `src/api/indices.ts`: `type SerieIndice = 'anp' | 'igp-di'`; `importarIndices(serie, arquivo: File, opcoes: { simular: boolean; sobrescrever_manuais?: boolean }): Promise<ResultadoImportacao>`.
  - `ImportarIndices({ serie, aoFechar })` — diálogo; o botão **Importar** das duas grades o abre.

O backend (`app/services/importacao.py`) já faz tudo que este diálogo mostra: `simular=true` compara com o banco sem gravar; na prévia sem sobrescrever, os conflitos com valores manuais ficam **fora** de `atualizados` e dentro de `conflitos_manuais`. Arquivo inválido é 422 com `erros` por linha, que `MensagemErro` já lista. Nada é gravado em arquivo inválido — é tudo ou nada.

- [ ] **Step 1: Testes**

`frontend/tests/importar.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import type { ResultadoImportacao } from '../src/api/tipos'
import { umaCobertura } from './fabricas'
import { renderApp } from './render'
import { servidor } from './servidor'

function umResultado(parcial: Partial<ResultadoImportacao> = {}): ResultadoImportacao {
  return {
    arquivo: 'igp_di.xlsx',
    simulacao: true,
    periodo: { de: '2022-01-01', ate: '2023-03-01' },
    inseridos: 1,
    atualizados: [{ chave: { mes: '2022-06' }, antes: '1001', depois: '1002' }],
    inalterados: 12,
    conflitos_manuais: [
      { chave: { mes: '2023-02' }, valor_banco: '1085.3', valor_arquivo: '1084.9', atualizado_em: '2026-09-24T10:02:00+00:00' },
    ],
    manuais_preservados: 1,
    avisos: ['Linha 20 vazia, ignorada.'],
    ...parcial,
  }
}

function preparar(respostas: (params: URLSearchParams) => Response) {
  const pedidos: URLSearchParams[] = []
  servidor.use(
    http.get('/api/v1/indices/cobertura', () => HttpResponse.json(umaCobertura())),
    http.get('/api/v1/indices/igp-di', () => HttpResponse.json([])),
    http.post('/api/v1/indices/igp-di/importar', async ({ request }) => {
      const form = await request.formData()
      expect(form.get('arquivo')).toBeInstanceOf(File)
      const params = new URL(request.url).searchParams
      pedidos.push(params)
      return respostas(params)
    }),
  )
  return pedidos
}

const arquivo = () => new File(['conteudo'], 'igp_di.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })

async function abrirPrevia() {
  const { usuario } = renderApp('/indices/igp-di')
  await usuario.click(await screen.findByRole('button', { name: 'Importar' }))
  const dialogo = screen.getByRole('dialog')
  await usuario.upload(within(dialogo).getByLabelText('Arquivo'), arquivo())
  await usuario.click(within(dialogo).getByRole('button', { name: 'Ver prévia' }))
  return { usuario, dialogo }
}

describe('Importar índices', () => {
  it('a prévia simula e mostra cartões, conflitos e avisos', async () => {
    const pedidos = preparar(() => HttpResponse.json(umResultado()))
    const { dialogo } = await abrirPrevia()

    expect(await within(dialogo).findByText('Novos')).toBeInTheDocument()
    expect(pedidos[0].get('simular')).toBe('true')
    const cartao = (rotulo: string) => within(dialogo).getByText(rotulo).closest('.cartao')!
    expect(cartao('Novos')).toHaveTextContent('1')
    expect(cartao('Alterados')).toHaveTextContent('1')
    expect(cartao('Iguais')).toHaveTextContent('12')
    expect(cartao('Seus valores manuais em conflito')).toHaveClass('warn')

    const conflito = within(dialogo).getByText('fev/2023').closest('tr')!
    expect(within(conflito).getByText('1.085,3')).toBeInTheDocument()
    expect(within(conflito).getByText('1.084,9')).toBeInTheDocument()
    expect(within(conflito).getByText('24/09/2026 07:02')).toBeInTheDocument()
    expect(within(dialogo).getByText('Linha 20 vazia, ignorada.')).toBeInTheDocument()
  })

  it('gravar mantendo os manuais não sobrescreve e mostra o resumo', async () => {
    const pedidos = preparar((p) => HttpResponse.json(umResultado({ simulacao: p.get('simular') === 'true' })))
    const { usuario, dialogo } = await abrirPrevia()
    await usuario.click(await within(dialogo).findByRole('button', { name: 'Gravar e manter meus valores manuais' }))

    expect(pedidos.at(-1)!.get('simular')).toBe('false')
    expect(pedidos.at(-1)!.get('sobrescrever_manuais')).toBe('false')
    expect(await within(dialogo).findByText('Importação gravada.')).toBeInTheDocument()
    expect(within(dialogo).getByText(/1 valor manual preservado/)).toBeInTheDocument()
  })

  it('sobrescrever os manuais manda sobrescrever_manuais=true', async () => {
    const pedidos = preparar((p) =>
      HttpResponse.json(umResultado({ simulacao: p.get('simular') === 'true', manuais_preservados: p.get('sobrescrever_manuais') === 'true' ? 0 : 1 })),
    )
    const { usuario, dialogo } = await abrirPrevia()
    await usuario.click(await within(dialogo).findByRole('button', { name: 'Gravar e sobrescrever os 1 manuais' }))
    expect(pedidos.at(-1)!.get('sobrescrever_manuais')).toBe('true')
    expect(await within(dialogo).findByText('Importação gravada.')).toBeInTheDocument()
  })

  it('sem conflitos, só um botão de gravar', async () => {
    preparar(() => HttpResponse.json(umResultado({ conflitos_manuais: [], manuais_preservados: 0 })))
    const { dialogo } = await abrirPrevia()
    expect(await within(dialogo).findByRole('button', { name: 'Gravar' })).toBeInTheDocument()
    expect(within(dialogo).queryByRole('button', { name: /sobrescrever/ })).not.toBeInTheDocument()
    expect(within(dialogo).queryByText('Seus valores manuais em conflito')?.closest('.cartao')).not.toHaveClass('warn')
  })

  it('arquivo inválido lista os erros por linha e não sai do primeiro passo', async () => {
    preparar(() =>
      HttpResponse.json(
        { detail: 'O arquivo tem 2 linha(s) inválida(s); nada foi gravado.', erros: ['Linha 3: mês ilegível.', 'Linha 7: valor negativo.'] },
        { status: 422 },
      ),
    )
    const { dialogo } = await abrirPrevia()
    expect(await within(dialogo).findByText('Linha 3: mês ilegível.')).toBeInTheDocument()
    expect(within(dialogo).getByText('Linha 7: valor negativo.')).toBeInTheDocument()
    expect(within(dialogo).getByRole('button', { name: 'Ver prévia' })).toBeInTheDocument()
  })
})
```

Run: `npm run test -- importar`
Expected: FAIL — não há botão Importar.

- [ ] **Step 2: Cliente**

Acrescentar ao fim de `frontend/src/api/indices.ts` (e `ResultadoImportacao` ao import de tipos):

```ts
export type SerieIndice = 'anp' | 'igp-di'

export function importarIndices(
  serie: SerieIndice,
  arquivo: File,
  opcoes: { simular: boolean; sobrescrever_manuais?: boolean },
) {
  const form = new FormData()
  form.append('arquivo', arquivo)
  return pedir<ResultadoImportacao>(`${BASE}/${serie}/importar`, {
    metodo: 'POST',
    form,
    params: { simular: opcoes.simular, sobrescrever_manuais: opcoes.sobrescrever_manuais ?? false },
  })
}
```

`montarUrl` descarta só `undefined`, `null` e `''`: `false` vira `simular=false` na query, que é o que o FastAPI lê.

- [ ] **Step 3: O diálogo**

`frontend/src/pages/indices/ImportarIndices.tsx`:

```tsx
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { importarIndices, type SerieIndice } from '../../api/indices'
import { aposIndices } from '../../api/invalidar'
import type { ResultadoImportacao } from '../../api/tipos'
import { Dialogo } from '../../components/Dialogo'
import { MensagemErro } from '../../components/MensagemErro'
import { data, dataHora, exato, mesAno, semana } from '../../lib/formato'

const TITULO: Record<SerieIndice, string> = {
  anp: 'Importar preços ANP',
  'igp-di': 'Importar IGP-DI',
}

const AJUDA: Record<SerieIndice, string> = {
  anp: 'O .xls semanal da ANP, como publicado (todos os produtos).',
  'igp-di': 'O template do IGP-DI preenchido (.xlsx).',
}

// A chave que o backend devolve em cada conflito: {mes} no IGP-DI,
// {produto, regiao, vigencia_inicio, vigencia_fim} no ANP.
function rotuloChave(chave: Record<string, string>): string {
  if (chave.mes) return mesAno(chave.mes)
  return `${chave.regiao} · ${semana(chave.vigencia_inicio, chave.vigencia_fim)} · ${chave.produto}`
}

type Passo = 'arquivo' | 'previa' | 'gravado'

export function ImportarIndices({ serie, aoFechar }: { serie: SerieIndice; aoFechar: () => void }) {
  const qc = useQueryClient()
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [passo, setPasso] = useState<Passo>('arquivo')
  const [resultado, setResultado] = useState<ResultadoImportacao | null>(null)

  const simular = useMutation({
    mutationFn: (f: File) => importarIndices(serie, f, { simular: true }),
    onSuccess: (r) => {
      setResultado(r)
      setPasso('previa')
    },
  })
  const gravar = useMutation({
    mutationFn: (sobrescrever: boolean) =>
      importarIndices(serie, arquivo!, { simular: false, sobrescrever_manuais: sobrescrever }),
    onSuccess: async (r) => {
      setResultado(r)
      setPasso('gravado')
      await aposIndices(qc)
    },
  })

  const conflitos = resultado?.conflitos_manuais.length ?? 0
  const acoes =
    passo === 'arquivo' ? (
      <>
        <button type="button" className="btn" onClick={aoFechar}>Cancelar</button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={!arquivo || simular.isPending}
          onClick={() => arquivo && simular.mutate(arquivo)}
        >
          Ver prévia
        </button>
      </>
    ) : passo === 'previa' ? (
      <>
        <button type="button" className="btn" onClick={aoFechar}>Cancelar</button>
        {conflitos > 0 ? (
          <>
            <button type="button" className="btn" disabled={gravar.isPending} onClick={() => gravar.mutate(true)}>
              Gravar e sobrescrever os {conflitos} manuais
            </button>
            <button type="button" className="btn btn-primary" disabled={gravar.isPending} onClick={() => gravar.mutate(false)}>
              Gravar e manter meus valores manuais
            </button>
          </>
        ) : (
          <button type="button" className="btn btn-primary" disabled={gravar.isPending} onClick={() => gravar.mutate(false)}>
            Gravar
          </button>
        )}
      </>
    ) : (
      <button type="button" className="btn btn-primary" onClick={aoFechar}>Fechar</button>
    )

  return (
    <Dialogo titulo={TITULO[serie]} aoFechar={aoFechar} acoes={acoes}>
      <ol className="passos" aria-label="Passos">
        <li className={passo === 'arquivo' ? 'passo active' : 'passo'}>1. Arquivo</li>
        <li className={passo === 'previa' ? 'passo active' : 'passo'}>2. Prévia</li>
        <li className={passo === 'gravado' ? 'passo active' : 'passo'}>3. Gravado</li>
      </ol>

      {passo === 'arquivo' && (
        <div className="field mt-md">
          <label className="field-label" htmlFor="importar-arquivo">Arquivo</label>
          <input
            id="importar-arquivo"
            type="file"
            className="input"
            accept={serie === 'anp' ? '.xls,.xlsx' : '.xlsx'}
            onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
          />
          <p className="contagem">{AJUDA[serie]} Nada é gravado antes da prévia.</p>
        </div>
      )}

      {passo === 'previa' && resultado && <Previa resultado={resultado} />}

      {passo === 'gravado' && resultado && (
        <div className="notice ok mt-md" role="status">
          <div>
            <p className="notice-title">Importação gravada.</p>
            <p className="notice-text">
              {resultado.inseridos} novos, {resultado.atualizados.length} alterados, {resultado.inalterados} iguais
              {resultado.manuais_preservados > 0 &&
                `; ${resultado.manuais_preservados} ${resultado.manuais_preservados === 1 ? 'valor manual preservado' : 'valores manuais preservados'}`}
              .
            </p>
          </div>
        </div>
      )}

      <MensagemErro erro={simular.error ?? gravar.error} />
    </Dialogo>
  )
}

function Previa({ resultado }: { resultado: ResultadoImportacao }) {
  const formatarPeriodo = resultado.periodo.de?.endsWith('-01') ? mesAno : data
  const conflitos = resultado.conflitos_manuais
  return (
    <>
      <p className="contagem mt-md">
        {resultado.arquivo}
        {resultado.periodo.de && ` · ${formatarPeriodo(resultado.periodo.de)} a ${formatarPeriodo(resultado.periodo.ate)}`}
      </p>
      <div className="cartoes mt-md">
        <div className="cartao"><strong>{resultado.inseridos}</strong>Novos</div>
        <div className="cartao"><strong>{resultado.atualizados.length}</strong>Alterados</div>
        <div className="cartao"><strong>{resultado.inalterados}</strong>Iguais</div>
        <div className={conflitos.length > 0 ? 'cartao warn' : 'cartao'}>
          <strong>{conflitos.length}</strong>Seus valores manuais em conflito
        </div>
      </div>

      {conflitos.length > 0 && (
        <div className="table-scroll mt-md">
          <table className="data-table">
            <thead>
              <tr>
                <th>Registro</th>
                <th className="num">No banco (manual)</th>
                <th className="num">No arquivo</th>
                <th>Editado em</th>
              </tr>
            </thead>
            <tbody>
              {conflitos.map((c) => (
                <tr key={JSON.stringify(c.chave)}>
                  <td>{rotuloChave(c.chave)}</td>
                  <td className="num">{exato(c.valor_banco)}</td>
                  <td className="num">{exato(c.valor_arquivo)}</td>
                  <td>{dataHora(c.atualizado_em)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {resultado.avisos.length > 0 && (
        <div className="notice warn mt-md">
          <div>
            <p className="notice-title">Avisos</p>
            <ul className="lista-erros">
              {resultado.avisos.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </>
  )
}
```

A prévia do ANP abrange a vigência (`periodo` em datas cheias) e a do IGP-DI meses (`AAAA-MM-01`); o `endsWith('-01')` escolhe o formato — uma semana ANP que começa num dia 1 aparece como mês, o que ainda é legível e só afeta a linha de contexto.

- [ ] **Step 4: Botão Importar nas grades**

Em `frontend/src/pages/indices/GradeAnp.tsx`: `import { ImportarIndices } from './ImportarIndices'`; estado `const [importando, setImportando] = useState(false)`; antes do botão **Nova semana**:

```tsx
        <button type="button" className="btn" onClick={() => setImportando(true)}>
          <Icone nome="upload_file" />
          <span>Importar</span>
        </button>
```

e, junto aos outros diálogos no fim do JSX:

```tsx
      {importando && <ImportarIndices serie="anp" aoFechar={() => setImportando(false)} />}
```

Em `frontend/src/pages/indices/GradeIgpDi.tsx`: os mesmos imports (`useState` de `'react'`, `Icone` de `'../../components/Icone'`, `ImportarIndices`), o mesmo estado, o botão depois de **Exportar .csv**:

```tsx
        <button type="button" className="btn btn-primary" onClick={() => setImportando(true)}>
          <Icone nome="upload_file" />
          <span>Importar</span>
        </button>
```

e o diálogo com `serie="igp-di"` no fim do JSX.

Run: `npm run test -- importar indices`
Expected: PASS.

- [ ] **Step 5: Rodar tudo e commitar**

Run: `npm run test && npm run build`
Expected: todos passam; build sem erro.

```bash
git add frontend/src/api/indices.ts frontend/src/pages/indices frontend/tests/importar.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): importação de índices com prévia e conflitos manuais

O arquivo é simulado primeiro: cartões de novos, alterados, iguais e
valores manuais em conflito, tabela dos conflitos e avisos. Gravar mantém
os manuais por padrão; sobrescrever é um botão à parte, só quando há
conflito. Arquivo inválido lista os erros por linha sem sair do passo 1.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarefa 11: Upload de PDFs

**Files:**
- Create: `frontend/src/api/jobs.ts`
- Create: `frontend/src/pages/upload/{PaginaUpload.tsx,AreaArquivos.tsx,TabelaLote.tsx,LotesAnteriores.tsx}`
- Modify: `frontend/src/App.tsx` (rota `upload`)
- Modify: `frontend/src/lib/formato.ts` (`tamanho`), `frontend/tests/formato.test.ts`
- Create: `frontend/tests/{jobs.test.ts,upload.test.tsx}`

**Interfaces:**
- Consumes: `pedir`, `caminhoCom` (Tarefa 4); `StatusJob`, `ArquivoDoJob`, `StatusArquivo`, `ResumoJob` (com `contrato_id` e `itens` que a Tarefa 3 acrescentou ao status); `chaves.jobs(status)`, `chaves.contratos`; `aposUpload(qc)`; `listarContratos` (Tarefa 5); `Cabecalho`, `Icone`, `MensagemErro`; `dataHora`.
- Produces:
  - `src/api/jobs.ts`: `enviarPdfs(arquivos: File[]): Promise<{ job_id: string }>`, `buscarStatusJob(id)`, `listarJobs(status)`, `tentarDeNovo(id, arquivo)`, `urlResultado(id, arquivo)`, `urlZip(id)`, `acompanharJob(id, { aoAtualizar, aoTerminar }, intervalo = 1500): () => void`.
  - `tamanho(bytes: number): string` em `src/lib/formato.ts` (`'48 KB'`, `'3,3 MB'`).
  - `PaginaUpload` na rota `/upload`.

Rotas do backend (`app/routers/upload.py`, `app/routers/jobs.py`), que esta tarefa só consome: `POST /upload` (multipart, campo `files`, repetido) → `{job_id}`; `GET /jobs?status=active|completed` → `ResumoJob[]` (50 mais recentes); `GET /jobs/{id}/status` → `StatusJob`; `GET /jobs/{id}/events` → SSE com `data: <StatusJob>` a cada mudança e, ao fim, `event: complete`; `GET /jobs/{id}/download/{arquivo}` (JSON de um arquivo) e `/download` (zip, 409 enquanto processa); `POST /jobs/{id}/retry/{arquivo}` (só em `failed`). O status não informa progresso por página: a tabela mostra só pendente, processando, concluído ou falhou.

- [ ] **Step 1: Testes do acompanhamento**

`frontend/tests/jobs.test.ts`:

```ts
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { acompanharJob } from '../src/api/jobs'
import type { StatusJob } from '../src/api/tipos'
import { servidor } from './servidor'

const status = (completed: boolean): StatusJob => ({
  job_id: 'j1',
  completed,
  files: { 'a.pdf': { status: completed ? 'completed' : 'processing', error: null, contrato_id: null, itens: null } },
})

class EventSourceFalso {
  static ultima: EventSourceFalso
  onmessage: ((e: MessageEvent) => void) | null = null
  onerror: (() => void) | null = null
  ouvintes: Record<string, () => void> = {}
  fechada = false
  constructor(public url: string) {
    EventSourceFalso.ultima = this
  }
  addEventListener(nome: string, f: () => void) {
    this.ouvintes[nome] = f
  }
  close() {
    this.fechada = true
  }
}

afterEach(() => vi.unstubAllGlobals())

describe('acompanharJob', () => {
  it('com EventSource, repassa cada status e termina no evento complete', () => {
    vi.stubGlobal('EventSource', EventSourceFalso)
    const aoAtualizar = vi.fn()
    const aoTerminar = vi.fn()
    acompanharJob('j1', { aoAtualizar, aoTerminar })
    const es = EventSourceFalso.ultima
    expect(es.url).toBe('/jobs/j1/events')

    es.onmessage!(new MessageEvent('message', { data: JSON.stringify(status(false)) }))
    expect(aoAtualizar).toHaveBeenCalledWith(status(false))
    es.ouvintes.complete()
    expect(aoTerminar).toHaveBeenCalled()
    expect(es.fechada).toBe(true)
  })

  it('se o SSE cair, passa a consultar o status até concluir', async () => {
    vi.stubGlobal('EventSource', EventSourceFalso)
    let chamadas = 0
    servidor.use(http.get('/jobs/j1/status', () => HttpResponse.json(status(++chamadas >= 2))))
    const aoTerminar = vi.fn()
    const aoAtualizar = vi.fn()
    acompanharJob('j1', { aoAtualizar, aoTerminar }, 5)
    EventSourceFalso.ultima.onerror!()
    expect(EventSourceFalso.ultima.fechada).toBe(true)
    await vi.waitFor(() => expect(aoTerminar).toHaveBeenCalled())
    expect(aoAtualizar).toHaveBeenLastCalledWith(status(true))
  })

  it('sem EventSource, consulta o status; cancelar interrompe', async () => {
    vi.stubGlobal('EventSource', undefined)
    const pedidos = vi.fn()
    servidor.use(
      http.get('/jobs/j1/status', () => {
        pedidos()
        return HttpResponse.json(status(false))
      }),
    )
    const cancelar = acompanharJob('j1', { aoAtualizar: vi.fn(), aoTerminar: vi.fn() }, 5)
    await vi.waitFor(() => expect(pedidos).toHaveBeenCalledTimes(2))
    cancelar()
    const feitos = pedidos.mock.calls.length
    await new Promise((r) => setTimeout(r, 30))
    expect(pedidos.mock.calls.length).toBeLessThanOrEqual(feitos + 1)
  })
})
```

Run: `npm run test -- jobs`
Expected: FAIL — módulo não existe.

- [ ] **Step 2: Implementar `api/jobs.ts`**

`frontend/src/api/jobs.ts`:

```ts
import { caminhoCom, pedir } from './client'
import type { ResumoJob, StatusJob } from './tipos'

const c = encodeURIComponent

export function enviarPdfs(arquivos: File[]) {
  const form = new FormData()
  for (const a of arquivos) form.append('files', a)
  return pedir<{ job_id: string }>('/upload', { metodo: 'POST', form })
}

export const buscarStatusJob = (id: string) => pedir<StatusJob>(`/jobs/${c(id)}/status`)

export const listarJobs = (status: 'active' | 'completed') => pedir<ResumoJob[]>('/jobs', { params: { status } })

export const tentarDeNovo = (id: string, arquivo: string) =>
  pedir<unknown>(`/jobs/${c(id)}/retry/${c(arquivo)}`, { metodo: 'POST' })

export const urlResultado = (id: string, arquivo: string) => caminhoCom(`/jobs/${c(id)}/download/${c(arquivo)}`)

export const urlZip = (id: string) => caminhoCom(`/jobs/${c(id)}/download`)

interface Ouvintes {
  aoAtualizar: (s: StatusJob) => void
  aoTerminar: () => void
}

// SSE quando o navegador tem EventSource e a conexão aguenta; se ela cair (proxy
// que corta streams, por exemplo), consulta /status até o lote concluir.
// Devolve a função que para de acompanhar.
export function acompanharJob(id: string, { aoAtualizar, aoTerminar }: Ouvintes, intervalo = 1500): () => void {
  let parado = false
  let temporizador: ReturnType<typeof setTimeout> | undefined
  let fonte: EventSource | undefined

  async function consultar() {
    if (parado) return
    try {
      const s = await buscarStatusJob(id)
      if (parado) return
      aoAtualizar(s)
      if (s.completed) {
        aoTerminar()
        return
      }
    } catch {
      // Falha passageira: a próxima volta tenta de novo.
    }
    temporizador = setTimeout(consultar, intervalo)
  }

  if (typeof EventSource === 'undefined') {
    void consultar()
  } else {
    fonte = new EventSource(`/jobs/${c(id)}/events`)
    fonte.onmessage = (e) => aoAtualizar(JSON.parse(e.data) as StatusJob)
    fonte.addEventListener('complete', () => {
      fonte?.close()
      aoTerminar()
    })
    fonte.onerror = () => {
      fonte?.close()
      fonte = undefined
      void consultar()
    }
  }

  return () => {
    parado = true
    fonte?.close()
    clearTimeout(temporizador)
  }
}
```

Run: `npm run test -- jobs`
Expected: PASS.

- [ ] **Step 3: Testes da tela**

`frontend/tests/upload.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ResumoJob, StatusJob } from '../src/api/tipos'
import { renderApp } from './render'
import { servidor } from './servidor'

// jsdom não tem EventSource: a tela segue pelo /status, como num proxy que corta SSE.
beforeEach(() => vi.stubGlobal('EventSource', undefined))

function umStatus(completed: boolean, files: StatusJob['files']): StatusJob {
  return { job_id: 'j1', completed, files }
}

const CONCLUIDO = umStatus(true, {
  'medicao_fev.pdf': { status: 'completed', error: null, contrato_id: 1, itens: 48 },
  'escaneado.pdf': { status: 'failed', error: 'Nenhum registro encontrado no PDF.', contrato_id: null, itens: null },
})

function umResumo(parcial: Partial<ResumoJob> = {}): ResumoJob {
  return {
    job_id: 'antigo',
    created_at: '2026-09-20T13:00:00+00:00',
    completed: true,
    file_count: 3,
    completed_count: 3,
    failed_count: 0,
    processing_count: 0,
    pending_count: 0,
    ...parcial,
  }
}

function preparar({ ativos = [] as ResumoJob[], status = CONCLUIDO } = {}) {
  const enviados: string[] = []
  const retentativas: string[] = []
  servidor.use(
    http.get('/api/v1/contratos', () =>
      HttpResponse.json([{ id: 1, numero: '15 00716/2022', data_base: null, contratada: null, rodovia: null, regioes: {} }]),
    ),
    http.get('/jobs', ({ request }) =>
      HttpResponse.json(new URL(request.url).searchParams.get('status') === 'active' ? ativos : [umResumo()]),
    ),
    http.post('/upload', async ({ request }) => {
      const form = await request.formData()
      for (const f of form.getAll('files')) enviados.push((f as File).name)
      return HttpResponse.json({ job_id: 'j1' })
    }),
    http.get('/jobs/:id/status', () => HttpResponse.json(status)),
    http.post('/jobs/j1/retry/:arquivo', ({ params }) => {
      retentativas.push(params.arquivo as string)
      return HttpResponse.json({ ok: true })
    }),
  )
  return { enviados, retentativas }
}

const pdf = (nome: string) => new File(['%PDF-1.4'], nome, { type: 'application/pdf' })

describe('Upload de PDFs', () => {
  it('envia os PDFs escolhidos e mostra o resultado de cada um', async () => {
    const { enviados } = preparar()
    const { usuario } = renderApp('/upload')
    await usuario.upload(screen.getByLabelText('Arquivos PDF'), [pdf('medicao_fev.pdf'), pdf('escaneado.pdf')])
    expect(screen.getByText('2 arquivos selecionados')).toBeInTheDocument()
    await usuario.click(screen.getByRole('button', { name: 'Enviar para processamento' }))

    const ok = (await screen.findByText('medicao_fev.pdf', { selector: 'td' })).closest('tr')!
    expect(enviados).toEqual(['medicao_fev.pdf', 'escaneado.pdf'])
    expect(await within(ok).findByText('Concluído')).toHaveClass('badge-completed')
    expect(within(ok).getByText(/48 itens/)).toBeInTheDocument()
    expect(within(ok).getByRole('link', { name: '15 00716/2022' })).toHaveAttribute('href', '/contratos/1')
    expect(within(ok).getByRole('link', { name: 'JSON' })).toHaveAttribute('href', '/jobs/j1/download/medicao_fev.pdf')

    const falhou = screen.getByText('escaneado.pdf', { selector: 'td' }).closest('tr')!
    expect(within(falhou).getByText('Falhou')).toHaveClass('badge-failed')
    expect(within(falhou).getByText('Nenhum registro encontrado no PDF.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Baixar todos os resultados (.zip)' })).toHaveAttribute('href', '/jobs/j1/download')
  })

  it('tentar de novo reenvia o arquivo que falhou', async () => {
    const { retentativas } = preparar({ ativos: [umResumo({ job_id: 'j1', completed: false })] })
    const { usuario } = renderApp('/upload')
    const falhou = (await screen.findByText('escaneado.pdf', { selector: 'td' })).closest('tr')!
    await usuario.click(within(falhou).getByRole('button', { name: 'Tentar de novo' }))
    expect(retentativas).toEqual(['escaneado.pdf'])
  })

  it('retoma o lote em andamento ao abrir a tela', async () => {
    preparar({
      ativos: [umResumo({ job_id: 'j1', completed: false })],
      status: umStatus(false, { 'lento.pdf': { status: 'processing', error: null, contrato_id: null, itens: null } }),
    })
    renderApp('/upload')
    const linha = (await screen.findByText('lento.pdf', { selector: 'td' })).closest('tr')!
    expect(within(linha).getByText('Processando')).toHaveClass('badge-processing')
    expect(screen.queryByRole('link', { name: 'Baixar todos os resultados (.zip)' })).not.toBeInTheDocument()
  })

  it('só aceita PDF', async () => {
    preparar()
    const { usuario } = renderApp('/upload', { applyAccept: false })
    await usuario.upload(screen.getByLabelText('Arquivos PDF'), [pdf('a.pdf'), new File(['x'], 'planilha.xlsx')])
    expect(screen.getByText('1 arquivo selecionado')).toBeInTheDocument()
    expect(screen.getByText('Ignorado: planilha.xlsx (não é PDF).')).toBeInTheDocument()
  })

  it('lotes anteriores ficam recolhidos, com o zip de cada um', async () => {
    preparar()
    const { usuario } = renderApp('/upload')
    await usuario.click(await screen.findByText('Lotes anteriores (1)'))
    const linha = screen.getByText('20/09/2026 10:00').closest('tr')!
    expect(within(linha).getByText('3 de 3')).toBeInTheDocument()
    expect(within(linha).getByRole('link', { name: 'Baixar .zip' })).toHaveAttribute('href', '/jobs/antigo/download')
  })
})
```

O quarto teste passa `{ applyAccept: false }` para o `userEvent` deixar passar o `.xlsx` apesar do `accept=".pdf"` — é o que acontece quando o usuário solta arquivos na área de arrastar, que não respeita `accept`. `renderApp(rota, opcoesUsuario?)` (Tarefa 1) repassa o segundo argumento a `userEvent.setup`.

Run: `npm run test -- upload`
Expected: FAIL — rota `upload` não existe.

- [ ] **Step 4: Tamanho de arquivo e área de arquivos**

Acrescentar ao fim de `frontend/tests/formato.test.ts`:

```ts
describe('tamanho', () => {
  it('KB até 1 MB, MB com uma casa depois', () => {
    expect(tamanho(200)).toBe('1 KB')
    expect(tamanho(48 * 1024)).toBe('48 KB')
    expect(tamanho(3.25 * 1024 * 1024)).toBe('3,3 MB')
  })
})
```

(e `tamanho` ao import de `../src/lib/formato` no topo do arquivo). Acrescentar ao fim de `frontend/src/lib/formato.ts`:

```ts
// Tamanho de arquivo para listas e para a área de upload.
export function tamanho(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / 1024 / 1024).toFixed(1).replace('.', ',')} MB`
}
```

A Tarefa 12 usa o mesmo `tamanho` nas listas de templates e backups.

`frontend/src/pages/upload/AreaArquivos.tsx`:

```tsx
import { useState, type DragEvent } from 'react'
import { Icone } from '../../components/Icone'
import { tamanho } from '../../lib/formato'

const ehPdf = (f: File) => f.name.toLowerCase().endsWith('.pdf')

interface Props {
  arquivos: File[]
  aoEscolher: (arquivos: File[]) => void
  desabilitado: boolean
}

// Arrastar e soltar ou escolher. Soltar não respeita o accept do input, por isso
// o filtro de PDF é feito aqui e o ignorado é dito ao usuário.
export function AreaArquivos({ arquivos, aoEscolher, desabilitado }: Props) {
  const [sobre, setSobre] = useState(false)
  const [ignorados, setIgnorados] = useState<string[]>([])

  function receber(lista: FileList | null) {
    const todos = [...(lista ?? [])]
    setIgnorados(todos.filter((f) => !ehPdf(f)).map((f) => f.name))
    aoEscolher(todos.filter(ehPdf))
  }

  function soltar(e: DragEvent) {
    e.preventDefault()
    setSobre(false)
    if (!desabilitado) receber(e.dataTransfer.files)
  }

  const total = arquivos.reduce((soma, f) => soma + f.size, 0)
  return (
    <>
      <label
        className={sobre ? 'dropzone over' : 'dropzone'}
        onDragOver={(e) => {
          e.preventDefault()
          setSobre(true)
        }}
        onDragLeave={() => setSobre(false)}
        onDrop={soltar}
      >
        <input
          type="file"
          accept=".pdf"
          multiple
          aria-label="Arquivos PDF"
          disabled={desabilitado}
          onChange={(e) => {
            receber(e.target.files)
            e.target.value = ''
          }}
        />
        <span className="dropzone-icon"><Icone nome="cloud_upload" /></span>
        <span className="dropzone-title">Arraste os PDFs aqui ou clique para escolher</span>
        <span className="dropzone-text">
          PDFs de Resumo da Medição, com texto ou digitalizados. Os digitalizados passam pelo OCR automaticamente.
        </span>
        <span className="dropzone-meta">
          <span>
            <Icone nome="summarize" />
            <span>
              {arquivos.length === 0
                ? 'Nenhum arquivo selecionado'
                : `${arquivos.length} ${arquivos.length === 1 ? 'arquivo selecionado' : 'arquivos selecionados'}`}
            </span>
          </span>
          {arquivos.length > 0 && (
            <span>
              <Icone nome="scale" />
              <span>{tamanho(total)}</span>
            </span>
          )}
        </span>
      </label>
      {ignorados.length > 0 && (
        <p className="erro-campo mt-md">Ignorado: {ignorados.join(', ')} (não é PDF).</p>
      )}
    </>
  )
}
```

`style.css` (via `upload.css`, Tarefa 1) esconde o `input[type=file]` dentro de `.dropzone`; o `label` o aciona ao clique.

- [ ] **Step 5: Tabela do lote e lotes anteriores**

`frontend/src/pages/upload/TabelaLote.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { chaves } from '../../api/chaves'
import { listarContratos } from '../../api/contratos'
import { urlResultado, urlZip } from '../../api/jobs'
import type { StatusArquivo, StatusJob } from '../../api/tipos'
import { Icone } from '../../components/Icone'

const ROTULO: Record<StatusArquivo, string> = {
  pending: 'Pendente',
  processing: 'Processando',
  completed: 'Concluído',
  failed: 'Falhou',
}

interface Props {
  status: StatusJob
  aoTentarDeNovo: (arquivo: string) => void
  tentando: string | null
}

export function TabelaLote({ status, aoTentarDeNovo, tentando }: Props) {
  const contratos = useQuery({ queryKey: chaves.contratos, queryFn: listarContratos })
  const numero = (id: number) => contratos.data?.find((c) => c.id === id)?.numero ?? `contrato ${id}`
  const arquivos = Object.entries(status.files)
  const concluidos = arquivos.filter(([, a]) => a.status === 'completed').length

  return (
    <section className="panel mt-md">
      <div className="panel-head">
        <h2 className="panel-title">Arquivos no lote</h2>
        <span className="badge badge-mono">
          {concluidos} de {arquivos.length} concluídos
        </span>
      </div>
      <div className="panel-body flush table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Arquivo</th>
              <th>Status</th>
              <th>Resultado</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {arquivos.map(([nome, a]) => (
              <tr key={nome}>
                <td className="file-row-name">{nome}</td>
                <td>
                  <span className={`badge badge-${a.status}`}>{ROTULO[a.status]}</span>
                </td>
                <td>
                  {a.status === 'completed' && a.contrato_id !== null && (
                    <>
                      {a.itens} {a.itens === 1 ? 'item' : 'itens'} →{' '}
                      <Link to={`/contratos/${a.contrato_id}`}>{numero(a.contrato_id)}</Link>
                    </>
                  )}
                  {a.status === 'failed' && <span className="erro-campo">{a.error}</span>}
                </td>
                <td>
                  {a.status === 'completed' && (
                    <a className="btn btn-sm" href={urlResultado(status.job_id, nome)} download>JSON</a>
                  )}
                  {a.status === 'failed' && (
                    <button
                      type="button"
                      className="btn btn-sm"
                      disabled={tentando === nome}
                      onClick={() => aoTentarDeNovo(nome)}
                    >
                      Tentar de novo
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {status.completed && concluidos > 0 && (
        <div className="barra panel-body">
          <span className="espaco" />
          <a className="btn" href={urlZip(status.job_id)} download>
            <Icone nome="folder_zip" />
            <span>Baixar todos os resultados (.zip)</span>
          </a>
        </div>
      )}
    </section>
  )
}
```

`frontend/src/pages/upload/LotesAnteriores.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query'
import { chaves } from '../../api/chaves'
import { listarJobs, urlZip } from '../../api/jobs'
import { dataHora } from '../../lib/formato'

export function LotesAnteriores() {
  const lotes = useQuery({ queryKey: chaves.jobs('completed'), queryFn: () => listarJobs('completed') })
  if (!lotes.data?.length) return null
  return (
    <details className="lotes mt-md">
      <summary>Lotes anteriores ({lotes.data.length})</summary>
      <div className="table-scroll mt-md">
        <table className="data-table">
          <thead>
            <tr>
              <th>Enviado em</th>
              <th className="num">Concluídos</th>
              <th className="num">Falhas</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {lotes.data.map((l) => (
              <tr key={l.job_id}>
                <td>{dataHora(l.created_at)}</td>
                <td className="num">{l.completed_count} de {l.file_count}</td>
                <td className={l.failed_count > 0 ? 'num neg' : 'num'}>{l.failed_count}</td>
                <td>
                  {l.completed_count > 0 && (
                    <a className="btn btn-sm" href={urlZip(l.job_id)} download>Baixar .zip</a>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
```

- [ ] **Step 6: A página e a rota**

`frontend/src/pages/upload/PaginaUpload.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { chaves } from '../../api/chaves'
import { acompanharJob, enviarPdfs, listarJobs, tentarDeNovo } from '../../api/jobs'
import { aposUpload } from '../../api/invalidar'
import type { StatusJob } from '../../api/tipos'
import { Cabecalho } from '../../components/Cabecalho'
import { Icone } from '../../components/Icone'
import { MensagemErro } from '../../components/MensagemErro'
import { AreaArquivos } from './AreaArquivos'
import { LotesAnteriores } from './LotesAnteriores'
import { TabelaLote } from './TabelaLote'

export function PaginaUpload() {
  const qc = useQueryClient()
  const [arquivos, setArquivos] = useState<File[]>([])
  const [jobId, setJobId] = useState<string | null>(null)
  const [status, setStatus] = useState<StatusJob | null>(null)
  // Muda a cada retentativa, para reabrir o acompanhamento de um lote já concluído.
  const [rodada, setRodada] = useState(0)

  // Um lote enviado em outra aba (ou antes de recarregar a página) continua aqui.
  const ativos = useQuery({ queryKey: chaves.jobs('active'), queryFn: () => listarJobs('active') })
  useEffect(() => {
    if (!jobId && ativos.data?.length) setJobId(ativos.data[0].job_id)
  }, [jobId, ativos.data])

  useEffect(() => {
    if (!jobId) return
    return acompanharJob(jobId, {
      aoAtualizar: setStatus,
      aoTerminar: () => {
        void aposUpload(qc)
        void qc.invalidateQueries({ queryKey: ['jobs'] })
      },
    })
  }, [jobId, rodada, qc])

  const enviar = useMutation({
    mutationFn: () => enviarPdfs(arquivos),
    onSuccess: ({ job_id }) => {
      setStatus(null)
      setArquivos([])
      setJobId(job_id)
    },
  })
  const repetir = useMutation({
    mutationFn: (arquivo: string) => tentarDeNovo(jobId!, arquivo),
    onSuccess: () => setRodada((r) => r + 1),
  })

  const processando = !!status && !status.completed
  return (
    <>
      <Cabecalho
        titulo="Upload de PDFs"
        subtitulo="Cada PDF grava o contrato e os itens da medição; reenviar o mesmo arquivo não duplica."
      />
      <AreaArquivos arquivos={arquivos} aoEscolher={setArquivos} desabilitado={enviar.isPending} />
      <div className="barra mt-md">
        <span className="contagem">O envio volta na hora; o andamento de cada arquivo aparece abaixo.</span>
        <span className="espaco" />
        {status?.completed && (
          <button
            type="button"
            className="btn"
            onClick={() => {
              setJobId(null)
              setStatus(null)
            }}
          >
            <Icone nome="restart_alt" />
            <span>Novo lote</span>
          </button>
        )}
        <button
          type="button"
          className="btn btn-primary"
          disabled={arquivos.length === 0 || enviar.isPending || processando}
          onClick={() => enviar.mutate()}
        >
          <Icone nome="play_arrow" />
          <span>Enviar para processamento</span>
        </button>
      </div>
      <MensagemErro erro={enviar.error ?? repetir.error} />
      {status && (
        <TabelaLote
          status={status}
          aoTentarDeNovo={(a) => repetir.mutate(a)}
          tentando={repetir.isPending ? (repetir.variables ?? null) : null}
        />
      )}
      <LotesAnteriores />
    </>
  )
}
```

"Novo lote" limpa só a tela: `jobId` nulo não readota o lote porque, concluído, ele já não está em `status=active`.

Em `frontend/src/App.tsx`, antes de `path="*"`:

```tsx
        <Route path="upload" element={<PaginaUpload />} />
```

com `import { PaginaUpload } from './pages/upload/PaginaUpload'`.

Run: `npm run test -- jobs upload formato`
Expected: PASS.

- [ ] **Step 7: Rodar tudo e commitar**

Run: `npm run test && npm run build`
Expected: todos passam; build sem erro.

```bash
git add frontend/src/App.tsx frontend/src/api/jobs.ts frontend/src/lib/formato.ts frontend/src/pages/upload \
  frontend/tests/formato.test.ts frontend/tests/jobs.test.ts frontend/tests/upload.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): upload de PDFs com andamento por arquivo

Área de arrastar e escolher (só PDF, o ignorado é dito), envio que volta
na hora e andamento por SSE, com consulta ao status quando o SSE cai.
Cada arquivo mostra o status, os itens gravados com o link do contrato,
o JSON e "Tentar de novo" nos que falharam; o lote em andamento é
retomado ao abrir a tela, e os anteriores ficam recolhidos com o zip.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarefa 12: Templates e Backups

**Files:**
- Create: `frontend/src/api/sistema.ts`
- Create: `frontend/src/pages/sistema/{PaginaTemplates.tsx,PaginaBackups.tsx,EnviarArquivo.tsx}`
- Modify: `frontend/src/App.tsx` (rotas `sistema/templates`, `sistema/backups`)
- Create: `frontend/tests/sistema.test.tsx`

**Interfaces:**
- Consumes: `pedir`, `caminhoCom` (Tarefa 4); `Template`, `Backup`; `chaves.templates`, `chaves.backups`; `ConfirmarDialogo` (com `textoExigido`), `MensagemErro`, `Cabecalho`, `Icone`, `Carregando`; `dataHora`, `tamanho` (Tarefa 11).
- Produces:
  - `src/api/sistema.ts`: `listarTemplates()`, `enviarTemplate(arquivo, { observacao?, ativar })`, `ativarTemplate(id)`, `excluirTemplate(id)`, `urlTemplate(id)`, `listarBackups()`, `gerarBackup()`, `enviarBackup(arquivo)`, `restaurarBackup(nome, confirmacao): Promise<{ restaurado: string; seguranca: string }>`, `excluirBackup(nome)`, `urlBackup(nome)`.
  - `EnviarArquivo({ rotulo, accept, botao, pendente, aoEnviar, children? })` — campo de arquivo com botão, usado pelas duas páginas.

Rotas do backend (`app/routers/admin.py`), sem mudança: `GET/POST /admin/templates` (multipart `arquivo`, `observacao`, `ativar`), `GET /admin/templates/{id}/download`, `POST /admin/templates/{id}/ativar`, `DELETE /admin/templates/{id}`; `GET/POST /admin/backups`, `GET /admin/backups/{nome}/download`, `POST /admin/backups/upload` (multipart `arquivo`), `POST /admin/backups/{nome}/restaurar` (form `confirmacao`), `DELETE /admin/backups/{nome}`. Toda recusa é `422 {"detail": "<mensagem para o usuário>"}` — template inválido, excluir o ativo, `pg_dump` incompatível, dump inválido — e a tela a mostra como veio.

Restaurar troca o banco inteiro, então depois dele **todo** o cache do TanStack Query é invalidado (`qc.invalidateQueries()` sem chave).

- [ ] **Step 1: Testes**

`frontend/tests/sistema.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Backup, Template } from '../src/api/tipos'
import { renderApp } from './render'
import { servidor } from './servidor'

const TEMPLATES: Template[] = [
  { id: 2, nome: 'reequilibrio_v2.xlsx', tamanho: 48 * 1024, sha256: 'ab'.repeat(32), ativo: true, criado_em: '2026-09-20T13:00:00+00:00', observacao: 'Logo novo' },
  { id: 1, nome: 'reequilibrio_template.xlsx', tamanho: 45 * 1024, sha256: 'cd'.repeat(32), ativo: false, criado_em: '2026-01-10T13:00:00+00:00', observacao: null },
]

const BACKUPS: Backup[] = [
  { nome: 'dnit_20260924_0300_agendado.dump', tamanho: 3.2 * 1024 * 1024, criado_em: '2026-09-24T06:00:00+00:00' },
]

function preparar() {
  const chamadas: { metodo: string; caminho: string; form?: Record<string, FormDataEntryValue> }[] = []
  const registrar = async (request: Request) => {
    const form = request.headers.get('content-type')?.includes('multipart')
      ? Object.fromEntries(await request.formData())
      : undefined
    chamadas.push({ metodo: request.method, caminho: new URL(request.url).pathname, form })
  }
  servidor.use(
    http.get('/admin/templates', () => HttpResponse.json(TEMPLATES)),
    http.post('/admin/templates', async ({ request }) => {
      await registrar(request)
      return HttpResponse.json({ id: 3, ativo: true })
    }),
    http.post('/admin/templates/:id/ativar', async ({ request }) => {
      await registrar(request)
      return HttpResponse.json({ ativo: 1 })
    }),
    http.delete('/admin/templates/:id', async ({ request }) => {
      await registrar(request)
      return HttpResponse.json({ excluido: 1 })
    }),
    http.get('/admin/backups', () => HttpResponse.json(BACKUPS)),
    http.post('/admin/backups', async ({ request }) => {
      await registrar(request)
      return HttpResponse.json(
        { detail: 'pg_dump 17 é mais novo que o servidor 16; defina PG_BIN.' },
        { status: 422 },
      )
    }),
    http.post('/admin/backups/:nome/restaurar', async ({ request }) => {
      await registrar(request)
      return HttpResponse.json({ restaurado: BACKUPS[0].nome, seguranca: 'dnit_20260924_1010_antes_de_restaurar.dump' })
    }),
  )
  return chamadas
}

describe('Templates', () => {
  it('lista com o ativo marcado; o ativo não tem Excluir nem Ativar', async () => {
    preparar()
    renderApp('/sistema/templates')
    const ativo = (await screen.findByText('reequilibrio_v2.xlsx')).closest('tr')!
    expect(within(ativo).getByText('Ativo')).toHaveClass('badge-ok')
    expect(within(ativo).getByText('Logo novo')).toBeInTheDocument()
    expect(within(ativo).getByText('48 KB')).toBeInTheDocument()
    expect(within(ativo).queryByRole('button', { name: /Excluir/ })).not.toBeInTheDocument()
    expect(within(ativo).getByRole('link', { name: 'Baixar' })).toHaveAttribute('href', '/admin/templates/2/download')

    const antigo = screen.getByText('reequilibrio_template.xlsx').closest('tr')!
    expect(within(antigo).getByRole('button', { name: 'Ativar' })).toBeInTheDocument()
  })

  it('ativar e excluir (com confirmação) um template antigo', async () => {
    const chamadas = preparar()
    const { usuario } = renderApp('/sistema/templates')
    const antigo = (await screen.findByText('reequilibrio_template.xlsx')).closest('tr')!
    await usuario.click(within(antigo).getByRole('button', { name: 'Ativar' }))
    expect(chamadas.at(-1)).toMatchObject({ metodo: 'POST', caminho: '/admin/templates/1/ativar' })

    await usuario.click(within(antigo).getByRole('button', { name: 'Excluir' }))
    await usuario.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Excluir' }))
    expect(chamadas.at(-1)).toMatchObject({ metodo: 'DELETE', caminho: '/admin/templates/1' })
  })

  it('enviar um template manda arquivo, observação e ativar', async () => {
    const chamadas = preparar()
    const { usuario } = renderApp('/sistema/templates')
    await screen.findByText('reequilibrio_v2.xlsx')
    await usuario.upload(screen.getByLabelText('Novo template (.xlsx)'), new File(['x'], 'v3.xlsx'))
    await usuario.type(screen.getByLabelText('Observação'), 'Rodapé corrigido')
    await usuario.click(screen.getByRole('button', { name: 'Enviar template' }))
    const envio = chamadas.at(-1)!
    expect(envio.caminho).toBe('/admin/templates')
    expect((envio.form!.arquivo as File).name).toBe('v3.xlsx')
    expect(envio.form!.observacao).toBe('Rodapé corrigido')
    expect(envio.form!.ativar).toBe('true')
  })
})

describe('Backups', () => {
  it('gerar mostra a recusa do backend como veio', async () => {
    preparar()
    const { usuario } = renderApp('/sistema/backups')
    await usuario.click(await screen.findByRole('button', { name: 'Gerar backup agora' }))
    expect(await screen.findByText('pg_dump 17 é mais novo que o servidor 16; defina PG_BIN.')).toBeInTheDocument()
  })

  it('restaurar exige digitar o nome e informa o backup de segurança', async () => {
    const chamadas = preparar()
    const { usuario } = renderApp('/sistema/backups')
    const nome = BACKUPS[0].nome
    const linha = (await screen.findByText(nome)).closest('tr')!
    expect(within(linha).getByText('3,2 MB')).toBeInTheDocument()
    expect(within(linha).getByRole('link', { name: 'Baixar' })).toHaveAttribute('href', `/admin/backups/${nome}/download`)

    await usuario.click(within(linha).getByRole('button', { name: 'Restaurar' }))
    const dialogo = screen.getByRole('dialog')
    const confirmar = within(dialogo).getByRole('button', { name: 'Restaurar' })
    expect(confirmar).toBeDisabled()
    await usuario.type(within(dialogo).getByLabelText(`Digite ${nome} para confirmar`), nome)
    await usuario.click(confirmar)

    expect(chamadas.at(-1)).toMatchObject({ caminho: `/admin/backups/${nome}/restaurar`, form: { confirmacao: nome } })
    expect(await screen.findByText(/dnit_20260924_1010_antes_de_restaurar\.dump/)).toBeInTheDocument()
  })
})
```

O texto "Digite … para confirmar" e o botão desabilitado até o nome bater vêm de `ConfirmarDialogo` com `textoExigido` (Tarefa 4).

Run: `npm run test -- sistema`
Expected: FAIL — rotas `sistema/*` não existem.

- [ ] **Step 2: Cliente**

`frontend/src/api/sistema.ts`:

```ts
import { caminhoCom, pedir } from './client'
import type { Backup, Template } from './tipos'

const c = encodeURIComponent

export const listarTemplates = () => pedir<Template[]>('/admin/templates')

export function enviarTemplate(arquivo: File, { observacao, ativar }: { observacao?: string; ativar: boolean }) {
  const form = new FormData()
  form.append('arquivo', arquivo)
  if (observacao) form.append('observacao', observacao)
  form.append('ativar', String(ativar))
  return pedir<{ id: number; ativo: boolean }>('/admin/templates', { metodo: 'POST', form })
}

export const ativarTemplate = (id: number) => pedir<unknown>(`/admin/templates/${id}/ativar`, { metodo: 'POST' })

export const excluirTemplate = (id: number) => pedir<unknown>(`/admin/templates/${id}`, { metodo: 'DELETE' })

export const urlTemplate = (id: number) => caminhoCom(`/admin/templates/${id}/download`)

export const listarBackups = () => pedir<Backup[]>('/admin/backups')

export const gerarBackup = () => pedir<{ nome: string; tamanho: number }>('/admin/backups', { metodo: 'POST' })

export function enviarBackup(arquivo: File) {
  const form = new FormData()
  form.append('arquivo', arquivo)
  return pedir<{ nome: string }>('/admin/backups/upload', { metodo: 'POST', form })
}

export function restaurarBackup(nome: string, confirmacao: string) {
  const form = new FormData()
  form.append('confirmacao', confirmacao)
  return pedir<{ restaurado: string; seguranca: string }>(`/admin/backups/${c(nome)}/restaurar`, { metodo: 'POST', form })
}

export const excluirBackup = (nome: string) => pedir<unknown>(`/admin/backups/${c(nome)}`, { metodo: 'DELETE' })

export const urlBackup = (nome: string) => caminhoCom(`/admin/backups/${c(nome)}/download`)
```

- [ ] **Step 3: Campo de envio compartilhado**

`frontend/src/pages/sistema/EnviarArquivo.tsx`:

```tsx
import { useId, useRef, useState, type FormEvent, type ReactNode } from 'react'

interface Props {
  rotulo: string
  accept: string
  botao: string
  pendente: boolean
  aoEnviar: (arquivo: File) => Promise<unknown>
  // Campos extras entre o arquivo e o botão (a observação do template).
  children?: ReactNode
}

export function EnviarArquivo({ rotulo, accept, botao, pendente, aoEnviar, children }: Props) {
  const id = useId()
  const campo = useRef<HTMLInputElement>(null)
  const [arquivo, setArquivo] = useState<File | null>(null)

  async function enviar(e: FormEvent) {
    e.preventDefault()
    if (!arquivo) return
    try {
      await aoEnviar(arquivo)
      setArquivo(null)
      if (campo.current) campo.current.value = ''
    } catch {
      // O erro já aparece na página, pela mutação que aoEnviar dispara.
    }
  }

  return (
    <form className="barra" onSubmit={enviar}>
      <div className="field">
        <label className="field-label" htmlFor={id}>{rotulo}</label>
        <input
          ref={campo}
          id={id}
          type="file"
          className="input"
          accept={accept}
          onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
        />
      </div>
      {children}
      <button type="submit" className="btn btn-primary" disabled={!arquivo || pendente}>{botao}</button>
    </form>
  )
}
```

- [ ] **Step 4: Página de templates**

`frontend/src/pages/sistema/PaginaTemplates.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { chaves } from '../../api/chaves'
import { ativarTemplate, enviarTemplate, excluirTemplate, listarTemplates, urlTemplate } from '../../api/sistema'
import type { Template } from '../../api/tipos'
import { Cabecalho } from '../../components/Cabecalho'
import { Carregando } from '../../components/Carregando'
import { ConfirmarDialogo } from '../../components/ConfirmarDialogo'
import { MensagemErro } from '../../components/MensagemErro'
import { dataHora, tamanho } from '../../lib/formato'
import { EnviarArquivo } from './EnviarArquivo'

export function PaginaTemplates() {
  const qc = useQueryClient()
  const [observacao, setObservacao] = useState('')
  const [ativar, setAtivar] = useState(true)
  const [excluindo, setExcluindo] = useState<Template | null>(null)
  const templates = useQuery({ queryKey: chaves.templates, queryFn: listarTemplates })
  const recarregar = () => qc.invalidateQueries({ queryKey: chaves.templates })

  const enviar = useMutation({
    mutationFn: (arquivo: File) => enviarTemplate(arquivo, { observacao: observacao.trim() || undefined, ativar }),
    onSuccess: async () => {
      setObservacao('')
      await recarregar()
    },
  })
  const ativarUm = useMutation({ mutationFn: ativarTemplate, onSuccess: recarregar })
  const excluir = useMutation({
    mutationFn: (t: Template) => excluirTemplate(t.id),
    onSuccess: async () => {
      setExcluindo(null)
      await recarregar()
    },
  })

  return (
    <>
      <Cabecalho
        titulo="Templates"
        subtitulo="A planilha de reequilíbrio sai do template ativo. Um envio é validado antes de ser aceito."
      />
      <section className="panel">
        <div className="panel-body">
          <EnviarArquivo
            rotulo="Novo template (.xlsx)"
            accept=".xlsx"
            botao="Enviar template"
            pendente={enviar.isPending}
            aoEnviar={(a) => enviar.mutateAsync(a)}
          >
            <div className="field">
              <label className="field-label" htmlFor="template-observacao">Observação</label>
              <input id="template-observacao" className="input" value={observacao} onChange={(e) => setObservacao(e.target.value)} />
            </div>
            <label className="field-label">
              <input type="checkbox" checked={ativar} onChange={(e) => setAtivar(e.target.checked)} /> Ativar ao enviar
            </label>
          </EnviarArquivo>
          <MensagemErro erro={enviar.error ?? ativarUm.error} />
        </div>
      </section>

      {templates.isPending && <Carregando />}
      <MensagemErro erro={templates.error} />
      {templates.data && (
        <section className="panel mt-md">
          <div className="panel-body flush table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Arquivo</th>
                  <th>Observação</th>
                  <th>Enviado em</th>
                  <th className="num">Tamanho</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {templates.data.map((t) => (
                  <tr key={t.id}>
                    <td>
                      {t.nome} {t.ativo && <span className="badge badge-ok">Ativo</span>}
                    </td>
                    <td>{t.observacao ?? '—'}</td>
                    <td>{dataHora(t.criado_em)}</td>
                    <td className="num">{tamanho(t.tamanho)}</td>
                    <td>
                      <a className="btn btn-sm" href={urlTemplate(t.id)} download>Baixar</a>{' '}
                      {!t.ativo && (
                        <>
                          <button type="button" className="btn btn-sm" disabled={ativarUm.isPending} onClick={() => ativarUm.mutate(t.id)}>
                            Ativar
                          </button>{' '}
                          <button type="button" className="btn btn-sm" onClick={() => setExcluindo(t)}>Excluir</button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {excluindo && (
        <ConfirmarDialogo
          titulo={`Excluir ${excluindo.nome}?`}
          mensagem="O template sai do histórico e do próximo backup. O ativo não muda."
          rotuloConfirmar="Excluir"
          perigoso
          pendente={excluir.isPending}
          erro={excluir.error}
          aoCancelar={() => setExcluindo(null)}
          aoConfirmar={() => excluir.mutate(excluindo)}
        />
      )}
    </>
  )
}
```

- [ ] **Step 5: Página de backups**

`frontend/src/pages/sistema/PaginaBackups.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { chaves } from '../../api/chaves'
import { enviarBackup, excluirBackup, gerarBackup, listarBackups, restaurarBackup, urlBackup } from '../../api/sistema'
import type { Backup } from '../../api/tipos'
import { Cabecalho } from '../../components/Cabecalho'
import { Carregando } from '../../components/Carregando'
import { ConfirmarDialogo } from '../../components/ConfirmarDialogo'
import { Icone } from '../../components/Icone'
import { MensagemErro } from '../../components/MensagemErro'
import { dataHora, tamanho } from '../../lib/formato'
import { EnviarArquivo } from './EnviarArquivo'

export function PaginaBackups() {
  const qc = useQueryClient()
  const [restaurando, setRestaurando] = useState<Backup | null>(null)
  const [excluindo, setExcluindo] = useState<Backup | null>(null)
  const backups = useQuery({ queryKey: chaves.backups, queryFn: listarBackups })
  const recarregar = () => qc.invalidateQueries({ queryKey: chaves.backups })

  const gerar = useMutation({ mutationFn: gerarBackup, onSuccess: recarregar })
  const enviar = useMutation({ mutationFn: enviarBackup, onSuccess: recarregar })
  const excluir = useMutation({
    mutationFn: (b: Backup) => excluirBackup(b.nome),
    onSuccess: async () => {
      setExcluindo(null)
      await recarregar()
    },
  })
  const restaurar = useMutation({
    mutationFn: (b: Backup) => restaurarBackup(b.nome, b.nome),
    onSuccess: async () => {
      setRestaurando(null)
      // O banco inteiro mudou: contratos, índices, catálogo, templates.
      await qc.invalidateQueries()
    },
  })

  return (
    <>
      <Cabecalho
        titulo="Backups"
        subtitulo="Um único arquivo guarda tudo: contratos, medições, catálogo, índices e templates."
        acoes={
          <button type="button" className="btn btn-primary" disabled={gerar.isPending} onClick={() => gerar.mutate()}>
            <Icone nome="backup" />
            <span>Gerar backup agora</span>
          </button>
        }
      />
      <MensagemErro erro={gerar.error} />
      {restaurar.data && (
        <div className="notice ok" role="status">
          <div>
            <p className="notice-title">Banco restaurado de {restaurar.data.restaurado}.</p>
            <p className="notice-text">O estado anterior foi guardado em {restaurar.data.seguranca}.</p>
          </div>
        </div>
      )}

      <section className="panel mt-md">
        <div className="panel-body">
          <EnviarArquivo
            rotulo="Enviar backup (.dump)"
            accept=".dump"
            botao="Enviar backup"
            pendente={enviar.isPending}
            aoEnviar={(a) => enviar.mutateAsync(a)}
          />
          <MensagemErro erro={enviar.error} />
        </div>
      </section>

      {backups.isPending && <Carregando />}
      <MensagemErro erro={backups.error} />
      {backups.data && backups.data.length === 0 && <p className="contagem mt-md">Nenhum backup ainda.</p>}
      {backups.data && backups.data.length > 0 && (
        <section className="panel mt-md">
          <div className="panel-body flush table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Arquivo</th>
                  <th>Gerado em</th>
                  <th className="num">Tamanho</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {backups.data.map((b) => (
                  <tr key={b.nome}>
                    <td className="num">{b.nome}</td>
                    <td>{dataHora(b.criado_em)}</td>
                    <td className="num">{tamanho(b.tamanho)}</td>
                    <td>
                      <a className="btn btn-sm" href={urlBackup(b.nome)} download>Baixar</a>{' '}
                      <button type="button" className="btn btn-sm" onClick={() => setRestaurando(b)}>Restaurar</button>{' '}
                      <button type="button" className="btn btn-sm" onClick={() => setExcluindo(b)}>Excluir</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {restaurando && (
        <ConfirmarDialogo
          titulo="Restaurar este backup?"
          mensagem={`Todo o banco volta ao estado de ${dataHora(restaurando.criado_em)}. O que foi gravado depois disso se perde; antes de restaurar, o estado atual é guardado num backup de segurança.`}
          rotuloConfirmar="Restaurar"
          textoExigido={restaurando.nome}
          perigoso
          pendente={restaurar.isPending}
          erro={restaurar.error}
          aoCancelar={() => setRestaurando(null)}
          aoConfirmar={() => restaurar.mutate(restaurando)}
        />
      )}
      {excluindo && (
        <ConfirmarDialogo
          titulo={`Excluir ${excluindo.nome}?`}
          mensagem="O arquivo do backup é apagado do servidor."
          rotuloConfirmar="Excluir"
          perigoso
          pendente={excluir.isPending}
          erro={excluir.error}
          aoCancelar={() => setExcluindo(null)}
          aoConfirmar={() => excluir.mutate(excluindo)}
        />
      )}
    </>
  )
}
```

- [ ] **Step 6: Rotas**

Em `frontend/src/App.tsx`, antes de `path="*"`:

```tsx
        <Route path="sistema" element={<Navigate to="templates" replace />} />
        <Route path="sistema/templates" element={<PaginaTemplates />} />
        <Route path="sistema/backups" element={<PaginaBackups />} />
```

com `import { PaginaBackups } from './pages/sistema/PaginaBackups'` e `import { PaginaTemplates } from './pages/sistema/PaginaTemplates'`.

Run: `npm run test -- sistema`
Expected: PASS.

- [ ] **Step 7: Rodar tudo e commitar**

Run: `npm run test && npm run build`
Expected: todos passam; build sem erro.

```bash
git add frontend/src/App.tsx frontend/src/api/sistema.ts frontend/src/pages/sistema frontend/tests/sistema.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): telas de templates e backups

Templates: enviar (com observação e ativar), baixar, ativar e excluir,
o ativo marcado e sem exclusão. Backups: gerar agora, enviar .dump,
baixar, excluir e restaurar, que exige digitar o nome, informa o backup
de segurança e invalida todo o cache. Recusas do backend aparecem como
vieram.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarefa 13: Ponta a ponta com Playwright

**Files:**
- Create: `scripts/preparar_e2e.py`
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/{apoio.ts,01-cadastro-calculo.spec.ts,02-catalogo.spec.ts,03-importacao-igp.spec.ts}`

**Interfaces:**
- Consumes: o script `"e2e": "npm run build && playwright test"` e a dependência `@playwright/test` (Tarefa 1); o SPA servido de `frontend/dist/` (Tarefa 2); `vincular_contrato` dentro de `_persistir` (Tarefa 3); os rótulos das telas das Tarefas 5 a 10, que os specs usam **exatamente** como estão:
  - lista: link com o número do contrato; abas `Cadastro`, `Cálculo e exportação`;
  - cadastro: `Região ANP — CAP`, `Região ANP — Emulsões`, `Contratada`, `Edital`, `Rodovia`, `Trecho`, `Subtrecho`, `Segmento`, `Extensão (km)`, botão `Salvar`, status `Cadastro salvo.`;
  - cálculo: link `Baixar planilha (.xlsx)`, select `Região CAP`, faixa `Simulação — o cadastro não muda.`, linha `Total geral`;
  - catálogo: `Novo produto`, `Descrição na planilha`, `Salvar`, `Adicionar códigos`, `Buscar código ou descrição`, `Associar selecionados (1)`;
  - índices: `Editar IGP-DI fev/2023`, campo `IGP-DI fev/2023`, `Importar`, `Arquivo`, `Ver prévia`, `Gravar e manter meus valores manuais`, `Importação gravada.`, `Fechar`.
- Produces: `npm run e2e` (de dentro de `frontend/`), que a Tarefa 14 documenta.

O e2e roda contra o FastAPI real (porta 8765) e o banco **`dnit_test`**, o mesmo do pytest — não rode os dois ao mesmo tempo. O `webServer` do Playwright executa `scripts/preparar_e2e.py` antes de subir o servidor, então **cada** `npm run e2e` começa do mesmo estado:

- schema de `dnit_test` zerado e migrações aplicadas;
- índices de `tests/fixtures/` (`anp_semanal.xls`, `igp_di.xlsx`) importados com `origem = 'seed'`;
- o contrato fictício `99 99999/2099` de `tests/fixtures/contrato_ficticio.json`, gravado por `_persistir` como um PDF processado — cadastro **incompleto** (sem regiões nem campos de cabeçalho);
- catálogo: as associações que a migração 003 traz são removidas; ficam só dois produtos, `Aquisição de CAP 50/70` (CAP, código 60112) e `Aquisição de Emulsão RR-1C` (EMULSOES, código 29083).

Nada disso lê `Reequilíbrio - 26 - Contrato 716-22.xlsx`.

Os specs rodam em série (`workers: 1`) e em ordem de arquivo. O 02 re-aponta o 60112 para um produto novo, o que tiraria o `Aquisição de CAP 50/70` do cálculo, por isso ele vem depois do 01. Cada spec que precisa do cadastro completo o garante pela API (`completarCadastro`, idempotente), então `npx playwright test e2e/02-catalogo.spec.ts` também funciona sozinho.

- [ ] **Step 1: Preparar o banco**

`scripts/preparar_e2e.py`:

```python
"""Deixa o banco de teste no estado inicial dos testes ponta a ponta.

Chamado pelo ``webServer`` de ``frontend/playwright.config.ts`` antes de subir
o servidor, com ``DATABASE_URL`` apontando para ``dnit_test``:

    DATABASE_URL=postgresql://dnit:dnit@localhost:5433/dnit_test \\
        uv run python scripts/preparar_e2e.py

Zera o schema, aplica as migrações, importa os índices de ``tests/fixtures/``,
grava o contrato fictício como um PDF processado e deixa no catálogo só dois
produtos com um código cada. Recusa qualquer banco cujo nome não termine em
``_test``: o primeiro passo apaga tudo.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db  # noqa: E402
from app.services import catalogo, importacao, indices_repo, template_repo  # noqa: E402
from app.services.file_processor import _persistir  # noqa: E402

FIXTURES = config.PROJECT_ROOT / "tests" / "fixtures"

PRODUTOS = (
    ("Aquisição de CAP 50/70", "CAP", "60112"),
    ("Aquisição de Emulsão RR-1C", "EMULSOES", "29083"),
)


def _preparar() -> None:
    for funcao, arquivo in (
        (importacao.importar_anp, "anp_semanal.xls"),
        (importacao.importar_igp_di, "igp_di.xlsx"),
    ):
        caminho = FIXTURES / arquivo
        funcao(caminho.read_bytes(), caminho.name, origem=indices_repo.ORIGEM_SEED)

    ficticio = json.loads((FIXTURES / "contrato_ficticio.json").read_text(encoding="utf-8"))
    for medicao in ficticio["arquivos"]:
        _persistir({"header": ficticio["header"], "rows": medicao["rows"]}, medicao["arquivo"], "e2e")

    with db.acquire_sync() as conn:
        conn.execute("DELETE FROM produto_codigo")
        conn.execute("DELETE FROM produto")
    for ordem, (descricao, familia, codigo) in enumerate(PRODUTOS, start=1):
        produto_id = catalogo.criar_produto(descricao, familia, ordem)
        catalogo.registrar_codigo(codigo, produto_id)

    template_repo.garantir_semente()


async def _rodar() -> int:
    nome = config.DATABASE_URL.rsplit("/", 1)[-1].split("?", 1)[0]
    if not nome.endswith("_test"):
        print(f"preparar_e2e: recusado, o banco '{nome}' não é de teste.", file=sys.stderr)
        return 1
    await db.open_pools()
    try:
        async with db.acquire() as conn:
            await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
        await db.apply_migrations()
        await asyncio.to_thread(_preparar)
    finally:
        await db.close_pools()
    print(f"preparar_e2e: {nome} pronto.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_rodar()))
```

Run (da raiz, com `docker compose up -d postgres`):
`DATABASE_URL=postgresql://dnit:dnit@localhost:5433/dnit_test uv run python scripts/preparar_e2e.py`
Expected: `preparar_e2e: dnit_test pronto.`

Run: `DATABASE_URL=postgresql://dnit:dnit@localhost:5433/dnit uv run python scripts/preparar_e2e.py`
Expected: `preparar_e2e: recusado, o banco 'dnit' não é de teste.` e código de saída 1 — o banco de desenvolvimento fica intacto.

- [ ] **Step 2: Configuração do Playwright**

`frontend/playwright.config.ts`:

```ts
import { fileURLToPath } from 'node:url'
import { defineConfig, devices } from '@playwright/test'

const PORTA = 8765
const RAIZ = fileURLToPath(new URL('..', import.meta.url))
const BANCO = process.env.DATABASE_URL_TEST ?? 'postgresql://dnit:dnit@localhost:5433/dnit_test'

export default defineConfig({
  testDir: 'e2e',
  // Os specs compartilham o banco e rodam em ordem de arquivo.
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: `http://localhost:${PORTA}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `uv run python scripts/preparar_e2e.py && uv run uvicorn main:app --port ${PORTA}`,
    cwd: RAIZ,
    url: `http://localhost:${PORTA}/api/v1/indices/cobertura`,
    // Sempre um servidor novo: é o preparar_e2e que zera o banco.
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      DATABASE_URL: BANCO,
      STORAGE_PATH: `${RAIZ}tmp/e2e-data`,
      BACKUP_INTERVAL_HOURS: '100000',
    },
  },
})
```

`STORAGE_PATH` separado mantém os artefatos e dumps do e2e fora de `data/`; `tmp/` já é ignorado pelo git.

- [ ] **Step 3: Apoio comum**

`frontend/e2e/apoio.ts`:

```ts
import type { APIRequestContext } from '@playwright/test'
import { expect } from '@playwright/test'

export const NUMERO = '99 99999/2099'

export async function contratoId(request: APIRequestContext): Promise<number> {
  const resposta = await request.get('/api/v1/contratos', { params: { numero: NUMERO } })
  expect(resposta.ok()).toBe(true)
  const [contrato] = await resposta.json()
  return contrato.id
}

// O mesmo cadastro que o spec 01 preenche pela tela; idempotente.
export async function completarCadastro(request: APIRequestContext): Promise<number> {
  const id = await contratoId(request)
  const resposta = await request.patch(`/api/v1/contratos/${id}`, {
    data: {
      contratada: 'CONSTRUTORA FICTÍCIA LTDA',
      edital: '999/2099-99',
      rodovia: 'BR-999',
      trecho: 'Trecho fictício',
      subtrecho: 'Subtrecho fictício',
      segmento: 'km 0,0 ao km 10,0',
      extensao: '10.0',
      regioes: { CAP: 'Nordeste', EMULSOES: 'Nordeste' },
    },
  })
  expect(resposta.ok()).toBe(true)
  return id
}
```

- [ ] **Step 4: Spec 01 — cadastro, cálculo e simulação**

`frontend/e2e/01-cadastro-calculo.spec.ts`:

```ts
import { expect, test } from '@playwright/test'
import { NUMERO } from './apoio'

test('completar o cadastro, calcular, baixar e simular outra região', async ({ page }) => {
  await page.goto('/contratos')
  // Cadastro incompleto: o link do contrato abre o Cadastro.
  await page.getByRole('link', { name: NUMERO }).click()
  await expect(page).toHaveURL(/\/contratos\/\d+\/cadastro$/)

  await page.getByLabel('Região ANP — CAP').selectOption('Nordeste')
  await page.getByLabel('Região ANP — Emulsões').selectOption('Nordeste')
  const campos: [string, string][] = [
    ['Contratada', 'CONSTRUTORA FICTÍCIA LTDA'],
    ['Edital', '999/2099-99'],
    ['Rodovia', 'BR-999'],
    ['Trecho', 'Trecho fictício'],
    ['Subtrecho', 'Subtrecho fictício'],
    ['Segmento', 'km 0,0 ao km 10,0'],
    ['Extensão (km)', '10,0'],
  ]
  for (const [rotulo, valor] of campos) {
    await page.getByLabel(rotulo, { exact: true }).fill(valor)
  }
  await page.getByRole('button', { name: 'Salvar' }).click()
  await expect(page.getByText('Cadastro salvo.')).toBeVisible()
  await expect(page.getByText('Parâmetros completos')).toBeVisible()

  await page.getByRole('link', { name: 'Cálculo e exportação' }).click()
  const tabela = page.getByRole('table')
  await expect(tabela).toContainText('Aquisição de CAP 50/70')
  await expect(tabela).toContainText('Aquisição de Emulsão RR-1C')
  await expect(tabela.getByRole('row').filter({ hasText: 'Total geral' })).toBeVisible()

  const baixar = page.getByRole('link', { name: 'Baixar planilha (.xlsx)' })
  const [planilha] = await Promise.all([page.waitForEvent('download'), baixar.click()])
  expect(planilha.suggestedFilename()).toMatch(/\.xlsx$/)
  expect(planilha.suggestedFilename()).not.toContain('SIMULACAO')

  await page.getByLabel('Região CAP').selectOption('Sul')
  await expect(page).toHaveURL(/regiao_cap=Sul/)
  await expect(page.getByText('Simulação — o cadastro não muda.')).toBeVisible()
  const [simulada] = await Promise.all([page.waitForEvent('download'), baixar.click()])
  expect(simulada.suggestedFilename()).toContain('SIMULACAO')
  expect(simulada.suggestedFilename()).toContain('CAP-Sul')

  // A simulação não tocou no cadastro.
  await page.getByRole('link', { name: 'Cadastro', exact: true }).click()
  await expect(page.getByLabel('Região ANP — CAP')).toHaveValue('Nordeste')
})
```

`getByLabel(..., { exact: true })` evita que `Trecho` case com `Subtrecho`. O asterisco de obrigatório dos rótulos de região é `aria-hidden`, então não entra no nome acessível — `getByLabel('Região ANP — CAP')` casa normalmente.

- [ ] **Step 5: Spec 02 — catálogo**

`frontend/e2e/02-catalogo.spec.ts`:

```ts
import { expect, test } from '@playwright/test'
import { completarCadastro } from './apoio'

test('criar um produto, associar o 60112 e ver a linha no cálculo', async ({ page, request }) => {
  const id = await completarCadastro(request)

  await page.goto('/catalogo')
  await page.getByRole('button', { name: 'Novo produto' }).click()
  const novo = page.getByRole('dialog')
  await novo.getByLabel('Descrição na planilha').fill('CAP 50/70 do teste ponta a ponta')
  await novo.getByRole('button', { name: 'Salvar' }).click()
  // O produto criado fica selecionado.
  await expect(page.getByRole('heading', { name: 'CAP 50/70 do teste ponta a ponta' })).toBeVisible()

  await page.getByRole('button', { name: 'Adicionar códigos' }).click()
  const adicionar = page.getByRole('dialog')
  await adicionar.getByLabel('Buscar código ou descrição').fill('60112')
  const linha = adicionar.getByRole('row').filter({ hasText: '60112' })
  await expect(linha).toContainText('em Aquisição de CAP 50/70')
  await linha.getByRole('checkbox').check()
  await adicionar.getByRole('button', { name: 'Associar selecionados (1)' }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByRole('cell', { name: '60112', exact: true })).toBeVisible()

  await page.goto(`/contratos/${id}/calculo`)
  const tabela = page.getByRole('table')
  await expect(tabela).toContainText('CAP 50/70 do teste ponta a ponta')
  // O produto antigo ficou sem código e sai do cálculo, sem bloquear nada.
  await expect(tabela).not.toContainText('Aquisição de CAP 50/70')
})
```

- [ ] **Step 6: Spec 03 — importação com valor manual em conflito**

`frontend/e2e/03-importacao-igp.spec.ts`:

```ts
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'

const IGP_DI = fileURLToPath(new URL('../../tests/fixtures/igp_di.xlsx', import.meta.url))

test('importar o IGP-DI mantendo um valor manual em conflito', async ({ page }) => {
  await page.goto('/indices/igp-di')

  // O seed gravou fev/2023 = 1144,271; a correção manual o troca.
  await page.getByRole('button', { name: 'Editar IGP-DI fev/2023' }).click()
  const campo = page.getByLabel('IGP-DI fev/2023', { exact: true })
  await campo.fill('1.150,5')
  await campo.press('Enter')
  const celula = page.getByRole('button', { name: 'Editar IGP-DI fev/2023' })
  await expect(celula).toHaveText(/1\.150,5/)

  await page.getByRole('button', { name: 'Importar' }).click()
  const dialogo = page.getByRole('dialog')
  await dialogo.getByLabel('Arquivo').setInputFiles(IGP_DI)
  await dialogo.getByRole('button', { name: 'Ver prévia' }).click()

  const conflitos = dialogo.locator('.cartao', { hasText: 'Seus valores manuais em conflito' })
  await expect(conflitos).toContainText('1')
  await expect(conflitos).toHaveClass(/warn/)
  const conflito = dialogo.getByRole('row').filter({ hasText: 'fev/2023' })
  await expect(conflito).toContainText('1.150,5')
  await expect(conflito).toContainText('1.144,271')

  await dialogo.getByRole('button', { name: 'Gravar e manter meus valores manuais' }).click()
  await expect(dialogo.getByText('Importação gravada.')).toBeVisible()
  await expect(dialogo).toContainText('1 valor manual preservado')
  await dialogo.getByRole('button', { name: 'Fechar' }).click()

  await expect(celula).toHaveText(/1\.150,5/)
})
```

- [ ] **Step 7: Rodar**

Run (de `frontend/`, com o Postgres de pé e **sem** pytest rodando):

```bash
npx playwright install chromium
npm run e2e
```

Expected: `3 passed`. Se um rótulo não bater, o erro do Playwright aponta o localizador: corrija o spec só se o rótulo da tela estiver certo segundo a spec de design; se a tela estiver errada, corrija a tela e o teste de componente dela.

Run (da raiz): `uv run pytest -q`
Expected: tudo passa — o pytest não depende do e2e, e o e2e deixou `dnit_test` num estado que o pytest zera por teste.

- [ ] **Step 8: Commitar**

```bash
git add scripts/preparar_e2e.py frontend/playwright.config.ts frontend/e2e
git commit -m "$(cat <<'EOF'
test(frontend): ponta a ponta com Playwright contra o FastAPI real

Três cenários sobre dnit_test, preparado a cada execução por
scripts/preparar_e2e.py a partir de tests/fixtures/: completar o cadastro,
calcular, baixar e simular CAP em Sul sem alterar o cadastro; criar um
produto e associar o 60112; editar um IGP-DI à mão e importar o arquivo
mantendo o valor manual. O script recusa bancos que não terminem em _test.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarefa 14: README e regras

**Files:**
- Modify: `README.md`
- Modify: `.claude/rules/frontend.md` (reescrito)
- Modify: `.claude/rules/architecture.md`, `.claude/rules/backend.md`, `.claude/rules/deployment.md`

**Interfaces:**
- Consumes: tudo o que as Tarefas 1 a 13 entregaram. Esta tarefa **não muda código**; se, ao reler, algo descrito aqui não existir no código, a descrição está errada — corrija o texto, não invente o código.
- Produces: a documentação exigida por `.claude/rules/documentation.md`, na mesma entrega do frontend.

Regras de `documentation.md` que valem aqui: README em português, na ordem *O que a aplicação faz*, *Telas*, *Requisitos*, *Setup em um ambiente novo*, *Testes*, *Produção*, *Backups*, *Estrutura do projeto*; nada descrito que não exista; o que serve aos dois públicos fica na regra e o README aponta para ela.

- [ ] **Step 1: README — *O que a aplicação faz***

Em `README.md`, substituir o parágrafo que começa com `**Extração dos PDFs.**` por:

```markdown
**Extração dos PDFs.** Aceita vários arquivos de uma vez, arrastados para a tela
de upload. PDFs com texto são lidos com `pdfplumber`; os digitalizados caem no
caminho de OCR (Tesseract, com EasyOCR como reserva). O processamento roda em
segundo plano e o progresso de cada arquivo aparece em tempo real; ao terminar,
cada arquivo mostra quantos itens gravou e leva direto ao contrato.
```

Substituir o parágrafo que começa com `**Uma trilha de seis etapas.**` por:

```markdown
**O contrato é uma página.** A tela inicial lista os contratos com a situação de
cada um — cálculo bloqueado (e o que falta), calcula com aviso, ou completo. Cada
contrato abre em três abas: *Cadastro*, *Medições* (os itens extraídos, com o
produto a que cada código está associado) e *Cálculo e exportação* (a mesma
tabela da planilha, com subtotais, total e o download). Quando o cálculo está
bloqueado, a aba lista tudo o que falta de uma vez, cada item com o atalho para
a tela que o resolve.
```

No parágrafo `**Índices globais, editáveis por qualquer usuário.**`, trocar a frase `Podem ser corrigidos um a um ou importados em massa:` por `Aparecem em grades — semana × região para a ANP, ano × mês para o IGP-DI —, com os valores corrigidos à mão marcados, e podem ser editados célula a célula ou importados em massa:`.

No parágrafo `**Simulação de região.**`, depois de `…o arquivo sai com `SIMULACAO` no nome.`, acrescentar: `A simulação fica no endereço da página, então pode ser recarregada ou enviada a um colega.`

No parágrafo `**Templates e backup pela interface.**`, nada muda.

- [ ] **Step 2: README — *Telas***

Substituir a tabela da seção `## Telas` por:

```markdown
| Endereço | O que é |
|---|---|
| `/` ou `/contratos` | Lista de contratos com a situação de cada um |
| `/contratos/<id>/cadastro` | Cadastro do contrato: Data Base, regiões da ANP e cabeçalho da planilha |
| `/contratos/<id>/medicoes` | Itens extraídos dos PDFs, filtráveis por mês e por "entra no cálculo" |
| `/contratos/<id>/calculo` | Cálculo, simulação de região e download da planilha |
| `/upload` | Envio dos PDFs, progresso e resultados da extração |
| `/catalogo` | Produtos da planilha e os códigos de serviço associados a cada um |
| `/indices/anp`, `/indices/igp-di` | Grades dos índices, edição, importação com prévia e exportação |
| `/sistema/templates`, `/sistema/backups` | Templates da planilha e backups do banco |
| `/docs` | Documentação interativa da API REST (`/api/v1`), gerada pelo FastAPI |
| `/dashboard` | Interface anterior (Dash), mantida sem mudanças até ser removida; fora do menu |

As telas são um frontend React servido pelo próprio FastAPI a partir do build em
`frontend/dist/` — ver *Setup*.
```

- [ ] **Step 3: README — *Requisitos***

Na lista de `## Requisitos`, depois do item do **uv**, acrescentar:

```markdown
- **Node 24** (com npm 11) para construir o frontend e rodar os testes dele. Não é
  necessário para executar a aplicação a partir da imagem Docker, que já traz o
  build, nem para a suíte `pytest`.
```

- [ ] **Step 4: README — *Setup em um ambiente novo***

Substituir o bloco de comandos da seção por:

````markdown
```bash
# 1. Dependências do backend (inclui as de desenvolvimento)
uv sync

# 2. Variáveis de ambiente
cp .env.example .env
#    Troque TROQUE_ESTA_SENHA nas duas URLs de conexão. A senha precisa ser a
#    mesma de POSTGRES_PASSWORD no docker-compose.yml.

# 3. Banco de dados (fica na porta 5433 do host)
docker compose up -d postgres

# 4. Banco usado pelos testes
docker compose exec postgres createdb -U dnit dnit_test

# 5. Carga inicial dos preços da ANP (cópia versionada do arquivo oficial)
uv run python scripts/seed_indices.py --anp tests/fixtures/anp_semanal.xls

# 6. Build do frontend (gera frontend/dist, servido pelo FastAPI)
cd frontend && npm ci && npm run build && cd ..

# 7. Servidor
uv run uvicorn main:app --reload --port 8000
```
````

Logo depois do bloco, antes de `As migrações são aplicadas na subida…`, acrescentar:

````markdown
Sem o passo 6, `http://localhost:8000/` responde uma página que explica como
gerar o build; a API e o `/docs` funcionam do mesmo jeito.

Para mexer no frontend, use o servidor do Vite, que recarrega a cada alteração e
repassa as rotas do backend para o FastAPI:

```bash
cd frontend
npm run dev                                            # http://localhost:5173
VITE_BACKEND_URL=http://localhost:8001 npm run dev     # backend em outra porta
```
````

No parágrafo `Depois disso: suba os PDFs em `http://localhost:8000/`, …`, trocar por:

```markdown
Depois disso: envie os PDFs em `http://localhost:8000/upload`, complete o cadastro
do contrato e as regiões da ANP, associe os códigos de CAP e de emulsão a
produtos do catálogo e baixe a planilha na aba *Cálculo e exportação* do
contrato — ou faça tudo pela API (`/docs`).
```

- [ ] **Step 5: README — *Testes***

Depois do bloco com `PG_BIN=/usr/lib/postgresql/16/bin uv run pytest -q`, acrescentar:

````markdown
### Frontend

Os testes de componente (Vitest, Testing Library e MSW) não precisam de backend
nem de banco:

```bash
cd frontend
npm ci
npm run test
```

Os testes ponta a ponta (Playwright) sobem o FastAPI de verdade na porta 8765,
contra o banco `dnit_test`. Antes de cada execução, `scripts/preparar_e2e.py`
zera esse banco e o carrega a partir de `tests/fixtures/`:

```bash
docker compose up -d postgres
cd frontend
npx playwright install chromium    # uma vez por máquina
npm run e2e
```

`pytest` e `npm run e2e` usam o mesmo `dnit_test`: não rode os dois ao mesmo
tempo.
````

- [ ] **Step 6: README — *Produção* e *Estrutura do projeto***

Em `## Produção`, depois do parágrafo dos volumes, acrescentar:

```markdown
A imagem constrói o frontend num estágio Node separado e leva só o
`frontend/dist/`; Node não é dependência de execução.
```

Substituir o bloco da seção `## Estrutura do projeto` por:

```
main.py            Ponto de entrada (main:app)
setup.sh           Preparação do ambiente de desenvolvimento (.env, Postgres,
                   banco de testes, uv sync e seed dos índices)
migrations/        Migrações SQL numeradas, aplicadas na subida
scripts/           Carga inicial dos índices, preparação do banco do e2e,
                   geração das fixtures do teste ponta a ponta e reconstrução
                   do template
frontend/          Interface React (Vite + TypeScript): src/ com as telas,
                   tests/ (Vitest) e e2e/ (Playwright); o build vai para dist/
app/
├── spa.py         Serve frontend/dist em qualquer rota que não seja do backend
├── routers/       Rotas HTTP: upload, jobs, admin, reequilíbrio e a API REST
│                  em api/ (/api/v1)
├── services/      Regra de negócio: extração, repositórios, ΔP, exportação, backup
├── dashboard/     Interface anterior (Dash) em /dashboard, congelada
├── templates/     HTML (Jinja2) da interface anterior, sem rota própria
├── templates_xlsx/Template inicial da planilha (semente do banco)
└── static/        CSS e fontes da interface anterior
tests/             Suíte pytest; fixtures/ com índices reais e o oráculo do ΔP
```

- [ ] **Step 7: `.claude/rules/frontend.md` reescrito**

Substituir o arquivo inteiro por:

````markdown
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
  produto, apagar semana ou mês, excluir template ou backup. Restaurar backup
  exige ainda digitar o nome (`textoExigido`).
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
- **Playwright** (`npm run e2e`) roda os cenários de `e2e/` contra o FastAPI na
  porta 8765 e o banco `dnit_test`, preparado a cada execução por
  `scripts/preparar_e2e.py` (ver `deployment.md`). Os specs rodam em série e em
  ordem de arquivo.
- `uv run pytest` não depende de Node nem de `frontend/dist/`: `tests/test_spa.py`
  cria um `dist` falso.
````

- [ ] **Step 8: `.claude/rules/architecture.md`**

No bloco `## File Layout`:

- depois da linha de `006_catalogo_indices.sql`, trocar `└── 006_…` por `├── 006_…` e acrescentar:
  ```
  └── 007_file_results_contrato.sql  # file_results.contrato_id / itens (which contract a file fed)
  ```
- em `scripts/`, trocar `├── seed_indices.py` … por, na ordem:
  ```
  ├── seed_indices.py            # Initial load through the importers (--anp, --igp-di)
  ├── preparar_e2e.py            # Resets dnit_test and loads tests/fixtures/ for the Playwright suite
  ├── gerar_fixtures_e2e.py      # One-off: builds tests/fixtures/ from the reference spreadsheet
  └── build_template.py          # Rebuilds app/templates_xlsx/reequilibrio_template.xlsx
  ```
- depois de `├── main.py                    # FastAPI app: …`, acrescentar:
  ```
  ├── spa.py                     # Serves frontend/dist: real files as-is, index.html for everything else
  ```
- trocar a linha de `templates/` por:
  ```
  ├── templates/                 # Jinja2 HTML of the previous interface (frozen; no route of its own)
  ```
- trocar `│   ├── upload.py              # GET / and POST /upload (starts an async job)` por:
  ```
  │   ├── upload.py              # POST /upload (starts an async job)
  ```
- trocar `└── dashboard/                 # Dash app mounted at /dashboard via a2wsgi (synchronous)` por `├── dashboard/                 # Dash app mounted at /dashboard via a2wsgi (synchronous; frozen, off the menu)`
- antes de `requirements.txt`, acrescentar:
  ```
  frontend/                      # React SPA (Vite + TypeScript) — see frontend.md; build output in dist/ (untracked)
  ```

Trocar a frase `Routes live in `app/routers/`, business logic in `app/services/`, HTML in `app/templates/`, client assets in `app/static/`.` por:

```markdown
Routes live in `app/routers/`, business logic in `app/services/`, the interface
in `frontend/` (see `frontend.md`). `app/templates/`, `app/static/` and
`app/dashboard/` belong to the previous interface and are frozen.
```

Na tabela `## Routing`, trocar a linha `| `GET /` | `upload.index` | Renders `index.html` |` por:

```markdown
| `GET /{path}` | `spa.spa` | Registered **last**: a real file from `frontend/dist`, else `index.html` (no-cache). Paths under `api`, `jobs`, `admin`, `reequilibrio`, `static`, `dashboard`, `docs`, `redoc`, `openapi.json` are 404 here, never HTML. Without a build, a page explaining how to run it |
```

e a linha de `/dashboard` por `| `/dashboard` | Dash app | Mounted WSGI app; frozen, off the menu |`.

Em `## Adding a New Router`, trocar o item 3 por:

```markdown
3. Register it **before** `spa.router`, which catches every GET left over; add
   its first path segment to `RESERVADOS` in `app/spa.py` and to `PREFIXOS` in
   `frontend/vite.config.ts`, so neither the SPA nor the dev proxy swallows it.
```

Em `## Data Flow`, trocar o parágrafo `The dashboard reads the same path …` por:

```markdown
The React interface only reads this path through `/api/v1` (`calculo` →
`reequilibrio_export.calcular`/`serializar`), and the Dash dashboard through
`data_loader` → `montar_grupos` / `calcular_deltas` — so the screen and the
downloaded spreadsheet cannot diverge.
```

- [ ] **Step 9: `.claude/rules/backend.md`**

Em `### medicoes_repo.py`, acrescentar ao fim:

```markdown
`listar_itens(contrato_id, mes=None, no_calculo=None, q=None)` serves the
*Medições* tab: every extracted item of the contract with its associated product
(or none), `no_calculo` filtering on whether the code has one, `q` matching code
or description with `ILIKE`.
```

Em `### catalogo.py`, na linha de `buscar_codigos`, acrescentar `produto_id` aos filtros (`buscar_codigos(q, associado, limite, produto_id)` — `produto_id` lists the codes of one product) e, depois dela:

```markdown
- `associar_codigos(produto_id, codigos)` associates or re-points several codes
  in one transaction; `False` when the product does not exist.
```

Em `### indices_repo.py`, trocar a descrição de `cobertura()` por `cobertura()` returns `{"anp": {de, ate, registros, manuais}, "igp_di": {…}, "regioes": [...]}` e acrescentar: ``produtos_anp()`` lists the distinct ANP products in the database (the filter of the ANP grid).

Em `## Routers`, trocar o `### upload.py` por:

```markdown
### upload.py

`POST /upload` reads each file in memory, saves it under `STORAGE_PATH`, creates
a job and returns `{"job_id": …}` immediately; the files are processed in
background tasks. `file_processor` writes the JSON artefact and then persists the
contract (`contratos_repo.registrar_do_pdf`) and the items
(`medicoes_repo.gravar_itens`), and records on the file which contract it fed and
how many items it stored (`job_manager.vincular_contrato`, migration 007). `GET /`
is no longer here: the SPA serves it.
```

Em `### jobs.py`, acrescentar: `Each file in the status carries `contrato_id` and `itens` once persisted, which is how the upload screen links a result to its contract.`

Em `### api/ — `/api/v1``, depois do primeiro parágrafo, acrescentar:

```markdown
Endpoints that exist for the React interface: `GET /contratos/{id}/medicoes?mes=&no_calculo=&q=`
(404 for an unknown contract), `GET /codigos?produto_id=`,
`PUT /produtos/{id}/codigos` with `{"codigos": [...]}` (404 for an unknown
product), `GET /indices/anp/produtos`, `manuais` in each series of
`GET /indices/cobertura`, and `arquivo` in the cálculo JSON — the filename the
spreadsheet download would get, so the screen can show it during a simulation.
```

Em `## Dashboard`, acrescentar ao início: `Frozen: kept mounted and working, off the menu, receiving no new features; the React interface replaces it.`

- [ ] **Step 10: `.claude/rules/deployment.md`**

Em `## System Dependencies`, antes de `The `Dockerfile` installs:`, acrescentar:

```markdown
The `Dockerfile` has two stages. The first, `node:24-slim`, runs `npm ci` and
`npm run build` in `frontend/`; the final Python image copies only
`frontend/dist/`, so Node is a build dependency, not a runtime one. Outside
Docker, Node 24 (npm 11) is needed to build the frontend and run its tests.
```

Na tabela de `## Environment Variables`, acrescentar a linha:

```markdown
| `VITE_BACKEND_URL` | `http://localhost:8000` | Development only: where `npm run dev` proxies the backend paths. Read by `frontend/vite.config.ts` from the shell or `frontend/.env.local`, not from the root `.env` |
```

e, logo abaixo da tabela: `VITE_BACKEND_URL` is not in `.env.example` on purpose: that file is read by the backend, which never uses it.

Trocar o bloco de `## Running Locally` por:

````markdown
```bash
docker compose up -d postgres            # server on host port 5433
(cd frontend && npm ci && npm run build) # frontend/dist, served by FastAPI
uv run uvicorn main:app --reload --port 8000
```

Without the build, `/` answers a page explaining how to run it; the API is
unaffected. To work on the frontend, `cd frontend && npm run dev` (Vite on port
5173) proxies `/api`, `/jobs`, `/admin`, `/reequilibrio`, `/static`,
`/dashboard`, `/docs`, `/redoc`, `/openapi.json` and `POST /upload` to
`VITE_BACKEND_URL`.
````

Em `## Running Tests`, acrescentar ao fim:

````markdown
The frontend has two suites of its own, run from `frontend/`:

```bash
npm run test          # Vitest; no backend, no database
npm run e2e           # builds, then Playwright against a real FastAPI on port 8765
```

`npm run e2e` starts the server itself through Playwright's `webServer`, after
`scripts/preparar_e2e.py` resets `dnit_test` (`DATABASE_URL_TEST`, the same
default as pytest) and loads `tests/fixtures/`. The script refuses a database
whose name does not end in `_test`. Artefacts go to `tmp/e2e-data`. pytest and
the e2e share `dnit_test`: never run both at once. Once per machine:
`npx playwright install chromium`.
````

Em `## Static Files`, acrescentar ao fim: `The SPA's own assets are served by `app/spa.py` from `frontend/dist/` — the same proxy advice applies to that directory; `index.html` must keep `Cache-Control: no-cache`, since it points at the hashed assets of the current build.`

- [ ] **Step 11: Verificar do ambiente mais limpo possível**

`documentation.md` exige executar a sequência de setup e de testes como está escrita, não conferir pela leitura. Num clone novo (com o Postgres já de pé na 5433 e `dnit_test` criado):

```bash
rm -rf /tmp/dnit-limpo && git clone . /tmp/dnit-limpo && cd /tmp/dnit-limpo
cp .env.example .env && sed -i 's/TROQUE_ESTA_SENHA/dnit/g' .env
uv sync
cd frontend && npm ci && npm run build && cd ..
uv run uvicorn main:app --port 8010 &
sleep 5
curl -s http://localhost:8010/ | grep -c '<div id="root">'
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8010/contratos/1/calculo
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8010/api/v1/nao-existe
kill %1
cd frontend && npm run test && cd ..
uv run pytest -q
```

Expected: `1` (o `index.html` do build), `200` (rota do SPA), `404` (prefixo do backend), Vitest e pytest verdes. A senha `dnit` é a do `docker-compose.yml` de desenvolvimento; use a sua se for outra. Se algum comando do README falhar no clone limpo, corrija o README (ou o código, se o README estiver certo segundo a spec) antes de commitar. Apague `/tmp/dnit-limpo` ao final.

Depois, confira que nada descrito deixou de existir:

```bash
grep -n "upload.index\|trilha de seis\|_topbar\|index.html\b" README.md .claude/rules/*.md
```

Expected: nenhuma ocorrência que descreva `GET /` como página Jinja ou a trilha de seis etapas como parte da interface atual (menções à interface anterior congelada são corretas).

- [ ] **Step 12: Commitar**

```bash
git add README.md .claude/rules/frontend.md .claude/rules/architecture.md .claude/rules/backend.md .claude/rules/deployment.md
git commit -m "$(cat <<'EOF'
docs: README e regras para o frontend React

README: as telas novas, Node 24 nos requisitos, o build do frontend no
setup, npm run dev com VITE_BACKEND_URL, os testes Vitest e Playwright e
frontend/ na estrutura. frontend.md reescrito para o SPA (rotas, camada de
API, regras de tela, testes); architecture, backend e deployment com
app/spa.py, a migração 007, os endpoints novos da API, o estágio Node do
Dockerfile e o e2e. A interface anterior fica descrita como congelada.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```
