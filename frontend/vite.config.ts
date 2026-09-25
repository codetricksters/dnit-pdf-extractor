import react from '@vitejs/plugin-react'
import type { ProxyOptions } from 'vite'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'

// Prefixos que pertencem ao FastAPI. Em produção o próprio FastAPI serve o
// SPA; em desenvolvimento o Vite repassa estes caminhos para ele.
const PREFIXOS = ['/api', '/jobs', '/admin', '/reequilibrio', '/static', '/dashboard', '/docs', '/redoc', '/openapi.json']

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const alvo = env.VITE_BACKEND_URL || 'http://localhost:8000'
  const proxy: Record<string, ProxyOptions> = Object.fromEntries(
    PREFIXOS.map((prefixo) => [prefixo, { target: alvo, changeOrigin: true }]),
  )
  // GET /upload no navegador é a tela do SPA; POST /upload é o envio dos PDFs.
  proxy['/upload'] = {
    target: alvo,
    changeOrigin: true,
    bypass: (req) =>
      req.method === 'GET' && req.headers.accept?.includes('text/html') ? '/index.html' : undefined,
  }
  return {
    plugins: [react()],
    server: { port: 5173, proxy },
    test: {
      environment: 'jsdom',
      setupFiles: ['./tests/setup.ts'],
      include: ['tests/**/*.test.{ts,tsx}'],
    },
  }
})
