import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { desassociarCodigo, excluirProduto, listarCodigos, listarProdutos } from '../../api/catalogo'
import { chaves } from '../../api/chaves'
import { aposCatalogo } from '../../api/invalidar'
import { FAMILIAS, ROTULO_FAMILIA, type Produto } from '../../api/tipos'
import { Cabecalho } from '../../components/Cabecalho'
import { Carregando } from '../../components/Carregando'
import { ConfirmarDialogo } from '../../components/ConfirmarDialogo'
import { Icone } from '../../components/Icone'
import { MensagemErro } from '../../components/MensagemErro'
import { AdicionarCodigos } from './AdicionarCodigos'
import { ProdutoDialogo } from './ProdutoDialogo'

type Dialogo = { tipo: 'novo' } | { tipo: 'editar'; produto: Produto } | { tipo: 'excluir'; produto: Produto } | null

const plural = (n: number, um: string, varios: string) => `${n} ${n === 1 ? um : varios}`

export function PaginaCatalogo() {
  const qc = useQueryClient()
  const [busca, setBusca] = useSearchParams()
  const [dialogo, setDialogo] = useState<Dialogo>(null)
  const produtos = useQuery({ queryKey: chaves.produtos, queryFn: listarProdutos })

  const lista = produtos.data ?? []
  const produtoParam = busca.get('produto')
  const idUrl = produtoParam !== null ? Number(produtoParam) : null
  const selecionado = (idUrl !== null ? lista.find((p) => p.id === idUrl) : undefined) ?? lista[0]
  const produtoNaoEncontrado = idUrl !== null && lista.length > 0 && selecionado?.id !== idUrl
  const buscaCodigo = busca.get('q')
  const semProdutoParaAdicionar = buscaCodigo !== null && lista.length === 0

  const codigos = useQuery({
    queryKey: chaves.codigos({ produtoId: selecionado?.id }),
    queryFn: () => listarCodigos({ produtoId: selecionado!.id }),
    enabled: selecionado !== undefined,
  })
  const remover = useMutation({
    mutationFn: desassociarCodigo,
    onSuccess: () => aposCatalogo(qc),
  })
  const excluir = useMutation({
    mutationFn: (id: number) => excluirProduto(id),
    onSuccess: async () => {
      await aposCatalogo(qc)
      setDialogo(null)
      setBusca(new URLSearchParams())
    },
  })

  function selecionar(id: number) {
    setBusca(new URLSearchParams({ produto: String(id) }))
  }

  function fecharAdicionar() {
    const proxima = new URLSearchParams(busca)
    proxima.delete('q')
    setBusca(proxima)
  }

  function abrirAdicionar() {
    const proxima = new URLSearchParams(busca)
    proxima.set('q', '')
    setBusca(proxima)
  }

  return (
    <>
      <Cabecalho
        titulo="Catálogo"
        subtitulo="Produtos da planilha e os códigos de serviço que entram em cada um. Código sem produto fica fora do cálculo."
        acoes={
          <button type="button" className="btn btn-primary" onClick={() => setDialogo({ tipo: 'novo' })}>
            <Icone nome="add" />
            <span>Novo produto</span>
          </button>
        }
      />
      <MensagemErro erro={produtos.error} />
      {produtos.isPending && <Carregando />}

      {produtos.data && lista.length === 0 && (
        <div className="notice info">
          <div>
            <p className="notice-title">Nenhum produto ainda.</p>
            <p className="notice-text">
              Crie um produto para cada material que entra no reequilíbrio (CAP ou emulsão) e associe a ele os
              códigos de serviço dos PDFs.
              {semProdutoParaAdicionar &&
                ` Não é possível abrir "Adicionar códigos" para o código ${buscaCodigo || '(vazio)'} sem um produto.`}
            </p>
          </div>
        </div>
      )}

      {produtoNaoEncontrado && (
        <div className="notice warn">
          <div>
            <p className="notice-title">Produto não encontrado.</p>
            <p className="notice-text">
              O produto de id {idUrl} não existe mais; mostrando {selecionado!.descricao_export}.
            </p>
          </div>
        </div>
      )}

      {selecionado && (
        <div className="duas-colunas">
          <nav className="panel lista-produtos" aria-label="Produtos">
            {FAMILIAS.map((familia) => {
              const daFamilia = lista.filter((p) => p.familia === familia)
              if (daFamilia.length === 0) return null
              return (
                <div key={familia} className="panel-body">
                  <p className="field-label">{ROTULO_FAMILIA[familia]}</p>
                  {daFamilia.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      className={p.id === selecionado.id ? 'nav-item active' : 'nav-item'}
                      aria-current={p.id === selecionado.id ? 'true' : undefined}
                      onClick={() => selecionar(p.id)}
                    >
                      <span>{p.descricao_export}</span>
                      <span className="nav-item-badge">{p.codigos}</span>
                    </button>
                  ))}
                </div>
              )
            })}
          </nav>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2 className="panel-title">{selecionado.descricao_export}</h2>
                <p className="contagem">
                  {ROTULO_FAMILIA[selecionado.familia]} · {plural(selecionado.codigos, 'código', 'códigos')}
                </p>
              </div>
              <div className="barra">
                <button type="button" className="btn" onClick={() => setDialogo({ tipo: 'editar', produto: selecionado })}>
                  Editar
                </button>
                <button type="button" className="btn" onClick={() => setDialogo({ tipo: 'excluir', produto: selecionado })}>
                  Excluir produto
                </button>
                <button type="button" className="btn btn-primary" onClick={abrirAdicionar}>
                  Adicionar códigos
                </button>
              </div>
            </div>
            <div className="panel-body flush">
              <MensagemErro erro={codigos.error ?? remover.error} />
              {codigos.data && codigos.data.length === 0 && (
                <p className="panel-body contagem">Nenhum código neste produto. Use Adicionar códigos.</p>
              )}
              {codigos.data && codigos.data.length > 0 && (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Código</th>
                      <th>Descrição no PDF</th>
                      <th className="num">Contratos</th>
                      <th className="num">Ocorrências</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {codigos.data.map((c) => (
                      <tr key={c.codigo}>
                        <td className="num">{c.codigo}</td>
                        <td>{c.descricao_pdf ?? 'Ainda não extraído'}</td>
                        <td className="num">{c.contratos}</td>
                        <td className="num">{c.ocorrencias}</td>
                        <td>
                          <button
                            type="button"
                            className="btn btn-sm"
                            aria-label={`Remover ${c.codigo}`}
                            disabled={remover.isPending}
                            onClick={() => remover.mutate(c.codigo)}
                          >
                            Remover
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>
        </div>
      )}

      {dialogo?.tipo === 'novo' && (
        <ProdutoDialogo aoFechar={() => setDialogo(null)} aoSalvar={(p) => { setDialogo(null); selecionar(p.id) }} />
      )}
      {dialogo?.tipo === 'editar' && (
        <ProdutoDialogo produto={dialogo.produto} aoFechar={() => setDialogo(null)} aoSalvar={() => setDialogo(null)} />
      )}
      {dialogo?.tipo === 'excluir' && (
        <ConfirmarDialogo
          titulo={`Excluir ${dialogo.produto.descricao_export}?`}
          mensagem={`As associações são removidas: ${plural(dialogo.produto.codigos, 'código deixa', 'códigos deixam')} o cálculo. Os itens extraídos continuam nas medições.`}
          rotuloConfirmar="Excluir"
          perigoso
          pendente={excluir.isPending}
          erro={excluir.error}
          aoCancelar={() => setDialogo(null)}
          aoConfirmar={() => excluir.mutate(dialogo.produto.id)}
        />
      )}
      {buscaCodigo !== null && selecionado && (
        <AdicionarCodigos
          produtos={lista}
          produtoInicial={selecionado.id}
          buscaInicial={buscaCodigo}
          aoFechar={fecharAdicionar}
        />
      )}
    </>
  )
}
