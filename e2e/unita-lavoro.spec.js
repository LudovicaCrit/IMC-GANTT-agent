/**
 * unita-lavoro.spec.js — «che cos'è un'unità di lavoro, e quando è dichiarata».
 *
 * Le due funzioni di `_shared/unitaLavoro.js` sono PURE: si importano e si
 * chiamano, senza browser, senza database, senza montare una pagina. È il modo
 * in cui il file dice di volersi provare, e qui lo si fa davvero.
 *
 * Perché stanno in e2e/ e non in un test-runner a parte: perché il frontend non
 * ne ha uno, e un secondo apparato per cinque funzioni pure costerebbe più di
 * quello che prova. Playwright le esegue come qualunque altro spec.
 *
 * COSA PROVANO, in particolare: i due sganci del passo 5.2.
 *   · «dichiarata» non guarda più `percentuale` (colonna che sparisce al 5.6);
 *   · «scomposto» si decide sui pezzi VIVI, non sulla lunghezza della lista —
 *     lo stesso bug M9 già chiuso in `costruisciGruppi`.
 */
import { test, expect } from '@playwright/test'
import {
  unitaDichiarata, unitaCompilabili,
} from '../frontend/src/components/_shared/unitaLavoro.js'
import { UTENTI, statoAuth } from './utenti.js'
import { GRIGLIA, metti, salva } from './griglia.js'

const IO = 'D004'
const COLLEGA = 'D002'

/** Una riga di /me come la restituisce il server, coi campi che contano. */
const riga = (extra = {}) => ({
  blocchi: [], blocchi_storico: [], stato_dichiarato: null, nota: null,
  presa_visione: false, ...extra,
})
const pezzo = (extra = {}) => ({
  id: 1, stato: 'Da iniziare', assegnatario_id: IO, ...riga(), ...extra,
})

test.describe('unitaDichiarata', () => {
  test('le ORE sono una dichiarazione', () => {
    expect(unitaDichiarata(riga({ blocchi: [{ giorno: '2026-09-21', ore: 2 }] }))).toBe(true)
  })

  test('anche lo stato o la nota da soli, senza ore (N6)', () => {
    expect(unitaDichiarata(riga({ stato_dichiarato: 'Bloccato' }))).toBe(true)
    expect(unitaDichiarata(riga({ nota: 'aspetto il cliente' }))).toBe(true)
    expect(unitaDichiarata(riga({ presa_visione: true }))).toBe(true)
  })

  test('una riga intonsa non è dichiarata', () => {
    expect(unitaDichiarata(riga())).toBe(false)
    expect(unitaDichiarata(riga({ nota: '   ' }))).toBe(false)
  })

  test('la PERCENTUALE non conta più, e lo storico nemmeno', () => {
    // Lo sgancio del 5.2: `percentuale` è la colonna del vecchio cursore, che
    // sparisce al 5.6. Una riga che ha solo quella non è dichiarata in questa
    // settimana — e fino al 23/09/2026 lo era.
    expect(unitaDichiarata(riga({ percentuale: 60 }))).toBe(false)
    // `blocchi_storico` sono ore migrate dai consuntivi vecchi, in sola
    // lettura: non le ha dichiarate questa persona questa settimana.
    expect(unitaDichiarata(riga({ blocchi_storico: [{ giorno: '2026-07-20', ore: 8 }] }))).toBe(false)
  })

  test('la nota EREDITATA non conta: è il promemoria di un’altra settimana', () => {
    expect(unitaDichiarata(riga({ nota_ereditata: 'fermo da tre settimane' }))).toBe(false)
  })
})

