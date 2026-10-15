import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState, type FormEvent } from 'react'
import { Link, useOutletContext } from 'react-router'
import { chaves, type FiltrosMedicoes } from '../../api/chaves'
import { excluirMedicao, excluirMedicoes, listarMedicoes } from '../../api/contratos'
import { aposMedicao } from '../../api/invalidar'
import type { Contrato, ItemMedicao } from '../../api/tipos'
import { Carregando } from '../../components/Carregando'
import { ConfirmarDialogo } from '../../components/ConfirmarDialogo'
import { Icone } from '../../components/Icone'
import { MensagemErro } from '../../components/MensagemErro'
import { SeletorMes } from '../../components/SeletorMes'
import { dinheiro, fator, mesAno, negativo } from '../../lib/formato'
import { DialogoMedicao } from './DialogoMedicao'
import { DialogoRegiaoLote } from './DialogoRegiaoLote'

type Situacao = '' | 'true' | 'false'

// O source_file dos registros incluídos à mão.
const MANUAL = 'manual'

// Os itens como o PDF os trouxe, editáveis um a um. Um código sem produto não é pendência: fica
// fora do cálculo, e o atalho leva ao catálogo para associá-lo se for material.
export function AbaMedicoes() {
  const contrato = useOutletContext<Contrato>()
  const [mes, setMes] = useState<string | null>('')
  const [situacao, setSituacao] = useState<Situacao>('')
  const [q, setQ] = useState('')
  const [arquivo, setArquivo] = useState('')
  const [filtros, setFiltros] = useState<FiltrosMedicoes>({})
  const [editando, setEditando] = useState<ItemMedicao | 'novo' | null>(null)
  const [excluindo, setExcluindo] = useState<ItemMedicao | null>(null)
  const [regiaoLote, setRegiaoLote] = useState(false)
  const [aviso, setAviso] = useState<string | null>(null)
  const [marcados, setMarcados] = useState<number[]>([])
  const [excluindoVarios, setExcluindoVarios] = useState(false)
  const qc = useQueryClient()
  const excluir = useMutation({
    mutationFn: (itemId: number) => excluirMedicao(contrato.id, itemId),
    onSuccess: async () => {
      setExcluindo(null)
      await aposMedicao(qc, contrato.id)
    },
  })
  const excluirVarios = useMutation({
    mutationFn: (ids: number[]) => excluirMedicoes(contrato.id, ids),
    onSuccess: async () => {
      setExcluindoVarios(false)
      setMarcados([])
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
  const arquivos = useMemo(
    () => [...new Set((todos.data ?? []).map((i) => i.arquivo))].filter((a) => a !== MANUAL).sort(),
    [todos.data],
  )
  const temManuais = (todos.data ?? []).some((i) => i.arquivo === MANUAL)

  // Só conta o que está na tela: um registro marcado que saiu do filtro não é excluído.
  const visiveis = itens.data ?? []
  const selecionados = visiveis.filter((i) => marcados.includes(i.id)).map((i) => i.id)
  const todosMarcados = visiveis.length > 0 && selecionados.length === visiveis.length
  function alternar(id: number) {
    setMarcados((m) => (m.includes(id) ? m.filter((x) => x !== id) : [...m, id]))
  }

  function filtrar(e: FormEvent) {
    e.preventDefault()
    if (mes === null) return
    setFiltros({
      mes: mes || undefined,
      noCalculo: situacao === '' ? undefined : situacao === 'true',
      q: q.trim() || undefined,
      arquivo: arquivo || undefined,
    })
    setMarcados([])
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
        <div className="field">
          <label className="field-label" htmlFor="filtro-arquivo">Arquivo</label>
          <select id="filtro-arquivo" className="input" value={arquivo} onChange={(e) => setArquivo(e.target.value)}>
            <option value="">Todos</option>
            {temManuais && <option value={MANUAL}>Incluídos manualmente</option>}
            {arquivos.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
        <button type="submit" className="btn">Filtrar</button>
        <button type="button" className="btn btn-primary" onClick={() => setEditando('novo')}>
          <Icone nome="add" /> Incluir registro
        </button>
        <button type="button" className="btn" onClick={() => setRegiaoLote(true)} disabled={meses.length === 0}>
          <Icone nome="map" /> Aplicar região
        </button>
        <button
          type="button"
          className="btn"
          disabled={selecionados.length === 0}
          onClick={() => setExcluindoVarios(true)}
        >
          <Icone nome="delete" /> Excluir selecionados ({selecionados.length})
        </button>
        <span className="espaco" />
        {itens.data && <span className="contagem">{itens.data.length} {itens.data.length === 1 ? 'item' : 'itens'}</span>}
      </form>

      {aviso && <p className="contagem mt-md" role="status">{aviso}</p>}
      <MensagemErro erro={itens.error} />
      {itens.isPending && <Carregando />}

      {itens.data && itens.data.length === 0 && <p className="contagem mt-md">Nenhum item com esses filtros.</p>}
      {itens.data && itens.data.length > 0 && (
        <section className="panel mt-md">
          <div className="panel-body flush table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      aria-label="Selecionar todos"
                      checked={todosMarcados}
                      onChange={() => setMarcados(todosMarcados ? [] : visiveis.map((i) => i.id))}
                    />
                  </th>
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
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`Selecionar ${item.codigo} de ${mesAno(item.mes)}`}
                        checked={marcados.includes(item.id)}
                        onChange={() => alternar(item.id)}
                      />
                    </td>
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
      {regiaoLote && (
        <DialogoRegiaoLote
          contratoId={contrato.id}
          meses={meses}
          aoAplicar={(n) => {
            setRegiaoLote(false)
            setAviso(`Região aplicada em ${n} ${n === 1 ? 'registro' : 'registros'}.`)
          }}
          aoFechar={() => setRegiaoLote(false)}
        />
      )}
      {excluindoVarios && (
        <ConfirmarDialogo
          titulo="Excluir registros"
          mensagem={`Excluir ${selecionados.length} ${selecionados.length === 1 ? 'registro' : 'registros'}? Eles saem do cálculo e não voltam ao reprocessar o PDF.`}
          rotuloConfirmar="Excluir registros"
          perigoso
          pendente={excluirVarios.isPending}
          erro={excluirVarios.error}
          aoConfirmar={() => excluirVarios.mutate(selecionados)}
          aoCancelar={() => setExcluindoVarios(false)}
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
