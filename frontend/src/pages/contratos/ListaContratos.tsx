import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'
import { chaves } from '../../api/chaves'
import { listarContratos } from '../../api/contratos'
import type { ContratoResumo } from '../../api/tipos'
import { Cabecalho } from '../../components/Cabecalho'
import { Carregando } from '../../components/Carregando'
import { Icone } from '../../components/Icone'
import { MensagemErro } from '../../components/MensagemErro'
import { mesAno } from '../../lib/formato'
import { BADGE_NIVEL, bloqueado, situacao } from './situacao'

function periodo(c: ContratoResumo) {
  if (!c.primeiro_mes) return '—'
  if (c.primeiro_mes === c.ultimo_mes) return mesAno(c.primeiro_mes)
  return `${mesAno(c.primeiro_mes)} – ${mesAno(c.ultimo_mes)}`
}

function BotaoEnviar() {
  return (
    <Link to="/upload" className="btn btn-primary">
      <Icone nome="upload_file" />
      <span>Enviar PDFs</span>
    </Link>
  )
}

export function ListaContratos() {
  const [busca, setBusca] = useState('')
  const consulta = useQuery({ queryKey: chaves.contratos, queryFn: listarContratos })
  const termo = busca.trim().toLowerCase()
  const lista = (consulta.data ?? []).filter((c) => c.numero.toLowerCase().includes(termo))

  return (
    <>
      <Cabecalho
        titulo="Contratos"
        subtitulo="Contratos extraídos dos PDFs de medição. Abra um para completar o cadastro, conferir as medições e gerar a planilha."
        acoes={<BotaoEnviar />}
      />
      <MensagemErro erro={consulta.error} />
      {consulta.isPending && <Carregando />}
      {consulta.data?.length === 0 && (
        <div className="panel">
          <div className="empty-state">
            <p className="headline-sm">Nenhum contrato ainda.</p>
            <p className="muted">Os contratos aparecem aqui depois que os PDFs do Resumo da Medição são processados.</p>
            <BotaoEnviar />
          </div>
        </div>
      )}
      {!!consulta.data?.length && (
        <div className="panel">
          <div className="panel-head">
            <div className="inline-form">
              <label className="field-label" htmlFor="busca-contrato">
                Pesquisar contrato
              </label>
              <input
                id="busca-contrato"
                className="input"
                placeholder="Número do contrato"
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
              />
            </div>
          </div>
          <div className="panel-body flush table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Contrato</th>
                  <th>Contratada</th>
                  <th>Rodovia</th>
                  <th>Data Base</th>
                  <th>Região CAP</th>
                  <th>Região Emulsões</th>
                  <th className="num">Medições</th>
                  <th>Período</th>
                  <th>Situação</th>
                </tr>
              </thead>
              <tbody>
                {lista.map((c) => {
                  const s = situacao(c.faltantes)
                  const aba = bloqueado(c.faltantes) ? 'cadastro' : 'calculo'
                  return (
                    <tr key={c.id}>
                      <td>
                        <Link className="cell-title" to={`/contratos/${c.id}/${aba}`}>
                          {c.numero}
                        </Link>
                      </td>
                      <td>{c.contratada ?? '—'}</td>
                      <td>{c.rodovia ?? '—'}</td>
                      <td>{mesAno(c.data_base)}</td>
                      <td>{c.regioes.CAP ?? '—'}</td>
                      <td>{c.regioes.EMULSOES ?? '—'}</td>
                      <td className="num">{c.medicoes}</td>
                      <td>{periodo(c)}</td>
                      <td>
                        <span className={BADGE_NIVEL[s.nivel]}>{s.texto}</span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {lista.length === 0 && <p className="empty-state muted">Nenhum contrato com “{busca}”.</p>}
          </div>
        </div>
      )}
    </>
  )
}
