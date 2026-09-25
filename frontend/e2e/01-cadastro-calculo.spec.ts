import { expect, test } from '@playwright/test'
import { NUMERO } from './apoio'

test('completar o cadastro, calcular, baixar e simular outra região', async ({ page }) => {
  await page.goto('/contratos')
  // Cadastro incompleto: o link do contrato abre o Cadastro.
  await page.getByRole('link', { name: NUMERO }).click()
  await expect(page).toHaveURL(/\/contratos\/\d+\/cadastro$/)

  await page.getByLabel('Região ANP — CAP').selectOption('Nordeste')
  await page.getByLabel('Região ANP — Emulsões').selectOption('Nordeste')
  const campos: [string, string][] = [
    ['Contratada', 'CONSTRUTORA FICTÍCIA LTDA'],
    ['Edital', '999/2099-99'],
    ['Rodovia', 'BR-999'],
    ['Trecho', 'Trecho fictício'],
    ['Subtrecho', 'Subtrecho fictício'],
    ['Segmento', 'km 0,0 ao km 10,0'],
    ['Extensão (km)', '10,0'],
  ]
  for (const [rotulo, valor] of campos) {
    await page.getByLabel(rotulo, { exact: true }).fill(valor)
  }
  await page.getByRole('button', { name: 'Salvar' }).click()
  await expect(page.getByText('Cadastro salvo.')).toBeVisible()
  await expect(page.getByText('Parâmetros completos')).toBeVisible()

  await page.getByRole('link', { name: 'Cálculo e exportação' }).click()
  const tabela = page.getByRole('table')
  await expect(tabela).toContainText('Aquisição de CAP 50/70')
  await expect(tabela).toContainText('Aquisição de Emulsão RR-1C')
  await expect(tabela.getByRole('row').filter({ hasText: 'Total geral' })).toBeVisible()

  const baixar = page.getByRole('link', { name: 'Baixar planilha (.xlsx)' })
  const [planilha] = await Promise.all([page.waitForEvent('download'), baixar.click()])
  expect(planilha.suggestedFilename()).toMatch(/\.xlsx$/)
  expect(planilha.suggestedFilename()).not.toContain('SIMULACAO')

  await page.getByLabel('Região CAP').selectOption('Sul')
  await expect(page).toHaveURL(/regiao_cap=Sul/)
  await expect(page.getByText('Simulação — o cadastro não muda.')).toBeVisible()
  const [simulada] = await Promise.all([page.waitForEvent('download'), baixar.click()])
  expect(simulada.suggestedFilename()).toContain('SIMULACAO')
  expect(simulada.suggestedFilename()).toContain('CAP-Sul')

  // A simulação não tocou no cadastro.
  await page.getByRole('link', { name: 'Cadastro', exact: true }).click()
  await expect(page.getByLabel('Região ANP — CAP')).toHaveValue('Nordeste')
})
