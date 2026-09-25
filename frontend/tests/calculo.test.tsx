import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Calculo } from '../src/api/tipos'
import { umContrato, umaCobertura } from './fabricas'
import { renderApp } from './render'
import { servidor } from './servidor'

function umCalculo(parcial: Partial<Calculo> = {}): Calculo {
  return {
    contrato: { id: 1, numero: '15 00716/2022' },
    parametros: { data_base: '2022-01-01', regioes: { CAP: 'Nordeste', EMULSOES: 'Nordeste' }, simulacao: false, lucro: '0.0511' },
    familias: [
      {
        familia: 'CAP',
        rotulo: 'CAP',
        subtotal: '-38275.68',
        produtos: [
          {
            descricao: 'Aquisição de CAP 50/70',
            subtotal: '-38275.68',
            linhas: [
              { mes: '2023-02-01', a: '412300.00', fator: '0.1480', b: '61020.40', d: '0.049812',
                c: '20537.4876', e: '-40482.9124', f: '-38275.68' },
            ],
          },
        ],
      },
    ],
    total: '-38275.68',
    avisos: ['Campo(s) do cadastro vazio(s): edital.'],
    arquivo: 'Reequilibrio_15_00716-2022.xlsx',
    ...parcial,
  }
}

function preparar(resposta: (url: URL) => Response) {
  const pedidos: URL[] = []
  servidor.use(
    http.get('/api/v1/contratos/1', () => HttpResponse.json(umContrato())),
    http.get('/api/v1/indices/cobertura', () => HttpResponse.json(umaCobertura())),
    http.get('/api/v1/contratos/1/calculo', ({ request }) => {
      const url = new URL(request.url)
      pedidos.push(url)
      return resposta(url)
    }),
  )
  return pedidos
}

describe('Aba Cálculo', () => {
  it('tabela espelha a planilha: letras, grupos, subtotal, total e negativos', async () => {
    preparar(() => HttpResponse.json(umCalculo()))
    renderApp('/contratos/1/calculo')
    const tabela = await screen.findByRole('table')
    for (const letra of ['a', 'b', 'd', 'c = a·d', 'e = c − b', 'f = e·(1 − 5,11%)']) {
      expect(within(tabela).getByText(letra)).toBeInTheDocument()
    }
    expect(within(tabela).getByText('Aquisição de CAP 50/70')).toBeInTheDocument()
    const linha = within(tabela).getByText('fev/2023').closest('tr')!
    expect(within(linha).getByText('412.300,00')).toBeInTheDocument()
    expect(within(linha).getByText('0,049812')).toBeInTheDocument()
    expect(within(linha).getByText('-40.482,91')).toHaveClass('neg')
    expect(within(tabela).getByText('Total geral').closest('tr')).toHaveTextContent('-38.275,68')
    expect(screen.getByText('Campo(s) do cadastro vazio(s): edital.')).toBeInTheDocument()
    expect(screen.getByText('Data Base: jan/2022')).toBeInTheDocument()
  })

  it('simulação vai para a URL, mostra o aviso e muda o link de download', async () => {
    const pedidos = preparar((url) =>
      HttpResponse.json(
        url.searchParams.get('regiao_cap')
          ? umCalculo({
              parametros: { data_base: '2022-01-01', regioes: { CAP: 'Sul', EMULSOES: 'Nordeste' }, simulacao: true, lucro: '0.0511' },
              arquivo: 'Reequilibrio_15_00716-2022_SIMULACAO_CAP-Sul.xlsx',
            })
          : umCalculo(),
      ),
    )
    const { usuario } = renderApp('/contratos/1/calculo')
    const baixar = await screen.findByRole('button', { name: 'Baixar planilha (.xlsx)' })

    await usuario.selectOptions(screen.getByLabelText('Região CAP'), 'Sul')
    expect(screen.getByTestId('local')).toHaveTextContent('/contratos/1/calculo?regiao_cap=Sul')
    const faixa = await screen.findByText(/Simulação/)
    expect(faixa.closest('.notice')).toHaveTextContent('CAP em Sul (cadastro: Nordeste)')
    expect(faixa.closest('.notice')).toHaveTextContent('Reequilibrio_15_00716-2022_SIMULACAO_CAP-Sul.xlsx')
    expect(pedidos.at(-1)!.searchParams.get('regiao_cap')).toBe('Sul')

    // O download busca como blob, não como <a href>, para não salvar uma
    // resposta de erro como se fosse a planilha; a query da simulação vai no
    // pedido, igual à do JSON que a tela está mostrando.
    const pedidosPlanilha: URL[] = []
    servidor.use(
      http.get('/api/v1/contratos/1/planilha', ({ request }) => {
        pedidosPlanilha.push(new URL(request.url))
        return HttpResponse.text('xlsx', {
          headers: { 'Content-Disposition': 'attachment; filename="Reequilibrio_15_00716-2022_SIMULACAO_CAP-Sul.xlsx"' },
        })
      }),
    )
    await usuario.click(baixar)
    await waitFor(() => expect(pedidosPlanilha).toHaveLength(1))
    expect(pedidosPlanilha[0].pathname).toBe('/api/v1/contratos/1/planilha')
    expect(pedidosPlanilha[0].searchParams.get('regiao_cap')).toBe('Sul')

    await usuario.click(screen.getByRole('button', { name: 'Voltar ao cadastro' }))
    expect(screen.getByTestId('local')).toHaveTextContent(/^\/contratos\/1\/calculo$/)
    expect(screen.queryByText(/Simulação/)).not.toBeInTheDocument()
  })

  it('escolher a região do cadastro tira o parâmetro da URL', async () => {
    preparar(() => HttpResponse.json(umCalculo()))
    const { usuario } = renderApp('/contratos/1/calculo?regiao_cap=Sul')
    await usuario.selectOptions(await screen.findByLabelText('Região CAP'), 'Nordeste')
    expect(screen.getByTestId('local')).toHaveTextContent(/^\/contratos\/1\/calculo$/)
  })

  it('bloqueado lista todos os faltantes com atalhos', async () => {
    preparar(() =>
      HttpResponse.json(
        {
          detail: 'Não é possível calcular:\n- regiao_emulsoes\n- Sem valor de IGP - DI para 02/2023 (mês da medição).',
          faltando: ['regiao_emulsoes', 'Sem valor de IGP - DI para 02/2023 (mês da medição).'],
        },
        { status: 422 },
      ),
    )
    renderApp('/contratos/1/calculo')
    const caixa = (await screen.findByText('Cálculo bloqueado')).closest('.notice')!
    expect(within(caixa as HTMLElement).getByText('Falta a região ANP das Emulsões.')).toBeInTheDocument()
    expect(within(caixa as HTMLElement).getByRole('link', { name: 'Abrir cadastro' })).toHaveAttribute('href', '/contratos/1/cadastro')
    expect(within(caixa as HTMLElement).getByRole('link', { name: 'Abrir IGP-DI' })).toHaveAttribute('href', '/indices/igp-di')
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Baixar planilha (.xlsx)' })).not.toBeInTheDocument()
  })
})
