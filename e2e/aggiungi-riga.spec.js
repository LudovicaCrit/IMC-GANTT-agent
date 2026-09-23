/**
 * aggiungi-riga.spec.js — la verifica in browser di «Ho lavorato su altro»
 * (consuntivazione a ore, passo 4 sotto-passo 5).
 *
 * COSA PROVA, e perché in browser e non a unità. La regola che conta non è una
 * funzione: è «la lista offre esattamente ciò che il salvataggio accetterebbe,
 * e ciò che si salva torna alla riapertura». Sta metà nel filtro del client,
 * metà nel payload di /salva-blocchi e metà in N21 dentro /me — tre punti che
 * solo un giro vero attraversa tutti e tre.
 *
 * I test sono IN ORDINE e non parallelizzabili (`serial`): il primo guarda la
 * lista, il secondo ci salva sopra. Salvare per primo toglierebbe T900 dalla
 * lista (diventa una riga di /me) e il primo test non avrebbe più niente da
 * vedere. I dati di prova li mette e li toglie `dati_prova.py`, chiamato da
 * apparecchia.js / sparecchia.js.
 *
 * NESSUN TEST FA LOGIN: la sessione arriva già aperta da apparecchia.js
 * (`storageState`). Accedere a ogni test sfonderebbe il rate limit di
 * `/api/auth/login` — 5 al minuto — e i test in coda fallirebbero sulla pagina
 * di login, per un motivo che non ha niente a che vedere con quello che stanno
 * provando.
 */
import { test, expect } from '@playwright/test'
import { UTENTI, statoAuth } from './utenti.js'
import { GRIGLIA, riga as rigaUnita, totaleRiga, metti, apriPannello } from './griglia.js'

test.describe.configure({ mode: 'serial' })

// I task di prova (vedi dati_prova.py).
const T_ATTIVO = 'T900'     // su P002, progetto su cui Helena sta già lavorando
const T_ALTRO = 'T901'      // su P011, progetto non attivo questa settimana
// Già in griglia questa settimana: non devono comparire nella lista.
const GIA_IN_GRIGLIA = ['T015', 'T024', 'T026', 'T057', 'T063', 'T079', 'T091', 'T107']
// Suoi, ma con la finestra chiusa da mesi: fuori dall'orizzonte del mese.
const FUORI_ORIZZONTE = ['T004', 'T014', 'T020', 'T030', 'T043', 'T104', 'T109']

// Qui tutte le righe sono task: l'aiutante condiviso vuole anche il tipo.
const riga = (page, taskId) => rigaUnita(page, 'task', taskId)

