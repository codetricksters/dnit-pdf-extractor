import { expect, test } from '@playwright/test'
import { completarCadastro } from './apoio'

test('criar um produto, associar o 60112 e ver a linha no cálculo', async ({ page, request }) => {
  const id = await completarCadastro(request)

  await page.goto('/catalogo')
  await page.getByRole('button', { name: 'Novo produto' }).click()
  const novo = page.getByRole('dialog')
  await novo.getByLabel('Descrição na planilha').fill('CAP 50/70 do teste ponta a ponta')
  await novo.getByRole('button', { name: 'Salvar' }).click()
  // O produto criado fica selecionado.
  await expect(page.getByRole('heading', { name: 'CAP 50/70 do teste ponta a ponta' })).toBeVisible()

  await page.getByRole('button', { name: 'Adicionar códigos' }).click()
  const adicionar = page.getByRole('dialog')
  await adicionar.getByLabel('Buscar código ou descrição').fill('60112')
  await adicionar.getByRole('button', { name: 'Buscar' }).click()
  const linha = adicionar.getByRole('row').filter({ hasText: '60112' })
  await expect(linha).toContainText('em Aquisição de CAP 50/70')
  await linha.getByRole('checkbox').check()
  await adicionar.getByRole('button', { name: 'Associar selecionados (1)' }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByRole('cell', { name: '60112', exact: true })).toBeVisible()

  await page.goto(`/contratos/${id}/calculo`)
  const tabela = page.getByRole('table')
  await expect(tabela).toContainText('CAP 50/70 do teste ponta a ponta')
  // O produto antigo ficou sem código e sai do cálculo, sem bloquear nada.
  await expect(tabela).not.toContainText('Aquisição de CAP 50/70')
})
