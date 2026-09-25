import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import type { IndiceMensal, SemanaAnp } from '../src/api/tipos'
import { umaCobertura } from './fabricas'
import { renderApp } from './render'
import { servidor } from './servidor'

const CAP = 'Cimento Asfáltico de Petróleo 50 70 (R$/kg)'

function umaSemana(parcial: Partial<SemanaAnp>): SemanaAnp {
  return {
    id: 1,
    produto: CAP,
    regiao: 'Nordeste',
    vigencia_inicio: '2023-01-08',
    vigencia_fim: '2023-01-14',
    preco: '3.61475',
    origem: 'seed',
    atualizado_em: '2026-09-24T10:02:00+00:00',
    ...parcial,
  }
}

const SEMANAS = [
  umaSemana({ id: 1 }),
  umaSemana({ id: 2, regiao: 'Sul', preco: null }),
  umaSemana({ id: 3, regiao: 'Norte', preco: '3.9', origem: 'manual' }),
]

function preparar() {
  const escritas: { metodo: string; url: string; corpo: unknown }[] = []
  const registrar = async (request: Request) => {
    escritas.push({ metodo: request.method, url: request.url, corpo: request.method === 'DELETE' ? null : await request.json() })
  }
  servidor.use(
    http.get('/api/v1/indices/cobertura', () => HttpResponse.json(umaCobertura())),
    http.get('/api/v1/indices/anp/produtos', () => HttpResponse.json([CAP, 'Óleo Diesel (R$/l)'])),
    http.get('/api/v1/indices/anp', () => HttpResponse.json(SEMANAS)),
    http.put('/api/v1/indices/anp', async ({ request }) => {
      await registrar(request)
      return HttpResponse.json(umaSemana({ id: 9 }))
    }),
    http.delete('/api/v1/indices/anp/:id', async ({ request }) => {
      await registrar(request)
      return new HttpResponse(null, { status: 204 })
    }),
    http.get('/api/v1/indices/igp-di', () =>
      HttpResponse.json<IndiceMensal[]>([
        { mes: '2023-02', valor: '1085.3', origem: 'manual', atualizado_em: '2026-09-24T10:02:00+00:00' },
      ]),
    ),
    http.put('/api/v1/indices/igp-di/:mes', async ({ request }) => {
      await registrar(request)
      return HttpResponse.json({ mes: '2023-03', valor: '1090.1', origem: 'manual', atualizado_em: '2026-09-24T10:02:00+00:00' })
    }),
    http.delete('/api/v1/indices/igp-di/:mes', async ({ request }) => {
      await registrar(request)
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return escritas
}

describe('Índices', () => {
  it('/indices abre o ANP, com a cobertura do CAP rotulada', async () => {
    preparar()
    renderApp('/indices')
    expect(screen.getByTestId('local')).toHaveTextContent('/indices/anp')
    expect(await screen.findByText(/60\.114 registros/)).toBeInTheDocument()
    // GET /indices/cobertura não é por produto: o backend sempre soma a série
    // do CAP, mesmo que a grade esteja mostrando outro produto — o rótulo diz
    // isso, em vez de parecer a cobertura do produto selecionado.
    expect(screen.getByText(/Período \(CAP\):/)).toBeInTheDocument()
  })

  it('grade do ANP: preço, sem cotação, célula vazia e marca de manual', async () => {
    preparar()
    renderApp('/indices/anp')
    const linha = (await screen.findByText('08/01 – 14/01/2023')).closest('tr')!
    expect(within(linha).getByRole('button', { name: 'Editar Nordeste 08/01 – 14/01/2023' })).toHaveTextContent('3,61475')
    expect(within(linha).getByRole('button', { name: 'Editar Sul 08/01 – 14/01/2023' })).toHaveTextContent('sem cotação')
    expect(within(linha).getByRole('button', { name: 'Editar Sudeste 08/01 – 14/01/2023' })).toHaveTextContent('—')
    const norte = within(linha).getByRole('button', { name: 'Editar Norte 08/01 – 14/01/2023' }).closest('td')!
    expect(norte).toHaveClass('manual')
    expect(norte).toHaveAttribute('title', 'manual · 24/09/2026 07:02')
  })

  it('exportar busca o arquivo como blob, com os filtros da tela, em vez de um link puro', async () => {
    preparar()
    const pedidos: URL[] = []
    servidor.use(
      http.get('/api/v1/indices/anp/exportar', ({ request }) => {
        pedidos.push(new URL(request.url))
        return HttpResponse.text('conteudo', { headers: { 'Content-Disposition': 'attachment; filename="indices_anp.xlsx"' } })
      }),
    )
    const { usuario } = renderApp('/indices/anp')
    await screen.findByText('08/01 – 14/01/2023')
    await usuario.click(screen.getByRole('button', { name: 'Exportar .xlsx' }))
    await waitFor(() => expect(pedidos).toHaveLength(1))
    expect(pedidos[0].pathname).toBe('/api/v1/indices/anp/exportar')
    expect(Object.fromEntries(pedidos[0].searchParams)).toEqual({ produto: CAP, formato: 'xlsx' })
  })

  it('exportar mostra o erro do backend em vez de salvar a resposta como arquivo', async () => {
    preparar()
    servidor.use(
      http.get('/api/v1/indices/anp/exportar', () => HttpResponse.json({ detail: 'Falha ao gerar o arquivo.' }, { status: 500 })),
    )
    const { usuario } = renderApp('/indices/anp')
    await screen.findByText('08/01 – 14/01/2023')
    await usuario.click(screen.getByRole('button', { name: 'Exportar .xlsx' }))
    expect(await screen.findByText('Falha ao gerar o arquivo.')).toBeInTheDocument()
  })

  it('editar uma célula do ANP grava a semana inteira da região', async () => {
    const escritas = preparar()
    const { usuario } = renderApp('/indices/anp')
    await usuario.click(await screen.findByRole('button', { name: 'Editar Sudeste 08/01 – 14/01/2023' }))
    await usuario.type(screen.getByLabelText('Sudeste 08/01 – 14/01/2023'), '3,7{Enter}')
    expect(escritas[0]).toMatchObject({
      metodo: 'PUT',
      corpo: { produto: CAP, regiao: 'Sudeste', vigencia_inicio: '2023-01-08', vigencia_fim: '2023-01-14', preco: '3.7' },
    })
  })

  it('apagar a semana confirma e exclui todas as regiões dela', async () => {
    const escritas = preparar()
    const { usuario } = renderApp('/indices/anp')
    const linha = (await screen.findByText('08/01 – 14/01/2023')).closest('tr')!
    await usuario.click(within(linha).getByRole('button', { name: 'Apagar semana 08/01 – 14/01/2023' }))
    await usuario.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Apagar' }))
    const apagadas = escritas.filter((e) => e.metodo === 'DELETE').map((e) => e.url.split('/').at(-1))
    expect(apagadas.sort()).toEqual(['1', '2', '3'])
  })

  it('apagar a semana com falha parcial ainda atualiza a grade com o que foi apagado', async () => {
    const deletadas = new Set<string>()
    servidor.use(
      http.get('/api/v1/indices/cobertura', () => HttpResponse.json(umaCobertura())),
      http.get('/api/v1/indices/anp/produtos', () => HttpResponse.json([CAP, 'Óleo Diesel (R$/l)'])),
      http.get('/api/v1/indices/anp', () => HttpResponse.json(SEMANAS.filter((s) => !deletadas.has(String(s.id))))),
      // A região Sul (id 2) falha; Nordeste (id 1), que vem antes na ordem de
      // inserção, já foi apagada com sucesso antes da falha interromper o laço.
      http.delete('/api/v1/indices/anp/:id', ({ params }) => {
        const id = String(params.id)
        if (id === '2') return HttpResponse.json({ detail: 'falha ao apagar' }, { status: 500 })
        deletadas.add(id)
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const { usuario } = renderApp('/indices/anp')
    const linha = (await screen.findByText('08/01 – 14/01/2023')).closest('tr')!
    await usuario.click(within(linha).getByRole('button', { name: 'Apagar semana 08/01 – 14/01/2023' }))
    await usuario.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Apagar' }))

    // A mutação como um todo falhou (Sul não foi apagada) e o diálogo continua
    // aberto mostrando o erro — mas a grade já reflete a região que foi
    // apagada com sucesso antes da falha, em vez de continuar mostrando um
    // preço que já não existe mais no banco.
    expect(await screen.findByRole('dialog')).toHaveTextContent('falha ao apagar')
    const linhaAtualizada = (await screen.findByText('08/01 – 14/01/2023')).closest('tr')!
    expect(within(linhaAtualizada).getByRole('button', { name: 'Editar Nordeste 08/01 – 14/01/2023' })).toHaveTextContent('—')
  })

  it('nova semana grava pelo diálogo', async () => {
    const escritas = preparar()
    const { usuario } = renderApp('/indices/anp')
    await usuario.click(await screen.findByRole('button', { name: 'Nova semana' }))
    const dialogo = screen.getByRole('dialog')
    await usuario.type(within(dialogo).getByLabelText('Início da vigência'), '2023-01-15')
    await usuario.type(within(dialogo).getByLabelText('Fim da vigência'), '2023-01-21')
    await usuario.selectOptions(within(dialogo).getByLabelText('Região'), 'Sul')
    await usuario.type(within(dialogo).getByLabelText('Preço (R$)'), '3,65')
    await usuario.click(within(dialogo).getByRole('button', { name: 'Gravar' }))
    expect(escritas[0]).toMatchObject({
      metodo: 'PUT',
      corpo: { produto: CAP, regiao: 'Sul', vigencia_inicio: '2023-01-15', vigencia_fim: '2023-01-21', preco: '3.65' },
    })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('grade do IGP-DI: grava um mês novo e apaga um existente', async () => {
    const escritas = preparar()
    const { usuario } = renderApp('/indices/igp-di')
    const fev = await screen.findByRole('button', { name: 'Editar IGP-DI fev/2023' })
    expect(fev.closest('td')).toHaveClass('manual')

    await usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI mar/2023' }))
    await usuario.type(screen.getByLabelText('IGP-DI mar/2023'), '1090,1{Enter}')
    expect(escritas.at(-1)).toMatchObject({ metodo: 'PUT', corpo: { valor: '1090.1' } })
    expect(escritas.at(-1)!.url).toContain('/igp-di/2023-03')

    await usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' }))
    await usuario.clear(screen.getByLabelText('IGP-DI fev/2023'))
    await usuario.keyboard('{Enter}')
    expect(escritas.filter((e) => e.metodo === 'DELETE')).toHaveLength(0)
    const dialogo = screen.getByRole('dialog')
    expect(dialogo).toHaveTextContent('IGP-DI fev/2023')
    await usuario.click(within(dialogo).getByRole('button', { name: 'Apagar' }))
    expect(escritas.at(-1)).toMatchObject({ metodo: 'DELETE' })
    expect(escritas.at(-1)!.url).toContain('/igp-di/2023-02')
    expect(screen.getByRole('button', { name: 'Baixar template' })).toBeInTheDocument()
  })

  it('baixar o template do IGP-DI busca como blob, não como link puro', async () => {
    preparar()
    const pedidos: string[] = []
    servidor.use(
      http.get('/api/v1/indices/igp-di/template', ({ request }) => {
        pedidos.push(new URL(request.url).pathname)
        return HttpResponse.text('modelo', { headers: { 'Content-Disposition': 'attachment; filename="igp_di_template.xlsx"' } })
      }),
    )
    const { usuario } = renderApp('/indices/igp-di')
    await screen.findByRole('button', { name: 'Editar IGP-DI fev/2023' })
    await usuario.click(screen.getByRole('button', { name: 'Baixar template' }))
    await waitFor(() => expect(pedidos).toEqual(['/api/v1/indices/igp-di/template']))
  })

  it('apagar o valor de uma célula do ANP pede confirmação antes de gravar nulo', async () => {
    const escritas = preparar()
    const { usuario } = renderApp('/indices/anp')
    const linha = (await screen.findByText('08/01 – 14/01/2023')).closest('tr')!
    await usuario.click(within(linha).getByRole('button', { name: 'Editar Nordeste 08/01 – 14/01/2023' }))
    await usuario.clear(screen.getByLabelText('Nordeste 08/01 – 14/01/2023'))
    await usuario.keyboard('{Enter}')
    expect(escritas.filter((e) => e.metodo === 'PUT')).toHaveLength(0)
    const dialogo = screen.getByRole('dialog')
    expect(dialogo).toHaveTextContent('Nordeste 08/01 – 14/01/2023')

    await usuario.click(within(dialogo).getByRole('button', { name: 'Cancelar' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(escritas).toHaveLength(0)
    expect(within(linha).getByRole('button', { name: 'Editar Nordeste 08/01 – 14/01/2023' })).toHaveTextContent('3,61475')

    await usuario.click(within(linha).getByRole('button', { name: 'Editar Nordeste 08/01 – 14/01/2023' }))
    await usuario.clear(screen.getByLabelText('Nordeste 08/01 – 14/01/2023'))
    await usuario.keyboard('{Enter}')
    await usuario.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Apagar' }))
    expect(escritas.at(-1)).toMatchObject({
      metodo: 'PUT',
      corpo: { produto: CAP, regiao: 'Nordeste', vigencia_inicio: '2023-01-08', vigencia_fim: '2023-01-14', preco: null },
    })
  })
})
