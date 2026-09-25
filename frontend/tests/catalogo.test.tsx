import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Codigo, Produto } from '../src/api/tipos'
import { renderApp } from './render'
import { servidor } from './servidor'

const CAP: Produto = { id: 3, descricao_export: 'Aquisição de CAP 50/70', familia: 'CAP', ordem: 0, codigos: 1 }
const RR: Produto = { id: 4, descricao_export: 'Emulsão RR-1C', familia: 'EMULSOES', ordem: 0, codigos: 0 }

function umCodigo(parcial: Partial<Codigo> = {}): Codigo {
  return {
    codigo: '60112',
    descricao_pdf: 'Fornecimento de CAP 50/70',
    contratos: 1,
    ocorrencias: 2,
    produto_id: 3,
    descricao_export: CAP.descricao_export,
    familia: 'CAP',
    ...parcial,
  }
}

const SEM_PRODUTO = umCodigo({ codigo: '40210', descricao_pdf: 'Escavação', produto_id: null, descricao_export: null, familia: null })
const EM_RR = umCodigo({ codigo: '60113', descricao_pdf: 'Emulsão RR', produto_id: 4, descricao_export: RR.descricao_export, familia: 'EMULSOES' })

function preparar(produtos: Produto[] = [CAP, RR]) {
  const escritas: { metodo: string; url: string; corpo: unknown }[] = []
  servidor.use(
    http.get('/api/v1/produtos', () => HttpResponse.json(produtos)),
    http.get('/api/v1/codigos', ({ request }) => {
      const p = new URL(request.url).searchParams
      if (p.get('produto_id') === '3') return HttpResponse.json([umCodigo()])
      if (p.get('produto_id')) return HttpResponse.json([])
      return HttpResponse.json([umCodigo(), SEM_PRODUTO, EM_RR])
    }),
    http.post('/api/v1/produtos', async ({ request }) => {
      const corpo = await request.json()
      escritas.push({ metodo: 'POST', url: request.url, corpo })
      return HttpResponse.json({ ...RR, id: 9, ...(corpo as object) }, { status: 201 })
    }),
    http.delete('/api/v1/produtos/:id', ({ request }) => {
      escritas.push({ metodo: 'DELETE', url: request.url, corpo: null })
      return new HttpResponse(null, { status: 204 })
    }),
    http.delete('/api/v1/codigos/:codigo', ({ request }) => {
      escritas.push({ metodo: 'DELETE', url: request.url, corpo: null })
      return new HttpResponse(null, { status: 204 })
    }),
    http.put('/api/v1/produtos/:id/codigos', async ({ request }) => {
      escritas.push({ metodo: 'PUT', url: request.url, corpo: await request.json() })
      return HttpResponse.json({ ...CAP, codigos: 3 })
    }),
  )
  return escritas
}

describe('Catálogo', () => {
  it('lista os produtos por família e mostra os códigos do selecionado', async () => {
    preparar()
    renderApp('/catalogo')
    const lista = await screen.findByRole('navigation', { name: 'Produtos' })
    expect(within(lista).getByText('CAP')).toBeInTheDocument()
    expect(within(lista).getByText('Emulsões')).toBeInTheDocument()
    // O primeiro produto fica selecionado.
    expect(await screen.findByRole('heading', { name: 'Aquisição de CAP 50/70' })).toBeInTheDocument()
    const linha = (await screen.findByText('60112')).closest('tr')!
    expect(within(linha).getByText('Fornecimento de CAP 50/70')).toBeInTheDocument()
  })

  it('sem produtos explica o que fazer', async () => {
    preparar([])
    renderApp('/catalogo')
    expect(await screen.findByText(/Nenhum produto ainda/)).toBeInTheDocument()
  })

  it('cria um produto', async () => {
    const escritas = preparar()
    const { usuario } = renderApp('/catalogo')
    await usuario.click(await screen.findByRole('button', { name: 'Novo produto' }))
    const dialogo = screen.getByRole('dialog')
    await usuario.type(within(dialogo).getByLabelText('Descrição na planilha'), 'Emulsão RL-1C')
    await usuario.selectOptions(within(dialogo).getByLabelText('Família'), 'Emulsões')
    await usuario.click(within(dialogo).getByRole('button', { name: 'Salvar' }))
    expect(escritas[0]).toMatchObject({ metodo: 'POST', corpo: { descricao_export: 'Emulsão RL-1C', familia: 'EMULSOES' } })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(screen.getByTestId('local')).toHaveTextContent('/catalogo?produto=9'))
  })

  it('duplicado mostra o erro dentro do diálogo', async () => {
    preparar()
    servidor.use(
      http.post('/api/v1/produtos', () =>
        HttpResponse.json({ detail: "Já existe o produto 'Emulsão RR-1C'." }, { status: 409 }),
      ),
    )
    const { usuario } = renderApp('/catalogo')
    await usuario.click(await screen.findByRole('button', { name: 'Novo produto' }))
    const dialogo = screen.getByRole('dialog')
    await usuario.type(within(dialogo).getByLabelText('Descrição na planilha'), 'Emulsão RR-1C')
    await usuario.click(within(dialogo).getByRole('button', { name: 'Salvar' }))
    expect(await within(dialogo).findByText("Já existe o produto 'Emulsão RR-1C'.")).toBeInTheDocument()
  })

  it('excluir pede confirmação e explica o efeito', async () => {
    const escritas = preparar()
    const { usuario } = renderApp('/catalogo?produto=3')
    await usuario.click(await screen.findByRole('button', { name: 'Excluir produto' }))
    const dialogo = screen.getByRole('dialog')
    expect(dialogo).toHaveTextContent('1 código deixa o cálculo')
    await usuario.click(within(dialogo).getByRole('button', { name: 'Excluir' }))
    expect(escritas).toContainEqual(expect.objectContaining({ metodo: 'DELETE', url: expect.stringContaining('/produtos/3') }))
  })

  it('remove um código do produto sem confirmação', async () => {
    const escritas = preparar()
    const { usuario } = renderApp('/catalogo?produto=3')
    const linha = (await screen.findByText('60112')).closest('tr')!
    await usuario.click(within(linha).getByRole('button', { name: 'Remover 60112' }))
    expect(escritas).toContainEqual(expect.objectContaining({ metodo: 'DELETE', url: expect.stringContaining('/codigos/60112') }))
  })

  it('adicionar códigos: status de cada um e associação em lote', async () => {
    const escritas = preparar()
    const { usuario } = renderApp('/catalogo?produto=3&q=60')
    const dialogo = await screen.findByRole('dialog')
    expect(within(dialogo).getByLabelText('Buscar código ou descrição')).toHaveValue('60')
    const linha = (texto: string) => within(dialogo).getByText(texto).closest('tr')!
    expect(await within(dialogo).findByText('40210')).toBeInTheDocument()
    expect(linha('60112')).toHaveTextContent('neste produto')
    expect(linha('40210')).toHaveTextContent('sem produto')
    expect(linha('60113')).toHaveTextContent('em Emulsão RR-1C')

    await usuario.click(within(linha('40210')).getByRole('checkbox'))
    await usuario.click(within(linha('60113')).getByRole('checkbox'))
    await usuario.click(within(dialogo).getByRole('button', { name: 'Associar selecionados (2)' }))
    expect(escritas.at(-1)).toMatchObject({ metodo: 'PUT', corpo: { codigos: ['40210', '60113'] } })
    expect(escritas.at(-1)!.url).toContain('/produtos/3/codigos')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(screen.getByTestId('local')).toHaveTextContent(/^\/catalogo\?produto=3$/))
  })
})
