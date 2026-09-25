import { Route, Routes } from 'react-router'
import { NaoEncontrado } from './components/NaoEncontrado'
import { Shell } from './components/Shell'
import { AbaCadastro } from './pages/contrato/AbaCadastro'
import { AbaCalculo } from './pages/contrato/AbaCalculo'
import { PaginaContrato } from './pages/contrato/PaginaContrato'
import { ListaContratos } from './pages/contratos/ListaContratos'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<ListaContratos />} />
        <Route path="contratos" element={<ListaContratos />} />
        <Route path="contratos/:id" element={<PaginaContrato />}>
          <Route path="cadastro" element={<AbaCadastro />} />
          <Route path="calculo" element={<AbaCalculo />} />
        </Route>
        <Route path="*" element={<NaoEncontrado />} />
      </Route>
    </Routes>
  )
}
