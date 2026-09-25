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
