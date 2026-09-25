import { useQuery } from '@tanstack/react-query'
import { chaves } from '../../api/chaves'
import { buscarCobertura } from '../../api/indices'
import { data, mesAno, numero } from '../../lib/formato'

// O que há no banco para a série da aba: período, quantidade e quantos valores
// foram digitados à mão (esses a importação preserva).
export function FaixaCobertura({ serie }: { serie: 'anp' | 'igp_di' }) {
  const cobertura = useQuery({ queryKey: chaves.cobertura, queryFn: buscarCobertura })
  const periodo = cobertura.data?.[serie]
  if (!periodo) return null
  const formatar = serie === 'anp' ? data : mesAno
  return (
    <div className="faixa">
      <span>
        Período: <strong>{periodo.de ? `${formatar(periodo.de)} a ${formatar(periodo.ate)}` : 'sem dados'}</strong>
      </span>
      <span>
        <strong>{numero(String(periodo.registros), 0)} registros</strong>
      </span>
      <span>
        <span className="marca-manual" />
        <strong>{periodo.manuais} {periodo.manuais === 1 ? 'valor manual' : 'valores manuais'}</strong>
      </span>
    </div>
  )
}
