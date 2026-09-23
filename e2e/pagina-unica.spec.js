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
