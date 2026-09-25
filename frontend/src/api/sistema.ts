import { caminhoCom, pedir } from './client'
import type { Backup, Template } from './tipos'

const c = encodeURIComponent

export const listarTemplates = () => pedir<Template[]>('/admin/templates')

export function enviarTemplate(arquivo: File, { observacao, ativar }: { observacao?: string; ativar: boolean }) {
  const form = new FormData()
  form.append('arquivo', arquivo)
  if (observacao) form.append('observacao', observacao)
  form.append('ativar', String(ativar))
  return pedir<{ id: number; ativo: boolean }>('/admin/templates', { metodo: 'POST', form })
}

export const ativarTemplate = (id: number) => pedir<unknown>(`/admin/templates/${id}/ativar`, { metodo: 'POST' })

export const excluirTemplate = (id: number) => pedir<unknown>(`/admin/templates/${id}`, { metodo: 'DELETE' })

export const urlTemplate = (id: number) => caminhoCom(`/admin/templates/${id}/download`)

export const listarBackups = () => pedir<Backup[]>('/admin/backups')

export const gerarBackup = () => pedir<{ nome: string; tamanho: number }>('/admin/backups', { metodo: 'POST' })

export function enviarBackup(arquivo: File) {
  const form = new FormData()
  form.append('arquivo', arquivo)
  return pedir<{ nome: string }>('/admin/backups/upload', { metodo: 'POST', form })
}

export function restaurarBackup(nome: string, confirmacao: string) {
  const form = new FormData()
  form.append('confirmacao', confirmacao)
  return pedir<{ restaurado: string; seguranca: string }>(`/admin/backups/${c(nome)}/restaurar`, { metodo: 'POST', form })
}

export const excluirBackup = (nome: string) => pedir<unknown>(`/admin/backups/${c(nome)}`, { metodo: 'DELETE' })

export const urlBackup = (nome: string) => caminhoCom(`/admin/backups/${c(nome)}/download`)
