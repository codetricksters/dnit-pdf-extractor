import { expect, test } from '@playwright/test'
import { completarCadastro } from './apoio'

test('região fixada num registro aparece marcada no Cálculo', async ({ page, request }) => {
  const id = await completarCadastro(request)

  await page.goto(`/contratos/${id}/medicoes`)
  const linha = page.getByRole('row').filter({ hasText: 'Aquisição de CAP 50/70' }).first()
  await linha.getByRole('button', { name: /Editar/ }).click()
  await page.getByLabel('Região ANP — CAP').selectOption('Sul')
  await page.getByRole('button', { name: 'Salvar' }).click()
  await expect(page.getByText('CAP: Sul *').first()).toBeVisible()

  await page.getByRole('link', { name: 'Cálculo e exportação' }).click()
  await expect(page.locator('tr.linha-regiao-manual').first()).toBeVisible()
  await expect(page.getByText('Região ANP definida no registro: Aquisição de CAP — Sul')).toBeVisible()

  // Devolve a fixture ao estado anterior, que os specs seguintes esperam.
  await page.getByRole('link', { name: 'Medições', exact: true }).click()
  await page.getByRole('row').filter({ hasText: 'CAP: Sul *' }).first()
    .getByRole('button', { name: /Editar/ }).click()
  await page.getByLabel('Região ANP — CAP').selectOption('Seguir o contrato')
  await page.getByRole('button', { name: 'Salvar' }).click()
  await expect(page.getByText('CAP: Sul *')).toHaveCount(0)
})
