/**
 * griglia.js — i modi di parlare alla griglia a ore, in un posto solo.
 *
 * Due spec la guidano (`aggiungi-riga`, `sottotask-griglia`) e ne guideranno
 * altri: i selettori della matrice — la riga di un'unità, la cella di una mezza
 * giornata — non devono essere riscritti in ognuno, o divergeranno appena la
 * griglia cambia una `data-`.
 */
import { expect } from '@playwright/test'

export const GRIGLIA = '/consuntivazione'

/** La riga di un'unità: `riga(page, 'task', 'T950')`, `riga(page, 'sott', 748)`. */
export const riga = (page, tipo, id) => page.locator(`[data-riga="${tipo}:${id}"]`)

/** Il totale della riga, come lo legge l'utente («3,5»). */
export const totaleRiga = (page, tipo, id) => page.locator(`[data-totale-riga="${tipo}:${id}"]`)

/** Il giorno n-esimo della settimana in ISO, letto dalla riga dei totali. */
export const giornoSettimana = (page, indice) =>
  page.locator('[data-totale-giorno]').nth(indice).getAttribute('data-totale-giorno')

/** Sceglie le ore di una mezza giornata su una riga. */
export async function metti(page, tipo, id, indiceGiorno, meta, ore) {
  const giorno = await giornoSettimana(page, indiceGiorno)
  await riga(page, tipo, id).locator(`[data-cella="${giorno}:${meta}"] select`)
    .selectOption(String(ore))
}

/** Salva la settimana e aspetta la conferma. */
export async function salva(page) {
  await page.getByRole('button', { name: 'Salva' }).click()
  await expect(page.getByText('✓ Salvato')).toBeVisible()
}

/** Apre la selezione «Ho lavorato su altro», o la lascia aperta se già lo è. */
export async function apriPannello(page) {
  const pannello = page.locator('[data-aggiungi-riga="pannello"]')
  if (await pannello.count() === 0) await page.locator('[data-aggiungi-riga="apri"]').click()
  await expect(pannello).toBeVisible()
}
