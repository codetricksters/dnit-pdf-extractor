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
