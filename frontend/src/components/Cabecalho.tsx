import type { ReactNode } from 'react'

interface Props {
  titulo: ReactNode
  subtitulo?: ReactNode
  trilha?: ReactNode
  acoes?: ReactNode
}

export function Cabecalho({ titulo, subtitulo, trilha, acoes }: Props) {
  return (
    <div className="page-head">
      <div>
        {trilha && <div className="page-crumb">{trilha}</div>}
        <h1 className="page-title">{titulo}</h1>
        {subtitulo && <p className="page-subtitle">{subtitulo}</p>}
      </div>
      {acoes && <div className="page-actions">{acoes}</div>}
    </div>
  )
}
