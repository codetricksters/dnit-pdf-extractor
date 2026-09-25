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

export interface Arquivo {
  blob: Blob
  nomeArquivo: string | null
}

const NOME_ARQUIVO = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i

// Downloads (planilha, CSV/XLSX de índices, .zip do lote, template, backup)
// buscam o arquivo como blob em vez de usar um <a href download> puro: uma
// resposta de erro (4xx/422) do backend não é o arquivo, e não deve ser salva
// pelo navegador como se fosse.
export async function pedirArquivo(caminho: string): Promise<Arquivo> {
  let resposta: Response
  try {
    resposta = await fetch(caminho, { headers: { Accept: '*/*' } })
  } catch {
    marcarOffline()
    throw new ErroConexao()
  }

  if (SEM_SERVIDOR.has(resposta.status)) {
    marcarOffline()
    throw new ErroConexao()
  }
  marcarOnline()

  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => null)
    throw normalizarErro(resposta.status, corpo)
  }

  const disposicao = resposta.headers.get('Content-Disposition')
  const nomeCru = disposicao?.match(NOME_ARQUIVO)?.[1] ?? null
  return { blob: await resposta.blob(), nomeArquivo: nomeCru ? decodeURIComponent(nomeCru) : null }
}

// Dispara o download de um blob já obtido — o que o navegador faria sozinho
// com um <a href download>.
export function salvarArquivo(blob: Blob, nomeArquivo: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nomeArquivo
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
