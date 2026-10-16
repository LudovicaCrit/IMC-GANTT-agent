/**
 * ciclo-progetto.spec.js — un progetto «Da iniziare» nato dal Wizard.
 *
 * Il percorso intero, dal browser: il Wizard del Cantiere chiede la società
 * (dalle società di Configurazione) e crea un progetto «Da iniziare»; il
 * progetto compare poi nel Cantiere, fra quelli a cui aggiungere task, e nel
 * GANTT, sia nel disegno sia nella tendina dei progetti. Prima del passo 5
 * della fase 1 nasceva senza società e non compariva in nessuno dei due.
 *
 * L'id lo dà il server, dalla sequenza dei progetti (passo 6a): il test lo
 * legge dalla risposta della creazione e lo usa per ritrovarlo e toglierlo.
 * Ogni giro consuma un numero, e la numerazione ha quindi dei buchi: è il
 * comportamento voluto di una sequenza.
 *
 * Il progetto si toglie per id alla fine: il DELETE ammette solo le bozze,
 * quindi prima lo si riporta a «Bozza». Se un giro precedente è morto a metà,
 * il suo id non lo si conosce più: lo si ritrova all'inizio per nome esatto.
 */
process.env.TZ = 'Europe/Rome'

import { test, expect } from '@playwright/test'
import { UTENTI, statoAuth } from './utenti.js'
import { isoLocale } from '../frontend/src/components/_shared/ganttSvg.js'

test.describe.configure({ mode: 'serial' })

const NOME = '[PROVA] Ciclo di vita'
const fraGiorni = (n) => { const d = new Date(); d.setDate(d.getDate() + n); return isoLocale(d) }
const INIZIO = fraGiorni(30)
const FINE = fraGiorni(60)

async function togliProgetto(request, p) {
  if (p.stato !== 'Bozza') {
    const patch = await request.patch(`/api/progetti/${p.id}`, { data: { stato: 'Bozza' } })
    expect(patch.ok(), await patch.text()).toBeTruthy()
  }
  const del = await request.delete(`/api/progetti/${p.id}`)
  expect(del.status(), await del.text()).toBe(204)
}

async function progettiDiProva(request, filtro) {
  const r = await request.get('/api/progetti?stato=all')
  expect(r.ok()).toBeTruthy()
  return (await r.json()).filter(filtro)
}

const campo = (page, etichetta, tag) =>
  page.locator('label', { hasText: etichetta }).locator(`xpath=following-sibling::${tag}`)

test.describe('un progetto Da iniziare, dal Wizard al GANTT', () => {
  test.use({ storageState: statoAuth(UTENTI.ludovica) })

  let progettoId = null
  test.beforeAll(async ({ request }) => {
    for (const p of await progettiDiProva(request, (p) => p.nome === NOME)) await togliProgetto(request, p)
  })
  test.afterAll(async ({ request }) => {
    if (progettoId === null) return
    for (const p of await progettiDiProva(request, (p) => p.id === progettoId)) await togliProgetto(request, p)
  })

  test('il Wizard chiede la società e crea il progetto con quella', async ({ page, request }) => {
    const aziende = await (await request.get('/api/config/aziende')).json()
    expect(aziende.length).toBeGreaterThan(0)

    await page.goto('/cantiere')
    await page.getByRole('button', { name: /Nuovo progetto/ }).click()
    await campo(page, 'Nome progetto', 'input').fill(NOME)
    await campo(page, 'Budget ore totale', 'input').fill('40')
    await campo(page, 'Data inizio prevista', 'input').fill(INIZIO)
    await campo(page, 'Data fine prevista', 'input').fill(FINE)
    await campo(page, 'PM (Project Manager)', 'select').selectOption({ index: 1 })

    // Senza società non si va avanti: il backend la rifiuterebbe.
    const avanti = page.getByRole('button', { name: /Avanti/ })
    await expect(avanti).toBeDisabled()
    const societa = campo(page, 'Società', 'select')
    await expect(societa.locator('option')).toHaveCount(aziende.length + 1)
    await societa.selectOption(String(aziende[0].id))
    await avanti.click()

    const riga = page.locator('tbody tr').first()
    await riga.locator('input[type=text]').fill('Analisi')
    await riga.locator('input[type=date]').nth(0).fill(INIZIO)
    await riga.locator('input[type=date]').nth(1).fill(FINE)
    await riga.locator('input[type=number]').fill('40')
    await avanti.click()

    const creazione = page.waitForResponse((r) =>
      r.url().endsWith('/api/progetti/completo') && r.request().method() === 'POST')
    await page.getByRole('button', { name: 'Crea · Da iniziare' }).click()
    const risposta = await creazione
    expect(risposta.status(), await risposta.text()).toBe(201)
    progettoId = (await risposta.json()).id
    expect(progettoId).toMatch(/^P\d{3,}$/)

    const [creato] = await (await request.get(`/api/gantt/strutturato?progetto_id=${progettoId}`)).json()
    expect(creato.stato).toBe('Da iniziare')
    expect(creato.azienda_id).toBe(aziende[0].id)
  })

  test('il Cantiere lo mostra fra i progetti a cui aggiungere task', async ({ page }) => {
    expect(progettoId).not.toBeNull()
    await page.goto('/cantiere')
    const sezione = page.locator('section', { hasText: 'Progetti da iniziare, attivi e sospesi' })
    await expect(sezione.getByText(NOME)).toBeVisible()
  })

  test('il GANTT lo disegna e lo offre nella tendina dei progetti', async ({ page }) => {
    expect(progettoId).not.toBeNull()
    const caricamento = page.waitForResponse((r) => r.url().includes('/api/gantt/strutturato'))
    await page.goto('/gantt')
    const progetti = await (await caricamento).json()
    expect(progetti.map((p) => p.id)).toContain(progettoId)
    await expect(page.getByText(NOME).filter({ visible: true }).first()).toBeVisible()

    const tendina = page.locator('select').filter({ has: page.locator('option', { hasText: 'Tutti i progetti' }) })
    await expect(tendina.locator(`option[value="${progettoId}"]`)).toHaveCount(1)
    // E i sospesi, che la tendina prima escludeva.
    const sospesi = await (await page.request.get('/api/progetti?stato=sospeso')).json()
    for (const p of sospesi) await expect(tendina.locator(`option[value="${p.id}"]`)).toHaveCount(1)
  })
})
