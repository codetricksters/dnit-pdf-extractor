import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { atualizarProduto, criarProduto, type ProdutoNovo } from '../../api/catalogo'
import { aposCatalogo } from '../../api/invalidar'
import { FAMILIAS, ROTULO_FAMILIA, type Familia, type Produto } from '../../api/tipos'
import { Dialogo } from '../../components/Dialogo'
import { MensagemErro } from '../../components/MensagemErro'

interface Props {
  produto?: Produto
  aoFechar: () => void
  aoSalvar: (produto: Produto) => void
}

// Criar e editar são o mesmo formulário: descrição livre (é o texto que sai na
// planilha) e a família, que decide a fórmula do ΔP.
export function ProdutoDialogo({ produto, aoFechar, aoSalvar }: Props) {
  const qc = useQueryClient()
  const [descricao, setDescricao] = useState(produto?.descricao_export ?? '')
  const [familia, setFamilia] = useState<Familia>(produto?.familia ?? 'CAP')
  const salvar = useMutation({
    mutationFn: (dados: ProdutoNovo) => (produto ? atualizarProduto(produto.id, dados) : criarProduto(dados)),
    onSuccess: async (salvo) => {
      await aposCatalogo(qc)
      aoSalvar(salvo)
    },
  })

  function enviar(e: FormEvent) {
    e.preventDefault()
    salvar.mutate({ descricao_export: descricao.trim(), familia })
  }

  return (
    <Dialogo
      titulo={produto ? 'Editar produto' : 'Novo produto'}
      aoFechar={aoFechar}
      acoes={
        <>
          <button type="button" className="btn" onClick={aoFechar}>Cancelar</button>
          <button type="submit" form="form-produto" className="btn btn-primary" disabled={!descricao.trim() || salvar.isPending}>
            Salvar
          </button>
        </>
      }
    >
      <form id="form-produto" onSubmit={enviar}>
        <div className="field">
          <label className="field-label" htmlFor="produto-descricao">Descrição na planilha</label>
          <input id="produto-descricao" className="input" value={descricao} onChange={(e) => setDescricao(e.target.value)} />
        </div>
        <div className="field mt-md">
          <label className="field-label" htmlFor="produto-familia">Família</label>
          <select id="produto-familia" className="input" value={familia} onChange={(e) => setFamilia(e.target.value as Familia)}>
            {FAMILIAS.map((f) => (
              <option key={f} value={f}>{ROTULO_FAMILIA[f]}</option>
            ))}
          </select>
        </div>
        <MensagemErro erro={salvar.error} />
      </form>
    </Dialogo>
  )
}