test.describe('da utente normale (Helena)', () => {
  test.use({ storageState: statoAuth(UTENTI.helena) })

  test('la lista offre solo il lavoro proprio, dell’orizzonte, non già in griglia', async ({ page }) => {
    await page.goto(GRIGLIA)
    await expect(page.locator('[data-sintesi]')).toBeVisible()
    await apriPannello(page)

    // I due task di prova ci sono, e con loro il T112 vero (ottobre, nell'orizzonte).
    await expect(page.locator(`[data-aggiungi-task="${T_ATTIVO}"]`)).toBeVisible()
    await expect(page.locator(`[data-aggiungi-task="${T_ALTRO}"]`)).toBeVisible()
    await expect(page.locator('[data-aggiungi-task="T112"]')).toBeVisible()

    // Niente doppioni di ciò che la griglia già mostra.
    for (const id of GIA_IN_GRIGLIA) {
      await expect(page.locator(`[data-aggiungi-task="${id}"]`), `${id} è già in griglia`).toHaveCount(0)
    }
    // L'orizzonte del mese tiene fuori lo storico: sono suoi, ma finiti in primavera.
    for (const id of FUORI_ORIZZONTE) {
      await expect(page.locator(`[data-aggiungi-task="${id}"]`), `${id} è fuori orizzonte`).toHaveCount(0)
    }

    // Progetto + nome, non il solo nome del task.
    const lista = page.locator('[data-aggiungi-lista]')
    await expect(lista).toContainText('Framework Compliance 262')
    await expect(lista).toContainText('AIoT Industria 4.0 Tecnomat')

    // ORDINAMENTO: il progetto su cui lavora già sta in cima, anche se
    // alfabeticamente verrebbe dopo («AIoT…» < «Framework…»).
    const primoGruppo = lista.locator('> div').first()
    await expect(primoGruppo).toContainText('Framework Compliance 262')
    await expect(primoGruppo).toContainText('ci stai già lavorando')

    // Nessun task di altri: qui il backend già filtra (Helena è `user`), e la
    // lista non può che essere un sottoinsieme dei suoi.
    const miei = await page.evaluate(async () => {
      const r = await fetch('/api/tasks', { credentials: 'include' })
      return (await r.json()).map((t) => t.dipendente_id)
    })
    expect([...new Set(miei)]).toEqual([UTENTI.helena.dipendente])
  })

  test('un task fuori settimana: lo aggiungo, ci metto le ore, salvo e lo ritrovo', async ({ page }) => {
    await page.goto(GRIGLIA)
    await apriPannello(page)

    await page.locator(`[data-aggiungi-task="${T_ATTIVO}"]`).click()
    await expect(riga(page, T_ATTIVO)).toBeVisible()
    await expect(riga(page, T_ATTIVO)).toContainText('aggiunta da te')

    // Appena aggiunta non ha ore: l'avvertenza dice cosa succederebbe a salvarla così.
    await expect(page.locator(`[data-avvertenza="task:${T_ATTIVO}"]`))
      .toContainText('senza ore questa riga non tornerà')

    await riga(page, T_ATTIVO).locator('select[aria-label^="Stato"]').selectOption('In corso')
    await metti(page, 'task', T_ATTIVO, 0, 'mattina', 2)
    await metti(page, 'task', T_ATTIVO, 0, 'pomeriggio', 1.5)

    // Con le ore l'avvertenza sparisce: la riga tornerà da sola (N21).
    await expect(page.locator(`[data-avvertenza="task:${T_ATTIVO}"]`)).toHaveCount(0)
    await expect(totaleRiga(page, 'task', T_ATTIVO)).toHaveText('3,5')

    await page.getByRole('button', { name: 'Salva' }).click()
    await expect(page.getByText('✓ Salvato')).toBeVisible()

    // Riapertura vera: ricarico la pagina e le ore devono venire dal server.
    await page.reload()
    await expect(page.locator('[data-sintesi]')).toBeVisible()
    await expect(riga(page, T_ATTIVO)).toBeVisible()
    await expect(totaleRiga(page, 'task', T_ATTIVO)).toHaveText('3,5')
    // Non è più «aggiunta da te»: ora è una riga della settimana come le altre.
    await expect(riga(page, T_ATTIVO)).not.toContainText('aggiunta da te')
    // E non si può aggiungere una seconda volta.
    await apriPannello(page)
    await expect(page.locator(`[data-aggiungi-task="${T_ATTIVO}"]`)).toHaveCount(0)
  })

  test('solo stato e niente ore: avvisa, chiede conferma, e la riga non torna', async ({ page }) => {
    await page.goto(GRIGLIA)
    await apriPannello(page)
    await page.locator(`[data-aggiungi-task="${T_ALTRO}"]`).click()

    await riga(page, T_ALTRO).locator('select[aria-label^="Stato"]').selectOption('Bloccato')
    await riga(page, T_ALTRO).locator('input[aria-label^="Nota"]').fill('fermo, aspetto il committente')
    await expect(page.locator(`[data-avvertenza="task:${T_ALTRO}"]`)).toBeVisible()

    // PRIMO tentativo: si annulla la conferma → non si salva niente.
    page.once('dialog', (d) => {
      expect(d.message()).toContain('senza ore la riga non tornerà')
      d.dismiss()
    })
    await page.getByRole('button', { name: 'Salva' }).click()
    await expect(page.getByText('✓ Salvato')).toHaveCount(0)
    await expect(riga(page, T_ALTRO)).toBeVisible()

    // SECONDO tentativo: si conferma → si salva, e alla riapertura la riga non
    // c'è più. È la conseguenza di cui l'avvertenza parlava.
    page.once('dialog', (d) => d.accept())
    await page.getByRole('button', { name: 'Salva' }).click()
    await expect(page.getByText('✓ Salvato')).toBeVisible()
    await expect(riga(page, T_ALTRO)).toHaveCount(0)
  })

  test('una riga aggiunta per sbaglio si toglie', async ({ page }) => {
    await page.goto(GRIGLIA)
    await apriPannello(page)
    await page.locator('[data-aggiungi-task="T112"]').click()
    await expect(riga(page, 'T112')).toBeVisible()

    await riga(page, 'T112').locator('[data-togli-riga]').click()
    await expect(riga(page, 'T112')).toHaveCount(0)
    // E torna disponibile nella lista, che nel frattempo è rimasta aperta.
    await expect(page.locator('[data-aggiungi-task="T112"]')).toBeVisible()
  })
})

test.describe('da manager (Ludovica)', () => {
  test.use({ storageState: statoAuth(UTENTI.ludovica) })

  test('a un manager la lista offre comunque solo i task suoi', async ({ page }) => {
    // /api/tasks dà al manager l'azienda intera, ma /salva-blocchi è self-only e
    // senza deroghe: offrirgli il task di un altro sarebbe offrirgli un 400.
    await page.goto(GRIGLIA)
    await expect(page.locator('[data-sintesi]')).toBeVisible()

    const altrui = await page.evaluate(async (mio) => {
      const r = await fetch('/api/tasks', { credentials: 'include' })
      const tutti = await r.json()
      return tutti.filter((t) => t.dipendente_id !== mio).map((t) => t.id)
    }, UTENTI.ludovica.dipendente)
    expect(altrui.length).toBeGreaterThan(0)   // il manager li vede davvero

    await apriPannello(page)
    const offerti = await page.locator('[data-aggiungi-task]').evaluateAll(
      (nodi) => nodi.map((n) => n.getAttribute('data-aggiungi-task')))
    expect(offerti.filter((id) => altrui.includes(id))).toEqual([])
  })
})
