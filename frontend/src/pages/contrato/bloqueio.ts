import type { RegioesSimuladas } from '../../api/chaves'
import { CAMPOS_BLOQUEIO, ehCampoBloqueio } from '../../lib/camposBloqueio'

// O 422 do cálculo traz em `faltando` códigos de campo do cadastro e frases
// sobre índices. Aqui cada item vira texto e atalho para onde se resolve.

export function destinoDoFaltante(item: string, contratoId: number) {
  if (ehCampoBloqueio(item)) {
    return { texto: CAMPOS_BLOQUEIO[item].mensagem, para: `/contratos/${contratoId}/cadastro`, rotulo: 'Abrir cadastro' }
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
