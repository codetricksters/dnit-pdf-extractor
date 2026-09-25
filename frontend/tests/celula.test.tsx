import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ErroApi } from '../src/api/erros'
import { CelulaEditavel } from '../src/components/CelulaEditavel'
import { exato } from '../src/lib/formato'

function montar(props: Partial<Parameters<typeof CelulaEditavel>[0]> = {}) {
  const aoSalvar = vi.fn().mockResolvedValue(undefined)
  render(
    <table>
      <tbody>
        <tr>
          <CelulaEditavel rotulo="IGP-DI fev/2023" valor="1000.5" formatar={exato} aoSalvar={aoSalvar} {...props} />
        </tr>
      </tbody>
    </table>,
  )
  return { aoSalvar, usuario: userEvent.setup() }
}

describe('CelulaEditavel', () => {
  it('mostra o valor formatado e, ao clicar, um campo com ele', async () => {
    const { usuario } = montar()
    await usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' }))
    expect(screen.getByLabelText('IGP-DI fev/2023')).toHaveValue('1.000,5')
  })

  it('Enter grava o número no formato da API', async () => {
    const { usuario, aoSalvar } = montar()
    await usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' }))
    await usuario.clear(screen.getByLabelText('IGP-DI fev/2023'))
    await usuario.type(screen.getByLabelText('IGP-DI fev/2023'), '1.234,56{Enter}')
    expect(aoSalvar).toHaveBeenCalledWith('1234.56')
    expect(screen.queryByLabelText('IGP-DI fev/2023')).not.toBeInTheDocument()
  })

  it('Esc cancela sem gravar', async () => {
    const { usuario, aoSalvar } = montar()
    await usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' }))
    await usuario.type(screen.getByLabelText('IGP-DI fev/2023'), '9{Escape}')
    expect(aoSalvar).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' })).toHaveTextContent('1.000,5')
  })

  it('texto ilegível não chega à API', async () => {
    const { usuario, aoSalvar } = montar()
    await usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' }))
    await usuario.clear(screen.getByLabelText('IGP-DI fev/2023'))
    await usuario.type(screen.getByLabelText('IGP-DI fev/2023'), 'abc{Enter}')
    expect(aoSalvar).not.toHaveBeenCalled()
    expect(screen.getByText('Número ilegível; use vírgula decimal, como 1.234,56.')).toBeInTheDocument()
  })

  it('recusa da API volta ao valor anterior e mostra o motivo', async () => {
    const aoSalvar = vi.fn().mockRejectedValue(new ErroApi(422, 'O IGP-DI deve ser positivo.'))
    const { usuario } = montar({ aoSalvar })
    await usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' }))
    await usuario.clear(screen.getByLabelText('IGP-DI fev/2023'))
    await usuario.type(screen.getByLabelText('IGP-DI fev/2023'), '-1{Enter}')
    expect(await screen.findByText('O IGP-DI deve ser positivo.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' })).toHaveTextContent('1.000,5')
  })

  it('vazio numa célula com valor pede confirmação antes de apagar', async () => {
    const aoApagar = vi.fn().mockResolvedValue(undefined)
    const primeiro = montar({ aoApagar })
    await primeiro.usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' }))
    await primeiro.usuario.clear(screen.getByLabelText('IGP-DI fev/2023'))
    await primeiro.usuario.keyboard('{Enter}')
    expect(aoApagar).not.toHaveBeenCalled()
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    await primeiro.usuario.click(screen.getByRole('button', { name: 'Apagar' }))
    expect(aoApagar).toHaveBeenCalled()
    expect(primeiro.aoSalvar).not.toHaveBeenCalled()
  })

  it('cancelar o diálogo de apagar não grava nada e mantém o valor', async () => {
    const aoApagar = vi.fn().mockResolvedValue(undefined)
    const { usuario, aoSalvar } = montar({ aoApagar })
    await usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' }))
    await usuario.clear(screen.getByLabelText('IGP-DI fev/2023'))
    await usuario.keyboard('{Enter}')
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    await usuario.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(aoApagar).not.toHaveBeenCalled()
    expect(aoSalvar).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' })).toHaveTextContent('1.000,5')
  })

  it('vazio com permiteVazio numa célula com valor pede confirmação e grava nulo ao confirmar', async () => {
    const { usuario, aoSalvar } = montar({ permiteVazio: true })
    await usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' }))
    await usuario.clear(screen.getByLabelText('IGP-DI fev/2023'))
    await usuario.keyboard('{Enter}')
    expect(aoSalvar).not.toHaveBeenCalled()
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    await usuario.click(screen.getByRole('button', { name: 'Apagar' }))
    expect(aoSalvar).toHaveBeenCalledWith(null)
  })

  it('vazio com permiteVazio numa célula já vazia grava nulo direto, sem confirmação', async () => {
    const { usuario, aoSalvar } = montar({ valor: null, permiteVazio: true })
    await usuario.click(screen.getByRole('button', { name: 'Editar IGP-DI fev/2023' }))
    await usuario.keyboard('{Enter}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(aoSalvar).toHaveBeenCalledWith(null)
  })
})
