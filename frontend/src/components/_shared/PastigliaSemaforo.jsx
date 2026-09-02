/**
 * ═════════════════════════════════════════════════════════════════════════
 * PastigliaSemaforo.jsx — Indicatore del semaforo ritardabilità
 * ═════════════════════════════════════════════════════════════════════════
 *
 * Semaforo strato 1 (01/09/2026). Disegna il colore che il backend calcola su
 * ogni unità di lavoro — progetto, fase, task, sottotask — e lo espone nel
 * payload di /api/gantt/strutturato come sotto-oggetto:
 *
 *     "semaforo": { colore, origine, figli_rossi }
 *
 * NON ESTENDE StatoBadge, pur standogli accanto e copiandone l'idioma
 * (text-xs, rounded, padding piccoli). Sono due ASSI DIVERSI:
 *   - StatoBadge       → lo STATO DICHIARATO. Una stringa che qualcuno ha
 *                        scritto: «In corso», «Sospeso».
 *   - PastigliaSemaforo→ un GIUDIZIO CALCOLATO sul rischio-ritardo, dedotto da
 *                        date e stato e aggregato dai figli.
 * Un task può essere «In corso» (stato) e rosso (semaforo): sono due
 * informazioni indipendenti, e fonderle in un badge solo ne farebbe sparire
 * una.
 *
 * FORMA — una PILLOLA orizzontale, non un cerchio, e la scelta è deliberata:
 * la tab Scenari usa già 🔴🟡⚪ (emoji tonde) per le criticità di
 * `calcolaCriticita`, che risponde a una domanda DIVERSA («il piano è scritto
 * bene?» invece di «siamo in ritardo?»). Le due possono comparire nella stessa
 * pagina: se avessero la stessa forma sembrerebbero lo stesso indicatore.
 *
 * COLORI — dalla palette già nel design system (index.css, `.conseguenza-*`):
 *   rosso  red-500    #ef4444   in ritardo
 *   giallo amber-500  #f59e0b   a rischio — STRATO 2, oggi non arriva mai
 *   grigio gray-500   #6b7280   non calcolabile (fermo, o senza data)
 *   verde  green-500  #22c55e   in tempo
 * Le classi stanno in una MAPPA STATICA con stringhe letterali, non composte a
 * runtime. Tailwind scansiona il sorgente e non vede le classi assemblate:
 * `bg-${colore}-500` non finirebbe nel CSS. È lo stesso difetto che oggi
 * lascia senza sfondo le criticità di livello «basso» in ElencoDettaglio
 * (`bg-gray-900/30` non esiste nel CSS compilato).
 *
 * IL VERDE SI RENDE SEMPRE, ma quieto: più corto e al 40% di opacità. Un
 * semaforo che non mostra niente quando va tutto bene è indistinguibile da un
 * semaforo rotto — «calcolato e a posto» e «non calcolato» devono restare due
 * cose diverse a colpo d'occhio. L'altezza resta la stessa degli altri colori
 * così la colonna di pastiglie non balla; cambia solo la larghezza.
 *
 * ORIGINE → FORMA, una regola sola valida per ogni colore:
 *   "propria" / "entrambe" → PIENA   «il problema è QUI»
 *   "figli"                → CAVA    «il problema è SOTTO»
 * È la gradazione che permette di distinguere un progetto rosso di suo (P004,
 * scadenza passata) da uno rosso perché contiene un task in ritardo (P002, che
 * ha ancora 60 giorni davanti) senza che il backend inventi soglie.
 *
 * `semaforo` assente o null → non rende NULLA. L'innesto resta additivo per
 * costruzione: una riga senza semaforo è identica a com'era prima. Un
 * segnaposto «neutro» inventerebbe un segnale, e il grigio è già preso e
 * significa un'altra cosa precisa.
 */

import React from 'react'

// Mappa statica: le classi devono comparire LETTERALI perché Tailwind le veda.
const STILE_COLORE = {
  rosso:  { pieno: 'bg-red-500 border-red-500',     cavo: 'border-red-500' },
  giallo: { pieno: 'bg-amber-500 border-amber-500', cavo: 'border-amber-500' },
  grigio: { pieno: 'bg-gray-500 border-gray-500',   cavo: 'border-gray-500' },
  verde:  { pieno: 'bg-green-500 border-green-500', cavo: 'border-green-500' },
}

// Come si chiamano i «figli» a ciascun livello. Serve solo al tooltip: il
// componente non sa da solo dove sta, e dire «task interni» sotto un progetto
// sarebbe sbagliato (i figli diretti di un progetto sono le FASI).
const FIGLI_DI = {
  progetto: ['fase', 'fasi'],
  fase: ['task', 'task'],
  task: ['sottotask', 'sottotask'],
}

const STATI_FERMI = ['Sospeso', 'Sospesa']

function testoTooltip({ colore, origine, figli_rossi }, stato, livello) {
  const n = figli_rossi || 0
  const [sing, plur] = FIGLI_DI[livello] || ['unità interna', 'unità interne']
  const quanti = `${n} ${n === 1 ? sing : plur}`
  const verbo = n === 1 ? 'è in ritardo' : 'sono in ritardo'

  if (colore === 'verde') return 'In tempo'

  if (colore === 'grigio') {
    // I DUE GRIGI, distinti QUI e non nel colore. La decisione presa a monte è
    // «un grigio solo, due tooltip»: il backend restituisce lo stesso colore
    // per «fermo» e «senza data» perché la risposta è la stessa — non
    // calcolabile — ma il motivo è diverso e l'utente ha diritto di saperlo.
    if (STATI_FERMI.includes(stato)) return 'Sospeso: fermo per decisione, il semaforo si astiene'
    if (origine === 'figli') return `Non calcolabile: ${quanti} senza giudizio`
    return 'Non calcolabile: manca la data di fine'
  }

  const etichetta = colore === 'rosso' ? 'In ritardo' : 'A rischio'
  if (origine === 'figli') return `${etichetta}: ${quanti} ${verbo}`
  if (origine === 'entrambe') return `${etichetta}: scadenza passata, e ${quanti} ${verbo}`
  return `${etichetta}: la scadenza è passata`
}

export default function PastigliaSemaforo({ semaforo, stato, livello = 'task' }) {
  // Additivo per costruzione: niente semaforo, niente pastiglia.
  if (!semaforo || !semaforo.colore) return null

  const stile = STILE_COLORE[semaforo.colore]
  if (!stile) return null   // colore fuori vocabolario: meglio niente che un buco colorato

  // "figli" = il colore viene da sotto → pastiglia cava. Ogni altro caso
  // ("propria", "entrambe", e il null del verde) → piena.
  const cava = semaforo.origine === 'figli'
  const quieto = semaforo.colore === 'verde'

  return (
    <span
      title={testoTooltip(semaforo, stato, livello)}
      aria-label={testoTooltip(semaforo, stato, livello)}
      className={
        'inline-block rounded-full border-[1.5px] align-middle flex-shrink-0 ' +
        (quieto ? 'w-3 h-2.5 opacity-40 ' : 'w-5 h-2.5 ') +
        (cava ? `bg-transparent ${stile.cavo}` : stile.pieno)
      }
    />
  )
}
