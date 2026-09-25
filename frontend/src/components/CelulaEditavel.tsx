import { useState, type KeyboardEvent } from 'react'
import { ErroApi } from '../api/erros'
import type { Decimal } from '../api/tipos'
import { ConfirmarDialogo } from './ConfirmarDialogo'
import { exato, paraDecimal } from '../lib/formato'

interface Props {
  rotulo: string
  valor: Decimal | null | undefined
  formatar: (v: Decimal) => string
  // Texto quando não há valor; o ANP distingue "sem registro" de "sem cotação".
  vazio?: string
  manual?: boolean
  titulo?: string
  // Vazio grava nulo (semana ANP sem cotação) em vez de ser ignorado.
  permiteVazio?: boolean
  aoSalvar: (valor: Decimal | null) => Promise<unknown>
  // Vazio numa célula com valor apaga o registro (IGP-DI).
  aoApagar?: () => Promise<unknown>
}

const ILEGIVEL = 'Número ilegível; use vírgula decimal, como 1.234,56.'

// Célula de grade editável no lugar: clique abre o campo, Enter grava, Esc
// cancela. Se a API recusar, a célula volta ao valor do banco e mostra o motivo.
export function CelulaEditavel({ rotulo, valor, formatar, vazio = '—', manual, titulo, permiteVazio, aoSalvar, aoApagar }: Props) {
  const [editando, setEditando] = useState(false)
  const [texto, setTexto] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [gravando, setGravando] = useState(false)
  const [apagando, setApagando] = useState(false)

  // Vazio numa célula com valor é destrutivo (apaga o registro ou grava nulo
  // por cima de um valor existente) e por isso pede confirmação; a mesma
  // função serve ao ANP (aoSalvar(null)) e ao IGP-DI (aoApagar).
  const acaoApagar = aoApagar ?? (permiteVazio ? () => aoSalvar(null) : undefined)

  function abrir() {
    setTexto(valor ? exato(valor) : '')
    setErro(null)
    setEditando(true)
  }

  async function executar(acao: () => Promise<unknown>) {
    setGravando(true)
    try {
      await acao()
      setEditando(false)
    } catch (e) {
      setEditando(false)
      setErro(e instanceof ErroApi ? e.detail : 'Não foi possível gravar.')
    } finally {
      setGravando(false)
      setApagando(false)
    }
  }

  function confirmar() {
    const limpo = texto.trim()
    if (!limpo) {
      if (valor && acaoApagar) {
        setEditando(false)
        setApagando(true)
        return
      }
      if (permiteVazio) return executar(() => aoSalvar(null))
      setEditando(false)
      return
    }
    const decimal = paraDecimal(limpo)
    if (decimal === null) {
      setErro(ILEGIVEL)
      return
    }
    return executar(() => aoSalvar(decimal))
  }

  function apagar() {
    if (acaoApagar) void executar(acaoApagar)
  }

  function tecla(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault()
      void confirmar()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      e.stopPropagation()
      setErro(null)
      setEditando(false)
    }
  }

  const classes = ['celula', 'num', manual ? 'manual' : '', valor ? '' : 'vazia'].filter(Boolean).join(' ')
  return (
    <td className={classes} title={titulo}>
      {editando ? (
        <input
          className="input"
          aria-label={rotulo}
          value={texto}
          disabled={gravando}
          autoFocus
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={tecla}
          onBlur={() => !gravando && setEditando(false)}
        />
      ) : (
        <button type="button" className="celula-botao" aria-label={`Editar ${rotulo}`} onClick={abrir}>
          {valor ? formatar(valor) : vazio}
        </button>
      )}
      {erro && <span className="celula-erro" role="alert">{erro}</span>}
      {apagando && (
        <ConfirmarDialogo
          titulo="Apagar valor?"
          mensagem={`O valor de ${rotulo} sai do banco.`}
          rotuloConfirmar="Apagar"
          perigoso
          pendente={gravando}
          aoCancelar={() => setApagando(false)}
          aoConfirmar={apagar}
        />
      )}
    </td>
  )
}
