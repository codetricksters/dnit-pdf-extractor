import { NavLink, Outlet } from 'react-router'
import { Cabecalho } from '../../components/Cabecalho'

export function PaginaIndices() {
  return (
    <>
      <Cabecalho
        titulo="Índices"
        subtitulo="Preços semanais da ANP e IGP-DI, comuns a todos os contratos. Clique numa célula para editar."
      />
      <nav className="tabs" aria-label="Séries">
        <NavLink to="/indices/anp" className="tab">ANP semanal</NavLink>
        <NavLink to="/indices/igp-di" className="tab">IGP-DI mensal</NavLink>
      </nav>
      <div className="mt-md">
        <Outlet />
      </div>
    </>
  )
}
