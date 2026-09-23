import { defineConfig } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const QUI = path.dirname(fileURLToPath(import.meta.url))
const RADICE = path.resolve(QUI, '..')
const PYTHON = path.join(RADICE, '.venv', 'bin', 'python')

/**
 * La verifica accende da sé i due server e li spegne alla fine. `reuseExisting`
 * lascia lavorare chi ha già backend e frontend aperti mentre sviluppa: se la
 * porta risponde, Playwright non ne avvia un secondo.
 *
 * `workers: 1` non è prudenza generica: i test di questo repo scrivono sullo
 * STESSO database di sviluppo e sugli stessi due task di prova. In parallelo si
 * pesterebbero i piedi.
 */
export default defineConfig({
  testDir: QUI,
  timeout: 30_000,
  workers: 1,
  fullyParallel: false,
  reporter: [['list']],
  globalSetup: path.join(QUI, 'apparecchia.js'),
  globalTeardown: path.join(QUI, 'sparecchia.js'),
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    locale: 'it-IT',
    timezoneId: 'Europe/Rome',
  },
  webServer: [
    {
      command: `${PYTHON} -m uvicorn main:app --port 8000`,
      cwd: path.join(RADICE, 'backend'),
      url: 'http://localhost:8000/api/agent/status',
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: 'npx vite --port 3000',
      cwd: path.join(RADICE, 'frontend'),
      url: 'http://localhost:3000',
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
})
