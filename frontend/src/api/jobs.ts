import { caminhoCom, pedir } from './client'
import type { ResumoJob, StatusJob } from './tipos'

const c = encodeURIComponent

export function enviarPdfs(arquivos: File[]) {
  const form = new FormData()
  for (const a of arquivos) form.append('files', a)
  return pedir<{ job_id: string }>('/upload', { metodo: 'POST', form })
}

export const buscarStatusJob = (id: string) => pedir<StatusJob>(`/jobs/${c(id)}/status`)

export const listarJobs = (status: 'active' | 'completed') => pedir<ResumoJob[]>('/jobs', { params: { status } })

export const tentarDeNovo = (id: string, arquivo: string) =>
  pedir<unknown>(`/jobs/${c(id)}/retry/${c(arquivo)}`, { metodo: 'POST' })

export const urlResultado = (id: string, arquivo: string) => caminhoCom(`/jobs/${c(id)}/download/${c(arquivo)}`)

export const urlZip = (id: string) => caminhoCom(`/jobs/${c(id)}/download`)

interface Ouvintes {
  aoAtualizar: (s: StatusJob) => void
  aoTerminar: () => void
}

// SSE quando o navegador tem EventSource e a conexão aguenta; se ela cair (proxy
// que corta streams, por exemplo), consulta /status até o lote concluir.
// Devolve a função que para de acompanhar.
export function acompanharJob(id: string, { aoAtualizar, aoTerminar }: Ouvintes, intervalo = 1500): () => void {
  let parado = false
  let temporizador: ReturnType<typeof setTimeout> | undefined
  let fonte: EventSource | undefined

  async function consultar() {
    if (parado) return
    try {
      const s = await buscarStatusJob(id)
      if (parado) return
      aoAtualizar(s)
      if (s.completed) {
        aoTerminar()
        return
      }
    } catch {
      // Falha passageira: a próxima volta tenta de novo.
    }
    temporizador = setTimeout(consultar, intervalo)
  }

  if (typeof EventSource === 'undefined') {
    void consultar()
  } else {
    fonte = new EventSource(`/jobs/${c(id)}/events`)
    fonte.onmessage = (e) => aoAtualizar(JSON.parse(e.data) as StatusJob)
    fonte.addEventListener('complete', () => {
      fonte?.close()
      aoTerminar()
    })
    fonte.onerror = () => {
      fonte?.close()
      fonte = undefined
      void consultar()
    }
  }

  return () => {
    parado = true
    fonte?.close()
    clearTimeout(temporizador)
  }
}
