import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { itemAtivo } from '../src/components/Shell'
import { renderApp } from './render'

describe('casca', () => {
  it('mostra os itens dos três grupos do menu', () => {
    renderApp('/rota-que-nao-existe')
    for (const nome of ['Contratos', 'Upload de PDFs', 'Catálogo de produtos', 'Índices ANP / IGP-DI', 'Templates', 'Backups']) {
      expect(screen.getByRole('link', { name: nome })).toBeInTheDocument()
    }
    expect(screen.getByText('Trabalho')).toBeInTheDocument()
    expect(screen.getByText('Bases globais')).toBeInTheDocument()
    expect(screen.getByText('Sistema')).toBeInTheDocument()
  })

  it('rota desconhecida mostra "Não encontrado" dentro da casca', () => {
    renderApp('/rota-que-nao-existe')
    expect(screen.getByRole('heading', { name: 'Não encontrado' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Menu principal' })).toBeInTheDocument()
  })

  it('marca o item ativo pelo prefixo da rota', () => {
    expect(itemAtivo(['/', '/contratos'], '/')).toBe(true)
    expect(itemAtivo(['/', '/contratos'], '/contratos/12/calculo')).toBe(true)
    expect(itemAtivo(['/', '/contratos'], '/catalogo')).toBe(false)
    expect(itemAtivo(['/indices'], '/indices/igp-di')).toBe(true)
    expect(itemAtivo(['/sistema/templates'], '/sistema/backups')).toBe(false)
  })
})
