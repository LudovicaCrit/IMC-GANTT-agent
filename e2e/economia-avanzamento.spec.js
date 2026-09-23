/**
 * economia-avanzamento.spec.js — la scheda che nessuno apriva.
 *
 * PERCHÉ ESISTE. La scheda «Avanzamento» dell'Economia usava un componente
 * `<Gauge>` che non era importato e non esisteva in nessun file del frontend.
 * La build passava — Vite non risolve i nomi dei componenti a build time — e al
 * click partiva un `ReferenceError: Gauge is not defined` che smontava l'intero
 * albero React: schermata nera. Era così da chissà quando, e non se n'era
 * accorto nessuno per una ragione sola: **nessun test apriva quella scheda**.
 *
 * Quindi il primo test qui sotto non verifica una regola di dominio, verifica
 * che la pagina esista. Sembra poco ed è il buco da cui è passato tutto il
 * resto: dentro quella scheda invisibile c'erano un «agente» che dava il verde
 * a chi aveva bruciato il 322% del budget, un quadrante duplicato che si
 * colorava in due modi sullo stesso numero, e 24 progetti interni a «€0 ·
 * valore contratto».
 *
 * `pageerror` è la rete: qualunque eccezione non catturata durante il rendering
 * fa fallire il test, anche se il DOM per caso contenesse ancora qualcosa.
 */
import { test, expect } from '@playwright/test'
import { UTENTI, statoAuth } from './utenti.js'

const ECONOMIA = '/economia'

/** Apre l'Economia raccogliendo ogni eccezione di rendering. */
async function apriEconomia(page) {
  const errori = []
  page.on('pageerror', (e) => errori.push(String(e).split('\n')[0]))
  await page.goto(ECONOMIA)
  await expect(page.getByText('Costi e Margini')).toBeVisible()
  return errori
}

test.describe('Economia — la scheda Avanzamento', () => {
  test.use({ storageState: statoAuth(UTENTI.ludovica) })

  test('si apre, e non è più una pagina bianca', async ({ page }) => {
    const errori = await apriEconomia(page)
    await page.getByRole('button', { name: /Avanzamento/ }).click()

    // La prova che il rendering è arrivato in fondo: i quadranti ci sono.
    await expect(page.locator('[data-gauge]').first()).toBeVisible()
    expect(errori, 'nessuna eccezione durante il rendering').toEqual([])

    // E la pagina ha ancora un contenuto: la schermata nera era body vuoto.
    const testo = await page.locator('body').innerText()
    expect(testo.length).toBeGreaterThan(200)
    expect(testo).toContain('Economia')
  })

  test('due quadranti per progetto, non tre, e senza gemelli', async ({ page }) => {
    await apriEconomia(page)
    await page.getByRole('button', { name: /Avanzamento/ }).click()
    await expect(page.locator('[data-gauge]').first()).toBeVisible()

    const etichette = await page.locator('[data-gauge]')
      .evaluateAll((n) => n.map((x) => x.getAttribute('data-gauge')))
    const distinte = [...new Set(etichette)]
    expect(distinte.sort()).toEqual(['Avanzamento temporale', 'Budget ore consumato'])
    // Ogni scheda ne ha due: il conto totale dev'essere il doppio dei progetti.
    expect(etichette.length).toBe(distinte.length * (etichette.length / 2))

    // Il quadrante duplicato e la terza comparsa dello stesso numero: via.
    await expect(page.getByText('Budget Utilizzato')).toHaveCount(0)
    await expect(page.getByText('Budget usato', { exact: true })).toHaveCount(0)
  })

  test('niente più «🤖 Agente»', async ({ page }) => {
    // Era un semaforo travestito da parere, e col segno al contrario.
    await apriEconomia(page)
    await page.getByRole('button', { name: /Avanzamento/ }).click()
    await expect(page.locator('[data-gauge]').first()).toBeVisible()

    await expect(page.getByText('Agente:')).toHaveCount(0)
    await expect(page.getByText('procede in linea con le tempistiche')).toHaveCount(0)
    await expect(page.getByText('Monitorare')).toHaveCount(0)
  })

  test('solo progetti commerciali: nessun «€0 · valore contratto»', async ({ page }) => {
    // La scheda Margini esclude gli interni per tipologia; questa faceva
    // altrimenti, e mostrava 24 corsi e attività interne con un contratto a
    // zero. Adesso i due universi coincidono.
    await apriEconomia(page)
    const commerciali = await page.evaluate(async () => {
      const r = await fetch('/api/economia/margini', { credentials: 'include' })
      return (await r.json()).progetti.map((p) => p.nome)
    })

    await page.getByRole('button', { name: /Avanzamento/ }).click()
    await expect(page.locator('[data-gauge]').first()).toBeVisible()

    const mostrati = await page.locator('h3').evaluateAll((n) => n.map((x) => x.innerText))
    expect(mostrati.length).toBeGreaterThan(0)
    for (const nome of mostrati) {
      expect(commerciali, `«${nome}» non è fra i progetti commerciali`).toContain(nome)
    }
    // Nessun valore-contratto azzerato in pagina.
    expect(await page.locator('body').innerText()).not.toContain('€0 ')
  })

  test('i numeri dei quadranti sono quelli veri', async ({ page }) => {
    // `Budget ore consumato` = ore_consuntivate / budget_ore, e deve
    // coincidere con quello che l'API dice, progetto per progetto.
    await apriEconomia(page)
    const progetti = await page.evaluate(async () => {
      const r = await fetch('/api/progetti', { credentials: 'include' })
      return (await r.json())
        .filter((p) => p.stato === 'In esecuzione' && p.tipologia !== 'interna')
        .map((p) => ({
          id: p.id, nome: p.nome,
          atteso: p.budget_ore > 0 ? (p.ore_consuntivate / p.budget_ore) * 100 : 0,
        }))
    })
    expect(progetti.length).toBeGreaterThan(0)

    await page.getByRole('button', { name: /Avanzamento/ }).click()
    await expect(page.locator('[data-gauge]').first()).toBeVisible()

    for (const p of progetti) {
      const scheda = page.locator(`[data-progetto="${p.id}"]`)
      await expect(scheda, `la scheda di «${p.nome}» è in pagina`).toHaveCount(1)
      const letto = await scheda.locator('[data-gauge="Budget ore consumato"]')
        .getAttribute('data-valore')
      expect(Math.abs(Number(letto) - p.atteso), `budget ore di «${p.nome}»`).toBeLessThan(0.2)
    }
  })

  test('la scheda Margini è rimasta com’era', async ({ page }) => {
    const errori = await apriEconomia(page)
    for (const etichetta of ['Valore portafoglio', 'Costo sostenuto', 'Margine reale',
                             'Progetti commerciali', 'Andamento per società']) {
      await expect(page.getByText(etichetta, { exact: true }).first()).toBeVisible()
    }
    // Le tre letture del margine, aprendo il dettaglio del primo progetto.
    await page.locator('tbody button').first().click()
    await expect(page.getByText('Le tre letture del margine')).toBeVisible()
    expect(errori).toEqual([])
  })
})
