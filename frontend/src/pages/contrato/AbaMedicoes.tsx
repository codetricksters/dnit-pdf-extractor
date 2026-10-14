import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState, type FormEvent } from 'react'
import { Link, useOutletContext } from 'react-router'
import { chaves, type FiltrosMedicoes } from '../../api/chaves'
import { excluirMedicao, listarMedicoes } from '../../api/contratos'
import { aposMedicao } from '../../api/invalidar'
import type { Contrato, ItemMedicao } from '../../api/tipos'
import { Carregando } from '../../components/Carregando'
import { ConfirmarDialogo } from '../../components/ConfirmarDialogo'
import { Icone } from '../../components/Icone'
import { MensagemErro } from '../../components/MensagemErro'
import { SeletorMes } from '../../components/SeletorMes'
import { dinheiro, fator, mesAno, negativo } from '../../lib/formato'
import { DialogoMedicao } from './DialogoMedicao'

type Situacao = '' | 'true' | 'false'

// Os itens como o PDF os trouxe, editáveis um a um. Um código sem produto não é pendência: fica
// fora do cálculo, e o atalho leva ao catálogo para associá-lo se for material.
export function AbaMedicoes() {
  const contrato = useOutletContext<Contrato>()
  const [mes, setMes] = useState<string | null>('')
  const [situacao, setSituacao] = useState<Situacao>('')
  const [q, setQ] = useState('')
  const [filtros, setFiltros] = useState<FiltrosMedicoes>({})
  const [editando, setEditando] = useState<ItemMedicao | 'novo' | null>(null)
  const [excluindo, setExcluindo] = useState<ItemMedicao | null>(null)
  const qc = useQueryClient()
  const excluir = useMutation({
    mutationFn: (itemId: number) => excluirMedicao(contrato.id, itemId),
    onSuccess: async () => {
      setExcluindo(null)
      await aposMedicao(qc, contrato.id)
    },
  })

  const itens = useQuery({
    queryKey: chaves.medicoes(contrato.id, filtros),
    queryFn: () => listarMedicoes(contrato.id, filtros),
    placeholderData: keepPreviousData,
  })

  // Os meses que o contrato tem: vêm da consulta sem filtros, que a tela já faz.
  const todos = useQuery({ queryKey: chaves.medicoes(contrato.id, {}), queryFn: () => listarMedicoes(contrato.id, {}) })
  const meses = useMemo(
    () => [...new Set((todos.data ?? []).map((i) => i.mes.slice(0, 7)))].sort().reverse(),
    [todos.data],
  )

  function filtrar(e: FormEvent) {
    e.preventDefault()
    if (mes === null) return
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
          <SeletorMes id="filtro-mes" opcoes={meses} aoMudar={setMes} />
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
        <button type="button" className="btn btn-primary" onClick={() => setEditando('novo')}>
          <Icone nome="add" /> Incluir registro
        </button>
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
                  <th>Origem</th>
                  <th>Região</th>
                  <th>Arquivo</th>
                  <th>Ações</th>
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
                    <td>{item.origem !== 'pdf' && <span className="badge">{item.origem}</span>}</td>
                    <td>
                      {item.regiao_cap && <span className="badge badge-regiao">CAP: {item.regiao_cap} *</span>}{' '}
                      {item.regiao_emulsoes && <span className="badge badge-regiao">Emulsões: {item.regiao_emulsoes} *</span>}
                    </td>
                    <td>{item.arquivo}</td>
                    <td>
                      <button type="button" className="btn btn-sm" onClick={() => setEditando(item)}>
                        <Icone nome="edit" /> Editar
                      </button>{' '}
                      <button type="button" className="btn btn-sm" onClick={() => setExcluindo(item)}>
                        <Icone nome="delete" /> Excluir
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {editando && (
        <DialogoMedicao
          contratoId={contrato.id}
          item={editando === 'novo' ? undefined : editando}
          aoFechar={() => setEditando(null)}
        />
      )}
      {excluindo && (
        <ConfirmarDialogo
          titulo="Excluir registro"
          mensagem={`Excluir o registro ${excluindo.codigo} de ${mesAno(excluindo.mes)}? Ele sai do cálculo e não volta ao reprocessar o PDF.`}
          rotuloConfirmar="Excluir registro"
          perigoso
          pendente={excluir.isPending}
          erro={excluir.error}
          aoConfirmar={() => excluir.mutate(excluindo.id)}
          aoCancelar={() => setExcluindo(null)}
        />
      )}
    </>
  )
}
