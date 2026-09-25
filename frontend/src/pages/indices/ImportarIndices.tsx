import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { importarIndices, type SerieIndice } from '../../api/indices'
import { aposIndices } from '../../api/invalidar'
import type { ResultadoImportacao } from '../../api/tipos'
import { Dialogo } from '../../components/Dialogo'
import { MensagemErro } from '../../components/MensagemErro'
import { data, dataHora, exato, mesAno, semana } from '../../lib/formato'

const TITULO: Record<SerieIndice, string> = {
  anp: 'Importar preços ANP',
  'igp-di': 'Importar IGP-DI',
}

const AJUDA: Record<SerieIndice, string> = {
  anp: 'O .xls semanal da ANP, como publicado (todos os produtos).',
  'igp-di': 'O template do IGP-DI preenchido (.xlsx).',
}

// A chave que o backend devolve em cada conflito: {mes} no IGP-DI,
// {produto, regiao, vigencia_inicio, vigencia_fim} no ANP.
function rotuloChave(chave: Record<string, string>): string {
  if (chave.mes) return mesAno(chave.mes)
  return `${chave.regiao} · ${semana(chave.vigencia_inicio, chave.vigencia_fim)} · ${chave.produto}`
}

type Passo = 'arquivo' | 'previa' | 'gravado'

export function ImportarIndices({ serie, aoFechar }: { serie: SerieIndice; aoFechar: () => void }) {
  const qc = useQueryClient()
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [passo, setPasso] = useState<Passo>('arquivo')
  const [resultado, setResultado] = useState<ResultadoImportacao | null>(null)

  const simular = useMutation({
    mutationFn: (f: File) => importarIndices(serie, f, { simular: true }),
    onSuccess: (r) => {
      setResultado(r)
      setPasso('previa')
    },
  })
  const gravar = useMutation({
    mutationFn: (sobrescrever: boolean) =>
      importarIndices(serie, arquivo!, { simular: false, sobrescrever_manuais: sobrescrever }),
    onSuccess: async (r) => {
      setResultado(r)
      setPasso('gravado')
      await aposIndices(qc)
    },
  })

  const conflitos = resultado?.conflitos_manuais.length ?? 0
  const acoes =
    passo === 'arquivo' ? (
      <>
        <button type="button" className="btn" onClick={aoFechar}>Cancelar</button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={!arquivo || simular.isPending}
          onClick={() => arquivo && simular.mutate(arquivo)}
        >
          Ver prévia
        </button>
      </>
    ) : passo === 'previa' ? (
      <>
        <button type="button" className="btn" onClick={aoFechar}>Cancelar</button>
        {conflitos > 0 ? (
          <>
            <button type="button" className="btn" disabled={gravar.isPending} onClick={() => gravar.mutate(true)}>
              Gravar e sobrescrever os {conflitos} manuais
            </button>
            <button type="button" className="btn btn-primary" disabled={gravar.isPending} onClick={() => gravar.mutate(false)}>
              Gravar e manter meus valores manuais
            </button>
          </>
        ) : (
          <button type="button" className="btn btn-primary" disabled={gravar.isPending} onClick={() => gravar.mutate(false)}>
            Gravar
          </button>
        )}
      </>
    ) : (
      <button type="button" className="btn btn-primary" onClick={aoFechar}>Fechar</button>
    )

  return (
    <Dialogo titulo={TITULO[serie]} aoFechar={aoFechar} acoes={acoes}>
      <ol className="passos" aria-label="Passos">
        <li className={passo === 'arquivo' ? 'passo active' : 'passo'}>1. Arquivo</li>
        <li className={passo === 'previa' ? 'passo active' : 'passo'}>2. Prévia</li>
        <li className={passo === 'gravado' ? 'passo active' : 'passo'}>3. Gravado</li>
      </ol>

      {passo === 'arquivo' && (
        <div className="field mt-md">
          <label className="field-label" htmlFor="importar-arquivo">Arquivo</label>
          <input
            id="importar-arquivo"
            type="file"
            className="input"
            accept={serie === 'anp' ? '.xls,.xlsx' : '.xlsx'}
            onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
          />
          <p className="contagem">{AJUDA[serie]} Nada é gravado antes da prévia.</p>
        </div>
      )}

      {passo === 'previa' && resultado && <Previa resultado={resultado} />}

      {passo === 'gravado' && resultado && (
        <div className="notice ok mt-md" role="status">
          <div>
            <p className="notice-title">Importação gravada.</p>
            <p className="notice-text">
              {resultado.inseridos} novos, {resultado.atualizados.length} alterados, {resultado.inalterados} iguais
              {resultado.manuais_preservados > 0 &&
                `; ${resultado.manuais_preservados} ${resultado.manuais_preservados === 1 ? 'valor manual preservado' : 'valores manuais preservados'}`}
              .
            </p>
          </div>
        </div>
      )}

      <MensagemErro erro={simular.error ?? gravar.error} />
    </Dialogo>
  )
}

function Previa({ resultado }: { resultado: ResultadoImportacao }) {
  const formatarPeriodo = resultado.periodo.de?.endsWith('-01') ? mesAno : data
  const conflitos = resultado.conflitos_manuais
  return (
    <>
      <p className="contagem mt-md">
        {resultado.arquivo}
        {resultado.periodo.de && ` · ${formatarPeriodo(resultado.periodo.de)} a ${formatarPeriodo(resultado.periodo.ate)}`}
      </p>
      <div className="cartoes mt-md">
        <div className="cartao"><strong>{resultado.inseridos}</strong>Novos</div>
        <div className="cartao"><strong>{resultado.atualizados.length}</strong>Alterados</div>
        <div className="cartao"><strong>{resultado.inalterados}</strong>Iguais</div>
        <div className={conflitos.length > 0 ? 'cartao warn' : 'cartao'}>
          <strong>{conflitos.length}</strong>Seus valores manuais em conflito
        </div>
      </div>

      {conflitos.length > 0 && (
        <div className="table-scroll mt-md">
          <table className="data-table">
            <thead>
              <tr>
                <th>Registro</th>
                <th className="num">No banco (manual)</th>
                <th className="num">No arquivo</th>
                <th>Editado em</th>
              </tr>
            </thead>
            <tbody>
              {conflitos.map((c) => (
                <tr key={JSON.stringify(c.chave)}>
                  <td>{rotuloChave(c.chave)}</td>
                  <td className="num">{exato(c.valor_banco)}</td>
                  <td className="num">{exato(c.valor_arquivo)}</td>
                  <td>{dataHora(c.atualizado_em)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {resultado.avisos.length > 0 && (
        <div className="notice warn mt-md">
          <div>
            <p className="notice-title">Avisos</p>
            <ul className="lista-erros">
              {resultado.avisos.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </>
  )
}
