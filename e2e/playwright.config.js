import { defineConfig } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { PORTA_BACKEND, PORTA_FRONTEND, URL_BACKEND, URL_FRONTEND } from './indirizzi.js'

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
    baseURL: URL_FRONTEND,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    locale: 'it-IT',
    timezoneId: 'Europe/Rome',
  },
  webServer: [
    {
      command: `${PYTHON} -m uvicorn main:app --port ${PORTA_BACKEND}`,
      cwd: path.join(RADICE, 'backend'),
      url: `${URL_BACKEND}/api/salute`,
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: `npx vite --port ${PORTA_FRONTEND} --strictPort`,
      cwd: path.join(RADICE, 'frontend'),
      url: URL_FRONTEND,
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
})
