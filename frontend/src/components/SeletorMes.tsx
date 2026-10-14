import { useId, useState } from 'react'
import { mesAno } from '../lib/formato'

// Escolha de um mês entre os que existem, por digitação ou pela lista.
// <input type="month"> não serve: no Firefox desktop é texto livre, e o valor
// digitado chegaria ao backend fora do padrão AAAA-MM. Aqui o texto só vira
// valor se casar com uma opção; do contrário o pai recebe `null` (ilegível).
// `aoMudar` recebe '' (vazio), 'AAAA-MM' (opção reconhecida) ou null.
interface Props {
  id: string
  opcoes: string[]
  aoMudar: (mes: string | null) => void
}

function apelidos(mes: string): string[] {
  const [ano, m] = mes.split('-')
  return [mesAno(mes), `${m}/${ano}`, mes].map((a) => a.toLowerCase())
}

export function SeletorMes({ id, opcoes, aoMudar }: Props) {
  const lista = useId()
  const [texto, setTexto] = useState('')
  const [ilegivel, setIlegivel] = useState(false)

  function mudar(valor: string) {
    setTexto(valor)
    const busca = valor.trim().toLowerCase()
    if (busca === '') {
      setIlegivel(false)
      aoMudar('')
      return
    }
    const achado = opcoes.find((o) => apelidos(o).includes(busca))
    setIlegivel(achado === undefined)
    aoMudar(achado ?? null)
  }

  return (
    <>
      <input
        id={id}
        className="input"
        list={lista}
        autoComplete="off"
        placeholder="ex.: fev/2023"
        value={texto}
        aria-invalid={ilegivel || undefined}
        onChange={(e) => mudar(e.target.value)}
      />
      <datalist id={lista}>
        {opcoes.map((o) => (
          <option key={o} value={mesAno(o)} />
        ))}
      </datalist>
      {ilegivel && <p className="erro-campo">Escolha um mês da lista, como fev/2023.</p>}
    </>
  )
}
