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
 * Gli stati sono quelli di models.py (STATI_PROGETTO, STATI_FASE, STATI_TASK):
 * l'ordine delle chiavi è l'ordine in cui compaiono in legenda.
 */

const GRIGIO = '#9ca3af'          // gray-400: non ancora partito
const BLU = '#3b82f6'             // blue-500: in lavorazione
const VERDE = '#22c55e'           // green-500: chiuso bene
const AMBRA = '#d97706'           // amber-600: in pausa
const ROSSO = '#ef4444'           // red-500: fermo per un problema
const GRIGIO_SPENTO = '#6b7280'   // gray-500: uscito di scena

export const STATI_PROGETTO = {
  'Bozza':         { colore: GRIGIO, etichetta: 'Bozza' },
  'Da iniziare':   { colore: GRIGIO, etichetta: 'Da iniziare' },
  'In esecuzione': { colore: BLU, etichetta: 'In esecuzione' },
  'Sospeso':       { colore: AMBRA, etichetta: 'Sospeso' },
  'Completato':    { colore: VERDE, etichetta: 'Completato' },
  'Annullato':     { colore: GRIGIO_SPENTO, etichetta: 'Annullato' },
}

export const STATI_FASE = {
  'Da iniziare': { colore: GRIGIO, etichetta: 'Da iniziare' },
  'In corso':    { colore: BLU, etichetta: 'In corso' },
  'Completata':  { colore: VERDE, etichetta: 'Completata' },
  'Sospesa':     { colore: AMBRA, etichetta: 'Sospesa' },
  'Annullata':   { colore: GRIGIO_SPENTO, etichetta: 'Annullata' },
}

export const STATI_TASK = {
  'Da iniziare': { colore: GRIGIO, etichetta: 'Da iniziare' },
  'In corso':    { colore: BLU, etichetta: 'In corso' },
  'Completato':  { colore: VERDE, etichetta: 'Completato' },
  'Bloccato':    { colore: ROSSO, etichetta: 'Bloccato' },
  'Sospeso':     { colore: AMBRA, etichetta: 'Sospeso' },
  'Annullato':   { colore: GRIGIO_SPENTO, etichetta: 'Annullato' },
}

// Uno stato che non conosciamo non deve far sparire la barra: meglio una barra
// neutra di un buco.
export const COLORE_IGNOTO = GRIGIO

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
