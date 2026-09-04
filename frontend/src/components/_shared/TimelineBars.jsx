/**
 * ═════════════════════════════════════════════════════════════════════════
 * TimelineBars.jsx — Barre su una scala del tempo, senza sapere da dove vengono
 * ═════════════════════════════════════════════════════════════════════════
 *
 * Riceve una lista piatta di barre e le disegna. Non sa cosa siano: possono
 * venire da uno snapshot SAL, da `/api/gantt/strutturato`, da un preventivo.
 * Chi chiama appiattisce la propria struttura in `{label, data_inizio,
 * data_fine, stato, livello}` e passa il risultato — l'adattatore è del
 * chiamante, la resa è qui.
 *
 * È l'AGNOSTICISMO a renderlo riusabile: nel momento in cui questo componente
 * sapesse cos'è una fase o cos'è uno snapshot, il prossimo che vuole disegnare
 * barre dovrebbe o piegare i propri dati a quel vocabolario o riscrivere tutto.
 *
 * ── PERCHÉ LE PROPORZIONI CORRISPONDONO AL GANTT VERO ────────────────
 * `buildTimeline` e `barXW` arrivano da `timelineScale.js`, la STESSA
 * aritmetica che usa `/gantt`. Non è una comodità: è l'unica ragione per cui
 * due barre che nel GANTT stanno in rapporto 1:3 stanno 1:3 anche qui. Se la
 * formula fosse ricopiata, le due viste divergerebbero senza che nessun test
 * se ne accorga — entrambe sarebbero internamente coerenti, e lo scarto si
 * vedrebbe solo affiancando due schermate.
 *
 * `weekPxMax` più basso del GANTT a pagina intera è l'UNICA differenza: cambia
 * la DENSITÀ (quanti pixel vale una settimana), non le proporzioni, perché
 * `barXW` divide per la stessa scala che ha prodotto quella larghezza.
 *
 * ── LE DUE LINEE DICONO COSE DIVERSE ─────────────────────────────────
 *   DATA-SCATTO → marcata. È un DATO: quel giorno qualcuno ha consolidato, e
 *                 tutto ciò che si vede è vero a quell'istante.
 *   OGGI        → tratteggiata. Su una fotografia del passato «oggi» non è
 *                 dato: è dove saremmo ORA rispetto a quei tempi congelati.
 *                 Utile per leggere («questa fase sarebbe già finita»), ma non
 *                 è nel dato — e il tratteggio lo dice senza una legenda.
 *
 * ── `livello`: PRONTO, NON COSTRUITO ─────────────────────────────────
 * Oggi 0 = fase, 1 = task. Il rientro cresce con il livello e i livelli ≥1
 * condividono lo stile-task, quindi dei sottotask (livello 2) si disegnerebbero
 * già — ma NESSUNO li passa ancora: il GANTT annidato è un lavoro suo, con la
 * sua espansione e i suoi colori. Qui c'è solo il posto dove andranno.
 */

import React, { useMemo } from 'react'
import { buildTimeline, barXW } from './timelineScale'

/* ── Colori per stato ──────────────────────────────────────────────────
 * Due mappe perché il dominio ha due generi: una fase è «Completata», un task
 * è «Completato». Sono stringhe diverse e nessuna delle due chiave funziona
 * sull'altra mappa — tenerle separate è più onesto di una mappa unica con le
 * chiavi doppie.
 *
 * La mappa TASK qui è COMPLETA (6 stati). Quella di `GanttChartFasi` ne ha 4:
 * lì un task «Sospeso» o «Annullato» cade sul fallback grigio, indistinguibile
 * da un «Da iniziare». Non l'ho allineata: cambiare i colori del GANTT vero è
 * un altro lavoro, e questo doveva essere additivo. Restano due copie — è un
 * debito noto, non una svista.
 */
export const COLORI_FASE = {
  'Da iniziare': '#9ca3af',  // gray-400
  'In corso':    '#3b82f6',  // blue-500
  'Completata':  '#22c55e',  // green-500
  'Sospesa':     '#d97706',  // amber-600
  'Annullata':   '#6b7280',  // gray-500 — più desaturato: è uscita di scena
}

export const COLORI_TASK = {
  'Da iniziare': '#9ca3af',
  'In corso':    '#3b82f6',
  'Completato':  '#22c55e',
  'Bloccato':    '#ef4444',  // red-500
  'Sospeso':     '#d97706',  // ← assente in GanttChartFasi
  'Annullato':   '#6b7280',  // ← assente in GanttChartFasi
}

// Stato ignoto → grigio, come il vecchio GANTT. Uno stato che non conosciamo
// non deve far sparire la barra: meglio una barra neutra di un buco.
const COLORE_IGNOTO = '#9ca3af'

