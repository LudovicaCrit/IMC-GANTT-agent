/**
 * sottotask-griglia.spec.js — il mondo-scomposto nella griglia a ore.
 *
 * Gira sullo scenario di `scenario_sottotask.py`, che apparecchia.js crea e
 * sparecchia.js porta via. Senza quello il database di sviluppo ha ZERO
 * sottotask, e tutto ciò che questo file prova non avrebbe righe su cui
 * esistere: il ramo dei pezzi di `task_settimana_dipendente`, la risoluzione
 * dell'assegnatario (C2), N21 sui pezzi, M8/M9, e nella pagina il ramo di
 * `costruisciGruppi` che monta intestazione + righe-pezzo.
 *
 * Tutte le righe che tocca stanno sotto il progetto `[PROVA]`: un fallimento
 * qui non può aver sporcato dati veri.
 */
import { test, expect } from '@playwright/test'
import { UTENTI, statoAuth } from './utenti.js'
import { GRIGLIA, riga, totaleRiga, metti, salva } from './griglia.js'

test.describe.configure({ mode: 'serial' })

// Gli id dei pezzi sono autoincrement: si leggono dal DOM a partire dal nome,
// che è l'unica cosa stabile fra una creazione dello scenario e l'altra.
const pezzo = (page, nome) => page.locator('tr', { hasText: nome }).first()

