import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router'
import { AppRoutes } from '../src/App'
import { criarQueryClient } from '../src/api/queryClient'

function LocalAtual() {
  const local = useLocation()
  return <output data-testid="local">{local.pathname + local.search}</output>
}

// A aplicação inteira numa rota, com um QueryClient novo por teste.
export function renderApp(rota = '/', opcoesUsuario?: Parameters<typeof userEvent.setup>[0]) {
  const qc = criarQueryClient()
  const usuario = userEvent.setup(opcoesUsuario)
  const resultado = render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[rota]}>
        <AppRoutes />
        <LocalAtual />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { ...resultado, usuario, qc }
}
