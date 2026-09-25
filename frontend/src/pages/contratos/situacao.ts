// Situação de um contrato a partir de `faltantes` (GET /contratos): Data Base e
// regiões bloqueiam o cálculo; campos de cabeçalho vazios só geram aviso na
// planilha.

export const ROTULO_BLOQUEIO = {
  data_base: 'Data Base',
  regiao_cap: 'região CAP',
  regiao_emulsoes: 'região Emulsões',
} as const

type CodigoBloqueio = keyof typeof ROTULO_BLOQUEIO

function ehBloqueio(campo: string): campo is CodigoBloqueio {
  return campo in ROTULO_BLOQUEIO
}

export type Nivel = 'bloqueado' | 'aviso' | 'completo'

export function bloqueado(faltantes: string[]): boolean {
  return faltantes.some(ehBloqueio)
}

export function situacao(faltantes: string[]): { nivel: Nivel; texto: string } {
  const bloqueios = faltantes.filter(ehBloqueio).map((c) => ROTULO_BLOQUEIO[c])
  if (bloqueios.length) return { nivel: 'bloqueado', texto: `Falta ${bloqueios.join(' e ')}` }
  const n = faltantes.length
  if (n === 1) return { nivel: 'aviso', texto: '1 campo do cabeçalho vazio' }
  if (n > 1) return { nivel: 'aviso', texto: `${n} campos do cabeçalho vazios` }
  return { nivel: 'completo', texto: 'Completo' }
}

export const BADGE_NIVEL: Record<Nivel, string> = {
  bloqueado: 'badge badge-danger',
  aviso: 'badge badge-warn',
  completo: 'badge badge-ok',
}
