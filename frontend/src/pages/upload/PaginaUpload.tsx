import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { chaves } from '../../api/chaves'
import { aposUpload } from '../../api/invalidar'
import { acompanharJob, enviarPdfs, listarJobs, tentarDeNovo } from '../../api/jobs'
import type { StatusJob } from '../../api/tipos'
import { Cabecalho } from '../../components/Cabecalho'
import { Icone } from '../../components/Icone'
import { MensagemErro } from '../../components/MensagemErro'
import { AreaArquivos } from './AreaArquivos'
import { LotesAnteriores } from './LotesAnteriores'
import { TabelaLote } from './TabelaLote'

export function PaginaUpload() {
  const qc = useQueryClient()
  const [arquivos, setArquivos] = useState<File[]>([])
  const [jobId, setJobId] = useState<string | null>(null)
  const [status, setStatus] = useState<StatusJob | null>(null)
  // Muda a cada retentativa, para reabrir o acompanhamento de um lote já concluído.
  const [rodada, setRodada] = useState(0)

  // Um lote enviado em outra aba (ou antes de recarregar a página) continua aqui.
  const ativos = useQuery({ queryKey: chaves.jobs('active'), queryFn: () => listarJobs('active') })
  useEffect(() => {
    if (!jobId && ativos.data?.length) setJobId(ativos.data[0].job_id)
  }, [jobId, ativos.data])

  useEffect(() => {
    if (!jobId) return
    return acompanharJob(jobId, {
      aoAtualizar: setStatus,
      aoTerminar: () => {
        void aposUpload(qc)
        void qc.invalidateQueries({ queryKey: ['jobs'] })
      },
    })
  }, [jobId, rodada, qc])

  const enviar = useMutation({
    mutationFn: () => enviarPdfs(arquivos),
    onSuccess: ({ job_id }) => {
      setStatus(null)
      setArquivos([])
      setJobId(job_id)
    },
  })
  const repetir = useMutation({
    mutationFn: (arquivo: string) => tentarDeNovo(jobId!, arquivo),
    onSuccess: () => setRodada((r) => r + 1),
  })

  const processando = !!status && !status.completed
  return (
    <>
      <Cabecalho
        titulo="Upload de PDFs"
        subtitulo="Cada PDF grava o contrato e os itens da medição; reenviar o mesmo arquivo não duplica."
      />
      <AreaArquivos arquivos={arquivos} aoEscolher={setArquivos} desabilitado={enviar.isPending} />
      <div className="barra mt-md">
        <span className="contagem">O envio volta na hora; o andamento de cada arquivo aparece abaixo.</span>
        <span className="espaco" />
        {status?.completed && (
          <button
            type="button"
            className="btn"
            onClick={() => {
              setJobId(null)
              setStatus(null)
            }}
          >
            <Icone nome="restart_alt" />
            <span>Novo lote</span>
          </button>
        )}
        <button
          type="button"
          className="btn btn-primary"
          disabled={arquivos.length === 0 || enviar.isPending || processando}
          onClick={() => enviar.mutate()}
        >
          <Icone nome="play_arrow" />
          <span>Enviar para processamento</span>
        </button>
      </div>
      <MensagemErro erro={enviar.error ?? repetir.error} />
      {status && (
        <TabelaLote
          status={status}
          aoTentarDeNovo={(a) => repetir.mutate(a)}
          tentando={repetir.isPending ? (repetir.variables ?? null) : null}
        />
      )}
      <LotesAnteriores />
    </>
  )
}
