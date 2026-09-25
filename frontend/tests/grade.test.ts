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
