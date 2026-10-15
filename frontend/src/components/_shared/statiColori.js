/**
 * statiColori.js — Colori ed etichette degli stati, in un posto solo.
 *
 * Lo leggono il GANTT a schermo (GanttChartFasi), il mini-GANTT degli snapshot
 * (TimelineBars), la legenda della pagina GANTT e il disegnatore SVG
 * dell'export (ganttSvg.js). JavaScript puro, senza React né classi Tailwind:
 * un colore è un esadecimale, perché lo usano anche un SVG e un PDF.
 *
 * Tre mappe e non una, perché il dominio ha tre vocabolari: una fase è
 * «Completata», un task «Completato»; «Sospeso» di un progetto e «Sospeso» di
 * un task sono stringhe uguali con soggetti diversi. Una mappa unica a chiavi
 * miste farebbe sembrare intercambiabili stati che non lo sono.
 *
 * La fonte è condiviso/stati.json, nella radice del repo: lo stesso file che
 * il backend legge per l'export Excel. Qui lo si importa, quindi Vite lo
 * incorpora nel bundle alla build: il frontend compilato non lo cerca più sul
 * disco. Gli stati sono quelli di models.py (STATI_PROGETTO, STATI_FASE,
 * STATI_TASK); l'ordine delle chiavi è l'ordine in cui compaiono in legenda.
 */

import STATI from '../../../../condiviso/stati.json' with { type: 'json' }

export const STATI_PROGETTO = STATI.progetto
export const STATI_FASE = STATI.fase
export const STATI_TASK = STATI.task

// Uno stato che non conosciamo non deve far sparire la barra: meglio una barra
// neutra di un buco.
export const COLORE_IGNOTO = STATI.ignoto.colore

const MAPPE = { progetto: STATI_PROGETTO, fase: STATI_FASE, task: STATI_TASK }

/** @param {'progetto'|'fase'|'task'} livello */
export function coloreStato(livello, stato) {
  return MAPPE[livello]?.[stato]?.colore ?? COLORE_IGNOTO
}

/**
 * Le voci di legenda per i soli stati presenti, nell'ordine della mappa.
 * Uno stato presente ma ignoto compare in coda col suo nome e il colore
 * neutro: la legenda deve spiegare ogni colore che si vede.
 * @param {'progetto'|'fase'|'task'} livello
 * @param {Iterable<string>} statiPresenti
 * @returns {Array<{stato, etichetta, colore}>}
 */
export function vociLegenda(livello, statiPresenti) {
  const presenti = new Set(statiPresenti)
  const mappa = MAPPE[livello] || {}
  const note = Object.entries(mappa)
    .filter(([stato]) => presenti.has(stato))
    .map(([stato, v]) => ({ stato, etichetta: v.etichetta, colore: v.colore }))
  const ignote = [...presenti]
    .filter(stato => stato && !(stato in mappa))
    .sort()
    .map(stato => ({ stato, etichetta: stato, colore: COLORE_IGNOTO }))
  return [...note, ...ignote]
}
