/**
 * Test del disegnatore del GANTT (src/components/_shared/ganttSvg.js).
 * Test runner integrato di Node, nessuna dipendenza: `npm run test:disegno`.
 *
 * Il fuso si fissa qui e non nello script npm (`TZ=… node`), che su Windows
 * non funzionerebbe: Node rilegge process.env.TZ alla prima data creata dopo.
 */
process.env.TZ = 'Europe/Rome'

import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {
  costruisciPagine, disegnaGantt, impaginaRighe, periodiAsse, righeGantt,
  isoLocale, titoloGantt, FOGLIO, SETTIMANA_MIN, ALTEZZA_RIGA,
} from '../src/components/_shared/ganttSvg.js'
import { STATI_FASE, STATI_TASK, COLORE_IGNOTO } from '../src/components/_shared/statiColori.js'

const OGGI = new Date(2026, 9, 15, 10, 0)
const OPZIONI = { titolo: 'GANTT — Portafoglio', oggi: OGGI, generatoIl: OGGI }

function task(id, stato = 'In corso', extra = {}) {
  return {
    id, nome: `Task ${id}`, stato, data_inizio: '2026-03-02', data_fine: '2026-04-10',
    dipendente_nome: 'Persona di prova', ore_pianificate: null, ...extra,
  }
}
function fase(id, tasks, extra = {}) {
  return {
    id, nome: `Fase ${id}`, stato: 'In corso', data_inizio: '2026-03-02', data_fine: '2026-06-30',
    ore_pianificate: null, tasks, ...extra,
  }
}
function progetto(id, fasi) {
  return { id, nome: `Progetto ${id}`, stato: 'In esecuzione', fasi }
}
/** n progetti × 4 fasi × 8 task: abbastanza righe per più pagine. */
function portafoglio(n = 4, date = {}) {
  return Array.from({ length: n }, (_, p) =>
    progetto(`P${p}`, Array.from({ length: 4 }, (_, f) =>
      fase(p * 10 + f, Array.from({ length: 8 }, (_, t) => task(`T${p}${f}${t}`, 'In corso', date)), date))))
}

