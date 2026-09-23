/**
 * guardia-fasi.spec.js — «questa fase non torna indietro: ci sono ore sopra».
 *
 * `PATCH /api/fasi/{id}` con `cascade` rifiuta di riportare una fase da «In
 * corso» a «Da iniziare» quando sui suoi task ci sono ore dichiarate. La
 * guardia c'era dal 18/05/2026 e non ha mai rifiutato niente: leggeva
 * `Task.ore_consumate`, una copia denormalizzata che nessuno aggiorna da quando
 * le ore vengono dai blocchi. Al 23/09/2026 valeva 0 su tutti e 114 i task, con
 * 17.535 ore in database. Dal fix legge la vista `ore_settimanali`.
 *
 * VERIFICA VIA API, non via browser: questa è una regola del backend, e la
 * pagina che la scatena (Cantiere → cambio stato fase) è solo uno dei modi di
 * arrivarci. Provarla dal DOM proverebbe il bottone, non la regola.
 *
 * Gira sullo scenario di `scenario_fasi.py`: due fasi «In corso» che
 * differiscono per una cosa sola — le ore.
 */
import { test, expect } from '@playwright/test'
import { UTENTI, statoAuth } from './utenti.js'

test.describe.configure({ mode: 'serial' })

const PROGETTO = 'PFASI'
const FASE_CON_ORE = '[PROVA] Fase CON ore'
const FASE_SENZA_ORE = '[PROVA] Fase SENZA ore'

/** Le fasi dello scenario, per nome: gli id sono autoincrement e cambiano a
 *  ogni creazione, quindi si chiedono al server invece di scriverli qui. */
async function fasi(request) {
  const r = await request.get(`/api/fasi/${PROGETTO}`)
  expect(r.ok(), await r.text()).toBeTruthy()
  return Object.fromEntries((await r.json()).map((f) => [f.nome, f]))
}

const aDaIniziare = (request, id) =>
  request.patch(`/api/fasi/${id}`, { data: { stato: 'Da iniziare', cascade: true } })

test.describe('il ritorno a «Da iniziare»', () => {
  // Manager: l'endpoint è `require_manager`.
  test.use({ storageState: statoAuth(UTENTI.ludovica) })

  test('la fase e il suo conteggio leggono le stesse ore', async ({ request }) => {
    // Non è un preambolo: `GET /api/fasi/{progetto}` somma le ore dalla vista,
    // e fino al fix la guardia del PATCH ne leggeva un'altra. Che i due numeri
    // coincidano È la correzione, vista dall'esterno.
    const f = await fasi(request)
    expect(f[FASE_CON_ORE].ore_consumate).toBe(4)
    expect(f[FASE_SENZA_ORE].ore_consumate).toBe(0)
    expect(f[FASE_CON_ORE].stato).toBe('In corso')
    expect(f[FASE_SENZA_ORE].stato).toBe('In corso')
  })

  test('con ore sopra: rifiutato, e dice quale task', async ({ request }) => {
    const f = await fasi(request)
    const r = await aDaIniziare(request, f[FASE_CON_ORE].id)

    expect(r.status()).toBe(409)
    const { detail } = await r.json()
    expect(detail).toContain(FASE_CON_ORE)
    expect(detail).toContain('1 task hanno ore consumate')
    expect(detail).toContain('T960')
    expect(detail).toContain('Azzera prima la consuntivazione')

    // Rifiutato vuol dire NON toccato: il check sta prima della scrittura.
    expect((await fasi(request))[FASE_CON_ORE].stato).toBe('In corso')
  })

  test('senza ore sopra: passa, e porta indietro anche il task', async ({ request }) => {
    const f = await fasi(request)
    const r = await aDaIniziare(request, f[FASE_SENZA_ORE].id)

    expect(r.status()).toBe(200)
    const esito = await r.json()
    expect(esito.stato).toBe('Da iniziare')
    expect(esito.task_aggiornati.map((t) => t.id)).toEqual(['T961'])
    expect(esito.task_aggiornati[0].nuovo_stato).toBe('Da iniziare')

    expect((await fasi(request))[FASE_SENZA_ORE].stato).toBe('Da iniziare')
  })

  test('appena il task prende delle ore, la fase non torna più indietro', async ({ request, playwright }) => {
    // LA PROVA CHE LA GUARDIA LEGGE IL DATO VIVO, e non una fotografia. È
    // esattamente ciò che la vecchia guardia non poteva fare: `ore_consumate`
    // restava 0 qualunque cosa il dipendente dichiarasse, e la fase tornava
    // indietro sopra il lavoro appena fatto.
    const f = await fasi(request)
    const id = f[FASE_SENZA_ORE].id

    // La fase è «Da iniziare» dal test precedente: la si rimette «In corso»,
    // che è lo stato da cui la guardia sorveglia.
    expect((await request.patch(`/api/fasi/${id}`, { data: { stato: 'In corso' } })).status()).toBe(200)

    // Le ore le scrive HELENA, dalla sua porta: /salva-blocchi è self-only e
    // non ha deroghe per il manager. Serve una seconda sessione.
    const comeHelena = await playwright.request.newContext({
      baseURL: 'http://localhost:3000',
      storageState: statoAuth(UTENTI.helena),
    })
    const me = await (await comeHelena.get('/api/consuntivi/me')).json()
    const salvato = await comeHelena.post('/api/consuntivi/salva-blocchi', {
      data: {
        settimana: me.settimana,
        unita: [{
          tipo: 'task', id: 'T961', stato_dichiarato: 'In corso',
          blocchi: [{ giorno: me.settimana, ore: 1 }],   // il lunedì: mai nel futuro
        }],
      },
    })
    expect(salvato.status(), await salvato.text()).toBe(200)
    await comeHelena.dispose()

    // Stessa fase, stessa richiesta di un attimo fa: adesso è un 409.
    const r = await aDaIniziare(request, id)
    expect(r.status()).toBe(409)
    expect((await r.json()).detail).toContain('T961')
    expect((await fasi(request))[FASE_SENZA_ORE].ore_consumate).toBe(1)
  })
})
