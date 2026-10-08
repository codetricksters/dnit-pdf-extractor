import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { gravarIgpDi } from '../../api/indices'
import { aposIndices } from '../../api/invalidar'
import { Dialogo } from '../../components/Dialogo'
import { MensagemErro } from '../../components/MensagemErro'
import { paraDecimal } from '../../lib/formato'

const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

// Mês e ano em campos separados: <input type="month"> não existe no Firefox
// desktop, e um texto livre ("04/2027") quebraria o caminho da requisição.
// Um mês do IGP-DI digitado. Mês que já existe é corrigido (o PUT é um upsert);
// valor inválido é recusado pelo backend e aparece aqui.
export function NovoIndice({ aoFechar }: { aoFechar: () => void }) {
  const qc = useQueryClient()
  const [mes, setMes] = useState('')
  const [ano, setAno] = useState(String(new Date().getFullYear()))
  const [valor, setValor] = useState('')
  const [ilegivel, setIlegivel] = useState(false)
  const gravar = useMutation({
    mutationFn: ({ mes, valor }: { mes: string; valor: string }) => gravarIgpDi(mes, valor),
    onSuccess: async () => {
      await aposIndices(qc)
      aoFechar()
    },
  })

  function enviar(e: FormEvent) {
    e.preventDefault()
    const decimal = paraDecimal(valor)
    setIlegivel(decimal === null)
    if (decimal === null) return
    gravar.mutate({ mes: `${ano}-${mes}`, valor: decimal })
  }

  return (
    <Dialogo
      titulo="Novo índice IGP-DI"
      aoFechar={aoFechar}
      acoes={
        <>
          <button type="button" className="btn" onClick={aoFechar}>Cancelar</button>
          <button type="submit" form="form-indice" className="btn btn-primary" disabled={!mes || !/^\d{4}$/.test(ano) || !valor.trim() || gravar.isPending}>
            Gravar
          </button>
        </>
      }
    >
      <form id="form-indice" className="field-grid" onSubmit={enviar}>
        <div className="field">
          <label className="field-label" htmlFor="indice-mes">Mês</label>
          <select id="indice-mes" className="input" value={mes} onChange={(e) => setMes(e.target.value)}>
            <option value="">Selecione</option>
            {MESES.map((nome, i) => (
              <option key={nome} value={String(i + 1).padStart(2, '0')}>{nome}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label className="field-label" htmlFor="indice-ano">Ano</label>
          <input id="indice-ano" type="number" className="input" min={1900} max={2999} value={ano} onChange={(e) => setAno(e.target.value)} />
        </div>
        <div className="field">
          <label className="field-label" htmlFor="indice-valor">Valor do índice</label>
          <input id="indice-valor" className="input" value={valor} placeholder="1090,1" onChange={(e) => setValor(e.target.value)} />
          {ilegivel && <p className="erro-campo">Número ilegível; use vírgula decimal, como 1090,1.</p>}
        </div>
      </form>
      <MensagemErro erro={gravar.error} />
    </Dialogo>
  )
}
