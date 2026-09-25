import { setupServer } from 'msw/node'

// Sem handlers globais: cada teste declara o que o backend responde, e
// qualquer requisição não declarada falha o teste (setup.ts).
export const servidor = setupServer()
