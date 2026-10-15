import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { chaves } from '../../api/chaves'
import { aplicarRegiao } from '../../api/contratos'
import { buscarCobertura } from '../../api/indices'
import { aposMedicao } from '../../api/invalidar'
import { FAMILIAS, ROTULO_FAMILIA, type Familia, type RegiaoEmLote } from '../../api/tipos'
import { Dialogo } from '../../components/Dialogo'
import { MensagemErro } from '../../components/MensagemErro'
import { mesAno } from '../../lib/formato'

interface Props {
  contratoId: number
  meses: string[] // AAAA-MM, do mais recente ao mais antigo
  aoAplicar: (alterados: number) => void
  aoFechar: () => void
}

// A região por registro gravada de uma vez numa família e num período. Primeiro o
// backend conta os registros (simular), e só depois da confirmação grava.
export function DialogoRegiaoLote({ contratoId, meses, aoAplicar, aoFechar }: Props) {
  const qc = useQueryClient()
  const cobertura = useQuery({ queryKey: chaves.cobertura, queryFn: buscarCobertura })
  const [familia, setFamilia] = useState<Familia>('CAP')
  const [de, setDe] = useState(meses.at(-1) ?? '')
  const [ate, setAte] = useState(meses[0] ?? '')
  const [regiao, setRegiao] = useState('')
  const [previa, setPrevia] = useState<number | null>(null)

  const corpo: RegiaoEmLote = { familia, mes_de: de, mes_ate: ate, regiao: regiao || null }
  const simular = useMutation({
    mutationFn: () => aplicarRegiao(contratoId, corpo, true),
    onSuccess: (r) => setPrevia(r.alterados),
  })
  const gravar = useMutation({
    mutationFn: () => aplicarRegiao(contratoId, corpo),
    onSuccess: async (r) => {
      await aposMedicao(qc, contratoId)
      aoAplicar(r.alterados)
    },
  })

  function mudou<T>(definir: (v: T) => void) {
    return (v: T) => {
      definir(v)
      setPrevia(null)
    }
  }

  function continuar(e: FormEvent) {
    e.preventDefault()
    simular.mutate()
  }

  const opcoesMes = meses.map((m) => <option key={m} value={m}>{mesAno(`${m}-01`)}</option>)
  const destino = regiao ? `a região ${regiao}` : 'a região do contrato'

  return (
    <Dialogo
      titulo="Aplicar região"
      aoFechar={aoFechar}
      acoes={
        <>
          <button type="button" className="btn" onClick={aoFechar}>Cancelar</button>
          {previa === null ? (
            <button type="submit" form="form-regiao-lote" className="btn btn-primary" disabled={simular.isPending}>
              Continuar
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-primary"
              disabled={previa === 0 || gravar.isPending}
              onClick={() => gravar.mutate()}
            >
              Aplicar região
            </button>
          )}
        </>
      }
    >
      <form id="form-regiao-lote" onSubmit={continuar}>
        <div className="field">
          <label className="field-label" htmlFor="lote-familia">Família</label>
          <select
            id="lote-familia"
            className="input"
            value={familia}
            onChange={(e) => mudou(setFamilia)(e.target.value as Familia)}
          >
            {FAMILIAS.map((f) => <option key={f} value={f}>{ROTULO_FAMILIA[f]}</option>)}
          </select>
        </div>
        <div className="field">
          <label className="field-label" htmlFor="lote-de">De</label>
          <select id="lote-de" className="input" value={de} onChange={(e) => mudou(setDe)(e.target.value)}>
            {opcoesMes}
          </select>
        </div>
        <div className="field">
          <label className="field-label" htmlFor="lote-ate">Até</label>
          <select id="lote-ate" className="input" value={ate} onChange={(e) => mudou(setAte)(e.target.value)}>
            {opcoesMes}
          </select>
        </div>
        <div className="field">
          <label className="field-label" htmlFor="lote-regiao">Região ANP</label>
          <select id="lote-regiao" className="input" value={regiao} onChange={(e) => mudou(setRegiao)(e.target.value)}>
            <option value="">Seguir o contrato</option>
            {(cobertura.data?.regioes ?? []).map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
      </form>
      {previa !== null && (
        <p role="status">
          {previa === 0
            ? 'Nenhum registro dessa família no período.'
            : `${previa} ${previa === 1 ? 'registro' : 'registros'} de ${ROTULO_FAMILIA[familia]} de ${mesAno(`${de}-01`)} a ${mesAno(`${ate}-01`)} passarão a usar ${destino}.`}
        </p>
      )}
      <MensagemErro erro={simular.error ?? gravar.error} />
    </Dialogo>
  )
}