test.describe('unitaCompilabili', () => {
  test('un task senza pezzi vale uno', () => {
    const t = { task_id: 'T001', ...riga() }
    expect(unitaCompilabili([t], IO)).toEqual([t])
  })

  test('un task scomposto vale i suoi pezzi, e solo i propri', () => {
    const miei = [pezzo({ id: 1 }), pezzo({ id: 2 })]
    const suo = pezzo({ id: 3, assegnatario_id: COLLEGA })
    const t = { task_id: 'T002', ...riga(), sottotask: [...miei, suo] }
    // Il pezzo del collega è in sola lettura: contarlo renderebbe il
    // denominatore irraggiungibile.
    expect(unitaCompilabili([t], IO).map((u) => u.id)).toEqual([1, 2])
  })

  test('i pezzi ANNULLATI non si contano: nessuno ci può più scrivere', () => {
    const t = {
      task_id: 'T003', ...riga(),
      sottotask: [pezzo({ id: 1 }), pezzo({ id: 2, stato: 'Annullato' })],
    }
    expect(unitaCompilabili([t], IO).map((u) => u.id)).toEqual([1])
  })

  test('M9 · coi pezzi tutti annullati il task torna a valere UNO', () => {
    // IL BUG DEL 5.2, gemello di quello chiuso in `costruisciGruppi`: la lista
    // dei pezzi NON è vuota — ci sta dentro l'annullato su cui ci sono ore, per
    // N21 — ma nessuno di quei pezzi è vivo. Con `pezzi.length === 0` come
    // discriminante il contatore contava il pezzo annullato: un'unità che
    // nessuno può compilare, e per giunta al posto della riga che invece si
    // compila.
    const annullatoConOre = pezzo({
      id: 7, stato: 'Annullato',
      blocchi: [{ giorno: '2026-09-22', ore: 1.5 }], stato_dichiarato: 'In corso',
    })
    const t = { task_id: 'T952', ...riga(), sottotask: [annullatoConOre] }

    const unita = unitaCompilabili([t], IO)
    expect(unita).toEqual([t])                       // il TASK, non il pezzo
    expect(unita[0].task_id).toBe('T952')
    // E il task non è dichiarato: le ore stanno sul pezzo annullato, non su di
    // lui. Prima il contatore lo dava per fatto leggendo la riga sbagliata.
    expect(unitaDichiarata(unita[0])).toBe(false)
  })

  test('nessun task: nessuna unità', () => {
    expect(unitaCompilabili(undefined, IO)).toEqual([])
    expect(unitaCompilabili([], IO)).toEqual([])
  })
})

test.describe('il contatore della Home, dal vivo', () => {
  test.use({ storageState: statoAuth(UTENTI.helena) })

  const contatore = async (page) => {
    await page.goto('/')
    const testo = await page.locator('[data-contatore-unita]').getAttribute('data-contatore-unita')
    const [fatte, totali] = testo.split('/').map(Number)
    return { fatte, totali }
  }

  test('dichiarare delle ORE fa salire il contatore', async ({ page }) => {
    // Il giro completo che le funzioni pure qui sopra non possono fare: ore
    // scritte dalla griglia, salvate, rilette da /me, contate dalla Home.
    // Prima del 5.2 il contatore guardava `percentuale`, che la griglia non
    // scrive: l'unità restava «da compilare» anche dopo averci messo le ore.
    const prima = await contatore(page)
    expect(prima.totali).toBeGreaterThan(0)

    await page.goto(GRIGLIA)
    await expect(page.locator('[data-sintesi]')).toBeVisible()
    // Un pezzo che nessun altro spec tocca, dallo scenario sottotask.
    const pezzoVergine = page.locator('tr', { hasText: 'Collaudo con il cliente' }).first()
    const id = (await pezzoVergine.getAttribute('data-riga')).split(':')[1]
    await pezzoVergine.locator('select[aria-label^="Stato"]').selectOption('In corso')
    await metti(page, 'sott', id, 0, 'pomeriggio', 0.5)
    await salva(page)

    const dopo = await contatore(page)
    expect(dopo.totali).toBe(prima.totali)      // il denominatore non si muove
    expect(dopo.fatte).toBe(prima.fatte + 1)    // il numeratore sì
  })
})
