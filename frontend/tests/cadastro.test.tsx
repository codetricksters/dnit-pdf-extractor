import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Contrato } from '../src/api/tipos'
import { umContrato, umaCobertura } from './fabricas'
import { renderApp } from './render'
import { servidor } from './servidor'

function preparar(contrato: Contrato) {
  let atual = contrato
  const recebidos: unknown[] = []
  servidor.use(
    http.get('/api/v1/contratos/1', () => HttpResponse.json(atual)),
    http.get('/api/v1/indices/cobertura', () => HttpResponse.json(umaCobertura())),
    http.patch('/api/v1/contratos/1', async ({ request }) => {
      const corpo = (await request.json()) as Record<string, unknown>
      recebidos.push(corpo)
      const regioes = { ...atual.regioes, ...(corpo.regioes as object) }
      atual = { ...atual, ...corpo, regioes, faltantes: [] } as Contrato
      return HttpResponse.json(atual)
    }),
  )
  return recebidos
}

describe('Aba Cadastro', () => {
  it('mostra pendências dos parâmetros e dos campos de cabeçalho', async () => {
    preparar(umContrato({ regioes: { CAP: 'Nordeste' }, edital: null, trecho: null, faltantes: ['edital', 'trecho', 'regiao_emulsoes'] }))
    renderApp('/contratos/1/cadastro')
    expect(await screen.findByText('1 pendente — cálculo bloqueado')).toBeInTheDocument()
    expect(screen.getByText('2 vazios — sairá com aviso')).toBeInTheDocument()
    expect(screen.getByLabelText('Nº do processo')).toHaveAttribute('readonly')
    expect(screen.getByLabelText('Data Base')).toHaveValue('2022-01')
    expect(screen.getByLabelText('Extensão (km)')).toHaveValue('45,7')
  })

  it('salva só o que mudou e volta a mostrar completo', async () => {
    const recebidos = preparar(umContrato({ regioes: { CAP: 'Nordeste' }, faltantes: ['regiao_emulsoes'] }))
    const { usuario } = renderApp('/contratos/1/cadastro')
    await usuario.selectOptions(await screen.findByLabelText('Região ANP — Emulsões'), 'Sul')
    await usuario.clear(screen.getByLabelText('Trecho'))
    await usuario.click(screen.getByRole('button', { name: 'Salvar' }))
    await waitFor(() => expect(recebidos).toHaveLength(1))
    expect(recebidos[0]).toEqual({ trecho: null, regioes: { EMULSOES: 'Sul' } })
    expect(await screen.findByText('Cadastro salvo.')).toBeInTheDocument()
    expect(screen.getByText('Parâmetros completos')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled()
  })

  it('erro do backend aparece no campo', async () => {
    preparar(umContrato())
    servidor.use(
      http.patch('/api/v1/contratos/1', () =>
        HttpResponse.json(
          { detail: "Região 'Sul' sem preços ANP do CAP 50/70. Regiões disponíveis: Nordeste." },
          { status: 422 },
        ),
      ),
    )
    const { usuario } = renderApp('/contratos/1/cadastro')
    await usuario.selectOptions(await screen.findByLabelText('Região ANP — CAP'), 'Sul')
    await usuario.click(screen.getByRole('button', { name: 'Salvar' }))
    const erro = await screen.findByText(/sem preços ANP do CAP 50\/70/)
    expect(erro).toHaveClass('erro-campo')
    expect(screen.getByLabelText('Região ANP — CAP')).toHaveAttribute('aria-invalid', 'true')
  })

  it('descartar volta ao que está gravado', async () => {
    preparar(umContrato())
    const { usuario } = renderApp('/contratos/1/cadastro')
    const rodovia = await screen.findByLabelText('Rodovia')
    await usuario.clear(rodovia)
    await usuario.type(rodovia, 'BR-999')
    await usuario.click(screen.getByRole('button', { name: 'Descartar' }))
    expect(rodovia).toHaveValue('BR-230')
    expect(screen.getByRole('button', { name: 'Descartar' })).toBeDisabled()
  })
})
