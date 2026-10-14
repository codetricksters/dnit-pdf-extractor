import { useEffect, useState } from 'react'

const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

// Mês e ano em dois campos, para um mês qualquer (a Data Base). <input
// type="month"> não serve: no Firefox desktop é texto livre. O valor que sobe é
// 'AAAA-MM' quando os dois estão preenchidos e '' enquanto falta um deles.
interface Props {
  id: string
  valor: string
  aoMudar: (valor: string) => void
  invalido?: boolean
  descritoPor?: string
}

function dividir(valor: string): [string, string] {
  const achado = /^(\d{4})-(0[1-9]|1[0-2])/.exec(valor)
  return achado ? [achado[2], achado[1]] : ['', '']
}

function juntar(mes: string, ano: string): string {
  return mes && /^\d{4}$/.test(ano) ? `${ano}-${mes}` : ''
}

export function CampoMesAno({ id, valor, aoMudar, invalido, descritoPor }: Props) {
  const [mes, setMes] = useState(() => dividir(valor)[0])
  const [ano, setAno] = useState(() => dividir(valor)[1])

  // O formulário foi relido (salvar, trocar de contrato): acompanha, mas não
  // apaga o que o usuário está digitando pela metade.
  useEffect(() => {
    if (valor !== juntar(mes, ano)) {
      const [m, a] = dividir(valor)
      setMes(m)
      setAno(a)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [valor])

  function mudar(novoMes: string, novoAno: string) {
    setMes(novoMes)
    setAno(novoAno)
    aoMudar(juntar(novoMes, novoAno))
  }

  const atributos = { 'aria-invalid': invalido || undefined, 'aria-describedby': descritoPor }
  return (
    <div className="barra">
      <select id={id} className="input" value={mes} onChange={(e) => mudar(e.target.value, ano)} {...atributos}>
        <option value="">Mês</option>
        {MESES.map((nome, i) => (
          <option key={nome} value={String(i + 1).padStart(2, '0')}>{nome}</option>
        ))}
      </select>
      <input
        id={`${id}_ano`}
        type="number"
        className="input"
        aria-label="Ano"
        placeholder="Ano"
        min={1900}
        max={2999}
        value={ano}
        onChange={(e) => mudar(mes, e.target.value)}
        {...atributos}
      />
    </div>
  )
}
