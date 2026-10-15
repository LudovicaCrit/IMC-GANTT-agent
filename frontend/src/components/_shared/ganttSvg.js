/**
 * ganttSvg.js — Il GANTT impaginato in fogli SVG.
 *
 * JavaScript puro: nessun React, nessuna classe CSS, solo attributi SVG
 * espliciti. Lo usa l'export (PDF e PNG, esportaGantt.js) e lo potrà usare
 * identico qualunque framework: riceve dati, restituisce stringhe.
 *
 * Due mestieri separati, perché in fase 2 lo stesso disegnatore servirà lo
 * schermo, con un foglio di misure diverse:
 *   costruisciPagine → la GEOMETRIA: righe, pagine, periodi, barre, legenda.
 *                      Solo numeri e testi, niente markup.
 *   paginaInSvg      → la RESA di una pagina già calcolata.
 *
 * La scala del tempo è quella di timelineScale.js (buildTimeline + barXW), la
 * stessa dello schermo: una barra cade nello stesso punto in entrambe le viste.
 */
import { buildTimeline, barXW } from './timelineScale.js'
import { coloreStato, vociLegenda } from './statiColori.js'

/* ── Il foglio: A4 orizzontale, in punti PDF (1 pt = 1/72 di pollice) ──── */
export const FOGLIO = { larghezza: 841.89, altezza: 595.28 }

/**
 * Larghezza minima di una settimana, in punti. Sotto, il periodo si spezza su
 * più pagine invece di stringersi.
 * 18 pt ≈ 6,3 mm: un giorno vale ≈ 0,9 mm, quindi un task di un giorno resta
 * distinguibile da uno di due; il numero del lunedì (due cifre a 6 pt, ≈ 7 pt)
 * ci sta con margine. Sul foglio entrano così ≈ 27 settimane, un semestre.
 */
export const SETTIMANA_MIN = 18

const MARGINE = 28
const COL_NOMI = 250          // nome + assegnatario
const COL_ASSEGNATARIO = 80   // la parte destra di COL_NOMI
const COL_ORE = 50
const Y_TITOLO = MARGINE + 14
const Y_SOTTOTITOLO = Y_TITOLO + 15
const Y_ASSE = Y_SOTTOTITOLO + 12
const ALTEZZA_MESI = 13
const ALTEZZA_SETTIMANE = 12
const Y_CORPO = Y_ASSE + ALTEZZA_MESI + ALTEZZA_SETTIMANE
const ALTEZZA_LEGENDA = 22
const Y_FONDO_CORPO = FOGLIO.altezza - MARGINE - ALTEZZA_LEGENDA

export const ALTEZZA_RIGA = { progetto: 16, fase: 14, task: 12 }
const ALTEZZA_BARRA = { fase: 8, task: 6 }
const FONT = 'Helvetica, Arial, sans-serif'
const ROSSO_OGGI = '#ef4444'

/* ── Date: stringhe ISO e date locali, mai toISOString ───────────────────
 * toISOString è in UTC: a mezzanotte e mezza ora italiana direbbe «ieri». */
