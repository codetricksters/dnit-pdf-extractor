import { pedir } from './client'
import type { Cobertura } from './tipos'

const BASE = '/api/v1/indices'

export const buscarCobertura = () => pedir<Cobertura>(`${BASE}/cobertura`)
