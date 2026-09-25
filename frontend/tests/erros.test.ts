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
