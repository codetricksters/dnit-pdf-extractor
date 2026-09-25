import type { QueryClient } from '@tanstack/react-query'
import { chaves } from './chaves'

// Prefixo comum de chaves.contrato(id) — invalida qualquer contrato em cache,
// sem repetir ['contrato'] como chave literal.
const PREFIXO_CONTRATO = chaves.contrato(0).slice(0, 1)

// Depois de cada gravação, as telas releem do banco o que ela pode ter mudado.

export function aposCadastro(qc: QueryClient, contratoId: number) {
  return Promise.all([
    qc.invalidateQueries({ queryKey: chaves.contrato(contratoId) }),
    qc.invalidateQueries({ queryKey: chaves.contratos }),
    qc.invalidateQueries({ queryKey: chaves.calculos }),
  ])
}

// Produto ou associação de código: muda o que entra em qualquer cálculo.
export function aposCatalogo(qc: QueryClient) {
  return Promise.all([
    qc.invalidateQueries({ queryKey: chaves.produtos }),
    qc.invalidateQueries({ queryKey: chaves.todosCodigos }),
    qc.invalidateQueries({ queryKey: chaves.todasMedicoes }),
    qc.invalidateQueries({ queryKey: chaves.calculos }),
  ])
}

// Índices são globais: todo cálculo em cache pode ter mudado.
export function aposIndices(qc: QueryClient) {
  return Promise.all([
    qc.invalidateQueries({ queryKey: chaves.todosAnp }),
    qc.invalidateQueries({ queryKey: chaves.produtosAnp }),
    qc.invalidateQueries({ queryKey: chaves.todosIgpDi }),
    qc.invalidateQueries({ queryKey: chaves.cobertura }),
    qc.invalidateQueries({ queryKey: chaves.calculos }),
  ])
}

// PDF processado: contrato novo ou itens novos.
export function aposUpload(qc: QueryClient) {
  return Promise.all([
    qc.invalidateQueries({ queryKey: chaves.contratos }),
    qc.invalidateQueries({ queryKey: PREFIXO_CONTRATO }),
    qc.invalidateQueries({ queryKey: chaves.todasMedicoes }),
    qc.invalidateQueries({ queryKey: chaves.todosCodigos }),
    qc.invalidateQueries({ queryKey: chaves.calculos }),
  ])
}
