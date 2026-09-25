import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ResumoJob, StatusJob } from '../src/api/tipos'
import { renderApp } from './render'
import { servidor } from './servidor'

// jsdom não tem EventSource: a tela segue pelo /status, como num proxy que corta SSE.
beforeEach(() => vi.stubGlobal('EventSource', undefined))

function umStatus(completed: boolean, files: StatusJob['files']): StatusJob {
  return { job_id: 'j1', completed, files }
}

const CONCLUIDO = umStatus(true, {
  'medicao_fev.pdf': { status: 'completed', error: null, contrato_id: 1, itens: 48 },
  'escaneado.pdf': { status: 'failed', error: 'Nenhum registro encontrado no PDF.', contrato_id: null, itens: null },
})

function umResumo(parcial: Partial<ResumoJob> = {}): ResumoJob {
  return {
    job_id: 'antigo',
    created_at: '2026-09-20T13:00:00+00:00',
    completed: true,
    file_count: 3,
    completed_count: 3,
    failed_count: 0,
    processing_count: 0,
    pending_count: 0,
    ...parcial,
  }
}

function preparar({ ativos = [] as ResumoJob[], status = CONCLUIDO } = {}) {
  const enviados: string[] = []
  const retentativas: string[] = []
  servidor.use(
    http.get('/api/v1/contratos', () =>
      HttpResponse.json([{ id: 1, numero: '15 00716/2022', data_base: null, contratada: null, rodovia: null, regioes: {} }]),
    ),
    http.get('/jobs', ({ request }) =>
      HttpResponse.json(new URL(request.url).searchParams.get('status') === 'active' ? ativos : [umResumo()]),
    ),
    http.post('/upload', async ({ request }) => {
      const form = await request.formData()
      for (const f of form.getAll('files')) enviados.push((f as File).name)
      return HttpResponse.json({ job_id: 'j1' })
    }),
    http.get('/jobs/:id/status', () => HttpResponse.json(status)),
    http.post('/jobs/j1/retry/:arquivo', ({ params }) => {
      retentativas.push(params.arquivo as string)
      return HttpResponse.json({ ok: true })
    }),
  )
  return { enviados, retentativas }
}

const pdf = (nome: string) => new File(['%PDF-1.4'], nome, { type: 'application/pdf' })

