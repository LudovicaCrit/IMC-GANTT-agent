/**
 * pagina-unica.spec.js — una strada sola per la Consuntivazione.
 *
 * Passo 5.1: `/consuntivazione` porta alla GRIGLIA a ore. La pagina a cursore
 * esiste ancora sul disco ma non ha più una rotta; i due indirizzi di cantiere
 * (`/consuntivazione/ore` e `/consuntivazione-new`) reindirizzano invece di
 * dare 404, perché sono stati in giro per mesi e stanno nei preferiti.
 *
 * QUELLO CHE C'È DA PROVARE non è il rendering della griglia — lo fanno già gli
 * altri spec — ma che OGNI STRADA ci arrivi: i due redirect, la voce di menu, i
 * due link sparsi nell'app. Un routing si rompe sempre dal lato che nessuno
 * guarda, ed è il link dentro una pagina che si apre una volta al mese.
 *
 * E che chi supervisiona non ci abbia rimesso niente: manager e PM devono
 * trovare la vista del gruppo dov'era, nel guscio, accanto alla propria
 * settimana.
 *
 * In fondo, la porta di scrittura: dal passo 5.3 `POST /api/consuntivi/salva`
 * non esiste più e ne resta una sola. Sta in questo file perché è la stessa
 * cosa vista dall'altro lato — una strada sola per arrivarci, una sola per
 * scrivere.
 */
import { test, expect } from '@playwright/test'
import { UTENTI, statoAuth } from './utenti.js'
import { GRIGLIA } from './griglia.js'

const url = (page) => new URL(page.url()).pathname

/** La griglia è caricata: la sintesi in cima e la matrice ci sono. */
async function griglia(page) {
  await expect(page.locator('[data-sintesi]')).toBeVisible()
  await expect(page.locator('[data-totale-settimana]')).toBeVisible()
}

test.describe('da utente normale (Helena)', () => {
  test.use({ storageState: statoAuth(UTENTI.helena) })

  test('/consuntivazione è la griglia a ore', async ({ page }) => {
    await page.goto(GRIGLIA)
    await griglia(page)
    await expect(page.getByText('la tua settimana, a ore')).toBeVisible()
    // E non è più la pagina a cursore.
    await expect(page.getByText('ecco cosa era in programma per te')).toHaveCount(0)
  })

  test('i due indirizzi di cantiere reindirizzano, non danno 404', async ({ page }) => {
    for (const vecchio of ['/consuntivazione/ore', '/consuntivazione-new']) {
      await page.goto(vecchio)
      await griglia(page)
      expect(url(page), `${vecchio} deve finire su /consuntivazione`).toBe('/consuntivazione')
    }
    // `replace`: il tasto Indietro non deve ripescare l'indirizzo vecchio e
    // rimbalzare avanti e indietro.
    await page.goBack()
    expect(url(page)).not.toBe('/consuntivazione-new')
  })

  test('la voce di menu porta alla griglia', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('link', { name: /Consuntivazione/ }).click()
    expect(url(page)).toBe('/consuntivazione')
    await griglia(page)
  })

  test('il link della Home porta alla griglia', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /da compilare →|Apri la consuntivazione →/ }).click()
    expect(url(page)).toBe('/consuntivazione')
    await griglia(page)
  })

  test('nessun traghetto residuo fra le due pagine', async ({ page }) => {
    await page.goto(GRIGLIA)
    await griglia(page)
    await expect(page.getByRole('link', { name: /Consuntivazione a cursore/ })).toHaveCount(0)
    await expect(page.getByRole('link', { name: /Griglia a ore/ })).toHaveCount(0)
  })
})

test.describe('da manager (Ludovica)', () => {
  test.use({ storageState: statoAuth(UTENTI.ludovica) })

  test('chi supervisiona trova la sua settimana E la vista del gruppo', async ({ page }) => {
    await page.goto(GRIGLIA)

    // Di default la propria settimana, manager compreso: anche chi supervisiona
    // ha delle ore da dichiarare.
    await griglia(page)

    // Lo scambio è quello del guscio, e la vista del gruppo è dov'era.
    await page.getByRole('button', { name: /Tutta l'azienda/ }).click()
    await expect(page.getByText('Compilati', { exact: true })).toBeVisible()
    await expect(page.getByText('Mancanti', { exact: true })).toBeVisible()
    await expect(page.locator('[data-sintesi]')).toHaveCount(0)

    // …e si torna indietro.
    await page.getByRole('button', { name: /La mia settimana/ }).click()
    await griglia(page)
  })

  test('il link di Attività interne porta alla griglia', async ({ page }) => {
    // Pagina manager-only: il link vive lì, e lì nessuno guarda mai.
    await page.goto('/attivita-interne')
    await page.getByRole('button', { name: 'Consuntivazione', exact: true }).click()
    expect(url(page)).toBe('/consuntivazione')
    await griglia(page)
  })
})

test.describe('la porta di scrittura è una sola', () => {
  test.use({ storageState: statoAuth(UTENTI.helena) })

  test('POST /consuntivi/salva non esiste più: 404 netto', async ({ request }) => {
    // 404 e non 500: la porta è tolta, non rotta. Un chiamante fantasma deve
    // vedere «questo indirizzo non c'è», non un errore che viene da dentro il
    // motore — è la ragione per cui il 5.3 (la porta) viene prima del 5.4
    // (il motore).
    const r = await request.post('/api/consuntivi/salva', {
      data: { dipendente_id: 'D004', ore_per_task: {}, stati_per_task: {} },
    })
    expect(r.status()).toBe(404)
  })

  test('POST /consuntivi/salva-blocchi scrive come prima', async ({ request }) => {
    // Il path nuovo non è stato toccato: un giro di scrittura completo deve
    // passare identico. Si scrive e si rilegge da /me, che è l'unico modo di
    // dire «è arrivato davvero in database».
    const me = await (await request.get('/api/consuntivi/me')).json()
    const r = await request.post('/api/consuntivi/salva-blocchi', {
      data: {
        settimana: me.settimana,
        unita: [{
          tipo: 'task', id: 'T902', stato_dichiarato: 'In corso',
          blocchi: [{ giorno: me.settimana, ore: 0.5 }],
        }],
      },
    })
    expect(r.status(), await r.text()).toBe(200)
    expect((await r.json()).salvato).toBe(true)

    const dopo = await (await request.get('/api/consuntivi/me')).json()
    const t902 = dopo.task_settimana.find((t) => t.task_id === 'T902')
    expect(t902.blocchi).toEqual([{ giorno: me.settimana, ore: 0.5 }])
    expect(t902.stato_dichiarato).toBe('In corso')
  })
})
