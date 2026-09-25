import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'

const IGP_DI = fileURLToPath(new URL('../../tests/fixtures/igp_di.xlsx', import.meta.url))

test('importar o IGP-DI mantendo um valor manual em conflito', async ({ page }) => {
  await page.goto('/indices/igp-di')

  // O seed gravou fev/2023 = 1144,271; a correção manual o troca.
  await page.getByRole('button', { name: 'Editar IGP-DI fev/2023' }).click()
  const campo = page.getByLabel('IGP-DI fev/2023', { exact: true })
  await campo.fill('1.150,5')
  await campo.press('Enter')
  const celula = page.getByRole('button', { name: 'Editar IGP-DI fev/2023' })
  await expect(celula).toHaveText(/1\.150,5/)

  await page.getByRole('button', { name: 'Importar' }).click()
  const dialogo = page.getByRole('dialog')
  await dialogo.getByLabel('Arquivo').setInputFiles(IGP_DI)
  await dialogo.getByRole('button', { name: 'Ver prévia' }).click()

  const conflitos = dialogo.locator('.cartao', { hasText: 'Seus valores manuais em conflito' })
  await expect(conflitos).toContainText('1')
  await expect(conflitos).toHaveClass(/warn/)
  const conflito = dialogo.getByRole('row').filter({ hasText: 'fev/2023' })
  await expect(conflito).toContainText('1.150,5')
  await expect(conflito).toContainText('1.144,271')

  await dialogo.getByRole('button', { name: 'Gravar e manter meus valores manuais' }).click()
  await expect(dialogo.getByText('Importação gravada.')).toBeVisible()
  await expect(dialogo).toContainText('1 valor manual preservado')
  await dialogo.getByRole('button', { name: 'Fechar' }).click()

  await expect(celula).toHaveText(/1\.150,5/)
})
