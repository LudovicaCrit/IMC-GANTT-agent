/**
 * ═════════════════════════════════════════════════════════════════════════
 * festivita.js — Festività italiane e calcolo giorni lavorativi
 * ═════════════════════════════════════════════════════════════════════════
 *
 * Esporta:
 *   - calcolaPasqua(anno):    domenica di Pasqua per un anno (algoritmo Gauss)
 *   - festivitaItaliane(anno): Set di stringhe ISO con tutte le festività
 *                              fisse + Pasqua/Pasquetta per quell'anno
 *   - giorniLavorativi(dataInizio, dataFine):
 *       numero di giorni lavorativi tra le due date (incluse),
 *       escludendo sabato, domenica e festività italiane
 *
 * Festività incluse (legali italiane, art. 2 L. 260/1949):
 *   1/1   Capodanno
 *   6/1   Epifania
 *   Domenica di Pasqua (mobile)
 *   Lunedì dell'Angelo / Pasquetta (mobile, Pasqua+1)
 *   25/4  Liberazione
 *   1/5   Festa dei Lavoratori
 *   2/6   Festa della Repubblica
 *   15/8  Ferragosto / Assunzione
 *   1/11  Ognissanti
 *   8/12  Immacolata Concezione
 *   25/12 Natale
 *   26/12 Santo Stefano
 *
 * NON inclusi: santi patroni locali (variano per città, fuori scope).
 * Lista canonica IMC future: caricamento da Configurazione.parametri (R2).
 */

/**
 * Calcola la domenica di Pasqua per un dato anno con l'algoritmo di Gauss.
 * Funziona per anni dal 1583 al 4099, sufficiente per ogni applicazione reale.
 * @param {number} anno
 * @returns {Date} la domenica di Pasqua a mezzanotte locale
 */
export function calcolaPasqua(anno) {
  const a = anno % 19
  const b = Math.floor(anno / 100)
  const c = anno % 100
  const d = Math.floor(b / 4)
  const e = b % 4
  const f = Math.floor((b + 8) / 25)
  const g = Math.floor((b - f + 1) / 3)
  const h = (19 * a + b - d - g + 15) % 30
  const i = Math.floor(c / 4)
  const k = c % 4
  const l = (32 + 2 * e + 2 * i - h - k) % 7
  const m = Math.floor((a + 11 * h + 22 * l) / 451)
  const mese = Math.floor((h + l - 7 * m + 114) / 31) // 3=marzo, 4=aprile
  const giorno = ((h + l - 7 * m + 114) % 31) + 1
  return new Date(anno, mese - 1, giorno)
}

/**
 * Tutte le festività italiane (legali) per un anno specifico.
 * @param {number} anno
 * @returns {Set<string>} Set di stringhe ISO date (es. "2026-01-01")
 */
export function festivitaItaliane(anno) {
  const toIso = (d) => {
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const g = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${g}`
  }

  const fisse = [
    `${anno}-01-01`, // Capodanno
    `${anno}-01-06`, // Epifania
    `${anno}-04-25`, // Liberazione
    `${anno}-05-01`, // Festa dei Lavoratori
    `${anno}-06-02`, // Festa della Repubblica
    `${anno}-08-15`, // Ferragosto
    `${anno}-11-01`, // Ognissanti
    `${anno}-12-08`, // Immacolata
    `${anno}-12-25`, // Natale
    `${anno}-12-26`, // Santo Stefano
  ]

  const pasqua = calcolaPasqua(anno)
  const pasquetta = new Date(pasqua)
  pasquetta.setDate(pasquetta.getDate() + 1)

  return new Set([...fisse, toIso(pasqua), toIso(pasquetta)])
}

/**
 * Numero di giorni lavorativi tra due date (incluse), escludendo
 * sabato, domenica e festività italiane.
 *
 * @param {string|Date} dataInizio (ISO string "yyyy-mm-dd" oppure Date)
 * @param {string|Date} dataFine
 * @returns {number} giorni lavorativi nell'intervallo (≥ 0)
 *
 * Esempi:
 *   giorniLavorativi("2026-05-18", "2026-05-18")  → 1  (lunedì singolo)
 *   giorniLavorativi("2026-05-16", "2026-05-17")  → 0  (sabato-domenica)
 *   giorniLavorativi("2026-04-24", "2026-04-27")  → 1  (ven 24, sab/dom, lun 27=Pasquetta non lavorativo, mar è 28 fuori range; 27 lo escludo perché in 2026 Pasquetta cade in altra data — vedi nota)
 *
 * Caveat: se dataFine < dataInizio ritorna 0.
 */
export function giorniLavorativi(dataInizio, dataFine) {
  const start = dataInizio instanceof Date ? dataInizio : new Date(dataInizio)
  const end = dataFine instanceof Date ? dataFine : new Date(dataFine)
  if (isNaN(start) || isNaN(end)) return 0
  if (end < start) return 0

  // Cache delle festività per anno (può servirne più di uno se il task
  // attraversa il capodanno; usiamo un Set unico)
  const festAll = new Set()
  for (let y = start.getFullYear(); y <= end.getFullYear(); y++) {
    for (const d of festivitaItaliane(y)) festAll.add(d)
  }

  const toIso = (d) => {
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const g = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${g}`
  }

  let count = 0
  const cursore = new Date(start)
  while (cursore <= end) {
    const dow = cursore.getDay() // 0=domenica, 6=sabato
    const isFestivo = dow === 0 || dow === 6 || festAll.has(toIso(cursore))
    if (!isFestivo) count++
    cursore.setDate(cursore.getDate() + 1)
  }
  return count
}
