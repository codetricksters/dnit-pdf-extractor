import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState, type FormEvent } from 'react'
import { chaves } from '../../api/chaves'
import {
  ANP_PRODUTO_CAP, excluirSemanaAnp, gravarSemanaAnp, listarAnp, listarProdutosAnp, urlExportarAnp,
} from '../../api/indices'
import { aposIndices } from '../../api/invalidar'
import { BotaoBaixar } from '../../components/BotaoBaixar'
import { CelulaEditavel } from '../../components/CelulaEditavel'
import { Carregando } from '../../components/Carregando'
import { ConfirmarDialogo } from '../../components/ConfirmarDialogo'
import { Icone } from '../../components/Icone'
import { MensagemErro } from '../../components/MensagemErro'
import { dataHora, exato, semana } from '../../lib/formato'
import { FaixaCobertura } from './FaixaCobertura'
import { montarGradeAnp, type LinhaAnp } from './grade'
import { ImportarIndices } from './ImportarIndices'
import { NovaSemana } from './NovaSemana'

export function GradeAnp() {
  const qc = useQueryClient()
  const [produto, setProduto] = useState(ANP_PRODUTO_CAP)
  const [de, setDe] = useState('')
  const [ate, setAte] = useState('')
  const [periodo, setPeriodo] = useState<{ de?: string; ate?: string }>({})
  const [novaSemana, setNovaSemana] = useState(false)
  const [apagando, setApagando] = useState<LinhaAnp | null>(null)
  const [importando, setImportando] = useState(false)

  const produtos = useQuery({ queryKey: chaves.produtosAnp, queryFn: listarProdutosAnp })
  const semanas = useQuery({
    queryKey: chaves.anp(produto, periodo.de, periodo.ate),
    queryFn: () => listarAnp({ produto, ...periodo }),
    placeholderData: keepPreviousData,
  })
  const grade = useMemo(() => montarGradeAnp(semanas.data ?? []), [semanas.data])

  const apagar = useMutation({
    mutationFn: async (linha: LinhaAnp) => {
      for (const s of Object.values(linha.celulas)) if (s) await excluirSemanaAnp(s.id)
    },
    onSuccess: () => {
      setApagando(null)
    },
    onSettled: async () => {
      // Mesmo numa falha parcial (uma região apagada, outra não), a grade
      // precisa refletir o estado real do banco em vez de continuar mostrando
      // dados que já não existem mais.
      await aposIndices(qc)
    },
  })

  async function gravar(linha: LinhaAnp, regiao: string, preco: string | null) {
    await gravarSemanaAnp({ produto, regiao, vigencia_inicio: linha.inicio, vigencia_fim: linha.fim, preco })
    await aposIndices(qc)
  }

  function filtrar(e: FormEvent) {
    e.preventDefault()
    setPeriodo({ de: de || undefined, ate: ate || undefined })
  }

  const opcoes = produtos.data?.length ? produtos.data : [ANP_PRODUTO_CAP]
  return (
    <>
      <FaixaCobertura serie="anp" />
      <form className="barra mt-md" onSubmit={filtrar}>
        <div className="field">
          <label className="field-label" htmlFor="anp-produto">Produto</label>
          <select id="anp-produto" className="input" value={produto} onChange={(e) => setProduto(e.target.value)}>
            {opcoes.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label className="field-label" htmlFor="anp-de">De</label>
          <input id="anp-de" type="date" className="input" value={de} onChange={(e) => setDe(e.target.value)} />
        </div>
        <div className="field">
          <label className="field-label" htmlFor="anp-ate">Até</label>
          <input id="anp-ate" type="date" className="input" value={ate} onChange={(e) => setAte(e.target.value)} />
        </div>
        <button type="submit" className="btn">Filtrar</button>
        <span className="espaco" />
        <BotaoBaixar caminho={urlExportarAnp({ produto, ...periodo, formato: 'xlsx' })} nomeArquivo="indices_anp.xlsx">
          Exportar .xlsx
        </BotaoBaixar>
        <BotaoBaixar caminho={urlExportarAnp({ produto, ...periodo, formato: 'csv' })} nomeArquivo="indices_anp.csv">
          Exportar .csv
        </BotaoBaixar>
        <button type="button" className="btn" onClick={() => setImportando(true)}>
          <Icone nome="upload_file" />
          <span>Importar</span>
        </button>
        <button type="button" className="btn btn-primary" onClick={() => setNovaSemana(true)}>
          <Icone nome="add" />
          <span>Nova semana</span>
        </button>
      </form>

      <MensagemErro erro={semanas.error} />
      {semanas.isPending && <Carregando />}
      {semanas.data && grade.linhas.length === 0 && <p className="contagem mt-md">Nenhuma semana gravada para este produto e período.</p>}
      {grade.linhas.length > 0 && (
        <section className="panel mt-md">
          <div className="panel-body flush table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Semana</th>
                  {grade.regioes.map((r) => (
                    <th key={r} className="num">{r}</th>
                  ))}
                  <th />
                </tr>
              </thead>
              <tbody>
                {grade.linhas.map((linha) => {
                  const rotuloSemana = semana(linha.inicio, linha.fim)
                  return (
                    <tr key={`${linha.inicio}|${linha.fim}`}>
                      <td className="num">{rotuloSemana}</td>
                      {grade.regioes.map((regiao) => {
                        const s = linha.celulas[regiao]
                        return (
                          <CelulaEditavel
                            key={regiao}
                            rotulo={`${regiao} ${rotuloSemana}`}
                            valor={s?.preco}
                            formatar={exato}
                            vazio={s ? 'sem cotação' : '—'}
                            manual={s?.origem === 'manual'}
                            titulo={s ? `${s.origem} · ${dataHora(s.atualizado_em)}` : undefined}
                            permiteVazio
                            aoSalvar={(preco) => gravar(linha, regiao, preco)}
                          />
                        )
                      })}
                      <td>
                        <button
                          type="button"
                          className="btn btn-sm"
                          aria-label={`Apagar semana ${rotuloSemana}`}
                          onClick={() => setApagando(linha)}
                        >
                          Apagar
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {novaSemana && <NovaSemana produto={produto} aoFechar={() => setNovaSemana(false)} />}
      {importando && <ImportarIndices serie="anp" aoFechar={() => setImportando(false)} />}
      {apagando && (
        <ConfirmarDialogo
          titulo={`Apagar a semana ${semana(apagando.inicio, apagando.fim)}?`}
          mensagem="Os preços de todas as regiões desta semana saem do banco. Cálculos que dependem dela ficam bloqueados até a semana voltar."
          rotuloConfirmar="Apagar"
          perigoso
          pendente={apagar.isPending}
          erro={apagar.error}
          aoCancelar={() => setApagando(null)}
          aoConfirmar={() => apagar.mutate(apagando)}
        />
      )}
    </>
  )
}
