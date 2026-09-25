import { useQuery } from '@tanstack/react-query'
import { chaves } from '../../api/chaves'
import { buscarCobertura } from '../../api/indices'
import { data, mesAno, numero } from '../../lib/formato'

// O que há no banco para a série da aba: período, quantidade e quantos valores
// foram digitados à mão (esses a importação preserva).
//
// GET /indices/cobertura não é por produto — o backend sempre soma a série ANP
// do CAP (indices_repo.cobertura), mesmo que a grade acima esteja mostrando
// outro produto. Em vez de um endpoint novo, o rótulo diz explicitamente de
// qual produto é essa faixa.
export function FaixaCobertura({ serie }: { serie: 'anp' | 'igp_di' }) {
  const cobertura = useQuery({ queryKey: chaves.cobertura, queryFn: buscarCobertura })
  const periodo = cobertura.data?.[serie]
  if (!periodo) return null
  const formatar = serie === 'anp' ? data : mesAno
  const rotulo = serie === 'anp' ? 'Período (CAP)' : 'Período'
  return (
    <div className="faixa">
      <span>
        {rotulo}: <strong>{periodo.de ? `${formatar(periodo.de)} a ${formatar(periodo.ate)}` : 'sem dados'}</strong>
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
