/**
 * export-gantt.spec.js — PDF e PNG del GANTT, generati nel browser.
 *
 * Dalla pagina GANTT si scaricano i due formati, sul portafoglio e su un
 * progetto solo, e si guarda che i file ci siano davvero: non vuoti, con la
 * firma del formato, e quanti ne servono. Il numero di pagine atteso lo
 * calcola lo stesso disegnatore (`ganttSvg.js`, JavaScript puro) sullo stesso
 * payload che legge la pagina: il PDF deve avere una pagina per foglio, e i
 * PNG un file per foglio. Se jsPDF perdesse un foglio per strada, o il
 * pulsante esportasse dati diversi da quelli filtrati, i conti non tornano.
 */
process.env.TZ = 'Europe/Rome'

import fs from 'node:fs'
import { test, expect } from '@playwright/test'
import { UTENTI, statoAuth } from './utenti.js'
import { costruisciPagine } from '../frontend/src/components/_shared/ganttSvg.js'

/** Le pagine di un PDF scritto da jsPDF: gli oggetti /Type /Page (non /Pages). */
const paginePdf = (buffer) => (buffer.toString('latin1').match(/\/Type\s*\/Page\b(?!s)/g) || []).length
const FIRMA_PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])

async function fogliAttesi(request, progettoId) {
  const query = progettoId ? `?stato=attivi&progetto_id=${progettoId}` : '?stato=attivi'
  const r = await request.get(`/api/gantt/strutturato${query}`)
  expect(r.status()).toBe(200)
  return costruisciPagine(await r.json(), { titolo: 'conteggio' }).length
}

/** Clicca il pulsante e raccoglie `quanti` download, salvandoli in uscita.
 *  I PNG partono a 250 ms l'uno dall'altro (esportaGantt.js) e il portafoglio
 *  di sviluppo ne fa una trentina: da qui un'attesa più lunga del default. */
async function scarica(page, pulsante, quanti, testInfo) {
  const arrivati = []
  const avvisi = []
  page.on('download', (d) => arrivati.push(d))
  // Un errore dell'export arriva come alert: Playwright lo chiuderebbe in
  // silenzio, e il test aspetterebbe download che non arriveranno mai.
  page.on('dialog', (d) => { avvisi.push(d.message()); d.dismiss() })
  await page.getByRole('button', { name: pulsante }).click()
  await expect.poll(() => (avvisi.length ? avvisi : arrivati.length), { timeout: 60_000 }).toBe(quanti)
  const file = []
  for (const d of arrivati) {
    const destinazione = testInfo.outputPath(d.suggestedFilename())
    await d.saveAs(destinazione)
    file.push({ nome: d.suggestedFilename(), contenuto: fs.readFileSync(destinazione) })
  }
  return file
}

async function apriGantt(page) {
  const errori = []
  page.on('pageerror', (e) => errori.push(String(e).split('\n')[0]))
  await page.goto('/gantt')
  await expect(page.getByRole('heading', { name: /GANTT/ })).toBeVisible()
  await expect(page.getByText('Progetto / Fase / Task')).toBeVisible()
  return errori
}

const tendinaProgetto = (page) =>
  page.locator('select').filter({ has: page.locator('option', { hasText: 'Tutti i progetti' }) })

test.describe('GANTT — export dal browser', () => {
  test.use({ storageState: statoAuth(UTENTI.ludovica), acceptDownloads: true })

  test('portafoglio: un PDF con una pagina per foglio', async ({ page, request }, testInfo) => {
    const errori = await apriGantt(page)
    const attese = await fogliAttesi(request, null)
    const [pdf] = await scarica(page, /PDF/, 1, testInfo)
    expect(pdf.nome).toMatch(/^gantt_portafoglio_\d{4}-\d{2}-\d{2}\.pdf$/)
    expect(pdf.contenuto.length).toBeGreaterThan(1000)
    expect(pdf.contenuto.subarray(0, 5).toString()).toBe('%PDF-')
    expect(paginePdf(pdf.contenuto)).toBe(attese)
    expect(errori).toEqual([])
  })

  test('portafoglio: un PNG per foglio, numerati se più di uno', async ({ page, request }, testInfo) => {
    test.setTimeout(90_000)
    await apriGantt(page)
    const attese = await fogliAttesi(request, null)
    const png = await scarica(page, /PNG/, attese, testInfo)
    for (const f of png) {
      expect(f.contenuto.length).toBeGreaterThan(1000)
      expect(f.contenuto.subarray(0, 8).equals(FIRMA_PNG)).toBe(true)
    }
    const nomi = png.map((f) => f.nome).sort()
    if (attese === 1) expect(nomi[0]).toMatch(/^gantt_portafoglio_\d{4}-\d{2}-\d{2}\.png$/)
    else nomi.forEach((n) => expect(n).toMatch(new RegExp(`_pagina-\\d+-di-${attese}\\.png$`)))
  })

  test('un progetto solo: segue la tendina, nel nome del file e nel numero di pagine', async ({ page, request }, testInfo) => {
    test.setTimeout(90_000)
    await apriGantt(page)
    const tendina = tendinaProgetto(page)
    const progettoId = await tendina.locator('option').nth(1).getAttribute('value')
    await tendina.selectOption(progettoId)
    await expect(page.getByText('Progetto / Fase / Task')).toBeVisible()
    const attese = await fogliAttesi(request, progettoId)

    const [pdf] = await scarica(page, /PDF/, 1, testInfo)
    expect(pdf.nome).toMatch(new RegExp(`^gantt_${progettoId}_\\d{4}-\\d{2}-\\d{2}\\.pdf$`))
    expect(paginePdf(pdf.contenuto)).toBe(attese)

    const png = await scarica(page, /PNG/, attese, testInfo)
    png.forEach((f) => expect(f.contenuto.subarray(0, 8).equals(FIRMA_PNG)).toBe(true))
  })
})
