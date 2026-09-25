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
    const partes = t.split(',')
    if (partes.length !== 2) return null
    const [inteiro, decimalTexto] = partes
    const inteiroSemPontos = inteiro.replace(/\./g, '')
    if (!/^-?\d+$/.test(inteiroSemPontos) || !/^\d+$/.test(decimalTexto)) return null
    t = `${inteiroSemPontos}.${decimalTexto}`
  } else if ((t.match(/\./g) ?? []).length > 1) {
    t = t.replace(/\./g, '')
  }
  return /^-?\d+(\.\d+)?$/.test(t) ? t : null
}
