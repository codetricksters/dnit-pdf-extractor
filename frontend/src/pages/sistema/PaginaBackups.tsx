import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { chaves } from '../../api/chaves'
import { enviarBackup, excluirBackup, gerarBackup, listarBackups, restaurarBackup, urlBackup } from '../../api/sistema'
import type { Backup } from '../../api/tipos'
import { Cabecalho } from '../../components/Cabecalho'
import { Carregando } from '../../components/Carregando'
import { ConfirmarDialogo } from '../../components/ConfirmarDialogo'
import { Icone } from '../../components/Icone'
import { MensagemErro } from '../../components/MensagemErro'
import { dataHora, tamanho } from '../../lib/formato'
import { EnviarArquivo } from './EnviarArquivo'

export function PaginaBackups() {
  const qc = useQueryClient()
  const [restaurando, setRestaurando] = useState<Backup | null>(null)
  const [excluindo, setExcluindo] = useState<Backup | null>(null)
  const backups = useQuery({ queryKey: chaves.backups, queryFn: listarBackups })
  const recarregar = () => qc.invalidateQueries({ queryKey: chaves.backups })

  const gerar = useMutation({ mutationFn: gerarBackup, onSuccess: recarregar })
  const enviar = useMutation({ mutationFn: enviarBackup, onSuccess: recarregar })
  const excluir = useMutation({
    mutationFn: (b: Backup) => excluirBackup(b.nome),
    onSuccess: async () => {
      setExcluindo(null)
      await recarregar()
    },
  })
  const restaurar = useMutation({
    mutationFn: (b: Backup) => restaurarBackup(b.nome, b.nome),
    onSuccess: async () => {
      setRestaurando(null)
      // O banco inteiro mudou: contratos, índices, catálogo, templates.
      await qc.invalidateQueries()
    },
  })

  return (
    <>
      <Cabecalho
        titulo="Backups"
        subtitulo="Um único arquivo guarda tudo: contratos, medições, catálogo, índices e templates."
        acoes={
          <button type="button" className="btn btn-primary" disabled={gerar.isPending} onClick={() => gerar.mutate()}>
            <Icone nome="backup" />
            <span>Gerar backup agora</span>
          </button>
        }
      />
      <MensagemErro erro={gerar.error} />
      {restaurar.data && (
        <div className="notice ok" role="status">
          <div>
            <p className="notice-title">Banco restaurado de {restaurar.data.restaurado}.</p>
            <p className="notice-text">O estado anterior foi guardado em {restaurar.data.seguranca}.</p>
          </div>
        </div>
      )}

      <section className="panel mt-md">
        <div className="panel-body">
          <EnviarArquivo
            rotulo="Enviar backup (.dump)"
            accept=".dump"
            botao="Enviar backup"
            pendente={enviar.isPending}
            aoEnviar={(a) => enviar.mutateAsync(a)}
          />
          <MensagemErro erro={enviar.error} />
        </div>
      </section>

      {backups.isPending && <Carregando />}
      <MensagemErro erro={backups.error} />
      {backups.data && backups.data.length === 0 && <p className="contagem mt-md">Nenhum backup ainda.</p>}
      {backups.data && backups.data.length > 0 && (
        <section className="panel mt-md">
          <div className="panel-body flush table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Arquivo</th>
                  <th>Gerado em</th>
                  <th className="num">Tamanho</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {backups.data.map((b) => (
                  <tr key={b.nome}>
                    <td className="num">{b.nome}</td>
                    <td>{dataHora(b.criado_em)}</td>
                    <td className="num">{tamanho(b.tamanho)}</td>
                    <td>
                      <a className="btn btn-sm" href={urlBackup(b.nome)} download>Baixar</a>{' '}
                      <button type="button" className="btn btn-sm" onClick={() => setRestaurando(b)}>Restaurar</button>{' '}
                      <button type="button" className="btn btn-sm" onClick={() => setExcluindo(b)}>Excluir</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {restaurando && (
        <ConfirmarDialogo
          titulo="Restaurar este backup?"
          mensagem={`Todo o banco volta ao estado de ${dataHora(restaurando.criado_em)}. O que foi gravado depois disso se perde; antes de restaurar, o estado atual é guardado num backup de segurança.`}
          rotuloConfirmar="Restaurar"
          textoExigido={restaurando.nome}
          perigoso
          pendente={restaurar.isPending}
          erro={restaurar.error}
          aoCancelar={() => setRestaurando(null)}
          aoConfirmar={() => restaurar.mutate(restaurando)}
        />
      )}
      {excluindo && (
        <ConfirmarDialogo
          titulo={`Excluir ${excluindo.nome}?`}
          mensagem="O arquivo do backup é apagado do servidor."
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
