import { screen, within } from '@testing-library/react'
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
  it('/indices abre o ANP, com a cobertura', async () => {
    preparar()
    renderApp('/indices')
    expect(screen.getByTestId('local')).toHaveTextContent('/indices/anp')
    expect(await screen.findByText(/60\.114 registros/)).toBeInTheDocument()
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
    const exportar = new URL(screen.getByRole('link', { name: 'Exportar .xlsx' }).getAttribute('href')!, 'http://x')
    expect(exportar.pathname).toBe('/api/v1/indices/anp/exportar')
    expect(Object.fromEntries(exportar.searchParams)).toEqual({ produto: CAP, formato: 'xlsx' })
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
    expect(escritas.at(-1)).toMatchObject({ metodo: 'DELETE' })
    expect(escritas.at(-1)!.url).toContain('/igp-di/2023-02')
    expect(screen.getByRole('link', { name: 'Baixar template' })).toHaveAttribute('href', '/api/v1/indices/igp-di/template')
  })
})
