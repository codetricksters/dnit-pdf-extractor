import { fileURLToPath } from 'node:url'
import { defineConfig, devices } from '@playwright/test'

const PORTA = 8765
const RAIZ = fileURLToPath(new URL('..', import.meta.url))
const BANCO = process.env.DATABASE_URL_TEST ?? 'postgresql://dnit:dnit@localhost:5433/dnit_test'

export default defineConfig({
  testDir: 'e2e',
  // Os specs compartilham o banco e rodam em ordem de arquivo.
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: `http://localhost:${PORTA}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `uv run python scripts/preparar_e2e.py && uv run uvicorn main:app --port ${PORTA}`,
    cwd: RAIZ,
    url: `http://localhost:${PORTA}/api/v1/indices/cobertura`,
    // Sempre um servidor novo: é o preparar_e2e que zera o banco.
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      DATABASE_URL: BANCO,
      STORAGE_PATH: `${RAIZ}tmp/e2e-data`,
      BACKUP_INTERVAL_HOURS: '100000',
    },
  },
})
