import { QueryClient } from '@tanstack/react-query'

// Sem retentativa: erro de regra (4xx) não muda repetindo, e falta de conexão
// vira o aviso fixo com "Tentar de novo" (BannerConexao).
export function criarQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false, staleTime: 30_000 },
      mutations: { retry: false },
    },
  })
}
