import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { caminhoCom, ErroConexao, pedir } from '../src/api/client'
import { useOffline } from '../src/api/conexao'
import { ErroApi } from '../src/api/erros'
import { renderHook } from '@testing-library/react'
import { servidor } from './servidor'

describe('pedir', () => {
  it('monta a query sem parâmetros vazios e devolve o JSON', async () => {
    let url = ''
    servidor.use(
      http.get('/api/v1/contratos/1/calculo', ({ request }) => {
        url = request.url
        return HttpResponse.json({ ok: true })
      }),
    )
    const corpo = await pedir<{ ok: boolean }>('/api/v1/contratos/1/calculo', {
      params: { regiao_cap: 'Sul', regiao_emulsoes: undefined, vazio: '' },
    })
    expect(corpo).toEqual({ ok: true })
    expect(new URL(url).search).toBe('?regiao_cap=Sul')
  })

  it('envia JSON e trata 204', async () => {
    let recebido: unknown
    servidor.use(
      http.patch('/api/v1/contratos/1', async ({ request }) => {
        recebido = await request.json()
        return new HttpResponse(null, { status: 204 })
      }),
    )
    expect(await pedir('/api/v1/contratos/1', { metodo: 'PATCH', json: { edital: 'X' } })).toBeUndefined()
    expect(recebido).toEqual({ edital: 'X' })
  })

  it('4xx vira ErroApi', async () => {
    servidor.use(http.get('/api/v1/x', () => HttpResponse.json({ detail: 'Contrato 9 não encontrado.' }, { status: 404 })))
    await expect(pedir('/api/v1/x')).rejects.toMatchObject({ status: 404, detail: 'Contrato 9 não encontrado.' })
    await expect(pedir('/api/v1/x')).rejects.toBeInstanceOf(ErroApi)
  })

  it('falha de rede e 502 marcam offline; resposta boa volta a online', async () => {
    const { result, rerender } = renderHook(() => useOffline())
    servidor.use(http.get('/api/v1/rede', () => HttpResponse.error()))
    await expect(pedir('/api/v1/rede')).rejects.toBeInstanceOf(ErroConexao)
    rerender()
    expect(result.current).toBe(true)

    servidor.use(http.get('/api/v1/ok', () => HttpResponse.json([])))
    await pedir('/api/v1/ok')
    rerender()
    expect(result.current).toBe(false)

    servidor.use(http.get('/api/v1/gateway', () => new HttpResponse('Bad Gateway', { status: 502 })))
    await expect(pedir('/api/v1/gateway')).rejects.toBeInstanceOf(ErroConexao)
    rerender()
    expect(result.current).toBe(true)
  })

  it('caminhoCom devolve caminho relativo para links de download', () => {
    expect(caminhoCom('/api/v1/contratos/1/planilha', { regiao_cap: 'Centro-Oeste', regiao_emulsoes: null }))
      .toBe('/api/v1/contratos/1/planilha?regiao_cap=Centro-Oeste')
  })
})
