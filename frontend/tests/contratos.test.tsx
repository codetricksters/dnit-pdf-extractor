import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { umContrato, umaCobertura, umResumo } from './fabricas'
import { renderApp } from './render'
import { servidor } from './servidor'

function comContratos(lista: unknown[]) {
  servidor.use(http.get('/api/v1/contratos', () => HttpResponse.json(lista)))
}

describe('Lista de contratos', () => {
  it('mostra a situação e aponta o número para cadastro ou cálculo', async () => {
    comContratos([
      umResumo({ id: 1, numero: '15 00716/2022' }),
      umResumo({ id: 2, numero: '15 00800/2023', faltantes: ['regiao_emulsoes'], regioes: { CAP: 'Sul' } }),
      umResumo({ id: 3, numero: '15 00900/2024', faltantes: ['edital'] }),
    ])
    renderApp('/')
    const linha1 = (await screen.findByText('15 00716/2022')).closest('tr')!
    expect(within(linha1).getByText('Completo')).toHaveClass('badge-ok')
    expect(within(linha1).getByRole('link', { name: '15 00716/2022' })).toHaveAttribute('href', '/contratos/1/calculo')
    expect(within(linha1).getByText('jan/2022')).toBeInTheDocument()
    expect(within(linha1).getByText('fev/2023 – mar/2023')).toBeInTheDocument()

    const linha2 = screen.getByText('15 00800/2023').closest('tr')!
    expect(within(linha2).getByText('Falta região Emulsões')).toHaveClass('badge-danger')
    expect(within(linha2).getByRole('link', { name: '15 00800/2023' })).toHaveAttribute('href', '/contratos/2/cadastro')

    const linha3 = screen.getByText('15 00900/2024').closest('tr')!
    expect(within(linha3).getByText('1 campo do cabeçalho vazio')).toHaveClass('badge-warn')
  })

  it('pesquisa por número', async () => {
    comContratos([umResumo({ id: 1, numero: '15 00716/2022' }), umResumo({ id: 2, numero: '15 00800/2023' })])
    const { usuario } = renderApp('/contratos')
    await screen.findByText('15 00716/2022')
    await usuario.type(screen.getByLabelText('Pesquisar contrato'), '800')
    expect(screen.queryByText('15 00716/2022')).not.toBeInTheDocument()
    expect(screen.getByText('15 00800/2023')).toBeInTheDocument()
  })

  it('sem contratos convida a enviar PDFs', async () => {
    comContratos([])
    renderApp('/')
    expect(await screen.findByText('Nenhum contrato ainda.')).toBeInTheDocument()
    for (const link of screen.getAllByRole('link', { name: 'Enviar PDFs' })) {
      expect(link).toHaveAttribute('href', '/upload')
    }
  })
})

describe('Página do contrato', () => {
  it('404 mostra "não encontrado"', async () => {
    servidor.use(
      http.get('/api/v1/contratos/9', () => HttpResponse.json({ detail: 'Contrato 9 não encontrado.' }, { status: 404 })),
    )
    renderApp('/contratos/9/cadastro')
    expect(await screen.findByText('Contrato 9 não encontrado.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Voltar aos contratos' })).toBeInTheDocument()
  })

  it('/contratos/:id abre a aba Cadastro', async () => {
    servidor.use(
      http.get('/api/v1/contratos/1', () => HttpResponse.json(umContrato())),
      http.get('/api/v1/indices/cobertura', () => HttpResponse.json(umaCobertura())),
    )
    renderApp('/contratos/1')
    expect(await screen.findByRole('heading', { name: '15 00716/2022' })).toBeInTheDocument()
    expect(screen.getByTestId('local')).toHaveTextContent('/contratos/1/cadastro')
    expect(screen.getByRole('link', { name: 'Cadastro' })).toHaveAttribute('aria-current', 'page')
  })
})
