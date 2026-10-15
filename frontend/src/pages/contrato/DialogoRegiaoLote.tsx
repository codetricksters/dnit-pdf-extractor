import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { chaves } from '../../api/chaves'
import { aplicarRegiao } from '../../api/contratos'
import { buscarCobertura } from '../../api/indices'
import { aposMedicao } from '../../api/invalidar'
import type { RegiaoEmLote } from '../../api/tipos'
import { Dialogo } from '../../components/Dialogo'
import { MensagemErro } from '../../components/MensagemErro'

interface Props {
  contratoId: number
  ids: number[] // os registros marcados na tabela
  aoAplicar: (alterados: number) => void
  aoFechar: () => void
}

// A região por registro gravada de uma vez nos registros marcados; cada um a recebe na
// família do seu produto. Primeiro o backend conta os registros (simular), e só depois da
// confirmação grava.
export function DialogoRegiaoLote({ contratoId, ids, aoAplicar, aoFechar }: Props) {
  const qc = useQueryClient()
  const cobertura = useQuery({ queryKey: chaves.cobertura, queryFn: buscarCobertura })
  const [regiao, setRegiao] = useState('')
  const [previa, setPrevia] = useState<number | null>(null)

  const corpo: RegiaoEmLote = { ids, regiao: regiao || null }
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

  function continuar(e: FormEvent) {
    e.preventDefault()
    simular.mutate()
  }

  const destino = regiao ? `a região ${regiao}` : 'a região do contrato'
  const total = `${ids.length} ${ids.length === 1 ? 'registro selecionado' : 'registros selecionados'}`

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
          <label className="field-label" htmlFor="lote-regiao">Região ANP</label>
          <select
            id="lote-regiao"
            className="input"
            value={regiao}
            onChange={(e) => {
              setRegiao(e.target.value)
              setPrevia(null)
            }}
          >
            <option value="">Seguir o contrato</option>
            {(cobertura.data?.regioes ?? []).map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
      </form>
      {previa !== null && (
        <p role="status">
          {previa === 0
            ? 'Nenhum dos registros selecionados tem produto no cálculo.'
            : `${previa} de ${total} ${previa === 1 ? 'passará' : 'passarão'} a usar ${destino}` +
              (previa < ids.length ? '; os demais não têm produto no cálculo.' : '.')}
        </p>
      )}
      <MensagemErro erro={simular.error ?? gravar.error} />
    </Dialogo>
  )
}
