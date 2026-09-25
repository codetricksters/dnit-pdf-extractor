import { useSyncExternalStore } from 'react'

// Estado "sem conexão com o servidor", compartilhado por toda a aplicação:
// qualquer requisição que falhe por rede liga o aviso, e a primeira que
// responder desliga.

let offline = false
const ouvintes = new Set<() => void>()

function avisar() {
  for (const ouvinte of ouvintes) ouvinte()
}

function assinar(ouvinte: () => void) {
  ouvintes.add(ouvinte)
  return () => ouvintes.delete(ouvinte)
}

export function marcarOffline() {
  if (!offline) {
    offline = true
    avisar()
  }
}

export function marcarOnline() {
  if (offline) {
    offline = false
    avisar()
  }
}

// Para os testes: cada teste começa online.
export function reiniciarConexao() {
  offline = false
  avisar()
}

export function useOffline(): boolean {
  return useSyncExternalStore(assinar, () => offline)
}
