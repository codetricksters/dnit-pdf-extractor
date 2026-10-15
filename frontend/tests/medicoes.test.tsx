import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import type { ItemMedicao } from '../src/api/tipos'
import { umaCobertura, umContrato } from './fabricas'
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
    origem: 'pdf',
    regiao_cap: null,
    regiao_emulsoes: null,
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

    await usuario.type(screen.getByLabelText('Mês'), 'fev/2023')
    await usuario.selectOptions(screen.getByLabelText('Situação'), 'Só no cálculo')
    await usuario.type(screen.getByLabelText('Código ou descrição'), 'cap')
    await usuario.click(screen.getByRole('button', { name: 'Filtrar' }))

    const ultimo = pedidos.at(-1)!
    expect(ultimo.get('mes')).toBe('2023-02')
    expect(ultimo.get('no_calculo')).toBe('true')
    expect(ultimo.get('q')).toBe('cap')
  })

  it('mês digitado fora da lista é recusado no campo, sem consultar a API', async () => {
    const pedidos = preparar([umItem()])
    const { usuario } = renderApp('/contratos/1/medicoes')
    await screen.findByText('60112')
    const antes = pedidos.length

    await usuario.type(screen.getByLabelText('Mês'), '2023-13')
    expect(screen.getByText('Escolha um mês da lista, como fev/2023.')).toBeInTheDocument()
    await usuario.click(screen.getByRole('button', { name: 'Filtrar' }))
    expect(pedidos).toHaveLength(antes)

    await usuario.clear(screen.getByLabelText('Mês'))
    await usuario.type(screen.getByLabelText('Mês'), '02/2023')
    expect(screen.queryByText(/Escolha um mês/)).not.toBeInTheDocument()
    await usuario.click(screen.getByRole('button', { name: 'Filtrar' }))
    expect(pedidos.at(-1)!.get('mes')).toBe('2023-02')
  })

  it('sem itens mostra o estado vazio', async () => {
    preparar([])
    renderApp('/contratos/1/medicoes')
    expect(await screen.findByText('Nenhum item com esses filtros.')).toBeInTheDocument()
  })

  function prepararEdicao(itens: ItemMedicao[]) {
    const corpos: unknown[] = []
    preparar(itens)
    servidor.use(
      http.get('/api/v1/indices/cobertura', () => HttpResponse.json(umaCobertura())),
      http.post('/api/v1/contratos/1/medicoes', async ({ request }) => {
        corpos.push(await request.json())
        return HttpResponse.json(umItem({ id: 9, origem: 'manual' }), { status: 201 })
      }),
      http.patch('/api/v1/contratos/1/medicoes/:item', async ({ request }) => {
        corpos.push(await request.json())
        return HttpResponse.json(umItem({ origem: 'editado', regiao_cap: 'Sul' }))
      }),
      http.delete('/api/v1/contratos/1/medicoes/:item', () => new HttpResponse(null, { status: 204 })),
    )
    return corpos
  }

  it('inclui um registro manual com a digitação brasileira', async () => {
    const corpos = prepararEdicao([umItem()])
    const { usuario } = renderApp('/contratos/1/medicoes')
    await usuario.click(await screen.findByRole('button', { name: /Incluir registro/ }))
    const dialogo = screen.getByRole('dialog')
    await usuario.selectOptions(within(dialogo).getByLabelText('Mês da medição'), '02')
    await usuario.type(within(dialogo).getByLabelText('Ano'), '2023')
    await usuario.type(within(dialogo).getByLabelText('Código'), '60112')
    await usuario.type(within(dialogo).getByLabelText('Valor PI líquido'), '1.234,56')
    await usuario.type(within(dialogo).getByLabelText('Fator'), '0,148')
    await usuario.click(within(dialogo).getByRole('button', { name: 'Salvar' }))
    await waitFor(() => expect(corpos).toEqual([
      { mes: '2023-02', codigo: '60112', descricao_pdf: null, valor_pi: '1234.56',
        fator: '0.148', regiao_cap: null, regiao_emulsoes: null },
    ]))
  })

  it('em registro do PDF, envia só o que mudou e trava código e mês', async () => {
    const corpos = prepararEdicao([umItem()])
    const { usuario } = renderApp('/contratos/1/medicoes')
    const linha = (await screen.findByText('60112')).closest('tr')!
    await usuario.click(within(linha).getByRole('button', { name: /Editar/ }))
    const dialogo = screen.getByRole('dialog')
    expect(within(dialogo).getByLabelText('Código')).toBeDisabled()
    await usuario.selectOptions(within(dialogo).getByLabelText('Região ANP — CAP'), 'Sul')
    await usuario.click(within(dialogo).getByRole('button', { name: 'Salvar' }))
    await waitFor(() => expect(corpos).toEqual([{ regiao_cap: 'Sul' }]))
  })

  it('mostra no campo o erro 422 do backend', async () => {
    prepararEdicao([umItem()])
    servidor.use(
      http.patch('/api/v1/contratos/1/medicoes/:item', () =>
        HttpResponse.json({ detail: 'fator: informe um número.' }, { status: 422 })),
    )
    const { usuario } = renderApp('/contratos/1/medicoes')
    const linha = (await screen.findByText('60112')).closest('tr')!
    await usuario.click(within(linha).getByRole('button', { name: /Editar/ }))
    const dialogo = screen.getByRole('dialog')
    await usuario.clear(within(dialogo).getByLabelText('Fator'))
    await usuario.type(within(dialogo).getByLabelText('Fator'), '2')
    await usuario.click(within(dialogo).getByRole('button', { name: 'Salvar' }))
    expect(await within(dialogo).findByText('fator: informe um número.')).toBeInTheDocument()
    expect(within(dialogo).getByLabelText('Fator')).toHaveAttribute('aria-invalid', 'true')
  })

  it('mostra no campo o erro 422 do Pydantic', async () => {
    prepararEdicao([umItem()])
    servidor.use(
      http.post('/api/v1/contratos/1/medicoes', () =>
        HttpResponse.json(
          { detail: [{ loc: ['body', 'valor_pi'], msg: 'Input should be a valid decimal', type: 'decimal_parsing' }] },
          { status: 422 },
        )),
    )
    const { usuario } = renderApp('/contratos/1/medicoes')
    await usuario.click(await screen.findByRole('button', { name: /Incluir registro/ }))
    const dialogo = screen.getByRole('dialog')
    await usuario.click(within(dialogo).getByRole('button', { name: 'Salvar' }))
    expect(await within(dialogo).findByText('Input should be a valid decimal')).toBeInTheDocument()
    expect(within(dialogo).getByLabelText('Valor PI líquido')).toHaveAttribute('aria-invalid', 'true')
  })

  it('exclui só depois de confirmar', async () => {
    prepararEdicao([umItem()])
    let excluiu = false
    servidor.use(http.delete('/api/v1/contratos/1/medicoes/1', () => {
      excluiu = true
      return new HttpResponse(null, { status: 204 })
    }))
    const { usuario } = renderApp('/contratos/1/medicoes')
    const linha = (await screen.findByText('60112')).closest('tr')!
    await usuario.click(within(linha).getByRole('button', { name: /Excluir/ }))
    expect(excluiu).toBe(false)
    await usuario.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Excluir registro' }))
    await waitFor(() => expect(excluiu).toBe(true))
  })

  it('aplica a região a uma família num período, depois de mostrar quantos registros mudam', async () => {
    prepararEdicao([umItem(), umItem({ id: 2, mes: '2023-03-01' }), umItem({ id: 3, mes: '2023-04-01' })])
    const pedidos: { simular: string | null; corpo: unknown }[] = []
    servidor.use(http.post('/api/v1/contratos/1/medicoes/regiao', async ({ request }) => {
      pedidos.push({ simular: new URL(request.url).searchParams.get('simular'), corpo: await request.json() })
      return HttpResponse.json({ alterados: 2 })
    }))
    const { usuario } = renderApp('/contratos/1/medicoes')
    await usuario.click(await screen.findByRole('button', { name: /Aplicar região/ }))
    const dialogo = screen.getByRole('dialog')
    await usuario.selectOptions(within(dialogo).getByLabelText('Família'), 'EMULSOES')
    await usuario.selectOptions(within(dialogo).getByLabelText('De'), '2023-03')
    await usuario.selectOptions(within(dialogo).getByLabelText('Até'), '2023-04')
    await usuario.selectOptions(within(dialogo).getByLabelText('Região ANP'), 'Sul')
    await usuario.click(within(dialogo).getByRole('button', { name: 'Continuar' }))

    expect(await within(dialogo).findByText(/2 registros de Emulsões/)).toBeInTheDocument()
    await usuario.click(within(dialogo).getByRole('button', { name: 'Aplicar região' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    const corpo = { familia: 'EMULSOES', mes_de: '2023-03', mes_ate: '2023-04', regiao: 'Sul' }
    expect(pedidos).toEqual([{ simular: 'true', corpo }, { simular: null, corpo }])
    expect(screen.getByText('Região aplicada em 2 registros.')).toBeInTheDocument()
  })

  it('mostra o erro do backend ao aplicar a região', async () => {
    prepararEdicao([umItem()])
    servidor.use(http.post('/api/v1/contratos/1/medicoes/regiao', () =>
      HttpResponse.json({ detail: 'mes_ate: o período termina antes de começar.' }, { status: 422 })))
    const { usuario } = renderApp('/contratos/1/medicoes')
    await usuario.click(await screen.findByRole('button', { name: /Aplicar região/ }))
    await usuario.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Continuar' }))
    expect(await screen.findByText('mes_ate: o período termina antes de começar.')).toBeInTheDocument()
  })

  it('filtra por arquivo, com os manuais numa opção própria', async () => {
    const pedidos = preparar([
      umItem(), umItem({ id: 2, arquivo: 'medicao_mar.pdf' }), umItem({ id: 3, arquivo: 'manual', origem: 'manual' }),
    ])
    const { usuario } = renderApp('/contratos/1/medicoes')
    await screen.findAllByText('60112')
    const arquivo = screen.getByLabelText('Arquivo')
    expect(within(arquivo).getAllByRole('option').map((o) => o.textContent)).toEqual(
      ['Todos', 'Incluídos manualmente', 'medicao_fev.pdf', 'medicao_mar.pdf'],
    )
    await usuario.selectOptions(arquivo, 'medicao_mar.pdf')
    await usuario.click(screen.getByRole('button', { name: 'Filtrar' }))
    expect(pedidos.at(-1)!.get('arquivo')).toBe('medicao_mar.pdf')
  })

  it('seleciona todos os itens do filtro e exclui de uma vez, depois de confirmar', async () => {
    prepararEdicao([umItem(), umItem({ id: 2, mes: '2023-03-01' }), umItem({ id: 3, mes: '2023-04-01' })])
    const corpos: unknown[] = []
    servidor.use(http.post('/api/v1/contratos/1/medicoes/excluir', async ({ request }) => {
      corpos.push(await request.json())
      return HttpResponse.json({ excluidos: 3 })
    }))
    const { usuario } = renderApp('/contratos/1/medicoes')
    await screen.findAllByText('60112')
    expect(screen.getByRole('button', { name: /Excluir selecionados/ })).toBeDisabled()

    await usuario.click(screen.getByLabelText('Selecionar todos'))
    await usuario.click(screen.getByLabelText('Selecionar 60112 de mar/2023'))
    await usuario.click(screen.getByRole('button', { name: 'Excluir selecionados (2)' }))
    expect(corpos).toEqual([])
    const dialogo = screen.getByRole('dialog')
    expect(within(dialogo).getByText(/Excluir 2 registros\?/)).toBeInTheDocument()
    await usuario.click(within(dialogo).getByRole('button', { name: 'Excluir registros' }))
    await waitFor(() => expect(corpos).toEqual([{ ids: [1, 3] }]))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('marca origem e região própria na lista', async () => {
    prepararEdicao([umItem({ origem: 'editado', regiao_cap: 'Sul' })])
    renderApp('/contratos/1/medicoes')
    const linha = (await screen.findByText('60112')).closest('tr')!
    expect(within(linha).getByText('editado')).toBeInTheDocument()
    expect(within(linha).getByText('CAP: Sul *')).toBeInTheDocument()
  })
})
