import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Backup, Template } from '../src/api/tipos'
import { renderApp } from './render'
import { servidor } from './servidor'

const TEMPLATES: Template[] = [
  { id: 2, nome: 'reequilibrio_v2.xlsx', tamanho: 48 * 1024, sha256: 'ab'.repeat(32), ativo: true, criado_em: '2026-09-20T13:00:00+00:00', observacao: 'Logo novo' },
  { id: 1, nome: 'reequilibrio_template.xlsx', tamanho: 45 * 1024, sha256: 'cd'.repeat(32), ativo: false, criado_em: '2026-01-10T13:00:00+00:00', observacao: null },
]

const BACKUPS: Backup[] = [
  { nome: 'dnit_20260924_0300_agendado.dump', tamanho: 3.2 * 1024 * 1024, criado_em: '2026-09-24T06:00:00+00:00' },
]

function preparar() {
  const chamadas: { metodo: string; caminho: string; form?: Record<string, FormDataEntryValue> }[] = []
  const registrar = async (request: Request) => {
    const form = request.headers.get('content-type')?.includes('multipart')
      ? Object.fromEntries(await request.formData())
      : undefined
    chamadas.push({ metodo: request.method, caminho: new URL(request.url).pathname, form })
  }
  servidor.use(
    http.get('/admin/templates', () => HttpResponse.json(TEMPLATES)),
    http.post('/admin/templates', async ({ request }) => {
      await registrar(request)
      return HttpResponse.json({ id: 3, ativo: true })
    }),
    http.post('/admin/templates/:id/ativar', async ({ request }) => {
      await registrar(request)
      return HttpResponse.json({ ativo: 1 })
    }),
    http.delete('/admin/templates/:id', async ({ request }) => {
      await registrar(request)
      return HttpResponse.json({ excluido: 1 })
    }),
    http.get('/admin/backups', () => HttpResponse.json(BACKUPS)),
    http.post('/admin/backups', async ({ request }) => {
      await registrar(request)
      return HttpResponse.json(
        { detail: 'pg_dump 17 é mais novo que o servidor 16; defina PG_BIN.' },
        { status: 422 },
      )
    }),
    http.post('/admin/backups/:nome/restaurar', async ({ request }) => {
      await registrar(request)
      return HttpResponse.json({ restaurado: BACKUPS[0].nome, seguranca: 'dnit_20260924_1010_antes_de_restaurar.dump' })
    }),
  )
  return chamadas
}

describe('Templates', () => {
  it('lista com o ativo marcado; o ativo não tem Excluir nem Ativar', async () => {
    preparar()
    renderApp('/sistema/templates')
    const ativo = (await screen.findByText('reequilibrio_v2.xlsx')).closest('tr')!
    expect(within(ativo).getByText('Ativo')).toHaveClass('badge-ok')
    expect(within(ativo).getByText('Logo novo')).toBeInTheDocument()
    expect(within(ativo).getByText('48 KB')).toBeInTheDocument()
    expect(within(ativo).queryByRole('button', { name: /Excluir/ })).not.toBeInTheDocument()
    expect(within(ativo).getByRole('link', { name: 'Baixar' })).toHaveAttribute('href', '/admin/templates/2/download')

    const antigo = screen.getByText('reequilibrio_template.xlsx').closest('tr')!
    expect(within(antigo).getByRole('button', { name: 'Ativar' })).toBeInTheDocument()
  })

  it('ativar e excluir (com confirmação) um template antigo', async () => {
    const chamadas = preparar()
    const { usuario } = renderApp('/sistema/templates')
    const antigo = (await screen.findByText('reequilibrio_template.xlsx')).closest('tr')!
    await usuario.click(within(antigo).getByRole('button', { name: 'Ativar' }))
    expect(chamadas.at(-1)).toMatchObject({ metodo: 'POST', caminho: '/admin/templates/1/ativar' })

    await usuario.click(within(antigo).getByRole('button', { name: 'Excluir' }))
    await usuario.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Excluir' }))
    expect(chamadas.at(-1)).toMatchObject({ metodo: 'DELETE', caminho: '/admin/templates/1' })
  })

  it('enviar um template manda arquivo, observação e ativar', async () => {
    const chamadas = preparar()
    const { usuario } = renderApp('/sistema/templates')
    await screen.findByText('reequilibrio_v2.xlsx')
    await usuario.upload(screen.getByLabelText('Novo template (.xlsx)'), new File(['x'], 'v3.xlsx'))
    await usuario.type(screen.getByLabelText('Observação'), 'Rodapé corrigido')
    await usuario.click(screen.getByRole('button', { name: 'Enviar template' }))
    const envio = chamadas.at(-1)!
    expect(envio.caminho).toBe('/admin/templates')
    expect((envio.form!.arquivo as File).name).toBe('v3.xlsx')
    expect(envio.form!.observacao).toBe('Rodapé corrigido')
    expect(envio.form!.ativar).toBe('true')
  })
})

describe('Backups', () => {
  it('gerar mostra a recusa do backend como veio', async () => {
    preparar()
    const { usuario } = renderApp('/sistema/backups')
    await usuario.click(await screen.findByRole('button', { name: 'Gerar backup agora' }))
    expect(await screen.findByText('pg_dump 17 é mais novo que o servidor 16; defina PG_BIN.')).toBeInTheDocument()
  })

  it('restaurar exige digitar o nome e informa o backup de segurança', async () => {
    const chamadas = preparar()
    const { usuario } = renderApp('/sistema/backups')
    const nome = BACKUPS[0].nome
    const linha = (await screen.findByText(nome)).closest('tr')!
    expect(within(linha).getByText('3,2 MB')).toBeInTheDocument()
    expect(within(linha).getByRole('link', { name: 'Baixar' })).toHaveAttribute('href', `/admin/backups/${nome}/download`)

    await usuario.click(within(linha).getByRole('button', { name: 'Restaurar' }))
    const dialogo = screen.getByRole('dialog')
    const confirmar = within(dialogo).getByRole('button', { name: 'Restaurar' })
    expect(confirmar).toBeDisabled()
    await usuario.type(within(dialogo).getByLabelText(`Digite ${nome} para confirmar`), nome)
    await usuario.click(confirmar)

    expect(chamadas.at(-1)).toMatchObject({ caminho: `/admin/backups/${nome}/restaurar`, form: { confirmacao: nome } })
    expect(await screen.findByText(/dnit_20260924_1010_antes_de_restaurar\.dump/)).toBeInTheDocument()
  })
})