export function isoLocale(d) {
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const gg = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${gg}`
}
const dataItaliana = (iso) => iso.split('-').reverse().join('/')
const dataOraItaliana = (d) =>
  `${dataItaliana(isoLocale(d))} alle ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`

/** Il titolo dei fogli: il progetto scelto, oppure il portafoglio. */
export function titoloGantt(nomeProgetto) {
  return nomeProgetto ? `GANTT — ${nomeProgetto}` : 'GANTT — Portafoglio'
}

/* ── 1. Le righe ─────────────────────────────────────────────────────────
 * Tutte le fasi e tutti i task, a prescindere da cosa è aperto a schermo:
 * un export è il piano intero dei progetti scelti. L'ordine è quello del
 * payload (/api/gantt/strutturato ordina progetti, fasi e task), non uno
 * nuovo deciso qui. I task «Eliminato» non sono piano: il backend già li
 * toglie, ma il disegnatore non si fida di chi lo chiama.
 */
export function righeGantt(progetti) {
  const righe = []
  for (const p of progetti || []) {
    righe.push({ tipo: 'progetto', progettoId: p.id, nome: p.nome, stato: p.stato })
    for (const f of p.fasi || []) {
      righe.push({
        tipo: 'fase', progettoId: p.id, id: f.id, nome: f.nome, stato: f.stato,
        inizio: f.data_inizio, fine: f.data_fine, ore: f.ore_pianificate,
      })
      for (const t of f.tasks || []) {
        if (t.stato === 'Eliminato') continue
        righe.push({
          tipo: 'task', progettoId: p.id, id: t.id, nome: t.nome, stato: t.stato,
          inizio: t.data_inizio, fine: t.data_fine, ore: t.ore_pianificate,
          assegnatario: t.dipendente_nome || '',
        })
      }
    }
  }
  return righe
}

const haDate = (r) => Boolean(r.inizio && r.fine)
// Le ore si mostrano solo se il payload le porta: null o assenti = niente.
const haOre = (r) => typeof r.ore === 'number' && Number.isFinite(r.ore)

/* ── 2. Impaginazione verticale ──────────────────────────────────────────
 * Una riga sta tutta in una pagina o passa alla successiva: mai tagliata.
 * Una pagina che comincia dentro un progetto ne ripete l'intestazione
 * («segue»), e un'intestazione non resta orfana in fondo a una pagina.
 */
export function impaginaRighe(righe, altezzaCorpo = Y_FONDO_CORPO - Y_CORPO) {
  const pagine = []
  let pagina = []
  let usata = 0
  let progettoCorrente = null

  const chiudi = () => { pagine.push(pagina); pagina = []; usata = 0 }
  const apriConSegue = () => {
    if (progettoCorrente) {
      pagina.push({ ...progettoCorrente, segue: true })
      usata += ALTEZZA_RIGA.progetto
    }
  }

  righe.forEach((r, i) => {
    let serve = ALTEZZA_RIGA[r.tipo]
    if (r.tipo === 'progetto') {
      const dopo = righe[i + 1]
      if (dopo && dopo.tipo !== 'progetto') serve += ALTEZZA_RIGA[dopo.tipo]
    }
    if (pagina.length > 0 && usata + serve > altezzaCorpo) {
      chiudi()
      if (r.tipo !== 'progetto') apriConSegue()
    }
    if (r.tipo === 'progetto') progettoCorrente = r
    pagina.push(r)
    usata += ALTEZZA_RIGA[r.tipo]
  })
  if (pagina.length > 0 || pagine.length === 0) pagine.push(pagina)
  return pagine
}

/* ── 3. Impaginazione orizzontale ────────────────────────────────────────
 * Se tutte le settimane entrano nella larghezza a SETTIMANA_MIN o più, un
 * periodo solo, allargato a riempire il foglio. Altrimenti il minimo numero di
 * periodi possibile, fatti di mesi interi e il più possibile uguali fra loro:
 * riempire ogni foglio fino al massimo lascerebbe in coda un foglio con poche
 * settimane e molto bianco. Stessa densità su tutte le pagine, così le barre
 * si confrontano fra un foglio e l'altro.
 * @returns {{weekPx, periodi: Array<{da, a}>}}  da/a: indici di settimana, a esclusa
 */
export function periodiAsse(totaleSettimane, inizioMesi, larghezzaAsse) {
  if (totaleSettimane * SETTIMANA_MIN <= larghezzaAsse) {
    return { weekPx: larghezzaAsse / totaleSettimane, periodi: [{ da: 0, a: totaleSettimane }] }
  }
  const massimo = Math.max(1, Math.floor(larghezzaAsse / SETTIMANA_MIN))
  const confini = [...inizioMesi.filter(s => s > 0 && s < totaleSettimane), totaleSettimane]
  const minimoPeriodi = Math.ceil(totaleSettimane / massimo)
  // Il tetto più basso che chiude ancora nel minimo numero di periodi: parte
  // dalla media e sale finché i confini dei mesi lo permettono.
  let periodi = null
  for (let tetto = Math.ceil(totaleSettimane / minimoPeriodi); tetto <= massimo; tetto++) {
    periodi = periodiAMesiInteri(confini, totaleSettimane, tetto)
    if (periodi.length <= minimoPeriodi) break
  }
  const piuLungo = Math.max(...periodi.map(p => p.a - p.da))
  return { weekPx: larghezzaAsse / piuLungo, periodi }
}

function periodiAMesiInteri(confini, totaleSettimane, tetto) {
  const periodi = []
  let da = 0
  let ultimoConfine = 0
  for (const c of confini) {
    if (c - da > tetto && ultimoConfine > da) {
      periodi.push({ da, a: ultimoConfine })
      da = ultimoConfine
    }
    // Un mese più lungo del tetto (non accade a 18 pt, ma la scala non lo
    // vieta) si taglia a settimane.
    while (c - da > tetto) {
      periodi.push({ da, a: da + tetto })
      da += tetto
    }
    ultimoConfine = c
  }
  if (da < totaleSettimane) periodi.push({ da, a: totaleSettimane })
  return periodi
}

/* ── 4. Le pagine ────────────────────────────────────────────────────────
 * @param {Array} progetti  già filtrati come a schermo, con fasi e task
 * @param {{titolo: string, oggi?: Date, generatoIl?: Date}} opzioni
 * @returns {Array<object>} un modello per foglio, in ordine di stampa: per
 *          ogni blocco di righe, i periodi da sinistra a destra.
 */
export function costruisciPagine(progetti, { titolo, oggi = new Date(), generatoIl = new Date() }) {
  const righe = righeGantt(progetti)
  const conOre = righe.some(haOre)
  const xOre = MARGINE + COL_NOMI
  const xAsse = xOre + (conOre ? COL_ORE : 0)
  const larghezzaAsse = FOGLIO.larghezza - MARGINE - xAsse

  const estremi = righe.filter(haDate).map(r => ({ start: r.inizio, end: r.fine }))
  // Una prima scala a 1 pt per settimana dice quante settimane e dove
  // cominciano i mesi; la densità vera si decide dopo, sul foglio.
  const grezza = buildTimeline(estremi, { weekPx: 1 })
  const { weekPx, periodi } = grezza
    ? periodiAsse(grezza.totalWeeks, grezza.months.map(m => m.x), larghezzaAsse)
    : { weekPx: 0, periodi: [{ da: 0, a: 0 }] }
  const scala = grezza && buildTimeline(estremi, { weekPx })

  const intervallo = estremi.length
    ? `${dataItaliana(estremi.map(e => e.start).sort()[0])} – ${dataItaliana(estremi.map(e => e.end).sort().at(-1))}`
    : 'nessuna data'
  const xOggi = scala ? barXW(scala, isoLocale(oggi), isoLocale(oggi)).x : null

  const blocchi = impaginaRighe(righe)
  const totale = blocchi.length * periodi.length
  const pagine = []
  blocchi.forEach(blocco => {
    periodi.forEach(periodo => {
      pagine.push(paginaDiBlocco(blocco, periodo, {
        scala, weekPx, xAsse, xOre, larghezzaAsse, conOre, xOggi,
        titolo, intervallo, generatoIl,
        numero: pagine.length + 1, totale, piuPeriodi: periodi.length > 1,
      }))
    })
  })
  return pagine
}

function paginaDiBlocco(blocco, periodo, c) {
  const x0 = periodo.da * c.weekPx
  const x1 = periodo.a * c.weekPx
  // Da coordinata della scala a coordinata del foglio, tagliata al periodo.
  const sulFoglio = (x, w) => {
    const a = Math.max(x, x0)
    const b = Math.min(x + w, x1)
    return b > a ? { x: c.xAsse + a - x0, w: b - a } : null
  }

  let y = Y_CORPO
  const barraSulFoglio = (r) => {
    if (!c.scala || r.tipo === 'progetto' || !haDate(r)) return null
    const { x, w } = barXW(c.scala, r.inizio, r.fine)
    return sulFoglio(x, w)
  }
  const righe = blocco.map(r => {
    const barra = barraSulFoglio(r)
    const riga = {
      ...r, y, altezza: ALTEZZA_RIGA[r.tipo], barra,
      colore: coloreStato(r.tipo, r.stato),
      ore: haOre(r) ? r.ore : null,
    }
    y += riga.altezza
    return riga
  })

  const settimane = c.scala ? c.scala.weeks.slice(periodo.da, periodo.a) : []
  const mesi = c.scala
    ? c.scala.months
        .map(m => ({ etichetta: m.label, ...sulFoglio(m.x, m.width) }))
        .filter(m => m.w > 0)
    : []
  // Gli stati delle barre DISEGNATE: una riga con date ma fuori dal periodo
  // della pagina non mostra colori, e la legenda non deve spiegarli.
  const statiDisegnati = (tipo) => righe.filter(r => r.tipo === tipo && r.barra).map(r => r.stato)
  const periodoTesto = c.piuPeriodi && settimane.length
    ? ` · Periodo della pagina: ${dataItaliana(isoLocale(settimane[0].monday))} – ${dataItaliana(isoLocale(new Date(settimane.at(-1).monday.getTime() + 6 * 86400000)))}`
    : ''

  return {
    numero: c.numero,
    totale: c.totale,
    titolo: c.titolo,
    sottotitolo: `Generato il ${dataOraItaliana(c.generatoIl)} · Intervallo ${c.intervallo}${periodoTesto} · Pagina ${c.numero} di ${c.totale}`,
    xAsse: c.xAsse,
    xOre: c.conOre ? c.xOre : null,
    fineAsse: c.xAsse + (x1 - x0),
    righe,
    mesi,
    settimane: settimane.map((s, i) => ({
      x: c.xAsse + i * c.weekPx,
      etichetta: String(s.monday.getDate()),
      inizioMese: s.monday.getDate() <= 7,
    })),
    larghezzaSettimana: c.weekPx,
    xOggi: c.xOggi != null && c.xOggi >= x0 && c.xOggi <= x1 ? c.xAsse + c.xOggi - x0 : null,
    legenda: { fase: vociLegenda('fase', statiDisegnati('fase')), task: vociLegenda('task', statiDisegnati('task')) },
  }
}

/* ── 5. La resa in SVG ─────────────────────────────────────────────────── */

const esc = (s) => String(s ?? '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
const n = (v) => Math.round(v * 100) / 100

// Senza misurare il testo (non c'è un DOM garantito): Helvetica sta sotto
// 0,55 em di media, quindi a questa stima un nome non sborda dalla colonna.
function tronca(testo, larghezza, corpo) {
  const max = Math.max(1, Math.floor(larghezza / (corpo * 0.55)))
  const s = String(testo ?? '')
  return s.length <= max ? s : `${s.slice(0, max - 1)}…`
}
const oreTesto = (ore) => `${String(Math.round(ore * 10) / 10).replace('.', ',')} h`

function testo(x, y, contenuto, { corpo = 7, colore = '#111827', grassetto = false, ancora = 'start' } = {}) {
  return `<text x="${n(x)}" y="${n(y)}" font-family="${FONT}" font-size="${corpo}" fill="${colore}"`
    + `${grassetto ? ' font-weight="bold"' : ''}${ancora !== 'start' ? ` text-anchor="${ancora}"` : ''}>${esc(contenuto)}</text>`
}
const rett = (x, y, w, h, fill, extra = '') =>
  `<rect x="${n(x)}" y="${n(y)}" width="${n(w)}" height="${n(h)}" fill="${fill}"${extra}/>`
const linea = (x1, y1, x2, y2, colore, extra = '') =>
  `<line x1="${n(x1)}" y1="${n(y1)}" x2="${n(x2)}" y2="${n(y2)}" stroke="${colore}" stroke-width="0.5"${extra}/>`

export function paginaInSvg(p) {
  const out = []
  const destra = FOGLIO.larghezza - MARGINE
  const fondoRighe = p.righe.length ? p.righe.at(-1).y + p.righe.at(-1).altezza : Y_CORPO

  out.push(rett(0, 0, FOGLIO.larghezza, FOGLIO.altezza, '#ffffff'))
  out.push(testo(MARGINE, Y_TITOLO, p.titolo, { corpo: 14, grassetto: true }))
  out.push(testo(MARGINE, Y_SOTTOTITOLO, p.sottotitolo, { corpo: 7.5, colore: '#4b5563' }))

  // Testata delle colonne e dell'asse
  const yMesi = Y_ASSE
  const ySett = Y_ASSE + ALTEZZA_MESI
  out.push(testo(MARGINE, ySett + 8.5, 'Progetto / Fase / Task', { corpo: 6.5, colore: '#6b7280' }))
  out.push(testo(MARGINE + COL_NOMI - 4, ySett + 8.5, 'Assegnatario', { corpo: 6.5, colore: '#6b7280', ancora: 'end' }))
  if (p.xOre != null) out.push(testo(p.xOre + COL_ORE - 4, ySett + 8.5, 'Ore pianificate', { corpo: 6, colore: '#6b7280', ancora: 'end' }))
  p.mesi.forEach((m, i) => {
    out.push(rett(m.x, yMesi, m.w, ALTEZZA_MESI, i % 2 === 0 ? '#e5e7eb' : '#f3f4f6'))
    if (m.w > 28) out.push(testo(m.x + 3, yMesi + 9, m.etichetta, { corpo: 7, grassetto: true, colore: '#374151' }))
  })
  p.settimane.forEach(s => {
    out.push(testo(s.x + p.larghezzaSettimana / 2, ySett + 8.5, s.etichetta, { corpo: 6, colore: '#6b7280', ancora: 'middle' }))
  })
  out.push(linea(MARGINE, Y_CORPO, destra, Y_CORPO, '#9ca3af'))

  // Corpo: fasce, nomi, ore
  p.righe.forEach(r => {
    if (r.tipo === 'progetto') {
      out.push(rett(MARGINE, r.y, destra - MARGINE, r.altezza, '#eef2f7'))
      // Si tronca il nome, non il «(segue)»: è lui a dire che la pagina continua.
      const spazio = COL_NOMI - COL_ASSEGNATARIO
      const nome = r.segue ? `${tronca(r.nome, spazio - 40, 8)} (segue)` : tronca(r.nome, spazio, 8)
      out.push(testo(MARGINE + 3, r.y + 10.5, nome, { corpo: 8, grassetto: true }))
      out.push(testo(MARGINE + COL_NOMI - 4, r.y + 10.5, r.stato, { corpo: 6.5, colore: coloreStato('progetto', r.stato), grassetto: true, ancora: 'end' }))
      return
    }
    const centro = r.y + r.altezza / 2
    if (r.tipo === 'fase') {
      out.push(testo(MARGINE + 8, centro + 2.6, tronca(r.nome, COL_NOMI - 12, 7.5), { corpo: 7.5, grassetto: true, colore: '#1f2937' }))
    } else {
      out.push(testo(MARGINE + 18, centro + 2.3, tronca(r.nome, COL_NOMI - COL_ASSEGNATARIO - 22, 6.5), { corpo: 6.5, colore: '#1f2937' }))
      out.push(testo(MARGINE + COL_NOMI - 4, centro + 2.3, tronca(r.assegnatario, COL_ASSEGNATARIO - 6, 6), { corpo: 6, colore: '#6b7280', ancora: 'end' }))
    }
    if (p.xOre != null && r.ore != null) {
      out.push(testo(p.xOre + COL_ORE - 4, centro + 2.3, oreTesto(r.ore), { corpo: 6.5, colore: '#374151', ancora: 'end' }))
    }
    out.push(linea(MARGINE, r.y + r.altezza, destra, r.y + r.altezza, '#e5e7eb'))
  })

  // Griglia delle settimane sopra le fasce, sotto le barre
  p.settimane.forEach(s => {
    out.push(linea(s.x, Y_ASSE + ALTEZZA_MESI, s.x, fondoRighe, s.inizioMese ? '#9ca3af' : '#e5e7eb'))
  })
  out.push(linea(p.xAsse, Y_ASSE, p.xAsse, fondoRighe, '#9ca3af'))

  // Barre
  p.righe.forEach(r => {
    if (!r.barra) return
    const h = ALTEZZA_BARRA[r.tipo]
    out.push(`<g data-riga="${r.tipo}" data-id="${esc(r.id)}" data-stato="${esc(r.stato)}">`
      + rett(r.barra.x, r.y + (r.altezza - h) / 2, Math.max(r.barra.w, 1.5), h, r.colore, ` rx="${r.tipo === 'fase' ? 1.5 : 1}"`)
      + '</g>')
  })

  if (p.xOggi != null) {
    out.push(linea(p.xOggi, Y_ASSE + ALTEZZA_MESI, p.xOggi, fondoRighe, ROSSO_OGGI, ' stroke-dasharray="3 2"'))
    out.push(testo(p.xOggi + 2, Y_ASSE + ALTEZZA_MESI - 2, 'oggi', { corpo: 6, colore: ROSSO_OGGI }))
  }

  // Legenda: i soli stati che compaiono in questa pagina
  let x = MARGINE
  const yLeg = FOGLIO.altezza - MARGINE - 6
  for (const [gruppo, voci] of [['Fasi', p.legenda.fase], ['Task', p.legenda.task]]) {
    if (voci.length === 0) continue
    out.push(testo(x, yLeg, `${gruppo}:`, { corpo: 7, grassetto: true, colore: '#374151' }))
    x += gruppo.length * 4.5 + 8
    for (const v of voci) {
      out.push(`<g data-legenda="${gruppo === 'Fasi' ? 'fase' : 'task'}" data-stato="${esc(v.stato)}">`
        + rett(x, yLeg - 6, 9, 6, v.colore, ' rx="1"') + '</g>')
      out.push(testo(x + 12, yLeg, v.etichetta, { corpo: 7, colore: '#374151' }))
      x += 12 + v.etichetta.length * 3.9 + 10
    }
    x += 10
  }

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${FOGLIO.larghezza}" height="${FOGLIO.altezza}" `
    + `viewBox="0 0 ${FOGLIO.larghezza} ${FOGLIO.altezza}">${out.join('')}</svg>`
}

/** I fogli SVG del GANTT, pronti per PDF o PNG. */
export function disegnaGantt(progetti, opzioni) {
  return costruisciPagine(progetti, opzioni).map(paginaInSvg)
}
