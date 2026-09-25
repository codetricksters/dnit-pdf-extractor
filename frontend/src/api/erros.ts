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
