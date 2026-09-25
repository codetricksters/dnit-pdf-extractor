import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { reiniciarConexao } from '../src/api/conexao'
import { servidor } from './servidor'

process.env.TZ = 'UTC'

// O ambiente jsdom substitui File/Blob/FormData pelos seus próprios: o
// FormData do jsdom só reconhece um valor como arquivo se ele for instância
// do *seu* Blob, então um upload real (input[type=file] -> FormData -> fetch)
// vira a string "[object File]" no corpo enviado, e o msw (que recebe a
// requisição via undici) não reconstrói um `File` compatível com o global
// jsdom. As classes do pacote `undici` são as mesmas que o runtime usa por
// baixo dos panos, então usá-las aqui faz o upload chegar ao handler do msw
// como um `File` de verdade.
const { Blob: BlobNativo, File: FileNativo } = await import('node:buffer')
const { fetch: fetchNativo, Headers: HeadersNativos, Request: RequestNativo, Response: ResponseNativo, FormData: FormDataNativa } =
  await import('undici')
globalThis.Blob = BlobNativo as unknown as typeof Blob
globalThis.File = FileNativo as unknown as typeof File
globalThis.FormData = FormDataNativa as unknown as typeof FormData
globalThis.Headers = HeadersNativos as unknown as typeof Headers
globalThis.Request = RequestNativo as unknown as typeof Request
globalThis.Response = ResponseNativo as unknown as typeof Response
globalThis.fetch = fetchNativo as unknown as typeof fetch

beforeAll(() => servidor.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  servidor.resetHandlers()
  reiniciarConexao()
})
afterAll(() => servidor.close())
