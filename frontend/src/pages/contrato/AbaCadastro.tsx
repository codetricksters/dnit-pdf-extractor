import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useOutletContext } from 'react-router'
import { chaves } from '../../api/chaves'
import { atualizarContrato } from '../../api/contratos'
import { ErroApi } from '../../api/erros'
import { buscarCobertura } from '../../api/indices'
import { aposCadastro } from '../../api/invalidar'
import type { Contrato } from '../../api/tipos'
import { MensagemErro } from '../../components/MensagemErro'
import {
  CABECALHO, campoDoErro, montarPatch, PARAMETROS, pendenciasParametros, vaziosCabecalho,
  valoresIniciais, type CampoForm, type ValoresCadastro,
} from './cadastro'

function plural(n: number, um: string, varios: string) {
  return `${n} ${n === 1 ? um : varios}`
}

export function AbaCadastro() {
  const contrato = useOutletContext<Contrato>()
  const qc = useQueryClient()
  const cobertura = useQuery({ queryKey: chaves.cobertura, queryFn: buscarCobertura })
  const form = useForm<ValoresCadastro>({ defaultValues: valoresIniciais(contrato) })
  const { register, handleSubmit, reset, watch, setError, formState } = form
  const [erroGeral, setErroGeral] = useState<unknown>(null)
  const [salvo, setSalvo] = useState(false)

  // Contrato relido do banco (depois de salvar ou de outra aba): o formulário
  // passa a partir dele.
  useEffect(() => reset(valoresIniciais(contrato)), [contrato, reset])

  const salvar = useMutation({
    mutationFn: (v: ValoresCadastro) => atualizarContrato(contrato.id, montarPatch(v, formState.dirtyFields)),
    onSuccess: async (atualizado) => {
      qc.setQueryData(chaves.contrato(contrato.id), atualizado)
      reset(valoresIniciais(atualizado))
      setSalvo(true)
      await aposCadastro(qc, contrato.id)
    },
    onError: (erro, v) => {
      if (!(erro instanceof ErroApi)) return setErroGeral(erro)
      for (const [campo, msg] of Object.entries(campoDoErro(erro, v))) {
        if (campo === 'geral') setErroGeral(new ErroApi(erro.status, msg!))
        else setError(campo as CampoForm, { type: 'servidor', message: msg })
      }
    },
  })

  const valores = watch()
  const pendentes = pendenciasParametros(valores)
  const vazios = vaziosCabecalho(valores)
  const regioes = cobertura.data?.regioes ?? []

  function opcoesRegiao(atual: string) {
    const lista = atual && !regioes.includes(atual) ? [atual, ...regioes] : regioes
    return lista.map((r) => (
      <option key={r} value={r}>
        {r}
      </option>
    ))
  }

  function erroDo(campo: CampoForm) {
    const msg = formState.errors[campo]?.message
    return msg ? (
      <p className="erro-campo" id={`erro-${campo}`}>
        {msg}
      </p>
    ) : null
  }

  function atributosDeErro(campo: CampoForm) {
    const tem = !!formState.errors[campo]
    return { 'aria-invalid': tem || undefined, 'aria-describedby': tem ? `erro-${campo}` : undefined }
  }

  return (
    <form
      onSubmit={handleSubmit((v) => {
        setErroGeral(null)
        setSalvo(false)
        salvar.mutate(v)
      })}
    >
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2 className="panel-title">Parâmetros do cálculo</h2>
            <p className="panel-subtitle">Na exportação dá para simular outra região sem alterar este cadastro.</p>
          </div>
          <span className={pendentes ? 'badge badge-danger' : 'badge badge-ok'}>
            {pendentes ? `${plural(pendentes, 'pendente', 'pendentes')} — cálculo bloqueado` : 'Parâmetros completos'}
          </span>
        </div>
        <div className="panel-body field-grid">
          <div className="field">
            <label className="field-label" htmlFor="data_base">
              Data Base <span className="field-required" aria-hidden="true" />
            </label>
            <input id="data_base" type="month" className="input" {...register('data_base')} {...atributosDeErro('data_base')} />
            <p className="field-hint">Sugerida pelo PDF; mês e ano.</p>
            {erroDo('data_base')}
          </div>
          {PARAMETROS.slice(1).map(({ campo, rotulo }) => (
            <div className="field" key={campo}>
              <label className="field-label" htmlFor={campo}>
                {rotulo} <span className="field-required" aria-hidden="true" />
              </label>
              <select id={campo} className="input" {...register(campo)} {...atributosDeErro(campo)}>
                <option value="">Escolha a região</option>
                {opcoesRegiao(valores[campo])}
              </select>
              {erroDo(campo)}
            </div>
          ))}
        </div>
      </section>

      <section className="panel mt-md">
        <div className="panel-head">
          <div>
            <h2 className="panel-title">Cabeçalho da planilha</h2>
            <p className="panel-subtitle">Campos impressos no bloco de identificação do Reequilíbrio.</p>
          </div>
          <span className={vazios ? 'badge badge-warn' : 'badge badge-ok'}>
            {vazios ? `${plural(vazios, 'vazio', 'vazios')} — sairá com aviso` : 'Cabeçalho completo'}
          </span>
        </div>
        <div className="panel-body field-grid">
          <div className="field">
            <label className="field-label" htmlFor="numero_processo">
              Nº do processo
            </label>
            <input id="numero_processo" className="input" readOnly value={contrato.numero_processo ?? ''} />
            <p className="field-hint">Vem do PDF.</p>
          </div>
          {CABECALHO.map(({ campo, rotulo }) => (
            <div className="field" key={campo}>
              <label className="field-label" htmlFor={campo}>
                {rotulo}
              </label>
              <input
                id={campo}
                className="input"
                inputMode={campo === 'extensao' ? 'decimal' : undefined}
                {...register(campo)}
                {...atributosDeErro(campo)}
              />
              {erroDo(campo)}
            </div>
          ))}
        </div>
      </section>

      <MensagemErro erro={erroGeral} />
      <div className="barra mt-md">
        {salvo && !formState.isDirty && (
          <p className="status-message" role="status">
            Cadastro salvo.
          </p>
        )}
        <span className="espaco" />
        <button type="button" className="btn" disabled={!formState.isDirty || salvar.isPending} onClick={() => reset()}>
          Descartar
        </button>
        <button type="submit" className="btn btn-primary" disabled={!formState.isDirty || salvar.isPending}>
          Salvar
        </button>
      </div>
    </form>
  )
}
