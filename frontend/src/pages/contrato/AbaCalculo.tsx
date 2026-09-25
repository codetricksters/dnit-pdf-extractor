import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link, useOutletContext, useSearchParams } from 'react-router'
import { chaves } from '../../api/chaves'
import { calcular, urlPlanilha } from '../../api/contratos'
import { ErroApi } from '../../api/erros'
import { buscarCobertura } from '../../api/indices'
import { FAMILIAS, ROTULO_FAMILIA, type Contrato, type Familia } from '../../api/tipos'
import { Carregando } from '../../components/Carregando'
import { Icone } from '../../components/Icone'
import { MensagemErro } from '../../components/MensagemErro'
import { mesAno } from '../../lib/formato'
import { destinoDoFaltante, regioesDaUrl } from './bloqueio'
import { TabelaCalculo } from './TabelaCalculo'

const PARAMETRO: Record<Familia, 'regiao_cap' | 'regiao_emulsoes'> = {
  CAP: 'regiao_cap',
  EMULSOES: 'regiao_emulsoes',
}

export function AbaCalculo() {
  const contrato = useOutletContext<Contrato>()
  const [busca, setBusca] = useSearchParams()
  const regioes = regioesDaUrl(busca)
  const cobertura = useQuery({ queryKey: chaves.cobertura, queryFn: buscarCobertura })
  const calculo = useQuery({
    queryKey: chaves.calculo(contrato.id, regioes),
    queryFn: () => calcular(contrato.id, regioes),
    placeholderData: keepPreviousData,
  })

  const simuladas = FAMILIAS.filter((f) => busca.get(PARAMETRO[f]))
  const opcoes = cobertura.data?.regioes ?? []

  function escolher(familia: Familia, regiao: string) {
    const proxima = new URLSearchParams(busca)
    // A região do cadastro não é simulação: sai da URL.
    if (!regiao || regiao === contrato.regioes[familia]) proxima.delete(PARAMETRO[familia])
    else proxima.set(PARAMETRO[familia], regiao)
    setBusca(proxima)
  }

  const erro = calculo.error
  const bloqueio = erro instanceof ErroApi && erro.status === 422 && erro.faltando.length > 0

  return (
    <>
      <div className="panel">
        <div className="panel-body barra">
          <span className="badge badge-mono">Data Base: {mesAno(contrato.data_base)}</span>
          {FAMILIAS.map((familia) => {
            const atual = busca.get(PARAMETRO[familia]) ?? contrato.regioes[familia] ?? ''
            const lista = atual && !opcoes.includes(atual) ? [atual, ...opcoes] : opcoes
            return (
              <div className="inline-form" key={familia}>
                <label className="field-label" htmlFor={`regiao-${familia}`}>
                  Região {ROTULO_FAMILIA[familia]}
                </label>
                <select
                  id={`regiao-${familia}`}
                  className="input"
                  value={atual}
                  onChange={(e) => escolher(familia, e.target.value)}
                >
                  {!atual && <option value="">Sem região</option>}
                  {lista.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </div>
            )
          })}
          <span className="espaco" />
          {simuladas.length > 0 && (
            <button type="button" className="btn" onClick={() => setBusca(new URLSearchParams())}>
              Voltar ao cadastro
            </button>
          )}
          {calculo.data && !bloqueio && (
            <a className="btn btn-primary" href={urlPlanilha(contrato.id, regioes)} download>
              <Icone nome="download" />
              <span>Baixar planilha (.xlsx)</span>
            </a>
          )}
        </div>
      </div>

      {simuladas.length > 0 && calculo.data && !calculo.isPlaceholderData && !bloqueio && (
        <div className="notice info mt-md" role="status">
          <div>
            <p className="notice-title">Simulação — o cadastro não muda.</p>
            <p className="notice-text">
              {simuladas
                .map((f) => `${ROTULO_FAMILIA[f]} em ${busca.get(PARAMETRO[f])} (cadastro: ${contrato.regioes[f] ?? 'sem região'})`)
                .join('; ')}
              . Arquivo: {calculo.data.arquivo}
            </p>
          </div>
        </div>
      )}

      {bloqueio && (
        <div className="notice danger mt-md" role="alert">
          <div className="notice-icon">
            <Icone nome="block" />
          </div>
          <div>
            <p className="notice-title">Cálculo bloqueado</p>
            <ul className="lista-erros">
              {erro.faltando.map((item) => {
                const destino = destinoDoFaltante(item, contrato.id)
                return (
                  <li key={item}>
                    {destino.texto}{' '}
                    {destino.para && (
                      <Link to={destino.para} className="btn btn-sm">
                        {destino.rotulo}
                      </Link>
                    )}
                  </li>
                )
              })}
            </ul>
          </div>
        </div>
      )}
      {!bloqueio && <MensagemErro erro={erro} />}
      {calculo.isPending && <Carregando />}

      {calculo.data && !bloqueio && (
        <>
          <section className="panel mt-md">
            <div className="panel-body flush">
              <TabelaCalculo calculo={calculo.data} />
            </div>
          </section>
          {calculo.data.avisos.length > 0 && (
            <div className="notice warn mt-md">
              <div>
                <p className="notice-title">Avisos da planilha</p>
                <ul className="lista-erros">
                  {calculo.data.avisos.map((aviso) => (
                    <li key={aviso}>{aviso}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </>
      )}
    </>
  )
}
