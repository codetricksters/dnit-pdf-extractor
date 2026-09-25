import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { chaves } from '../../api/chaves'
import { listarContratos } from '../../api/contratos'
import { urlResultado, urlZip } from '../../api/jobs'
import type { StatusArquivo, StatusJob } from '../../api/tipos'
import { Icone } from '../../components/Icone'

const ROTULO: Record<StatusArquivo, string> = {
  pending: 'Pendente',
  processing: 'Processando',
  completed: 'Concluído',
  failed: 'Falhou',
}

interface Props {
  status: StatusJob
  aoTentarDeNovo: (arquivo: string) => void
  tentando: string | null
}

export function TabelaLote({ status, aoTentarDeNovo, tentando }: Props) {
  const contratos = useQuery({ queryKey: chaves.contratos, queryFn: listarContratos })
  const numero = (id: number) => contratos.data?.find((c) => c.id === id)?.numero ?? `contrato ${id}`
  const arquivos = Object.entries(status.files)
  const concluidos = arquivos.filter(([, a]) => a.status === 'completed').length

  return (
    <section className="panel mt-md">
      <div className="panel-head">
        <h2 className="panel-title">Arquivos no lote</h2>
        <span className="badge badge-mono">
          {concluidos} de {arquivos.length} concluídos
        </span>
      </div>
      <div className="panel-body flush table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Arquivo</th>
              <th>Status</th>
              <th>Resultado</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {arquivos.map(([nome, a]) => (
              <tr key={nome}>
                <td className="file-row-name">{nome}</td>
                <td>
                  <span className={`badge badge-${a.status}`}>{ROTULO[a.status]}</span>
                </td>
                <td>
                  {a.status === 'completed' && a.contrato_id !== null && (
                    <>
                      {a.itens} {a.itens === 1 ? 'item' : 'itens'} →{' '}
                      <Link to={`/contratos/${a.contrato_id}`}>{numero(a.contrato_id)}</Link>
                    </>
                  )}
                  {a.status === 'failed' && <span className="erro-campo">{a.error}</span>}
                </td>
                <td>
                  {a.status === 'completed' && (
                    <a className="btn btn-sm" href={urlResultado(status.job_id, nome)} download>JSON</a>
                  )}
                  {a.status === 'failed' && (
                    <button
                      type="button"
                      className="btn btn-sm"
                      disabled={tentando === nome}
                      onClick={() => aoTentarDeNovo(nome)}
                    >
                      Tentar de novo
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {status.completed && concluidos > 0 && (
        <div className="barra panel-body">
          <span className="espaco" />
          <a className="btn" href={urlZip(status.job_id)} download>
            <Icone nome="folder_zip" />
            <span>Baixar todos os resultados (.zip)</span>
          </a>
        </div>
      )}
    </section>
  )
}
