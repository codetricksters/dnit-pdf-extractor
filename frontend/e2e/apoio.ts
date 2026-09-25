import type { APIRequestContext } from '@playwright/test'
import { expect } from '@playwright/test'

export const NUMERO = '99 99999/2099'

export async function contratoId(request: APIRequestContext): Promise<number> {
  const resposta = await request.get('/api/v1/contratos', { params: { numero: NUMERO } })
  expect(resposta.ok()).toBe(true)
  const [contrato] = await resposta.json()
  return contrato.id
}

// O mesmo cadastro que o spec 01 preenche pela tela; idempotente.
export async function completarCadastro(request: APIRequestContext): Promise<number> {
  const id = await contratoId(request)
  const resposta = await request.patch(`/api/v1/contratos/${id}`, {
    data: {
      contratada: 'CONSTRUTORA FICTÍCIA LTDA',
      edital: '999/2099-99',
      rodovia: 'BR-999',
      trecho: 'Trecho fictício',
      subtrecho: 'Subtrecho fictício',
      segmento: 'km 0,0 ao km 10,0',
      extensao: '10.0',
      regioes: { CAP: 'Nordeste', EMULSOES: 'Nordeste' },
    },
  })
  expect(resposta.ok()).toBe(true)
  return id
}
