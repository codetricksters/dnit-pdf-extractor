import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { chaves } from '../../api/chaves'
import { ativarTemplate, enviarTemplate, excluirTemplate, listarTemplates, urlTemplate } from '../../api/sistema'
import type { Template } from '../../api/tipos'
import { Cabecalho } from '../../components/Cabecalho'
import { Carregando } from '../../components/Carregando'
import { ConfirmarDialogo } from '../../components/ConfirmarDialogo'
import { MensagemErro } from '../../components/MensagemErro'
import { dataHora, tamanho } from '../../lib/formato'
import { EnviarArquivo } from './EnviarArquivo'

export function PaginaTemplates() {
  const qc = useQueryClient()
  const [observacao, setObservacao] = useState('')
  const [ativar, setAtivar] = useState(true)
  const [excluindo, setExcluindo] = useState<Template | null>(null)
  const templates = useQuery({ queryKey: chaves.templates, queryFn: listarTemplates })
  const recarregar = () => qc.invalidateQueries({ queryKey: chaves.templates })

  const enviar = useMutation({
    mutationFn: (arquivo: File) => enviarTemplate(arquivo, { observacao: observacao.trim() || undefined, ativar }),
    onSuccess: async () => {
      setObservacao('')
      await recarregar()
    },
  })
  const ativarUm = useMutation({ mutationFn: ativarTemplate, onSuccess: recarregar })
  const excluir = useMutation({
    mutationFn: (t: Template) => excluirTemplate(t.id),
    onSuccess: async () => {
      setExcluindo(null)
      await recarregar()
    },
  })

  return (
    <>
      <Cabecalho
        titulo="Templates"
        subtitulo="A planilha de reequilíbrio sai do template ativo. Um envio é validado antes de ser aceito."
      />
      <section className="panel">
        <div className="panel-body">
          <EnviarArquivo
            rotulo="Novo template (.xlsx)"
            accept=".xlsx"
            botao="Enviar template"
            pendente={enviar.isPending}
            aoEnviar={(a) => enviar.mutateAsync(a)}
          >
            <div className="field">
              <label className="field-label" htmlFor="template-observacao">Observação</label>
              <input id="template-observacao" className="input" value={observacao} onChange={(e) => setObservacao(e.target.value)} />
            </div>
            <label className="field-label">
              <input type="checkbox" checked={ativar} onChange={(e) => setAtivar(e.target.checked)} /> Ativar ao enviar
            </label>
          </EnviarArquivo>
          <MensagemErro erro={enviar.error ?? ativarUm.error} />
        </div>
      </section>

      {templates.isPending && <Carregando />}
      <MensagemErro erro={templates.error} />
      {templates.data && (
        <section className="panel mt-md">
          <div className="panel-body flush table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Arquivo</th>
                  <th>Observação</th>
                  <th>Enviado em</th>
                  <th className="num">Tamanho</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {templates.data.map((t) => (
                  <tr key={t.id}>
                    <td>
                      {t.nome} {t.ativo && <span className="badge badge-ok">Ativo</span>}
                    </td>
                    <td>{t.observacao ?? '—'}</td>
                    <td>{dataHora(t.criado_em)}</td>
                    <td className="num">{tamanho(t.tamanho)}</td>
                    <td>
                      <a className="btn btn-sm" href={urlTemplate(t.id)} download>Baixar</a>{' '}
                      {!t.ativo && (
                        <>
                          <button type="button" className="btn btn-sm" disabled={ativarUm.isPending} onClick={() => ativarUm.mutate(t.id)}>
                            Ativar
                          </button>{' '}
                          <button type="button" className="btn btn-sm" onClick={() => setExcluindo(t)}>Excluir</button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {excluindo && (
        <ConfirmarDialogo
          titulo={`Excluir ${excluindo.nome}?`}
          mensagem="O template sai do histórico e do próximo backup. O ativo não muda."
          rotuloConfirmar="Excluir"
          perigoso
          pendente={excluir.isPending}
          erro={excluir.error}
          aoCancelar={() => setExcluindo(null)}
          aoConfirmar={() => excluir.mutate(excluindo)}
        />
      )}
    </>
  )
}
