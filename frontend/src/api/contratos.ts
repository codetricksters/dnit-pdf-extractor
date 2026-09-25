import type { FiltrosMedicoes, RegioesSimuladas } from './chaves'
import { caminhoCom, pedir } from './client'
import type { Calculo, Contrato, ContratoPatch, ContratoResumo, ItemMedicao } from './tipos'

const BASE = '/api/v1/contratos'

export const listarContratos = () => pedir<ContratoResumo[]>(BASE)

export const buscarContrato = (id: number) => pedir<Contrato>(`${BASE}/${id}`)

export const atualizarContrato = (id: number, patch: ContratoPatch) =>
  pedir<Contrato>(`${BASE}/${id}`, { metodo: 'PATCH', json: patch })

function paramsRegioes(regioes: RegioesSimuladas) {
  return { regiao_cap: regioes.cap, regiao_emulsoes: regioes.emulsoes }
}

export const calcular = (id: number, regioes: RegioesSimuladas) =>
  pedir<Calculo>(`${BASE}/${id}/calculo`, { params: paramsRegioes(regioes) })

// O JSON e o arquivo saem da mesma função no backend; os mesmos parâmetros
// garantem que a planilha baixada é a tabela da tela.
export const urlPlanilha = (id: number, regioes: RegioesSimuladas) =>
  caminhoCom(`${BASE}/${id}/planilha`, paramsRegioes(regioes))

export const listarMedicoes = (id: number, filtros: FiltrosMedicoes) =>
  pedir<ItemMedicao[]>(`${BASE}/${id}/medicoes`, {
    params: { mes: filtros.mes, no_calculo: filtros.noCalculo, q: filtros.q },
  })
