import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import type { ItemMedicao } from '../src/api/tipos'
import { umContrato } from './fabricas'
import { renderApp } from './render'
import { servidor } from './servidor'

function umItem(parcial: Partial<ItemMedicao> = {}): ItemMedicao {
  return {
    id: 1,
    mes: '2023-02-01',
    codigo: '60112',
    descricao_pdf: 'Fornecimento de CAP 50/70',
    valor_pi: '412300.00',
    fator: '0.1480',
    reajuste: '61020.40',
    arquivo: 'medicao_fev.pdf',
    produto_id: 3,
    produto: 'Aquisição de CAP 50/70',
    familia: 'CAP',
    ...parcial,
  }
}

function preparar(itens: ItemMedicao[]) {
  const pedidos: URLSearchParams[] = []
  servidor.use(
    http.get('/api/v1/contratos/1', () => HttpResponse.json(umContrato())),
    http.get('/api/v1/contratos/1/medicoes', ({ request }) => {
      pedidos.push(new URL(request.url).searchParams)
      return HttpResponse.json(itens)
    }),
  )
  return pedidos
}

describe('Aba Medições', () => {
  it('lista os itens com o produto, ou o atalho para associar', async () => {
    preparar([
      umItem(),
      umItem({ id: 2, codigo: '40210', descricao_pdf: 'Escavação', produto_id: null, produto: null, familia: null }),
    ])
    renderApp('/contratos/1/medicoes')
    const linha = (await screen.findByText('60112')).closest('tr')!
    expect(within(linha).getByText('fev/2023')).toBeInTheDocument()
    expect(within(linha).getByText('412.300,00')).toBeInTheDocument()
    expect(within(linha).getByText('0,1480')).toBeInTheDocument()
    expect(within(linha).getByText('Aquisição de CAP 50/70')).toBeInTheDocument()
    expect(within(linha).getByText('medicao_fev.pdf')).toBeInTheDocument()

    const fora = screen.getByText('40210').closest('tr')!
    expect(within(fora).getByText('Fora do cálculo')).toBeInTheDocument()
    expect(within(fora).getByRole('link', { name: 'Associar' })).toHaveAttribute('href', '/catalogo?q=40210')
    expect(screen.getByText('2 itens')).toBeInTheDocument()
  })

  it('filtros viram parâmetros da API', async () => {
    const pedidos = preparar([umItem()])
    const { usuario } = renderApp('/contratos/1/medicoes')
    await screen.findByText('60112')

    await usuario.type(screen.getByLabelText('Mês'), '2023-02')
    await usuario.selectOptions(screen.getByLabelText('Situação'), 'Só no cálculo')
    await usuario.type(screen.getByLabelText('Código ou descrição'), 'cap')
    await usuario.click(screen.getByRole('button', { name: 'Filtrar' }))

    const ultimo = pedidos.at(-1)!
    expect(ultimo.get('mes')).toBe('2023-02')
    expect(ultimo.get('no_calculo')).toBe('true')
    expect(ultimo.get('q')).toBe('cap')
  })

  it('sem itens mostra o estado vazio', async () => {
    preparar([])
    renderApp('/contratos/1/medicoes')
    expect(await screen.findByText('Nenhum item com esses filtros.')).toBeInTheDocument()
  })
})
