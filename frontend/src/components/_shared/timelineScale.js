/**
 * ═════════════════════════════════════════════════════════════════════════
 * timelineScale.js — La scala del tempo, in un posto solo
 * ═════════════════════════════════════════════════════════════════════════
 *
 * ESTRATTA da `pages/Gantt.jsx` il 04/09/2026 (refactoring puro: il GANTT
 * principale deve disegnare identico a prima).
 *
 * PERCHÉ ESTRARLA. Questa aritmetica decide DOVE cade una barra e QUANTO è
 * larga. Se due viste dello stesso progetto la calcolassero in due modi, le
 * barre non corrisponderebbero — e nessun test se ne accorgerebbe, perché
 * entrambe le viste sarebbero internamente coerenti. È il tipo di divergenza
 * che si nota solo mettendo due schermate accanto, cioè quasi mai.
 *
 * Prima viveva dentro una PAGINA, e `_shared/GanttChartFasi.jsx` la importava
 * da lì (`import { buildTimeline } from '../../pages/Gantt'`): un componente
 * condiviso che dipende da una pagina è una dipendenza al contrario, e
 * trascinava l'intero modulo della pagina in chi voleva solo l'aritmetica.
 *
 * ── LA GRAMMATICA ────────────────────────────────────────────────────
 * Unità: la SETTIMANA. Origine: il LUNEDÌ.
 *   minDate = min(inizi) − 7gg      maxDate = max(fini) + 7gg   ← margine
 *   firstMonday = lunedì di minDate
 *   totalWeeks  = settimane(first→last) + 1
 *   weekPx      = min(TETTO, max(48, floor(900 / totalWeeks)))  ← adattiva
 *   totalWidth  = totalWeeks × weekPx
 *
 * `weekPx` prova a far stare tutto in ~900px senza scendere sotto 48 né
 * superare il tetto: un progetto lungo eccede e scrolla, uno corto non si
 * stira fino a diventare illeggibile.
 *
 * ── IL TETTO È PARAMETRICO, IL RESTO NO ──────────────────────────────
 * `weekPxMax` è l'unico parametro, e serve a chi disegna in uno spazio più
 * stretto (il mini-GANTT dentro il riquadro di uno snapshot). Cambia la
 * DENSITÀ — quanti pixel vale una settimana — non le PROPORZIONI: due barre in
 * rapporto 1:3 restano 1:3 a qualunque tetto, perché `barXW` divide per la
 * stessa scala che ha prodotto quella larghezza. È la ragione per cui il tetto
 * si può toccare e le formule no.
 */

// Larghezza minima di una settimana. Sotto questa soglia le etichette dei mesi
// si accavallano e l'asse diventa illeggibile.
export const WEEK_PX_DEFAULT = 48
// Tetto di riferimento del GANTT a pagina intera.
export const WEEK_PX_MAX = 80
// Larghezza "obiettivo" su cui si adatta la scala prima di scrollare.
const LARGHEZZA_OBIETTIVO = 900

/* ── Utility date ───────────────────────────────────────────────────── */

export function getMonday(d) {
  const date = new Date(d)
  const day = date.getDay()
  // domenica (0) appartiene alla settimana che INIZIA il lunedì precedente:
  // -6, non +1. Senza questo caso, ogni domenica salterebbe avanti di 7 giorni.
  const diff = day === 0 ? -6 : 1 - day
  date.setDate(date.getDate() + diff)
  date.setHours(0, 0, 0, 0)
  return date
}

export function addDays(d, n) { const r = new Date(d); r.setDate(r.getDate() + n); return r }

export function weeksBetween(a, b) {
  return Math.round((b.getTime() - a.getTime()) / (7 * 86400000))
}

function fmtMonth(d) { return d.toLocaleDateString('it-IT', { month: 'short', year: '2-digit' }) }

// Isolata perché il "presente" è l'unico ingresso non deterministico del
// calcolo: tenerla in una funzione permette di ragionarci (e, un giorno, di
// congelarla nei test) invece di avere `new Date()` sparso nel corpo.
function getOggi() { return new Date() }

/* ── Il costruttore della scala ─────────────────────────────────────── */

/**
 * @param {Array<{start,end}>} tasks  barre da contenere — solo start/end contano
 * @param {{weekPxMax?: number}} opts tetto della densità (default: WEEK_PX_MAX)
 * @returns {{firstMonday, totalWeeks, weekPx, totalWidth, weeks, months, oggiX}|null}
 *          `null` su lista vuota: il chiamante non disegna nulla, invece di
 *          ricevere una scala degenere da un min/max su un insieme vuoto.
 */
export function buildTimeline(tasks, { weekPxMax = WEEK_PX_MAX } = {}) {
  if (!tasks || tasks.length === 0) return null
  const starts = tasks.map(t => new Date(t.start).getTime())
  const ends = tasks.map(t => new Date(t.end).getTime())
  const minDate = addDays(new Date(Math.min(...starts)), -7)
  const maxDate = addDays(new Date(Math.max(...ends)), 7)
  const firstMonday = getMonday(minDate)
  const lastMonday = getMonday(maxDate)
  const totalWeeks = weeksBetween(firstMonday, lastMonday) + 1
  const weekPx = Math.min(weekPxMax, Math.max(WEEK_PX_DEFAULT, Math.floor(LARGHEZZA_OBIETTIVO / totalWeeks)))
  const totalWidth = totalWeeks * weekPx

  const weeks = []
  for (let i = 0; i < totalWeeks; i++) {
    weeks.push({ monday: addDays(firstMonday, i * 7), x: i * weekPx })
  }

  const months = []
  let curM = -1, curY = -1, mStart = 0
  for (let i = 0; i < weeks.length; i++) {
    const m = weeks[i].monday.getMonth(), y = weeks[i].monday.getFullYear()
    if (m !== curM || y !== curY) {
      if (curM !== -1) months[months.length - 1].width = weeks[i].x - mStart
      months.push({ label: fmtMonth(weeks[i].monday), x: weeks[i].x })
      mStart = weeks[i].x; curM = m; curY = y
    }
  }
  if (months.length > 0) months[months.length - 1].width = totalWidth - months[months.length - 1].x

  const oggi = getOggi()
  const oggiX = ((oggi.getTime() - firstMonday.getTime()) / (totalWeeks * 7 * 86400000)) * totalWidth
  return { firstMonday, totalWeeks, weekPx, totalWidth, weeks, months, oggiX }
}

/* ── Posizione di una barra sulla scala ─────────────────────────────── */

/**
 * Da (start, end) a (x, w) in pixel. Era una closure dentro `GanttChartFasi`
 * (`barXW`), che ricavava `msPerPx` dalla timeline: qui prende la timeline
 * esplicitamente, così chiunque disegni barre usa la stessa formula invece di
 * riderivarla dal proprio scope.
 *
 * `Math.max(4, …)` non è un dettaglio estetico: un task che inizia e finisce lo
 * stesso giorno avrebbe larghezza 0 e sparirebbe. Quattro pixel sono il minimo
 * perché resti visibile — un lavoro di un giorno esiste, e la scala
 * settimanale da sola lo cancellerebbe.
 */
export function barXW(timeline, start, end) {
  const msPerPx = (timeline.totalWeeks * 7 * 86400000) / timeline.totalWidth
  const x = (new Date(start).getTime() - timeline.firstMonday.getTime()) / msPerPx
  const w = Math.max(4, (new Date(end).getTime() - new Date(start).getTime()) / msPerPx)
  return { x, w }
}
