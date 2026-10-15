/**
 * esportaGantt.js — Dai fogli SVG di ganttSvg.js ai file: PDF e PNG.
 *
 * Gira nel browser (DOMParser, Image, canvas) ma non dipende da un framework.
 * Un solo disegnatore: PDF e PNG partono dalle stesse pagine SVG, quindi hanno
 * la stessa impaginazione — una pagina PDF per foglio, un PNG per foglio.
 *
 * jsPDF e svg2pdf.js pesano: chi lo usa lo importa al clic (`import()`), così
 * non entrano nel caricamento iniziale dell'applicazione.
 */
import { jsPDF } from 'jspdf'
import { svg2pdf } from 'svg2pdf.js'
import { FOGLIO, isoLocale } from './ganttSvg.js'

// 200 dpi: leggibile stampato, e un A4 resta sotto i 2400 px di lato.
const DPI_PNG = 200

const elementoSvg = (svg) => new DOMParser().parseFromString(svg, 'image/svg+xml').documentElement

export async function pdfDaPagine(pagine) {
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

// Chromium scarta in silenzio i download automatici oltre una decina al
// secondo, e un PNG si genera in ~15 ms: senza pausa, di 28 fogli ne
// arrivavano 10. Misurato: a 100 ms di distanza passano tutti; 250 dà margine.
const PAUSA_FRA_DOWNLOAD_MS = 250

export async function esportaPng(pagine, nomeBase) {
  for (let i = 0; i < pagine.length; i++) {
    if (i > 0) await new Promise(r => setTimeout(r, PAUSA_FRA_DOWNLOAD_MS))
    const nome = pagine.length === 1 ? `${nomeBase}.png` : `${nomeBase}_pagina-${i + 1}-di-${pagine.length}.png`
    scaricaBlob(await pngDaPagina(pagine[i]), nome)
  }
}
