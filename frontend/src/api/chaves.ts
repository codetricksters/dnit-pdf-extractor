// Chaves do TanStack Query. Os prefixos (todos*, calculos) existem para a
// invalidação em invalidar.ts: invalidar ['calculo'] atinge todo cálculo em
// cache, de qualquer contrato e simulação.

export interface RegioesSimuladas {
  cap?: string
  emulsoes?: string
}

export interface FiltrosMedicoes {
  mes?: string
  noCalculo?: boolean
  q?: string
}

export interface FiltrosCodigos {
  q?: string
  associado?: boolean
  produtoId?: number
}

export const chaves = {
  contratos: ['contratos'] as const,
  contrato: (id: number) => ['contrato', id] as const,
  calculos: ['calculo'] as const,
  calculo: (id: number, regioes: RegioesSimuladas) => ['calculo', id, regioes] as const,
  todasMedicoes: ['medicoes'] as const,
  medicoes: (id: number, filtros: FiltrosMedicoes) => ['medicoes', id, filtros] as const,
  produtos: ['produtos'] as const,
  todosCodigos: ['codigos'] as const,
  codigos: (filtros: FiltrosCodigos) => ['codigos', filtros] as const,
  todosAnp: ['anp'] as const,
  anp: (produto: string, de?: string, ate?: string) => ['anp', produto, de, ate] as const,
  produtosAnp: ['anp-produtos'] as const,
  todosIgpDi: ['igp-di'] as const,
  igpDi: (de?: string, ate?: string) => ['igp-di', de, ate] as const,
  cobertura: ['cobertura'] as const,
  jobs: (status: 'active' | 'completed') => ['jobs', status] as const,
  templates: ['templates'] as const,
  backups: ['backups'] as const,
}
