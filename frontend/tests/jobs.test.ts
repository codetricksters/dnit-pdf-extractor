import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { acompanharJob } from '../src/api/jobs'
import type { StatusJob } from '../src/api/tipos'
import { servidor } from './servidor'

const status = (completed: boolean): StatusJob => ({
  job_id: 'j1',
  completed,
  files: { 'a.pdf': { status: completed ? 'completed' : 'processing', error: null, contrato_id: null, itens: null } },
})

class EventSourceFalso {
  static ultima: EventSourceFalso
  onmessage: ((e: MessageEvent) => void) | null = null
  onerror: (() => void) | null = null
  ouvintes: Record<string, () => void> = {}
  fechada = false
  constructor(public url: string) {
    EventSourceFalso.ultima = this
  }
  addEventListener(nome: string, f: () => void) {
    this.ouvintes[nome] = f
  }
  close() {
    this.fechada = true
  }
}

afterEach(() => vi.unstubAllGlobals())

describe('acompanharJob', () => {
  it('com EventSource, repassa cada status e termina no evento complete', () => {
    vi.stubGlobal('EventSource', EventSourceFalso)
    const aoAtualizar = vi.fn()
    const aoTerminar = vi.fn()
    acompanharJob('j1', { aoAtualizar, aoTerminar })
    const es = EventSourceFalso.ultima
    expect(es.url).toBe('/jobs/j1/events')

    es.onmessage!(new MessageEvent('message', { data: JSON.stringify(status(false)) }))
    expect(aoAtualizar).toHaveBeenCalledWith(status(false))
    es.ouvintes.complete()
    expect(aoTerminar).toHaveBeenCalled()
    expect(es.fechada).toBe(true)
  })

  it('se o SSE cair, passa a consultar o status até concluir', async () => {
    vi.stubGlobal('EventSource', EventSourceFalso)
    let chamadas = 0
    servidor.use(http.get('/jobs/j1/status', () => HttpResponse.json(status(++chamadas >= 2))))
    const aoTerminar = vi.fn()
    const aoAtualizar = vi.fn()
    acompanharJob('j1', { aoAtualizar, aoTerminar }, 5)
    EventSourceFalso.ultima.onerror!()
    expect(EventSourceFalso.ultima.fechada).toBe(true)
    await vi.waitFor(() => expect(aoTerminar).toHaveBeenCalled())
    expect(aoAtualizar).toHaveBeenLastCalledWith(status(true))
  })

  it('sem EventSource, consulta o status; cancelar interrompe', async () => {
    vi.stubGlobal('EventSource', undefined)
    const pedidos = vi.fn()
    servidor.use(
      http.get('/jobs/j1/status', () => {
        pedidos()
        return HttpResponse.json(status(false))
      }),
    )
    const cancelar = acompanharJob('j1', { aoAtualizar: vi.fn(), aoTerminar: vi.fn() }, 5)
    // Concede o intervalo real de "polling" (5ms) mas evita contar uma quantidade exata
    // de chamadas: vi.waitFor confere a cada 50ms, tempo em que várias voltas de 5ms já
    // ocorreram, então "exatamente 2" é uma corrida perdida por definição.
    await vi.waitFor(() => expect(pedidos.mock.calls.length).toBeGreaterThanOrEqual(1))
    cancelar()
    const feitos = pedidos.mock.calls.length
    await new Promise((r) => setTimeout(r, 30))
    expect(pedidos.mock.calls.length).toBeLessThanOrEqual(feitos + 1)
  })
})
