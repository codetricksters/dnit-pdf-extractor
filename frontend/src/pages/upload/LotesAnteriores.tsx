import { useQuery } from '@tanstack/react-query'
import { chaves } from '../../api/chaves'
import { listarJobs, urlZip } from '../../api/jobs'
import { BotaoBaixar } from '../../components/BotaoBaixar'
import { dataHora } from '../../lib/formato'

export function LotesAnteriores() {
  const lotes = useQuery({ queryKey: chaves.jobs('completed'), queryFn: () => listarJobs('completed') })
  if (!lotes.data?.length) return null
  return (
    <details className="lotes mt-md">
      <summary>Lotes anteriores ({lotes.data.length})</summary>
      <div className="table-scroll mt-md">
        <table className="data-table">
          <thead>
            <tr>
              <th>Enviado em</th>
              <th className="num">Concluídos</th>
              <th className="num">Falhas</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {lotes.data.map((l) => (
              <tr key={l.job_id}>
                <td>{dataHora(l.created_at)}</td>
                <td className="num">{l.completed_count} de {l.file_count}</td>
                <td className={l.failed_count > 0 ? 'num neg' : 'num'}>{l.failed_count}</td>
                <td>
                  {l.completed_count > 0 && (
                    <BotaoBaixar caminho={urlZip(l.job_id)} nomeArquivo={`${l.job_id}.zip`} className="btn btn-sm">
                      Baixar .zip
                    </BotaoBaixar>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
