import { useEffect, useId, useRef, type ReactNode } from 'react'

interface Props {
  titulo: string
  aoFechar: () => void
  acoes: ReactNode
  children: ReactNode
}

// Modal simples: Esc e o fundo fecham; o foco entra no diálogo ao abrir.
export function Dialogo({ titulo, aoFechar, acoes, children }: Props) {
  const idTitulo = useId()
  const caixa = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const primeiro = caixa.current?.querySelector<HTMLElement>('input, select, textarea')
    ;(primeiro ?? caixa.current)?.focus()
  }, [])

  return (
    <div
      className="dialogo-fundo"
      onMouseDown={(e) => e.target === e.currentTarget && aoFechar()}
      onKeyDown={(e) => e.key === 'Escape' && aoFechar()}
    >
      <div ref={caixa} className="dialogo" role="dialog" aria-modal="true" aria-labelledby={idTitulo} tabIndex={-1}>
        <h2 id={idTitulo} className="dialogo-titulo">
          {titulo}
        </h2>
        <div className="dialogo-corpo">{children}</div>
        <div className="dialogo-acoes">{acoes}</div>
      </div>
    </div>
  )
}
