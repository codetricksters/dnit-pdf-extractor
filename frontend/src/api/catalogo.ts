import type { FiltrosCodigos } from './chaves'
import { pedir } from './client'
import type { Codigo, Familia, Produto } from './tipos'

const BASE = '/api/v1'

export interface ProdutoNovo {
  descricao_export: string
  familia: Familia
}

export const listarProdutos = () => pedir<Produto[]>(`${BASE}/produtos`)

export const criarProduto = (produto: ProdutoNovo) =>
  pedir<Produto>(`${BASE}/produtos`, { metodo: 'POST', json: produto })

export const atualizarProduto = (id: number, produto: Partial<ProdutoNovo>) =>
  pedir<Produto>(`${BASE}/produtos/${id}`, { metodo: 'PATCH', json: produto })

export const excluirProduto = (id: number) => pedir<void>(`${BASE}/produtos/${id}`, { metodo: 'DELETE' })

export const listarCodigos = (filtros: FiltrosCodigos) =>
  pedir<Codigo[]>(`${BASE}/codigos`, {
    params: { q: filtros.q, associado: filtros.associado, produto_id: filtros.produtoId, limite: 500 },
  })

// Um PUT só para vários códigos: ou todos são associados, ou nenhum.
export const associarCodigos = (produtoId: number, codigos: string[]) =>
  pedir<Produto>(`${BASE}/produtos/${produtoId}/codigos`, { metodo: 'PUT', json: { codigos } })

export const desassociarCodigo = (codigo: string) =>
  pedir<void>(`${BASE}/codigos/${encodeURIComponent(codigo)}`, { metodo: 'DELETE' })
