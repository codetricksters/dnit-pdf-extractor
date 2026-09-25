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
