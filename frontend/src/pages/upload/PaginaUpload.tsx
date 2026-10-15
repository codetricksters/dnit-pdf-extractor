import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { aposUpload } from '../../api/invalidar'
import { acompanharJob, enviarPdfs, tentarDeNovo, useLotesAtivos } from '../../api/jobs'
import type { StatusJob } from '../../api/tipos'
import { Cabecalho } from '../../components/Cabecalho'
import { ConfirmarDialogo } from '../../components/ConfirmarDialogo'
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
  const [atualizar, setAtualizar] = useState(false)
  const [limparRegioes, setLimparRegioes] = useState(false)
  const [confirmando, setConfirmando] = useState(false)

  // Um lote enviado em outra aba (ou antes de recarregar a página) continua aqui.
  const ativos = useLotesAtivos()
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
    mutationFn: () => enviarPdfs(arquivos, { atualizar, limparRegioes }),
    onSuccess: ({ job_id }) => {
      setConfirmando(false)
      setStatus(null)
      setArquivos([])
      setJobId(job_id)
      void qc.invalidateQueries({ queryKey: ['jobs'] })
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
        subtitulo="Cada PDF grava o contrato e os itens da medição; reenviar o mesmo arquivo não duplica nem desfaz as correções, a menos que se peça para atualizar."
      />
      <AreaArquivos arquivos={arquivos} aoEscolher={setArquivos} desabilitado={enviar.isPending} />
      <div className="barra mt-md">
        <label className="field-label">
          <input
            type="checkbox"
            checked={atualizar}
            onChange={(e) => {
              setAtualizar(e.target.checked)
              if (!e.target.checked) setLimparRegioes(false)
            }}
          />{' '}
          Atualizar registros já importados
        </label>
        <label className="field-label">
          <input
            type="checkbox"
            checked={limparRegioes}
            disabled={!atualizar}
            onChange={(e) => setLimparRegioes(e.target.checked)}
          />{' '}
          Remover também as regiões fixadas
        </label>
      </div>
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
          onClick={() => (atualizar ? setConfirmando(true) : enviar.mutate())}
        >
          <Icone nome="play_arrow" />
          <span>Enviar para processamento</span>
        </button>
      </div>
      {confirmando && (
        <ConfirmarDialogo
          titulo="Atualizar registros já importados"
          mensagem={`Os registros destes arquivos que já estão no banco serão regravados com os valores do PDF. Correções e exclusões feitas à mão serão perdidas${limparRegioes ? ', e as regiões fixadas também' : '; as regiões fixadas são mantidas'}. Registros incluídos manualmente não são afetados.`}
          rotuloConfirmar="Atualizar registros"
          perigoso
          pendente={enviar.isPending}
          erro={enviar.error}
          aoConfirmar={() => enviar.mutate()}
          aoCancelar={() => setConfirmando(false)}
        />
      )}
      <MensagemErro erro={confirmando ? null : (enviar.error ?? repetir.error)} />
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
