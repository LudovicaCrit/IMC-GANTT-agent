/**
 * letture-intatte.spec.js — «togliere il vecchio mondo non ha spento le luci».
 *
 * Ogni passo della rimozione (5.2 il frontend, 5.3 la porta, 5.4 il motore, e
 * poi 5.5-5.6 i campi e le colonne) cancella qualcosa che secondo la
 * ricognizione nessuno leggeva. «Secondo la ricognizione» è la parte fragile:
 * un aggancio nascosto non si vede col grep se passa da un `import *`, da un
 * getattr, o da una colonna che un serializzatore legge in blocco.
 *
 * Questo spec è la rete. Non prova cosa rispondono — lo fanno gli altri — ma
 * CHE rispondano: un colpo secco su tutte le letture dell'applicazione, per
 * accorgersi subito se una cancellazione ne ha spenta una. Costa pochi secondi
 * e va riletto a ogni sotto-passo del 5.
 *
 * Il SAL è in lista di proposito: è il lettore più goloso di dati-consuntivo di
 * tutta l'applicazione, quello che serializza la fotografia di un progetto.
 * Se un drop gli toglie una colonna da sotto, lo dice per primo.
 */
import { test, expect } from '@playwright/test'
import { UTENTI, statoAuth } from './utenti.js'

/** Le letture di chi supervisiona: quasi tutte sono manager-only. */
const DA_MANAGER = [
  '/api/consuntivi/settimana',
  '/api/gantt/strutturato',
  '/api/economia/margini',
  '/api/tasks',
  '/api/progetti',
  '/api/fasi/P002',
  '/api/sal/P002',
  '/api/risorse/carico',
  '/api/attivita-interne',
  '/api/home/dashboard',
]

test.describe('le letture dell’applicazione rispondono', () => {
  test.describe('da manager', () => {
    test.use({ storageState: statoAuth(UTENTI.ludovica) })

    for (const url of DA_MANAGER) {
      test(`GET ${url}`, async ({ request }) => {
        const r = await request.get(url)
        expect(r.status(), await r.text()).toBe(200)
      })
    }
  })

  test.describe('da utente normale', () => {
    test.use({ storageState: statoAuth(UTENTI.helena) })

    test('GET /api/consuntivi/me', async ({ request }) => {
      const r = await request.get('/api/consuntivi/me')
      expect(r.status()).toBe(200)
      const me = await r.json()
      // Non solo 200: il payload ha ancora le parti da cui la griglia dipende.
      expect(me).toHaveProperty('settimana')
      expect(me).toHaveProperty('settimane_disponibili')
      expect(Array.isArray(me.task_settimana)).toBe(true)
    })

    test('GET /api/consuntivi/settimana è 403 per lui, non 500', async ({ request }) => {
      // La sua vista è /me. Il 403 è una regola, non un guasto: se diventasse
      // 500 vorrebbe dire che il dispatch sul ruolo si è rotto.
      expect((await request.get('/api/consuntivi/settimana')).status()).toBe(403)
    })
  })
})
