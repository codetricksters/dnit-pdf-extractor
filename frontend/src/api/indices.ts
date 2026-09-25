import { caminhoCom, pedir } from './client'
import type { Cobertura, IndiceMensal, SemanaAnp, SemanaAnpEntrada } from './tipos'

const BASE = '/api/v1/indices'

// O produto padrão do backend (indices_repo.ANP_PRODUTO_CAP).
export const ANP_PRODUTO_CAP = 'Cimento Asfáltico de Petróleo 50 70 (R$/kg)'
// indices_repo.REGIOES: as que o backend aceita numa semana digitada.
export const REGIOES_ANP = ['Norte', 'Nordeste', 'Centro-Oeste', 'Sudeste', 'Sul', 'Brasil']

export type Formato = 'xlsx' | 'csv'

export interface FiltrosAnp {
  produto: string
  de?: string
  ate?: string
}

export const buscarCobertura = () => pedir<Cobertura>(`${BASE}/cobertura`)

// A grade precisa de todas as semanas do filtro: o limite padrão da API (500)
// cortaria o histórico sem aviso.
export const listarAnp = (f: FiltrosAnp) =>
  pedir<SemanaAnp[]>(`${BASE}/anp`, { params: { produto: f.produto, de: f.de, ate: f.ate, limite: 100000 } })

export const listarProdutosAnp = () => pedir<string[]>(`${BASE}/anp/produtos`)

export const gravarSemanaAnp = (entrada: SemanaAnpEntrada) =>
  pedir<SemanaAnp>(`${BASE}/anp`, { metodo: 'PUT', json: entrada })

export const excluirSemanaAnp = (id: number) => pedir<void>(`${BASE}/anp/${id}`, { metodo: 'DELETE' })

export const urlExportarAnp = (f: FiltrosAnp & { formato: Formato }) =>
  caminhoCom(`${BASE}/anp/exportar`, { produto: f.produto, de: f.de, ate: f.ate, formato: f.formato })

export const listarIgpDi = () => pedir<IndiceMensal[]>(`${BASE}/igp-di`)

export const gravarIgpDi = (mes: string, valor: string) =>
  pedir<IndiceMensal>(`${BASE}/igp-di/${mes}`, { metodo: 'PUT', json: { valor } })

export const excluirIgpDi = (mes: string) => pedir<void>(`${BASE}/igp-di/${mes}`, { metodo: 'DELETE' })

export const URL_TEMPLATE_IGP_DI = `${BASE}/igp-di/template`

export const urlExportarIgpDi = (formato: Formato) => caminhoCom(`${BASE}/igp-di/exportar`, { formato })
