import { useId, useState, type ReactNode } from 'react'
import { Dialogo } from './Dialogo'
import { MensagemErro } from './MensagemErro'

interface Props {
  titulo: string
  mensagem: ReactNode
  rotuloConfirmar: string
  // Ações irreversíveis (restaurar backup) exigem digitar este texto.
  textoExigido?: string
  perigoso?: boolean
  pendente?: boolean
  erro?: unknown
  aoConfirmar: () => void
  aoCancelar: () => void
}

export function ConfirmarDialogo({
  titulo, mensagem, rotuloConfirmar, textoExigido, perigoso, pendente, erro, aoConfirmar, aoCancelar,
}: Props) {
  const [digitado, setDigitado] = useState('')
  const idCampo = useId()
  const liberado = !pendente && (!textoExigido || digitado === textoExigido)
  return (
    <Dialogo
      titulo={titulo}
      aoFechar={aoCancelar}
      acoes={
        <>
          <button type="button" className="btn" onClick={aoCancelar}>
            Cancelar
          </button>
          <button
            type="button"
            className={perigoso ? 'btn btn-danger' : 'btn btn-primary'}
            disabled={!liberado}
            onClick={aoConfirmar}
          >
            {rotuloConfirmar}
          </button>
        </>
      }
    >
      <div>{mensagem}</div>
      {textoExigido && (
        <div className="field">
          <label className="field-label" htmlFor={idCampo}>
            Digite {textoExigido} para confirmar
          </label>
          <input id={idCampo} className="input" value={digitado} onChange={(e) => setDigitado(e.target.value)} autoComplete="off" />
        </div>
      )}
      <MensagemErro erro={erro} />
    </Dialogo>
  )
}
