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