/* ── Marcatura del CAMBIAMENTO (opzionale) ─────────────────────────────
 * Se una barra porta `diff`, il componente entra in «modalità evidenziato».
 * L'innesto è additivo per costruzione: senza `diff` non si attraversa una
 * sola riga di questo codice, e il mini-GANTT normale resta identico.
 *
 * IL COLORE DI STATO NON VIENE SOSTITUITO. Il diff si aggiunge come CONTORNO,
 * perché il GANTT che si guarda resta il «dopo» e deve restare leggibile come
 * GANTT: se il cambiamento rubasse il colore, per sapere in che stato è una
 * fase slittata bisognerebbe spegnere il confronto. Due informazioni, due
 * canali — riempimento = stato, contorno = cambiamento.
 *
 * L'INVARIATO SI ATTENUA. È questa la differenza fra «evidenziato» e
 * «colorato»: se tutto resta a piena intensità, il cambiato non salta
 * all'occhio — è solo un altro colore in mezzo a venti. Attenuando il resto,
 * ciò che è cambiato emerge senza bisogno di cercarlo.
 */
const MARCA_DIFF = {
  slittato:   { colore: '#f59e0b', etichetta: 'slittato' },   // amber-500
  nuovo:      { colore: '#22c55e', etichetta: 'nuovo' },      // green-500
  sparito:    { colore: '#ef4444', etichetta: 'sparito' },    // red-500
  modificato: { colore: '#a855f7', etichetta: 'modificato' }, // purple-500
  invariato:  null,                                            // nessuna marca
}
const OPACITA_INVARIATO = 0.28

/* ── Geometria delle righe ─────────────────────────────────────────────
 * Stesse altezze di `GanttChartFasi`, così le due viste "pesano" uguale
 * all'occhio: una fase è una fascia, un task un filo.
 */
const STILE_FASE = { riga: 28, barra: 16, colori: COLORI_FASE, raggio: 3, opacita: 0.9 }
const STILE_TASK = { riga: 18, barra: 10, colori: COLORI_TASK, raggio: 2, opacita: 0.65 }
const stilePerLivello = (livello) => (livello > 0 ? STILE_TASK : STILE_FASE)
const rientroPerLivello = (livello) => 10 + Math.max(0, livello) * 12

const HEADER_H = 24

/**
 * @param {Array} barre        {label, data_inizio, data_fine, stato, livello, sottotitolo?}
 * @param {number} weekPxMax   tetto della densità — più basso = più compatto
 * @param {number} labelW      larghezza colonna etichette (layout, non scala)
 * @param {string} dataScatto  ISO della linea marcata; null = nessuna linea
 * @param {number} maxHeight   oltre questa altezza il riquadro scorre da solo
 */
