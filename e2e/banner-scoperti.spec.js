/**
 * banner-scoperti.spec.js — «di queste non hai detto niente».
 *
 * Il promemoria in fondo alla griglia (passo 4, sotto-passo 6): le attività
 * rimaste senza ore E senza stato. Quello che c'è da provare non è come si
 * disegna il banner, ma QUANDO una riga ci entra e quando ne esce — e sono
 * decisioni che dipendono dallo stato vivo del form (le modifiche non ancora
 * salvate) e da quello che il server rimanda dopo il salvataggio. Un giro vero
 * attraversa tutte e due.
 *
 * I task su cui scrive sono T902 e T903 (`dati_prova.py`), dentro la settimana
 * e assegnati a Helena: le ore vere non si toccano.
 */
import { test, expect } from '@playwright/test'
import { UTENTI, statoAuth } from './utenti.js'
import { GRIGLIA, riga, metti, salva } from './griglia.js'

test.describe.configure({ mode: 'serial' })

const DA_STATO = 'T902'     // si spiega con lo stato, senza ore
const DA_ORE = 'T903'       // si spiega mettendoci le ore

const banner = (page) => page.locator('[data-banner-scoperti]')

/** I nomi elencati nel banner. `evaluateAll` non aspetta niente: si aspetta
 *  prima il banner, o su una pagina appena caricata si legge una lista vuota e
 *  la si scambia per «non c'è nessuno da spiegare». */
const elencati = async (page) => {
  await expect(banner(page)).toBeVisible()
  return page.locator('[data-vai-riga]')
    .evaluateAll((n) => n.map((x) => x.innerText.replace(' →', '').trim()))
}

test.describe('il banner delle attività senza spiegazione', () => {
  test.use({ storageState: statoAuth(UTENTI.helena) })

  test('su una settimana ancora vuota non compare', async ({ page }) => {
    // Ogni riga di una settimana intonsa è senza ore e senza stato: elencarle
    // tutte all'apertura non è un promemoria, è un rimprovero. Il banner
    // aspetta che nella settimana ci sia qualcosa.
    await page.goto(GRIGLIA)
    await expect(page.locator('[data-sintesi]')).toBeVisible()
    await page.getByRole('button', { name: /Settimana scorsa/ }).click()
    await expect(page.locator('[data-totale-settimana="0"]')).toBeVisible()
    await expect(banner(page)).toHaveCount(0)
  })

  test('un’attività senza ore né stato è nell’elenco, e il suo bottone ci porta', async ({ page }) => {
    await page.goto(GRIGLIA)
    await expect(banner(page)).toBeVisible()

    const nomi = await elencati(page)
    expect(nomi).toContain('[prova e2e] Da spiegare con lo stato')
    expect(nomi).toContain('[prova e2e] Da spiegare con le ore')

    // Le righe in SOLA LETTURA non sono roba di cui Helena debba rendere conto:
    // non ci entrano mai. (Vengono dallo scenario sottotask.)
    expect(nomi).not.toContain('[PROVA] Parte di Roberto')
    expect(nomi).not.toContain('ore sul task, prima della scomposizione')
    expect(nomi.some((n) => n.startsWith('[PROVA] Pezzo poi annullato'))).toBe(false)

    // Il bottone porta alla riga e lascia il fuoco sulla tendina dello stato,
    // che è la domanda appena fatta.
    await page.locator(`[data-vai-riga="task:${DA_STATO}"]`).click()
    await expect(riga(page, 'task', DA_STATO).locator('select[aria-label^="Stato"]')).toBeFocused()
  })

  test('si spiega con lo STATO, senza ore: esce dall’elenco e non ci torna', async ({ page }) => {
    await page.goto(GRIGLIA)
    const quanti = Number(await banner(page).getAttribute('data-banner-scoperti'))

    const r = riga(page, 'task', DA_STATO)
    await r.locator('select[aria-label^="Stato"]').selectOption('Bloccato')
    await r.locator('input[aria-label^="Nota"]').fill('aspetto il cliente')

    // Subito, senza salvare: l'elenco è vivo.
    expect(await elencati(page)).not.toContain('[prova e2e] Da spiegare con lo stato')
    await expect(banner(page)).toHaveAttribute('data-banner-scoperti', String(quanti - 1))

    await salva(page)
    await page.reload()
    await expect(page.locator('[data-sintesi]')).toBeVisible()
    // Riletto dal server: un fermo dichiarato resta una spiegazione.
    expect(await elencati(page)).not.toContain('[prova e2e] Da spiegare con lo stato')
    await expect(r.locator('select[aria-label^="Stato"]')).toHaveValue('Bloccato')
  })

  test('si spiega con le ORE: esce dall’elenco', async ({ page }) => {
    await page.goto(GRIGLIA)
    expect(await elencati(page)).toContain('[prova e2e] Da spiegare con le ore')

    await riga(page, 'task', DA_ORE).locator('select[aria-label^="Stato"]').selectOption('In corso')
    await metti(page, 'task', DA_ORE, 0, 'mattina', 1)
    expect(await elencati(page)).not.toContain('[prova e2e] Da spiegare con le ore')

    await salva(page)
    await page.reload()
    expect(await elencati(page)).not.toContain('[prova e2e] Da spiegare con le ore')
  })

  test('si salva anche con attività ancora mute, e il salvataggio lo dice', async ({ page }) => {
    // NIENTE FINESTRA DI CONFERMA: il salvataggio passa e basta. Playwright
    // scarta da sé i dialoghi non gestiti, quindi se ne comparisse uno il
    // salvataggio verrebbe annullato e questo test fallirebbe — è la sua
    // seconda ragione di esistere.
    await page.goto(GRIGLIA)
    const restano = Number(await banner(page).getAttribute('data-banner-scoperti'))
    expect(restano).toBeGreaterThan(0)

    // Una modifica qualunque su una riga già spiegata, per avere cosa salvare.
    await riga(page, 'task', DA_ORE).locator('input[aria-label^="Nota"]').fill('avanti così')
    await salva(page)

    // Il promemoria torna nella barra di salvataggio, dove lo vede anche chi ha
    // premuto Salva senza mai scendere in fondo alla griglia.
    await expect(page.getByText(/attività rest\w+ senza ore e senza stato/)).toBeVisible()
    await expect(banner(page)).toBeVisible()
  })
})
