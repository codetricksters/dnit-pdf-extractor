import { Route, Routes } from 'react-router'
import { NaoEncontrado } from './components/NaoEncontrado'
import { Shell } from './components/Shell'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route path="*" element={<NaoEncontrado />} />
      </Route>
    </Routes>
  )
}
