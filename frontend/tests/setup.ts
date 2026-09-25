import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { servidor } from './servidor'

process.env.TZ = 'UTC'

beforeAll(() => servidor.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  servidor.resetHandlers()
})
afterAll(() => servidor.close())
