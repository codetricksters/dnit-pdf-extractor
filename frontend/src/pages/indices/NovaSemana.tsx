import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { gravarSemanaAnp, REGIOES_ANP } from '../../api/indices'
import { aposIndices } from '../../api/invalidar'
import { Dialogo } from '../../components/Dialogo'
import { MensagemErro } from '../../components/MensagemErro'
import { paraDecimal } from '../../lib/formato'

// Uma semana digitada. Preço vazio = semana sem cotação; a sobreposição com
// outra semana da mesma região é recusada pelo backend e aparece aqui.
export function NovaSemana({ produto, aoFechar }: { produto: string; aoFechar: () => void }) {
  const qc = useQueryClient()
  const [inicio, setInicio] = useState('')
  const [fim, setFim] = useState('')
  const [regiao, setRegiao] = useState('Nordeste')
  const [preco, setPreco] = useState('')
  const [ilegivel, setIlegivel] = useState(false)
  const gravar = useMutation({
    mutationFn: gravarSemanaAnp,
    onSuccess: async () => {
      await aposIndices(qc)
      aoFechar()
    },
  })

  function enviar(e: FormEvent) {
    e.preventDefault()
    const valor = preco.trim() ? paraDecimal(preco) : null
    setIlegivel(preco.trim() !== '' && valor === null)
    if (preco.trim() !== '' && valor === null) return
    gravar.mutate({ produto, vigencia_inicio: inicio, vigencia_fim: fim, regiao, preco: valor })
  }

  return (
    <Dialogo
      titulo="Nova semana"
      aoFechar={aoFechar}
      acoes={
        <>
          <button type="button" className="btn" onClick={aoFechar}>Cancelar</button>
          <button type="submit" form="form-semana" className="btn btn-primary" disabled={!inicio || !fim || gravar.isPending}>
            Gravar
          </button>
        </>
      }
    >
      <p className="contagem">{produto}</p>
      <form id="form-semana" className="field-grid" onSubmit={enviar}>
        <div className="field">
          <label className="field-label" htmlFor="semana-inicio">Início da vigência</label>
          <input id="semana-inicio" type="date" className="input" value={inicio} onChange={(e) => setInicio(e.target.value)} />
        </div>
        <div className="field">
          <label className="field-label" htmlFor="semana-fim">Fim da vigência</label>
          <input id="semana-fim" type="date" className="input" value={fim} onChange={(e) => setFim(e.target.value)} />
        </div>
        <div className="field">
          <label className="field-label" htmlFor="semana-regiao">Região</label>
          <select id="semana-regiao" className="input" value={regiao} onChange={(e) => setRegiao(e.target.value)}>
            {REGIOES_ANP.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label className="field-label" htmlFor="semana-preco">Preço (R$)</label>
          <input id="semana-preco" className="input" value={preco} placeholder="vazio = sem cotação" onChange={(e) => setPreco(e.target.value)} />
          {ilegivel && <p className="erro-campo">Número ilegível; use vírgula decimal, como 3,61475.</p>}
        </div>
      </form>
      <MensagemErro erro={gravar.error} />
    </Dialogo>
  )
}
