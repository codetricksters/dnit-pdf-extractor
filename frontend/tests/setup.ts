import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { reiniciarConexao } from '../src/api/conexao'
import { servidor } from './servidor'

process.env.TZ = 'UTC'

beforeAll(() => servidor.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  servidor.resetHandlers()
  reiniciarConexao()
})
afterAll(() => servidor.close())
