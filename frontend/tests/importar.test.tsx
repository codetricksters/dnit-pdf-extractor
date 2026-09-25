import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import type { ResultadoImportacao } from '../src/api/tipos'
import { umaCobertura } from './fabricas'
import { renderApp } from './render'
import { servidor } from './servidor'

function umResultado(parcial: Partial<ResultadoImportacao> = {}): ResultadoImportacao {
  return {
    arquivo: 'igp_di.xlsx',
    simulacao: true,
    periodo: { de: '2022-01-01', ate: '2023-03-01' },
    inseridos: 1,
    atualizados: [{ chave: { mes: '2022-06' }, antes: '1001', depois: '1002' }],
    inalterados: 12,
    conflitos_manuais: [
      { chave: { mes: '2023-02' }, valor_banco: '1085.3', valor_arquivo: '1084.9', atualizado_em: '2026-09-24T10:02:00+00:00' },
    ],
    manuais_preservados: 1,
    avisos: ['Linha 20 vazia, ignorada.'],
    ...parcial,
  }
}

function preparar(respostas: (params: URLSearchParams) => Response) {
  const pedidos: URLSearchParams[] = []
  servidor.use(
    http.get('/api/v1/indices/cobertura', () => HttpResponse.json(umaCobertura())),
    http.get('/api/v1/indices/igp-di', () => HttpResponse.json([])),
    http.post('/api/v1/indices/igp-di/importar', async ({ request }) => {
      const form = await request.formData()
      expect(form.get('arquivo')).toBeInstanceOf(File)
      const params = new URL(request.url).searchParams
      pedidos.push(params)
      return respostas(params)
    }),
  )
  return pedidos
}

const arquivo = () => new File(['conteudo'], 'igp_di.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })

async function abrirPrevia() {
  const { usuario } = renderApp('/indices/igp-di')
  await usuario.click(await screen.findByRole('button', { name: 'Importar' }))
  const dialogo = screen.getByRole('dialog')
  await usuario.upload(within(dialogo).getByLabelText('Arquivo'), arquivo())
  await usuario.click(within(dialogo).getByRole('button', { name: 'Ver prévia' }))
  return { usuario, dialogo }
}

describe('Importar índices', () => {
  it('a prévia simula e mostra cartões, conflitos e avisos', async () => {
    const pedidos = preparar(() => HttpResponse.json(umResultado()))
    const { dialogo } = await abrirPrevia()

    expect(await within(dialogo).findByText('Novos')).toBeInTheDocument()
    expect(pedidos[0].get('simular')).toBe('true')
    const cartao = (rotulo: string) => within(dialogo).getByText(rotulo).closest('.cartao')!
    expect(cartao('Novos')).toHaveTextContent('1')
    expect(cartao('Alterados')).toHaveTextContent('1')
    expect(cartao('Iguais')).toHaveTextContent('12')
    expect(cartao('Seus valores manuais em conflito')).toHaveClass('warn')

    const conflito = within(dialogo).getByText('fev/2023').closest('tr')!
    expect(within(conflito).getByText('1.085,3')).toBeInTheDocument()
    expect(within(conflito).getByText('1.084,9')).toBeInTheDocument()
    expect(within(conflito).getByText('24/09/2026 07:02')).toBeInTheDocument()
    expect(within(dialogo).getByText('Linha 20 vazia, ignorada.')).toBeInTheDocument()
  })

  it('gravar mantendo os manuais não sobrescreve e mostra o resumo', async () => {
    const pedidos = preparar((p) => HttpResponse.json(umResultado({ simulacao: p.get('simular') === 'true' })))
    const { usuario, dialogo } = await abrirPrevia()
    await usuario.click(await within(dialogo).findByRole('button', { name: 'Gravar e manter meus valores manuais' }))

    expect(pedidos.at(-1)!.get('simular')).toBe('false')
    expect(pedidos.at(-1)!.get('sobrescrever_manuais')).toBe('false')
    expect(await within(dialogo).findByText('Importação gravada.')).toBeInTheDocument()
    expect(within(dialogo).getByText(/1 valor manual preservado/)).toBeInTheDocument()
  })

  it('sobrescrever os manuais manda sobrescrever_manuais=true', async () => {
    const pedidos = preparar((p) =>
      HttpResponse.json(umResultado({ simulacao: p.get('simular') === 'true', manuais_preservados: p.get('sobrescrever_manuais') === 'true' ? 0 : 1 })),
    )
    const { usuario, dialogo } = await abrirPrevia()
    await usuario.click(await within(dialogo).findByRole('button', { name: 'Gravar e sobrescrever os 1 manuais' }))
    expect(pedidos.at(-1)!.get('sobrescrever_manuais')).toBe('true')
    expect(await within(dialogo).findByText('Importação gravada.')).toBeInTheDocument()
  })

  it('sem conflitos, só um botão de gravar', async () => {
    preparar(() => HttpResponse.json(umResultado({ conflitos_manuais: [], manuais_preservados: 0 })))
    const { dialogo } = await abrirPrevia()
    expect(await within(dialogo).findByRole('button', { name: 'Gravar' })).toBeInTheDocument()
    expect(within(dialogo).queryByRole('button', { name: /sobrescrever/ })).not.toBeInTheDocument()
    expect(within(dialogo).queryByText('Seus valores manuais em conflito')?.closest('.cartao')).not.toHaveClass('warn')
  })

  it('arquivo inválido lista os erros por linha e não sai do primeiro passo', async () => {
    preparar(() =>
      HttpResponse.json(
        { detail: 'O arquivo tem 2 linha(s) inválida(s); nada foi gravado.', erros: ['Linha 3: mês ilegível.', 'Linha 7: valor negativo.'] },
        { status: 422 },
      ),
    )
    const { dialogo } = await abrirPrevia()
    expect(await within(dialogo).findByText('Linha 3: mês ilegível.')).toBeInTheDocument()
    expect(within(dialogo).getByText('Linha 7: valor negativo.')).toBeInTheDocument()
    expect(within(dialogo).getByRole('button', { name: 'Ver prévia' })).toBeInTheDocument()
  })
})
