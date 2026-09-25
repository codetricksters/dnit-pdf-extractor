import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useOutletContext } from 'react-router'
import { chaves, type FiltrosMedicoes } from '../../api/chaves'
import { listarMedicoes } from '../../api/contratos'
import type { Contrato } from '../../api/tipos'
import { Carregando } from '../../components/Carregando'
import { MensagemErro } from '../../components/MensagemErro'
import { dinheiro, fator, mesAno, negativo } from '../../lib/formato'

type Situacao = '' | 'true' | 'false'

// Os itens como o PDF os trouxe. Um código sem produto não é pendência: fica
// fora do cálculo, e o atalho leva ao catálogo para associá-lo se for material.
export function AbaMedicoes() {
  const contrato = useOutletContext<Contrato>()
  const [mes, setMes] = useState('')
  const [situacao, setSituacao] = useState<Situacao>('')
  const [q, setQ] = useState('')
  const [filtros, setFiltros] = useState<FiltrosMedicoes>({})

  const itens = useQuery({
    queryKey: chaves.medicoes(contrato.id, filtros),
    queryFn: () => listarMedicoes(contrato.id, filtros),
    placeholderData: keepPreviousData,
  })

  function filtrar(e: FormEvent) {
    e.preventDefault()
    setFiltros({
      mes: mes || undefined,
      noCalculo: situacao === '' ? undefined : situacao === 'true',
      q: q.trim() || undefined,
    })
  }

  return (
    <>
      <form className="barra" onSubmit={filtrar}>
        <div className="field">
          <label className="field-label" htmlFor="filtro-mes">Mês</label>
          <input id="filtro-mes" type="month" className="input" value={mes} onChange={(e) => setMes(e.target.value)} />
        </div>
        <div className="field">
          <label className="field-label" htmlFor="filtro-situacao">Situação</label>
          <select
            id="filtro-situacao"
            className="input"
            value={situacao}
            onChange={(e) => setSituacao(e.target.value as Situacao)}
          >
            <option value="">Todos</option>
            <option value="true">Só no cálculo</option>
            <option value="false">Fora do cálculo</option>
          </select>
        </div>
        <div className="field">
          <label className="field-label" htmlFor="filtro-q">Código ou descrição</label>
          <input id="filtro-q" className="input" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <button type="submit" className="btn">Filtrar</button>
        <span className="espaco" />
        {itens.data && <span className="contagem">{itens.data.length} {itens.data.length === 1 ? 'item' : 'itens'}</span>}
      </form>

      <MensagemErro erro={itens.error} />
      {itens.isPending && <Carregando />}

      {itens.data && itens.data.length === 0 && <p className="contagem mt-md">Nenhum item com esses filtros.</p>}
      {itens.data && itens.data.length > 0 && (
        <section className="panel mt-md">
          <div className="panel-body flush table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Mês</th>
                  <th>Código</th>
                  <th>Descrição no PDF</th>
                  <th className="num">Valor PI líquido</th>
                  <th className="num">Fator</th>
                  <th className="num">Reajuste líquido</th>
                  <th>Produto</th>
                  <th>Arquivo</th>
                </tr>
              </thead>
              <tbody>
                {itens.data.map((item) => (
                  <tr key={item.id}>
                    <td>{mesAno(item.mes)}</td>
                    <td className="num">{item.codigo}</td>
                    <td>{item.descricao_pdf ?? '—'}</td>
                    <td className={negativo(item.valor_pi) ? 'num neg' : 'num'}>{dinheiro(item.valor_pi)}</td>
                    <td className="num">{fator(item.fator)}</td>
                    <td className={negativo(item.reajuste) ? 'num neg' : 'num'}>{dinheiro(item.reajuste)}</td>
                    <td>
                      {item.produto ?? (
                        <>
                          <span className="badge">Fora do cálculo</span>{' '}
                          <Link className="btn btn-sm" to={`/catalogo?q=${encodeURIComponent(item.codigo)}`}>
                            Associar
                          </Link>
                        </>
                      )}
                    </td>
                    <td>{item.arquivo}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  )
}