describe('Upload de PDFs', () => {
  it('envia os PDFs escolhidos e mostra o resultado de cada um', async () => {
    const { enviados } = preparar()
    const { usuario } = renderApp('/upload')
    await usuario.upload(screen.getByLabelText('Arquivos PDF'), [pdf('medicao_fev.pdf'), pdf('escaneado.pdf')])
    expect(screen.getByText('2 arquivos selecionados')).toBeInTheDocument()
    await usuario.click(screen.getByRole('button', { name: 'Enviar para processamento' }))

    const ok = (await screen.findByText('medicao_fev.pdf', { selector: 'td' })).closest('tr')!
    expect(enviados).toEqual(['medicao_fev.pdf', 'escaneado.pdf'])
    expect(await within(ok).findByText('Concluído')).toHaveClass('badge-completed')
    expect(within(ok).getByText(/48 itens/)).toBeInTheDocument()
    expect(within(ok).getByRole('link', { name: '15 00716/2022' })).toHaveAttribute('href', '/contratos/1')
    expect(within(ok).getByRole('button', { name: 'JSON' })).toBeInTheDocument()

    const falhou = screen.getByText('escaneado.pdf', { selector: 'td' }).closest('tr')!
    expect(within(falhou).getByText('Falhou')).toHaveClass('badge-failed')
    expect(within(falhou).getByText('Nenhum registro encontrado no PDF.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Baixar todos os resultados (.zip)' })).toBeInTheDocument()
  })

  it('arquivo concluído sem número de contrato no cabeçalho avisa em vez de mostrar célula vazia', async () => {
    preparar({
      ativos: [umResumo({ job_id: 'j1', completed: false })],
      status: umStatus(true, {
        'sem_contrato.pdf': { status: 'completed', error: null, contrato_id: null, itens: 12 },
      }),
    })
    renderApp('/upload')
    const linha = (await screen.findByText('sem_contrato.pdf', { selector: 'td' })).closest('tr')!
    expect(within(linha).getByText('sem número de contrato no cabeçalho', { exact: false })).toBeInTheDocument()
  })

  it('baixar o JSON de um arquivo busca como blob, não como link puro', async () => {
    preparar({ ativos: [umResumo({ job_id: 'j1', completed: false })] })
    const pedidos: string[] = []
    servidor.use(
      http.get('/jobs/j1/download/medicao_fev.pdf', ({ request }) => {
        pedidos.push(new URL(request.url).pathname)
        return HttpResponse.text('{}', { headers: { 'Content-Disposition': 'attachment; filename="medicao_fev.pdf.json"' } })
      }),
    )
    const { usuario } = renderApp('/upload')
    const ok = (await screen.findByText('medicao_fev.pdf', { selector: 'td' })).closest('tr')!
    await usuario.click(within(ok).getByRole('button', { name: 'JSON' }))
    await waitFor(() => expect(pedidos).toEqual(['/jobs/j1/download/medicao_fev.pdf']))
  })

  it('baixar o zip do lote busca como blob, não como link puro', async () => {
    preparar({ ativos: [umResumo({ job_id: 'j1', completed: false })] })
    const pedidos: string[] = []
    servidor.use(
      http.get('/jobs/j1/download', ({ request }) => {
        pedidos.push(new URL(request.url).pathname)
        return HttpResponse.text('zip', { headers: { 'Content-Disposition': 'attachment; filename="j1.zip"' } })
      }),
    )
    const { usuario } = renderApp('/upload')
    await screen.findByText('medicao_fev.pdf', { selector: 'td' })
    await usuario.click(screen.getByRole('button', { name: 'Baixar todos os resultados (.zip)' }))
    await waitFor(() => expect(pedidos).toEqual(['/jobs/j1/download']))
  })

  it('tentar de novo reenvia o arquivo que falhou', async () => {
    const { retentativas } = preparar({ ativos: [umResumo({ job_id: 'j1', completed: false })] })
    const { usuario } = renderApp('/upload')
    const falhou = (await screen.findByText('escaneado.pdf', { selector: 'td' })).closest('tr')!
    await usuario.click(within(falhou).getByRole('button', { name: 'Tentar de novo' }))
    expect(retentativas).toEqual(['escaneado.pdf'])
  })

  it('retoma o lote em andamento ao abrir a tela', async () => {
    preparar({
      ativos: [umResumo({ job_id: 'j1', completed: false })],
      status: umStatus(false, { 'lento.pdf': { status: 'processing', error: null, contrato_id: null, itens: null } }),
    })
    renderApp('/upload')
    const linha = (await screen.findByText('lento.pdf', { selector: 'td' })).closest('tr')!
    expect(within(linha).getByText('Processando')).toHaveClass('badge-processing')
    expect(screen.queryByRole('link', { name: 'Baixar todos os resultados (.zip)' })).not.toBeInTheDocument()
  })

  it('só aceita PDF', async () => {
    preparar()
    const { usuario } = renderApp('/upload', { applyAccept: false })
    await usuario.upload(screen.getByLabelText('Arquivos PDF'), [pdf('a.pdf'), new File(['x'], 'planilha.xlsx')])
    expect(screen.getByText('1 arquivo selecionado')).toBeInTheDocument()
    expect(screen.getByText('Ignorado: planilha.xlsx (não é PDF).')).toBeInTheDocument()
  })

  it('lotes anteriores ficam recolhidos, com o zip de cada um', async () => {
    preparar()
    const { usuario } = renderApp('/upload')
    await usuario.click(await screen.findByText('Lotes anteriores (1)'))
    const linha = screen.getByText('20/09/2026 10:00').closest('tr')!
    expect(within(linha).getByText('3 de 3')).toBeInTheDocument()
    expect(within(linha).getByRole('button', { name: 'Baixar .zip' })).toBeInTheDocument()
  })
})
