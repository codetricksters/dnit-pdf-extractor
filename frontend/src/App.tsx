import { Navigate, Route, Routes } from 'react-router'
import { NaoEncontrado } from './components/NaoEncontrado'
import { Shell } from './components/Shell'
import { PaginaCatalogo } from './pages/catalogo/PaginaCatalogo'
import { AbaCadastro } from './pages/contrato/AbaCadastro'
import { AbaCalculo } from './pages/contrato/AbaCalculo'
import { AbaMedicoes } from './pages/contrato/AbaMedicoes'
import { PaginaContrato } from './pages/contrato/PaginaContrato'
import { ListaContratos } from './pages/contratos/ListaContratos'
import { GradeAnp } from './pages/indices/GradeAnp'
import { GradeIgpDi } from './pages/indices/GradeIgpDi'
import { PaginaIndices } from './pages/indices/PaginaIndices'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<ListaContratos />} />
        <Route path="contratos" element={<ListaContratos />} />
        <Route path="contratos/:id" element={<PaginaContrato />}>
          <Route path="cadastro" element={<AbaCadastro />} />
          <Route path="medicoes" element={<AbaMedicoes />} />
          <Route path="calculo" element={<AbaCalculo />} />
        </Route>
        <Route path="catalogo" element={<PaginaCatalogo />} />
        <Route path="indices" element={<PaginaIndices />}>
          <Route index element={<Navigate to="anp" replace />} />
          <Route path="anp" element={<GradeAnp />} />
          <Route path="igp-di" element={<GradeIgpDi />} />
        </Route>
        <Route path="*" element={<NaoEncontrado />} />
      </Route>
    </Routes>
  )
}
