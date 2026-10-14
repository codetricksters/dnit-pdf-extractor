import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { chaves } from '../../api/chaves'
import { alterarMedicao, incluirMedicao } from '../../api/contratos'
import { ErroApi } from '../../api/erros'
import { buscarCobertura } from '../../api/indices'
import { aposMedicao } from '../../api/invalidar'
import type { ItemMedicao } from '../../api/tipos'
import { CampoMesAno } from '../../components/CampoMesAno'
import { Dialogo } from '../../components/Dialogo'
import { MensagemErro } from '../../components/MensagemErro'
import { mesAno } from '../../lib/formato'
import {
  errosPorCampo, montarCorpo, valoresIniciais, type CampoMedicao, type ValoresMedicao,
} from './medicao'

interface Props {
  contratoId: number
  item?: ItemMedicao // ausente = inclusão
  aoFechar: () => void
}

// Inclusão e edição de um registro. Num registro do PDF, código e mês ficam
// travados: são a chave com que o reprocessamento o reencontra.
export function DialogoMedicao({ contratoId, item, aoFechar }: Props) {
  const qc = useQueryClient()
  const [erroGeral, setErroGeral] = useState<unknown>(null)
  const cobertura = useQuery({ queryKey: chaves.cobertura, queryFn: buscarCobertura })
  const { control, register, handleSubmit, setError, formState } = useForm<ValoresMedicao>({
    defaultValues: valoresIniciais(item),
  })
  // Lido no render para o formState assinar a mudança dos campos sujos.
  const sujos = formState.dirtyFields
  const travado = item !== undefined && item.origem !== 'manual'
  const regioes = cobertura.data?.regioes ?? []

  const salvar = useMutation({
    mutationFn: (v: ValoresMedicao) =>
      item
        ? alterarMedicao(contratoId, item.id, montarCorpo(v, sujos))
        : incluirMedicao(contratoId, montarCorpo(v)),
    onSuccess: async () => {
      await aposMedicao(qc, contratoId)
      aoFechar()
    },
    onError: (erro) => {
      if (!(erro instanceof ErroApi) || Object.keys(erro.campos).length || !erro.detail) {
        return setErroGeral(erro)
      }
      setErroGeral(null)
      for (const [campo, msg] of Object.entries(errosPorCampo(erro.detail))) {
        if (campo === 'geral') setErroGeral(new ErroApi(erro.status, msg!))
        else setError(campo as CampoMedicao, { type: 'servidor', message: msg })
      }
    },
  })

  function erro(campo: CampoMedicao) {
    const msg = formState.errors[campo]?.message
    return msg ? <p className="erro-campo" id={`erro-medicao-${campo}`}>{msg}</p> : null
  }
  function aria(campo: CampoMedicao) {
    const tem = Boolean(formState.errors[campo])
    return { 'aria-invalid': tem || undefined, 'aria-describedby': tem ? `erro-medicao-${campo}` : undefined }
  }

  return (
    <Dialogo
      titulo={item ? 'Editar registro' : 'Incluir registro'}
      aoFechar={aoFechar}
      acoes={
        <>
          <button type="button" className="btn" onClick={aoFechar}>Cancelar</button>
          <button type="submit" form="form-medicao" className="btn btn-primary" disabled={salvar.isPending}>
            Salvar
          </button>
        </>
      }
    >
      <form id="form-medicao" onSubmit={handleSubmit((v) => salvar.mutate(v))}>
        <MensagemErro erro={erroGeral} />
        <div className="field">
          <label className="field-label" htmlFor="medicao-mes">Mês da medição</label>
          {travado ? (
            <p id="medicao-mes">{mesAno(item.mes)}</p>
          ) : (
            <Controller
              name="mes"
              control={control}
              render={({ field }) => (
                <CampoMesAno
                  id="medicao-mes"
                  valor={field.value}
                  aoMudar={field.onChange}
                  invalido={Boolean(formState.errors.mes)}
                  descritoPor={formState.errors.mes ? 'erro-medicao-mes' : undefined}
                />
              )}
            />
          )}
          {erro('mes')}
        </div>
        <div className="field">
          <label className="field-label" htmlFor="medicao-codigo">Código</label>
          <input id="medicao-codigo" className="input" disabled={travado} {...register('codigo')} {...aria('codigo')} />
          {erro('codigo')}
        </div>
        <div className="field">
          <label className="field-label" htmlFor="medicao-descricao">Descrição</label>
          <input id="medicao-descricao" className="input" {...register('descricao_pdf')} {...aria('descricao_pdf')} />
          {erro('descricao_pdf')}
        </div>
        <div className="field">
          <label className="field-label" htmlFor="medicao-valor">Valor PI líquido</label>
          <input id="medicao-valor" className="input" inputMode="decimal" {...register('valor_pi')} {...aria('valor_pi')} />
          {erro('valor_pi')}
        </div>
        <div className="field">
          <label className="field-label" htmlFor="medicao-fator">Fator</label>
          <input id="medicao-fator" className="input" inputMode="decimal" {...register('fator')} {...aria('fator')} />
          {erro('fator')}
        </div>
        {(['regiao_cap', 'regiao_emulsoes'] as const).map((campo) => (
          <div className="field" key={campo}>
            <label className="field-label" htmlFor={`medicao-${campo}`}>
              {campo === 'regiao_cap' ? 'Região ANP — CAP' : 'Região ANP — Emulsões'}
            </label>
            <select id={`medicao-${campo}`} className="input" {...register(campo)} {...aria(campo)}>
              <option value="">Seguir o contrato</option>
              {regioes.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            {erro(campo)}
          </div>
        ))}
      </form>
    </Dialogo>
  )
}