test.describe('il mondo scomposto, da Helena', () => {
  test.use({ storageState: statoAuth(UTENTI.helena) })

  test('T950 · scomposto normale: intestazione, ore-del-task in sola lettura, pezzi compilabili', async ({ page }) => {
    await page.goto(GRIGLIA)
    await expect(page.locator('[data-sintesi]')).toBeVisible()

    // Il task NON è una riga compilabile: è un'intestazione, e le ore vanno sui pezzi.
    await expect(page.locator('tr', { hasText: '[PROVA] 1 · Task scomposto normale' }).first())
      .toContainText('scomposto in pezzi')
    await expect(riga(page, 'task', 'T950')).toHaveCount(0)

    // M8 — l'ora messa sul task PRIMA della scomposizione resta visibile, in
    // sola lettura: sta nei totali, quindi deve stare anche nella matrice.
    const prima = riga(page, 'task-prima', 'T950')
    await expect(prima).toContainText('ore sul task, prima della scomposizione')
    await expect(prima).toContainText('si compila sui pezzi')
    await expect(totaleRiga(page, 'task-prima', 'T950')).toHaveText('1')

    // I tre pezzi ci sono, tutti compilabili (due per eredità, uno per override).
    for (const nome of ['Analisi del tracciato', 'Stesura del modulo', 'Collaudo con il cliente']) {
      await expect(pezzo(page, nome).locator('select[aria-label^="Stato"]')).toBeVisible()
    }

    // Il pezzo già dichiarato si riapre PIENO: ore, stato, nota, resta.
    const stesura = pezzo(page, 'Stesura del modulo')
    await expect(stesura.locator('select[aria-label^="Stato"]')).toHaveValue('In corso')
    await expect(stesura.locator('input[aria-label^="Ore che restano"]')).toHaveValue('3,5')
    await expect(stesura.locator('input[aria-label^="Nota"]')).toHaveValue('Prima metà del modulo scritta.')
    await expect(stesura.locator('[data-totale-riga]')).toHaveText('3,5')
  })

  test('T950 · si dichiara sul pezzo, e alla riapertura le ore sono lì', async ({ page }) => {
    await page.goto(GRIGLIA)
    const analisi = pezzo(page, 'Analisi del tracciato')
    const id = (await analisi.getAttribute('data-riga')).split(':')[1]

    await analisi.locator('select[aria-label^="Stato"]').selectOption('In corso')
    await metti(page, 'sott', id, 2, 'mattina', 2)     // mercoledì mattina
    await expect(totaleRiga(page, 'sott', id)).toHaveText('2')
    await salva(page)

    await page.reload()
    await expect(page.locator('[data-sintesi]')).toBeVisible()
    await expect(totaleRiga(page, 'sott', id)).toHaveText('2')
    await expect(riga(page, 'sott', id).locator('select[aria-label^="Stato"]')).toHaveValue('In corso')
  })

  test('T951 · C2: il task è di un collega, il pezzo mio si compila', async ({ page }) => {
    await page.goto(GRIGLIA)

    // Il task compare pur non essendo suo: ci arriva dal pezzo affidato a lei.
    await expect(page.locator('tr', { hasText: '[PROVA] 2 · Task di un collega' }).first())
      .toContainText('scomposto in pezzi')

    const diRoberto = pezzo(page, 'Parte di Roberto')
    await expect(diRoberto).toContainText('sola lettura · di un collega')
    await expect(diRoberto.locator('select[aria-label^="Stato"]')).toHaveCount(0)

    const mio = pezzo(page, 'Parte affidata a Helena')
    const id = (await mio.getAttribute('data-riga')).split(':')[1]
    await mio.locator('select[aria-label^="Stato"]').selectOption('In corso')
    await metti(page, 'sott', id, 1, 'pomeriggio', 1)
    await salva(page)

    await page.reload()
    await expect(totaleRiga(page, 'sott', id)).toHaveText('1')
    // E il pezzo del collega resta com'era: non si scrive per conto suo.
    await expect(pezzo(page, 'Parte di Roberto')).toContainText('sola lettura · di un collega')
  })

  test('T952 · N21 sui pezzi: l’annullato con ore resta visibile, in sola lettura', async ({ page }) => {
    await page.goto(GRIGLIA)

    const annullato = pezzo(page, 'Pezzo poi annullato, con ore')
    await expect(annullato).toContainText('sola lettura · annullato')
    await expect(annullato.locator('[data-totale-riga]')).toHaveText('1,5')
    // Le sue ore stanno nei totali: una riga che non si vedesse li smentirebbe.
    await expect(annullato.locator('select[aria-label^="Stato"]')).toHaveCount(0)

    // L'altro annullato, che non ha ore, non compare affatto.
    await expect(page.locator('tr', { hasText: 'Pezzo poi annullato, senza ore' })).toHaveCount(0)
  })

  test.fixme('T952 · M9: col pezzo annullato-con-ore il task dovrebbe tornare compilabile', async ({ page }) => {
    // BUCO NOTO, lato frontend (`costruisciGruppi`), trovato accendendo questo
    // scenario. /me dice `modificabile: true` sul task T952 — per M9 un task i
    // cui pezzi sono tutti Annullati torna a essere unità di lavoro — ma la
    // pagina entra nel ramo scomposto per il solo fatto che `sottotask` non è
    // vuoto (ci sta dentro l'annullato con ore, per N21) e non disegna nessuna
    // riga compilabile per il task. Risultato: ore dichiarabili dal backend e
    // non dichiarabili dalla griglia.
    // Si toglie nel frontend, non qui: `scomposto` va deciso come lo decide il
    // backend (pezzi NON annullati), non su `pezzi.length`.
    await page.goto(GRIGLIA)
    await expect(riga(page, 'task', 'T952')).toBeVisible()
  })

  test('T953 · M9: tutti i pezzi annullati e niente ore → torna un task come gli altri', async ({ page }) => {
    await page.goto(GRIGLIA)

    // Nessuna intestazione, nessuna riga-pezzo: è una riga sola, compilabile.
    await expect(page.locator('tr', { hasText: 'Pezzo annullato A' })).toHaveCount(0)
    await expect(page.locator('tr', { hasText: 'Pezzo annullato B' })).toHaveCount(0)
    const t953 = riga(page, 'task', 'T953')
    await expect(t953).toBeVisible()
    await expect(t953).not.toContainText('scomposto in pezzi')

    await t953.locator('select[aria-label^="Stato"]').selectOption('In corso')
    await metti(page, 'task', 'T953', 0, 'pomeriggio', 0.5)
    await salva(page)

    await page.reload()
    await expect(totaleRiga(page, 'task', 'T953')).toHaveText('0,5')
  })
})
