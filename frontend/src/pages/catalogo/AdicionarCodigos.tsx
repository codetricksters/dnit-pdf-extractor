import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { associarCodigos, listarCodigos } from '../../api/catalogo'
import { chaves, type FiltrosCodigos } from '../../api/chaves'
import { aposCatalogo } from '../../api/invalidar'
import type { Codigo, Produto } from '../../api/tipos'
import { Carregando } from '../../components/Carregando'
import { Dialogo } from '../../components/Dialogo'
import { MensagemErro } from '../../components/MensagemErro'

type Filtro = 'todos' | 'sem' | 'associados'

const ASSOCIADO: Record<Filtro, boolean | undefined> = { todos: undefined, sem: false, associados: true }

interface Props {
  produtos: Produto[]
  produtoInicial: number
  buscaInicial: string
  aoFechar: () => void
}

function situacaoDoCodigo(codigo: Codigo, alvo: number): string {
  if (codigo.produto_id === alvo) return 'neste produto'
  if (codigo.produto_id === null) return 'sem produto'
  return `em ${codigo.descricao_export}`
}

// Busca entre os códigos já extraídos e associa vários de uma vez. Um código
// em outro produto pode ser marcado: o PUT o reaponta, como no backend.
export function AdicionarCodigos({ produtos, produtoInicial, buscaInicial, aoFechar }: Props) {
  const qc = useQueryClient()
  const [texto, setTexto] = useState(buscaInicial)
  const [filtro, setFiltro] = useState<Filtro>('todos')
  const [filtros, setFiltros] = useState<FiltrosCodigos>({ q: buscaInicial || undefined })
  const [alvo, setAlvo] = useState(produtoInicial)
  const [marcados, setMarcados] = useState<string[]>([])

  const codigos = useQuery({
    queryKey: chaves.codigos(filtros),
    queryFn: () => listarCodigos(filtros),
    placeholderData: keepPreviousData,
  })
  const associar = useMutation({
    mutationFn: () => associarCodigos(alvo, marcados),
    onSuccess: async () => {
      await aposCatalogo(qc)
      aoFechar()
    },
  })

  function buscar(e: FormEvent) {
    e.preventDefault()
    setFiltros({ q: texto.trim() || undefined, associado: ASSOCIADO[filtro] })
  }

  function alternar(codigo: string) {
    setMarcados((atual) => (atual.includes(codigo) ? atual.filter((c) => c !== codigo) : [...atual, codigo]))
  }

  return (
    <Dialogo
      titulo="Adicionar códigos"
      aoFechar={aoFechar}
      acoes={
        <>
          <button type="button" className="btn" onClick={aoFechar}>Cancelar</button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={marcados.length === 0 || associar.isPending}
            onClick={() => associar.mutate()}
          >
            Associar selecionados ({marcados.length})
          </button>
        </>
      }
    >
      <form className="barra" onSubmit={buscar}>
        <div className="field">
          <label className="field-label" htmlFor="busca-codigo">Buscar código ou descrição</label>
          <input id="busca-codigo" className="input" value={texto} onChange={(e) => setTexto(e.target.value)} />
        </div>
        <div className="field">
          <label className="field-label" htmlFor="filtro-associado">Mostrar</label>
          <select id="filtro-associado" className="input" value={filtro} onChange={(e) => setFiltro(e.target.value as Filtro)}>
            <option value="todos">Todos</option>
            <option value="sem">Sem produto</option>
            <option value="associados">Já associados</option>
          </select>
        </div>
        <button type="submit" className="btn">Buscar</button>
        <span className="espaco" />
        <div className="field">
          <label className="field-label" htmlFor="alvo-produto">Associar a</label>
          <select id="alvo-produto" className="input" value={alvo} onChange={(e) => setAlvo(Number(e.target.value))}>
            {produtos.map((p) => (
              <option key={p.id} value={p.id}>{p.descricao_export}</option>
            ))}
          </select>
        </div>
      </form>

      <MensagemErro erro={codigos.error ?? associar.error} />
      {codigos.isPending && <Carregando />}
      {codigos.data && codigos.data.length === 0 && <p className="contagem">Nenhum código encontrado.</p>}
      {codigos.data && codigos.data.length > 0 && (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th />
                <th>Código</th>
                <th>Descrição no PDF</th>
                <th className="num">Contratos</th>
                <th>Situação</th>
              </tr>
            </thead>
            <tbody>
              {codigos.data.map((c) => {
                const noAlvo = c.produto_id === alvo
                return (
                  <tr key={c.codigo}>
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`Selecionar ${c.codigo}`}
                        checked={marcados.includes(c.codigo)}
                        disabled={noAlvo}
                        onChange={() => alternar(c.codigo)}
                      />
                    </td>
                    <td className="num">{c.codigo}</td>
                    <td>{c.descricao_pdf ?? '—'}</td>
                    <td className="num">{c.contratos}</td>
                    <td>
                      <span className={noAlvo ? 'badge badge-ok' : c.produto_id === null ? 'badge' : 'badge badge-info'}>
                        {situacaoDoCodigo(c, alvo)}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </Dialogo>
  )
}
