import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { chaves } from '../../api/chaves'
import { excluirIgpDi, gravarIgpDi, listarIgpDi, URL_TEMPLATE_IGP_DI, urlExportarIgpDi } from '../../api/indices'
import { aposIndices } from '../../api/invalidar'
import { CelulaEditavel } from '../../components/CelulaEditavel'
import { Carregando } from '../../components/Carregando'
import { Icone } from '../../components/Icone'
import { MensagemErro } from '../../components/MensagemErro'
import { dataHora, exato, mesAno } from '../../lib/formato'
import { FaixaCobertura } from './FaixaCobertura'
import { montarGradeIgpDi } from './grade'
import { ImportarIndices } from './ImportarIndices'

const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']

export function GradeIgpDi() {
  const qc = useQueryClient()
  const indices = useQuery({ queryKey: chaves.igpDi(), queryFn: listarIgpDi })
  const grade = useMemo(() => montarGradeIgpDi(indices.data ?? [], new Date().getFullYear()), [indices.data])
  const [importando, setImportando] = useState(false)

  async function depois<T>(acao: Promise<T>) {
    await acao
    await aposIndices(qc)
  }

  return (
    <>
      <FaixaCobertura serie="igp_di" />
      <div className="barra mt-md">
        <span className="espaco" />
        <a className="btn" href={URL_TEMPLATE_IGP_DI} download>Baixar template</a>
        <a className="btn" href={urlExportarIgpDi('xlsx')} download>Exportar .xlsx</a>
        <a className="btn" href={urlExportarIgpDi('csv')} download>Exportar .csv</a>
        <button type="button" className="btn btn-primary" onClick={() => setImportando(true)}>
          <Icone nome="upload_file" />
          <span>Importar</span>
        </button>
      </div>

      <MensagemErro erro={indices.error} />
      {indices.isPending && <Carregando />}
      {indices.data && (
        <section className="panel mt-md">
          <div className="panel-body flush table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Ano</th>
                  {MESES.map((m) => (
                    <th key={m} className="num">{m}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {grade.anos.map((ano) => (
                  <tr key={ano}>
                    <td className="num">{ano}</td>
                    {MESES.map((_, i) => {
                      const mes = `${ano}-${String(i + 1).padStart(2, '0')}`
                      const indice = grade.valores.get(mes)
                      return (
                        <CelulaEditavel
                          key={mes}
                          rotulo={`IGP-DI ${mesAno(mes)}`}
                          valor={indice?.valor}
                          formatar={exato}
                          manual={indice?.origem === 'manual'}
                          titulo={indice ? `${indice.origem} · ${dataHora(indice.atualizado_em)}` : undefined}
                          aoSalvar={(valor) => depois(gravarIgpDi(mes, valor!))}
                          aoApagar={() => depois(excluirIgpDi(mes))}
                        />
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {importando && <ImportarIndices serie="igp-di" aoFechar={() => setImportando(false)} />}
    </>
  )
}
