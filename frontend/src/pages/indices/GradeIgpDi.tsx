import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { chaves } from '../../api/chaves'
import { excluirIgpDi, gravarIgpDi, listarIgpDi, URL_TEMPLATE_IGP_DI, urlExportarIgpDi } from '../../api/indices'
import { aposIndices } from '../../api/invalidar'
import { BotaoBaixar } from '../../components/BotaoBaixar'
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
  const indices = useQuery({ queryKey: chaves.todosIgpDi, queryFn: listarIgpDi })
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
        <BotaoBaixar caminho={URL_TEMPLATE_IGP_DI} nomeArquivo="igp_di_template.xlsx">Baixar template</BotaoBaixar>
        <BotaoBaixar caminho={urlExportarIgpDi('xlsx')} nomeArquivo="igp_di.xlsx">Exportar .xlsx</BotaoBaixar>
        <BotaoBaixar caminho={urlExportarIgpDi('csv')} nomeArquivo="igp_di.csv">Exportar .csv</BotaoBaixar>
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
