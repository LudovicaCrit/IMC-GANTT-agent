/**
 * esportaGantt.js — Dai fogli SVG di ganttSvg.js ai file: PDF e PNG; e il
 * download dei file, Excel compreso.
 *
 * Gira nel browser (DOMParser, Image, canvas) ma non dipende da un framework.
 * Un solo disegnatore: PDF e PNG partono dalle stesse pagine SVG, quindi hanno
 * la stessa impaginazione — una pagina PDF per foglio, un PNG per foglio (in
 * uno ZIP, se i fogli sono più d'uno).
 *
 * jsPDF, svg2pdf.js e fflate pesano: si importano (`import()`) solo dentro la
 * funzione che li usa, al clic. Così non entrano nel caricamento iniziale
 * dell'applicazione, e l'Excel, che arriva già fatto dal server, non li carica.
 */
import { FOGLIO, isoLocale } from './ganttSvg.js'

// 200 dpi: leggibile stampato, e un A4 resta sotto i 2400 px di lato.
const DPI_PNG = 200

const elementoSvg = (svg) => new DOMParser().parseFromString(svg, 'image/svg+xml').documentElement

export async function pdfDaPagine(pagine) {
  const [{ jsPDF }, { svg2pdf }] = await Promise.all([import('jspdf'), import('svg2pdf.js')])
  const doc = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'a4' })
  for (let i = 0; i < pagine.length; i++) {
    if (i > 0) doc.addPage('a4', 'landscape')
    await svg2pdf(elementoSvg(pagine[i]), doc, { x: 0, y: 0, width: FOGLIO.larghezza, height: FOGLIO.altezza })
  }
  return doc.output('blob')
}

export async function pngDaPagina(svg) {
  const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }))
  try {
    const img = new Image()
    img.src = url
    await img.decode()
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(FOGLIO.larghezza * DPI_PNG / 72)
    canvas.height = Math.round(FOGLIO.altezza * DPI_PNG / 72)
    canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height)
    return await new Promise((ok, ko) =>
      canvas.toBlob(b => (b ? ok(b) : ko(new Error('PNG non generato'))), 'image/png'))
  } finally {
    URL.revokeObjectURL(url)
  }
}

export function scaricaBlob(blob, nomeFile) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nomeFile
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/** gantt_<progetto o portafoglio>_<data locale> */
export function nomeBaseFile(progettoId, oggi = new Date()) {
  return `gantt_${progettoId || 'portafoglio'}_${isoLocale(oggi)}`
}

export async function esportaPdf(pagine, nomeBase) {
  scaricaBlob(await pdfDaPagine(pagine), `${nomeBase}.pdf`)
}

/** Il nome del PNG di un foglio dentro lo ZIP: il numero ha gli zeri davanti,
 *  così l'ordine alfabetico dei file è l'ordine dei fogli. */
export function nomePngFoglio(nomeBase, i, totale) {
  const cifre = String(totale).length
  return `${nomeBase}_pagina-${String(i + 1).padStart(cifre, '0')}-di-${totale}.png`
}

// Un foglio solo: un PNG. Più fogli: un solo ZIP con un PNG per foglio, un
// download e non uno per foglio (il browser li bloccherebbe o li chiederebbe
// uno a uno). Livello 0, cioè solo archiviati: un PNG è già compresso, e
// ricomprimerlo costerebbe tempo senza guadagnare spazio.
export async function esportaPng(pagine, nomeBase) {
  if (pagine.length === 1) {
    scaricaBlob(await pngDaPagina(pagine[0]), `${nomeBase}.png`)
    return
  }
  const { zipSync } = await import('fflate')
  const file = {}
  for (let i = 0; i < pagine.length; i++) {
    const png = await pngDaPagina(pagine[i])
    file[nomePngFoglio(nomeBase, i, pagine.length)] = new Uint8Array(await png.arrayBuffer())
  }
  scaricaBlob(new Blob([zipSync(file, { level: 0 })], { type: 'application/zip' }), `${nomeBase}.zip`)
}
