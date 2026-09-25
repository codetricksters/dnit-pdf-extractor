import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { chaves } from '../src/api/chaves'
import { marcarOffline } from '../src/api/conexao'
import { ErroApi } from '../src/api/erros'
import { aposCatalogo } from '../src/api/invalidar'
import { criarQueryClient } from '../src/api/queryClient'
import { BannerConexao } from '../src/components/BannerConexao'
import { ConfirmarDialogo } from '../src/components/ConfirmarDialogo'
import { MensagemErro } from '../src/components/MensagemErro'
import { servidor } from './servidor'

describe('ConfirmarDialogo', () => {
  it('só confirma depois de digitar o texto exigido', async () => {
    const usuario = userEvent.setup()
    const aoConfirmar = vi.fn()
    render(
      <ConfirmarDialogo
        titulo="Restaurar backup"
        mensagem="O banco atual será substituído."
        rotuloConfirmar="Restaurar"
        textoExigido="dnit_20260924.dump"
        perigoso
        aoConfirmar={aoConfirmar}
        aoCancelar={() => {}}
      />,
    )
    const botao = screen.getByRole('button', { name: 'Restaurar' })
    expect(botao).toBeDisabled()
    await usuario.type(screen.getByLabelText('Digite dnit_20260924.dump para confirmar'), 'dnit_2026')
    expect(botao).toBeDisabled()
    await usuario.type(screen.getByLabelText('Digite dnit_20260924.dump para confirmar'), '0924.dump')
    await usuario.click(botao)
    expect(aoConfirmar).toHaveBeenCalledOnce()
  })

  it('Esc cancela', async () => {
    const usuario = userEvent.setup()
    const aoCancelar = vi.fn()
    render(
      <ConfirmarDialogo titulo="Excluir" mensagem="Certeza?" rotuloConfirmar="Excluir"
        aoConfirmar={() => {}} aoCancelar={aoCancelar} />,
    )
    await usuario.keyboard('{Escape}')
    expect(aoCancelar).toHaveBeenCalledOnce()
  })
})

describe('MensagemErro', () => {
  it('mostra o detail como veio e a lista de erros', () => {
    render(<MensagemErro erro={new ErroApi(422, 'Arquivo inválido.', { erros: ['linha 3: mês ilegível'] })} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Arquivo inválido.')
    expect(screen.getByText('linha 3: mês ilegível')).toBeInTheDocument()
  })

  it('sem erro não renderiza nada', () => {
    const { container } = render(<MensagemErro erro={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('BannerConexao', () => {
  it('aparece sem conexão e "Tentar de novo" refaz as consultas ativas', async () => {
    const usuario = userEvent.setup()
    const qc = criarQueryClient()
    const refazer = vi.spyOn(qc, 'refetchQueries')
    render(
      <QueryClientProvider client={qc}>
        <BannerConexao />
      </QueryClientProvider>,
    )
    expect(screen.queryByText('Sem conexão com o servidor.')).not.toBeInTheDocument()
    marcarOffline()
    expect(await screen.findByText('Sem conexão com o servidor.')).toBeInTheDocument()
    await usuario.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    expect(refazer).toHaveBeenCalledWith({ type: 'active' })
  })
})

describe('invalidação', () => {
  it('aposCatalogo invalida produtos, códigos, medições e cálculos', async () => {
    servidor.use(http.get('*', () => HttpResponse.json([])))
    const qc = criarQueryClient()
    for (const chave of [chaves.produtos, chaves.codigos({}), chaves.medicoes(1, {}), chaves.calculo(1, {}), chaves.cobertura]) {
      qc.setQueryData(chave, [])
    }
    await aposCatalogo(qc)
    const invalida = (chave: readonly unknown[]) => qc.getQueryState(chave)?.isInvalidated
    expect(invalida(chaves.produtos)).toBe(true)
    expect(invalida(chaves.codigos({}))).toBe(true)
    expect(invalida(chaves.medicoes(1, {}))).toBe(true)
    expect(invalida(chaves.calculo(1, {}))).toBe(true)
    expect(invalida(chaves.cobertura)).toBe(false)
  })
})
