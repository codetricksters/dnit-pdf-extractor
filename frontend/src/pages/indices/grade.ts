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