/* Estrae dall'SVG le barre: [{tipo, stato, fill}]. */
function barre(svg) {
  return [...svg.matchAll(/<g data-riga="(\w+)" data-id="[^"]*" data-stato="([^"]*)"><rect [^>]*fill="(#[0-9a-f]{6})"/g)]
    .map(([, tipo, stato, fill]) => ({ tipo, stato, fill }))
}
const vociLegendaSvg = (svg, gruppo) =>
  [...svg.matchAll(new RegExp(`<g data-legenda="${gruppo}" data-stato="([^"]*)">`, 'g'))].map(m => m[1])

/* ── Impaginazione verticale ───────────────────────────────────────── */

test('nessuna riga tagliata: ogni riga sta dentro il corpo della sua pagina', () => {
  const pagine = costruisciPagine(portafoglio(), OPZIONI)
  assert.ok(pagine.length > 1, 'servono più pagine perché il test dica qualcosa')
  const fondo = FOGLIO.altezza - 28 - 22
  for (const p of pagine) {
    for (const r of p.righe) {
      assert.ok(r.y + r.altezza <= fondo + 1e-9, `riga ${r.tipo} ${r.nome} sborda a pagina ${p.numero}`)
    }
  }
})

test('ogni riga compare una volta sola, nell\'ordine progetto, fase, task', () => {
  const progetti = portafoglio()
  const attese = righeGantt(progetti).map(r => `${r.tipo}:${r.id ?? r.progettoId}`)
  const blocchi = impaginaRighe(righeGantt(progetti))
  const viste = blocchi.flat().filter(r => !r.segue).map(r => `${r.tipo}:${r.id ?? r.progettoId}`)
  assert.deepEqual(viste, attese)
})

test('una pagina che comincia dentro un progetto ne ripete l\'intestazione, e nessuna intestazione resta orfana', () => {
  const blocchi = impaginaRighe(righeGantt(portafoglio()))
  blocchi.forEach((b, i) => {
    assert.equal(b[0].tipo, 'progetto', `pagina ${i + 1} senza intestazione di progetto in testa`)
    if (i < blocchi.length - 1) assert.notEqual(b.at(-1).tipo, 'progetto', `intestazione orfana in fondo a pagina ${i + 1}`)
  })
  assert.ok(blocchi.slice(1).some(b => b[0].segue), 'nessuna intestazione «segue» in un portafoglio lungo')
})

test('le righe per pagina non superano l\'altezza a disposizione, al limite esatto', () => {
  const altezza = ALTEZZA_RIGA.progetto + ALTEZZA_RIGA.fase + 3 * ALTEZZA_RIGA.task
  const righe = righeGantt([progetto('P', [fase(1, [task('A'), task('B'), task('C'), task('D')])])])
  const blocchi = impaginaRighe(righe, altezza)
  assert.equal(blocchi.length, 2)
  assert.deepEqual(blocchi[0].map(r => r.tipo), ['progetto', 'fase', 'task', 'task', 'task'])
  assert.deepEqual(blocchi[1].map(r => `${r.tipo}${r.segue ? '+segue' : ''}`), ['progetto+segue', 'task'])
})

/* ── Impaginazione orizzontale ─────────────────────────────────────── */

test('un periodo corto sta in una pagina e la settimana si allarga a riempire il foglio', () => {
  const pagine = costruisciPagine([progetto('P', [fase(1, [task('A')])])], OPZIONI)
  assert.equal(pagine.length, 1)
  assert.ok(pagine[0].larghezzaSettimana >= SETTIMANA_MIN)
  assert.ok(Math.abs(pagine[0].fineAsse - (FOGLIO.larghezza - 28)) < 1e-6, 'l\'asse non arriva al margine destro')
})

test('un periodo lungo si spezza a mesi interi, con la colonna dei nomi su ogni pagina', () => {
  const lunghi = { data_inizio: '2026-01-05', data_fine: '2027-12-20' }
  const pagine = costruisciPagine([progetto('P', [fase(1, [task('A', 'In corso', lunghi)], lunghi)])], OPZIONI)
  assert.ok(pagine.length > 1)
  for (const p of pagine) {
    assert.ok(p.larghezzaSettimana >= SETTIMANA_MIN, `settimana a ${p.larghezzaSettimana} pt`)
    assert.ok(p.fineAsse <= FOGLIO.larghezza - 28 + 1e-6)
    assert.deepEqual(p.righe.map(r => r.nome), ['Progetto P', 'Fase 1', 'Task A'])
    // Ogni periodo dopo il primo comincia col primo lunedì di un mese.
    if (p.numero > 1) assert.ok(p.settimane[0].inizioMese, `pagina ${p.numero} non comincia a inizio mese`)
  }
  const svg = disegnaGantt([progetto('P', [fase(1, [task('A', 'In corso', lunghi)], lunghi)])], OPZIONI)
  svg.forEach(s => assert.match(s, /Progetto \/ Fase \/ Task/))
})

test('periodiAsse: periodi contigui che coprono tutte le settimane', () => {
  const inizioMesi = Array.from({ length: 24 }, (_, i) => Math.round(i * 4.35))
  const { weekPx, periodi } = periodiAsse(104, inizioMesi, 500)
  assert.ok(weekPx >= SETTIMANA_MIN)
  assert.equal(periodi[0].da, 0)
  assert.equal(periodi.at(-1).a, 104)
  periodi.slice(1).forEach((p, i) => assert.equal(p.da, periodi[i].a))
  periodi.forEach(p => assert.ok((p.a - p.da) * weekPx <= 500 + 1e-9))
})

test('periodiAsse: il minimo numero di periodi, senza un foglio di coda quasi vuoto', () => {
  // 58 settimane, al massimo 27 per foglio: tre fogli. Riempiendoli fino al
  // massimo, a mesi interi, sarebbero 26 + 26 + 6: un foglio quasi bianco.
  const inizioMesi = Array.from({ length: 14 }, (_, i) => Math.round(i * 4.35))
  const { periodi } = periodiAsse(58, inizioMesi, 27 * SETTIMANA_MIN)
  assert.equal(periodi.length, 3)
  const lunghezze = periodi.map(p => p.a - p.da)
  assert.ok(Math.min(...lunghezze) >= 10, `foglio di coda troppo corto: ${lunghezze}`)
  periodi.slice(1).forEach(p => assert.ok(inizioMesi.includes(p.da), `periodo che non comincia a inizio mese: ${p.da}`))
})

test('l\'intestazione «segue» resta leggibile anche con un nome lungo', () => {
  const nomeLungo = 'Progetto con un nome davvero molto lungo che non entra nella colonna'
  const progetti = portafoglio(1).map(p => ({ ...p, nome: nomeLungo }))
  const svg = disegnaGantt(progetti, OPZIONI)
  assert.ok(svg.length > 1)
  assert.match(svg[1], /… \(segue\)<\/text>/)
})

/* ── Colori e legenda ──────────────────────────────────────────────── */

test('i colori delle barre vengono dal modulo unico, stato per stato', () => {
  const stati = Object.keys(STATI_TASK)
  const progetti = [progetto('P', [
    fase(1, stati.map((s, i) => task(`T${i}`, s))),
    ...Object.keys(STATI_FASE).map((s, i) => fase(10 + i, [], { stato: s })),
    fase(99, [task('X', 'Stato inventato')]),
  ])]
  const tutte = disegnaGantt(progetti, OPZIONI).flatMap(barre)
  for (const s of stati) {
    assert.equal(tutte.find(b => b.tipo === 'task' && b.stato === s)?.fill, STATI_TASK[s].colore, `task ${s}`)
  }
  for (const s of Object.keys(STATI_FASE)) {
    assert.equal(tutte.find(b => b.tipo === 'fase' && b.stato === s)?.fill, STATI_FASE[s].colore, `fase ${s}`)
  }
  assert.equal(tutte.find(b => b.stato === 'Stato inventato').fill, COLORE_IGNOTO)
})

test('la legenda elenca i soli stati presenti nella pagina', () => {
  const progetti = [progetto('P', [fase(1, [task('A', 'Bloccato'), task('B', 'Completato')], { stato: 'Sospesa' })])]
  const [svg] = disegnaGantt(progetti, OPZIONI)
  assert.deepEqual(vociLegendaSvg(svg, 'task'), ['Completato', 'Bloccato'])
  assert.deepEqual(vociLegendaSvg(svg, 'fase'), ['Sospesa'])
})

test('la legenda non spiega colori che la pagina non mostra: un periodo senza quella barra non la cita', () => {
  const lunghi = { data_inizio: '2026-01-05', data_fine: '2027-12-20' }
  const progetti = [progetto('P', [fase(1, [
    task('PRESTO', 'Completato', { data_inizio: '2026-01-05', data_fine: '2026-01-20' }),
    task('TARDI', 'Bloccato', { data_inizio: '2027-11-01', data_fine: '2027-12-20' }),
  ], lunghi)])]
  const svg = disegnaGantt(progetti, OPZIONI)
  assert.ok(svg.length > 1)
  assert.deepEqual(vociLegendaSvg(svg[0], 'task'), ['Completato'])
  assert.deepEqual(vociLegendaSvg(svg.at(-1), 'task'), ['Bloccato'])
})

/* ── Contenuto ─────────────────────────────────────────────────────── */

test('i task «Eliminato» non entrano nel disegno', () => {
  const progetti = [progetto('P', [fase(1, [task('VIVO'), task('MORTO', 'Eliminato')])])]
  assert.deepEqual(righeGantt(progetti).filter(r => r.tipo === 'task').map(r => r.id), ['VIVO'])
  const [svg] = disegnaGantt(progetti, OPZIONI)
  assert.ok(!svg.includes('Task MORTO'))
  assert.ok(!vociLegendaSvg(svg, 'task').includes('Eliminato'))
})

test('tutte le fasi e tutti i task, con l\'assegnatario accanto al task', () => {
  const progetti = [progetto('P', [fase(1, [task('A')]), fase(2, [task('B', 'In corso', { dipendente_nome: 'Altra persona' })])])]
  const [svg] = disegnaGantt(progetti, OPZIONI)
  for (const testo of ['Fase 1', 'Fase 2', 'Task A', 'Task B', 'Persona di prova', 'Altra persona']) {
    assert.ok(svg.includes(testo), testo)
  }
})

test('le ore pianificate compaiono con la loro etichetta solo se il payload le porta', () => {
  const senza = disegnaGantt([progetto('P', [fase(1, [task('A', 'In corso', { ore_stimate: 40 })])])], OPZIONI)[0]
  assert.ok(!senza.includes('Ore pianificate'))
  assert.ok(!senza.includes('40 h'), 'le ore stimate non sostituiscono le pianificate')

  const con = disegnaGantt([progetto('P', [fase(1, [task('A', 'In corso', { ore_pianificate: 12.5 }), task('B')])])], OPZIONI)[0]
  assert.ok(con.includes('Ore pianificate'))
  assert.ok(con.includes('12,5 h'))
  assert.equal((con.match(/ h<\/text>/g) || []).length, 1, 'il task senza ore non ne mostra')
})

test('righe senza date: la riga c\'è, la barra no; nessun progetto: una pagina vuota', () => {
  const progetti = [progetto('P', [fase(1, [task('A', 'In corso', { data_inizio: null, data_fine: null })], { data_inizio: null, data_fine: null })])]
  const pagine = costruisciPagine(progetti, OPZIONI)
  assert.equal(pagine.length, 1)
  assert.ok(pagine[0].righe.every(r => r.barra === null))
  assert.match(pagine[0].sottotitolo, /Intervallo nessuna data/)
  assert.equal(costruisciPagine([], OPZIONI).length, 1)
  assert.equal(costruisciPagine(null, OPZIONI).length, 1)
})

test('intestazione: titolo, data di generazione, intervallo, «Pagina X di Y»', () => {
  const pagine = costruisciPagine(portafoglio(), OPZIONI)
  pagine.forEach(p => {
    assert.equal(p.titolo, 'GANTT — Portafoglio')
    assert.match(p.sottotitolo, /Generato il 15\/10\/2026 alle 10:00/)
    assert.match(p.sottotitolo, /Intervallo 02\/03\/2026 – 30\/06\/2026/)
    assert.match(p.sottotitolo, new RegExp(`Pagina ${p.numero} di ${pagine.length}$`))
  })
  assert.equal(titoloGantt('Progetto Uno'), 'GANTT — Progetto Uno')
  assert.equal(titoloGantt(null), 'GANTT — Portafoglio')
})

test('la data di oggi è quella locale, non quella UTC', () => {
  // 00:30 del 15 ottobre a Roma sono le 22:30 del 14 in UTC.
  const mezzanotte = new Date(2026, 9, 15, 0, 30)
  assert.equal(isoLocale(mezzanotte), '2026-10-15')
  assert.notEqual(mezzanotte.toISOString().slice(0, 10), '2026-10-15')
})

test('la linea di oggi cade sul giorno locale, e manca se oggi è fuori dal periodo', () => {
  const settimana = { data_inizio: '2026-10-12', data_fine: '2026-10-19' }
  const progetti = [progetto('P', [fase(1, [task('A', 'In corso', settimana)], settimana)])]
  const p = costruisciPagine(progetti, { ...OPZIONI, oggi: new Date(2026, 9, 15, 0, 30) })[0]
  const barra = p.righe.find(r => r.tipo === 'task').barra
  const giorno = barra.w / 7
  assert.ok(Math.abs(p.xOggi - (barra.x + 3 * giorno)) < 1e-6, 'oggi non cade sul 15/10')
  const fuori = costruisciPagine(progetti, { ...OPZIONI, oggi: new Date(2030, 0, 1) })[0]
  assert.equal(fuori.xOggi, null)
})

test('nessun nome di azienda nel modulo di disegno', () => {
  const sorgente = fs.readFileSync(new URL('../src/components/_shared/ganttSvg.js', import.meta.url), 'utf-8')
  assert.ok(!/IMC/i.test(sorgente))
})
