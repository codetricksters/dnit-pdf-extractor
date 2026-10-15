import type { FiltrosMedicoes, RegioesSimuladas } from './chaves'
import { caminhoCom, pedir } from './client'
import type {
  Calculo, Contrato, ContratoPatch, ContratoResumo, ItemMedicao, MedicaoCorpo, RegiaoEmLote, RegiaoAplicada,
} from './tipos'

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

export const incluirMedicao = (id: number, corpo: MedicaoCorpo) =>
  pedir<ItemMedicao>(`${BASE}/${id}/medicoes`, { metodo: 'POST', json: corpo })

export const alterarMedicao = (id: number, itemId: number, corpo: MedicaoCorpo) =>
  pedir<ItemMedicao>(`${BASE}/${id}/medicoes/${itemId}`, { metodo: 'PATCH', json: corpo })

export const excluirMedicao = (id: number, itemId: number) =>
  pedir<void>(`${BASE}/${id}/medicoes/${itemId}`, { metodo: 'DELETE' })

// simular só conta os registros que mudariam, para a tela confirmar antes de gravar.
export const aplicarRegiao = (id: number, corpo: RegiaoEmLote, simular = false) =>
  pedir<RegiaoAplicada>(`${BASE}/${id}/medicoes/regiao`, {
    metodo: 'POST', json: corpo, params: { simular: simular || undefined },
  })