export default function TimelineBars({
  barre,
  weekPxMax = 32,
  labelW = 190,
  dataScatto = null,
  maxHeight = 420,
  messaggioVuoto = 'Nessuna barra da disegnare.',
}) {
  // Solo le barre CON entrambe le date entrano nella scala: una data mancante
  // renderebbe la timeline degenere (NaN si propaga a min/max e l'asse sparisce
  // per tutti). La riga si disegna lo stesso, senza barra — vedi sotto.
  //
  // Le OMBRE (posizione precedente di una barra slittata) entrano nella scala
  // come le barre: se una fase è stata anticipata, il suo «prima» sta a
  // sinistra di tutto il resto, e lasciandolo fuori dal calcolo finirebbe fuori
  // dall'asse — visibile solo scrollando all'indietro nel vuoto.
  const timeline = useMemo(() => {
    const estremi = []
    for (const b of barre || []) {
      if (b.data_inizio && b.data_fine) estremi.push({ start: b.data_inizio, end: b.data_fine })
      if (b.ombra?.data_inizio && b.ombra?.data_fine) estremi.push({ start: b.ombra.data_inizio, end: b.ombra.data_fine })
    }
    return buildTimeline(estremi, { weekPxMax })
  }, [barre, weekPxMax])

  // Modalità dedotta, non un prop in più: una barra o porta un verdetto o no.
  // Un diff che risulta «tutto invariato» accende comunque la modalità — ed è
  // giusto, perché «ho confrontato e non è cambiato niente» è una risposta.
  const modalitaDiff = useMemo(() => (barre || []).some(b => b.diff), [barre])

  if (!timeline || !barre || barre.length === 0) {
    return <p className="text-xs text-gray-500 italic py-3">{messaggioVuoto}</p>
  }

  const { totalWidth, weekPx, weeks, months } = timeline

  // Le due linee verticali: stessa aritmetica delle barre (`barXW` su un
  // istante puntuale ⇒ la sua `x`), non una formula riderivata a mano.
  const xDi = (iso) => (iso ? barXW(timeline, iso, iso).x : null)
  const oggiX = xDi(new Date().toISOString().slice(0, 10))
  const scattoX = xDi(dataScatto)
  const dentro = (x) => x != null && x >= 0 && x <= totalWidth

  const larghezzaTotale = labelW + totalWidth

  return (
    <div>
      {/* UN solo contenitore che scorre in entrambe le direzioni. Le celle
          etichetta sono `sticky left: 0` e l'header `sticky top: 0`: il
          browser tiene le due cose ferme da solo, senza la sincronizzazione
          a tre scroll del GANTT grande — che lì serve perché le colonne sono
          pannelli separati, qui no. */}
      <div className="overflow-auto rounded-lg border border-border-subtle bg-surface-900/40"
           style={{ maxHeight }}>
        <div style={{ width: larghezzaTotale, position: 'relative' }}>

          {/* ── Header: i mesi ─────────────────────────────────────────
              Niente riga-settimane: a densità ridotta le date si
              accavallerebbero, e i mesi bastano a leggere «dove siamo». Le
              settimane restano come righello di sfondo. */}
          <div className="flex sticky top-0 z-30" style={{ height: HEADER_H }}>
            <div className="sticky left-0 z-40 flex items-end px-2 pb-0.5 bg-surface-900
                            border-b border-r border-border-subtle text-[10px] text-gray-500"
                 style={{ width: labelW, minWidth: labelW }}>
              Fase / Task
            </div>
            <div className="flex bg-surface-900 border-b border-border-subtle"
                 style={{ width: totalWidth }}>
              {months.map((m, i) => (
                <div key={i}
                     className="flex-shrink-0 text-[10px] text-gray-400 flex items-center px-1.5
                                border-r border-border-subtle/50 overflow-hidden"
                     style={{
                       width: m.width, minWidth: m.width,
                       backgroundColor: i % 2 === 0 ? 'rgba(30,35,50,0.5)' : 'transparent',
                     }}>
                  {m.width > 34 ? m.label : ''}
                </div>
              ))}
            </div>
          </div>

          {/* ── Corpo: una riga per barra ──────────────────────────────
              `position: relative` perché le due linee verticali sono un
              overlay a tutta altezza: devono attraversare TUTTE le righe,
              non ripetersi dentro ognuna. */}
          <div style={{ position: 'relative' }}>

            {/* Overlay linee — sopra le barre (le linee sono la lettura, le
                barre il dato) ma sotto le etichette sticky, e trasparente ai
                click perché non è un elemento con cui si interagisce. */}
            <div className="pointer-events-none"
                 style={{ position: 'absolute', top: 0, left: labelW, width: totalWidth, height: '100%', zIndex: 20 }}>
              {dentro(oggiX) && (
                <div title="oggi — non è nel dato: è dove saremmo ora"
                     style={{
                       position: 'absolute', left: oggiX, top: 0, height: '100%',
                       borderLeft: '1px dashed rgba(148,163,184,0.75)',   // slate-400
                     }} />
              )}
              {dentro(scattoX) && (
                <div style={{ position: 'absolute', left: scattoX, top: 0, height: '100%' }}>
                  <div style={{ width: 2, height: '100%', backgroundColor: 'rgba(245,158,11,0.9)' }} />
                  <span className="absolute top-0 text-[9px] font-semibold px-1 rounded-sm whitespace-nowrap"
                        style={{ left: 3, backgroundColor: 'rgba(245,158,11,0.9)', color: '#1c1917' }}>
                    scatto
                  </span>
                </div>
              )}
            </div>

            {barre.map((b, i) => {
              const st = stilePerLivello(b.livello)
              const disegnabile = Boolean(b.data_inizio && b.data_fine)
              const { x, w } = disegnabile ? barXW(timeline, b.data_inizio, b.data_fine) : { x: 0, w: 0 }
              const colore = st.colori[b.stato] || COLORE_IGNOTO
              const marca = modalitaDiff ? MARCA_DIFF[b.diff] : null
              const attenuata = modalitaDiff && !marca
              const sparita = b.diff === 'sparito'
              const titolo = [
                b.label,
                b.stato && `Stato: ${b.stato}`,
                disegnabile ? `${b.data_inizio} → ${b.data_fine}` : 'senza date',
                b.sottotitolo,
                b.diffTesto,
              ].filter(Boolean).join('\n')

              // Ombra: dov'era la barra PRIMA. Un contorno vuoto, senza
              // riempimento — non è uno stato, è una memoria.
              const ombra = b.ombra?.data_inizio && b.ombra?.data_fine
                ? barXW(timeline, b.ombra.data_inizio, b.ombra.data_fine)
                : null

              return (
                <div key={b.chiave ?? i} className="flex" style={{ height: st.riga }}>
                  <div className="sticky left-0 z-10 flex items-center bg-surface-900
                                  border-r border-border-subtle"
                       style={{ width: labelW, minWidth: labelW, paddingLeft: rientroPerLivello(b.livello) }}>
                    <span className={`truncate ${b.livello > 0
                            ? 'text-[11px] text-gray-400'
                            : 'text-xs font-medium text-gray-200'}`}
                          style={{
                            // La sbarratura sul NOME, non solo sulla barra:
                            // una voce sparita si riconosce dalla colonna
                            // etichette anche quando la sua barra è fuori
                            // dalla porzione visibile dell'asse.
                            textDecoration: sparita ? 'line-through' : undefined,
                            opacity: attenuata ? 0.45 : 1,
                          }}
                          title={titolo}>
                      {b.label}
                    </span>
                    {marca && (
                      <span className="ml-1 shrink-0 rounded-sm px-1 text-[8px] font-bold uppercase"
                            style={{ backgroundColor: marca.colore, color: '#0f1219' }}
                            title={b.diffTesto || marca.etichetta}>
                        {marca.etichetta[0]}
                      </span>
                    )}
                  </div>

                  {/* Il righello delle settimane è lo SFONDO della traccia, non
                      un layer di div: una linea ogni `weekPx` disegnata dal
                      gradiente costa zero nodi anche su un progetto di 4 anni. */}
                  <div style={{
                    position: 'relative', width: totalWidth,
                    backgroundImage: `repeating-linear-gradient(to right,
                        rgba(100,116,139,0.18) 0px, rgba(100,116,139,0.18) 1px,
                        transparent 1px, transparent ${weekPx}px)`,
                  }}>
                    {/* L'ombra si disegna PRIMA della barra: sta sotto, come
                        un ricordo dietro il fatto. */}
                    {ombra && (
                      <div className="absolute pointer-events-none"
                           style={{
                             left: ombra.x, top: (st.riga - st.barra) / 2,
                             width: ombra.w, height: st.barra,
                             border: `1px dashed ${MARCA_DIFF.slittato.colore}`,
                             borderRadius: st.raggio, opacity: 0.55,
                           }} />
                    )}
                    {disegnabile && (
                      <div className="absolute hover:brightness-110 transition-all"
                           style={{
                             left: x, top: (st.riga - st.barra) / 2,
                             width: w, height: st.barra, minWidth: 4,
                             // Una voce SPARITA non ha un "dopo": la sua barra
                             // è disegnata dai dati del PRIMA, e va detto —
                             // vuota e sbarrata, non piena come le altre.
                             backgroundColor: sparita ? 'transparent' : colore,
                             opacity: attenuata ? OPACITA_INVARIATO : st.opacita,
                             borderRadius: st.raggio,
                             border: sparita ? `1px dashed ${MARCA_DIFF.sparito.colore}` : undefined,
                             outline: marca && !sparita ? `2px solid ${marca.colore}` : undefined,
                             outlineOffset: marca && !sparita ? 1 : undefined,
                           }}
                           title={titolo}>
                        {sparita && (
                          // La sbarra: una riga orizzontale a metà altezza.
                          <div className="absolute pointer-events-none"
                               style={{
                                 left: 0, right: 0, top: '50%', height: 1,
                                 backgroundColor: MARCA_DIFF.sparito.colore,
                               }} />
                        )}
                        {b.livello === 0 && w > 70 && !sparita && (
                          <span className="text-[10px] text-white px-1.5 truncate block font-semibold"
                                style={{ lineHeight: `${st.barra}px` }}>
                            {b.label}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Legenda minima: dice cosa sono le due linee. Senza, il tratteggio è
          solo un tratteggio. */}
      <p className="text-[10px] text-gray-500 mt-1.5 flex items-center gap-3 flex-wrap">
        <span className="flex items-center gap-1">
          <span style={{ display: 'inline-block', width: 10, borderTop: '1px dashed rgba(148,163,184,0.9)' }} />
          oggi
        </span>
        {dataScatto && (
          <span className="flex items-center gap-1">
            <span style={{ display: 'inline-block', width: 10, height: 2, backgroundColor: 'rgba(245,158,11,0.9)' }} />
            data dello scatto
          </span>
        )}
        <span className="text-gray-600">·</span>
        {modalitaDiff ? (
          <>
            {Object.entries(MARCA_DIFF).filter(([, m]) => m).map(([k, m]) => (
              <span key={k} className="flex items-center gap-1">
                <span style={{
                  display: 'inline-block', width: 9, height: 9, borderRadius: 2,
                  border: `2px solid ${m.colore}`,
                }} />
                {m.etichetta}
              </span>
            ))}
            <span className="text-gray-600">· attenuato = invariato · tratteggio ambra = dov'era prima</span>
          </>
        ) : (
          <span>colore = stato · larghezza = durata (stessa scala del GANTT)</span>
        )}
      </p>
    </div>
  )
}
