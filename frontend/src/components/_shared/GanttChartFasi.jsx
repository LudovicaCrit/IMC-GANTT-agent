// frontend/src/components/_shared/GanttChartFasi.jsx
//
// GANTT gerarchico fase→task per la vista Timeline di /gantt.
// Creato per Step 2.3-bis sotto-passo 4b-1.
//
// NON sostituisce GanttChart legacy in Gantt.jsx (che resta in vita per
// AnalisiInterventi finché Step 2.7 non la elimina). È un componente nuovo,
// affiancato, che lavora sulla gerarchia restituita da /api/gantt/strutturato.
//
// Convenzioni:
// - Riusa buildTimeline() esportato da pages/Gantt.jsx per il calcolo
//   dell'asse temporale (settimane, mesi, oggiX).
// - Stato espansione = Set<faseId>. Default: tutte le fasi "In corso" aperte.
// - Click su barra-fase → toggle espansione (mostra/nasconde task figli).
// - Click su barra-task → callback onTaskClick(task) come il legacy.
// - Nessuna logica di edit: questo è il GANTT "lente di lettura" (§3.2).
//
import React, { useState, useMemo, useRef, useEffect } from 'react'
import { buildTimeline } from '../../pages/Gantt'

// ── Colori per stato (allineati al legacy GanttChart) ────────────────
// I task usano gli stessi 4 stati colorati del legacy. Le fasi hanno 5
// stati: aggiungiamo 'Completata', 'Sospesa', 'Annullata' (suffisso al
// femminile come da §5.1).
const COLORI_FASE = {
  'Da iniziare': '#9ca3af',  // gray-400
  'In corso':    '#3b82f6',  // blue-500
  'Completata':  '#22c55e',  // green-500
  'Sospesa':     '#d97706',  // amber-600
  'Annullata':   '#6b7280',  // gray-500 (più desaturato)
}

const COLORI_TASK = {
  'Da iniziare': '#9ca3af',
  'In corso':    '#3b82f6',
  'Completato':  '#22c55e',
  'Bloccato':    '#ef4444',  // red-500
}

// ── Costanti layout ──────────────────────────────────────────────────
const LABEL_W = 300
const HEADER_H = 52
const ROW_FASE_H = 28
const ROW_TASK_H = 18
const BAR_FASE_H = 16
const BAR_TASK_H = 10
const PROJECT_HEADER_H = 24

// Palette per banding cromatico progetto (riuso del legacy)
const PROJECT_PALETTES = [
  { bg: 'rgba(59, 130, 246, 0.08)', label: 'rgba(59, 130, 246, 0.15)', accent: '#3b82f6' },
  { bg: 'rgba(139, 92, 246, 0.08)', label: 'rgba(139, 92, 246, 0.15)', accent: '#8b5cf6' },
  { bg: 'rgba(16, 185, 129, 0.08)', label: 'rgba(16, 185, 129, 0.15)', accent: '#10b981' },
  { bg: 'rgba(245, 158, 11, 0.08)', label: 'rgba(245, 158, 11, 0.15)', accent: '#f59e0b' },
  { bg: 'rgba(236, 72, 153, 0.08)', label: 'rgba(236, 72, 153, 0.15)', accent: '#ec4899' },
  { bg: 'rgba(6, 182, 212, 0.08)',  label: 'rgba(6, 182, 212, 0.15)',  accent: '#06b6d4' },
  { bg: 'rgba(249, 115, 22, 0.08)', label: 'rgba(249, 115, 22, 0.15)', accent: '#f97316' },
  { bg: 'rgba(99, 102, 241, 0.08)', label: 'rgba(99, 102, 241, 0.15)', accent: '#6366f1' },
]

// ─────────────────────────────────────────────────────────────────────
// Componente principale
// ─────────────────────────────────────────────────────────────────────
export default function GanttChartFasi({ progetti, onTaskClick, onProgettoClick }) {
  const scrollRef = useRef(null)
  const labelsRef = useRef(null)

  // ── Stato espansione: Set<faseId> ──────────────────────────────────
  // Default: aperte le fasi "In corso" (le altre partono chiuse).
  const [setEspansione, setSetEspansione] = useState(() => {
    const s = new Set()
    if (progetti) {
      progetti.forEach(p => {
        (p.fasi || []).forEach(f => {
          if (f.stato === 'In corso') s.add(f.id)
        })
      })
    }
    return s
  })

  // Quando arrivano nuovi progetti (dopo filtro/refetch), apri di nuovo
  // le "In corso" — ma solo se l'utente non ha ancora interagito.
  // Per semplicità in questa prima versione resettiamo a ogni cambio
  // di identità dell'array `progetti`. Se diventa fastidioso, si può
  // raffinare in 4b-3 (test visivi).
  useEffect(() => {
    if (!progetti) return
    const s = new Set()
    progetti.forEach(p => {
      (p.fasi || []).forEach(f => {
        if (f.stato === 'In corso') s.add(f.id)
      })
    })
    setSetEspansione(s)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [progetti])

  // ── Costruzione righe visibili + barre per buildTimeline ───────────
  // Una "riga" è una entry visiva nella label-column e una banda nel
  // pannello timeline. Ogni riga sa il suo tipo, altezza, e (per le
  // barre) start/end/stato/etichette.
  const { rows, allBars, projectColors } = useMemo(() => {
    if (!progetti || progetti.length === 0) {
      return { rows: [], allBars: [], projectColors: {} }
    }

    const rows = []
    const allBars = []  // per buildTimeline: serve {start, end}
    const projectColors = {}

    progetti.forEach((prog, pIdx) => {
      const palette = PROJECT_PALETTES[pIdx % PROJECT_PALETTES.length]
      projectColors[prog.id] = palette

      // Header progetto: bandina-titolo sempre visibile.
      // Anche con un solo progetto è una "ridondanza comoda" (decisione
      // Ludovica 19/05). Le bande di sfondo cromatiche per riga
      // (r.progettoBg) restano lo strumento primario di distinzione.
      rows.push({
        kind: 'project_header',
        progettoId: prog.id,
        progettoNome: prog.nome,
        cliente: prog.cliente || '',
        accent: palette.accent,
        labelBg: palette.label,
        height: PROJECT_HEADER_H,
      })

      ;(prog.fasi || []).forEach(fase => {
        // Riga fase (sempre visibile)
        rows.push({
          kind: 'fase',
          faseId: fase.id,
          faseNome: fase.nome,
          stato: fase.stato,
          start: fase.data_inizio,
          end: fase.data_fine,
          progettoId: prog.id,
          progettoBg: palette.bg,
          height: ROW_FASE_H,
          isEspansa: setEspansione.has(fase.id),
        })
        allBars.push({ start: fase.data_inizio, end: fase.data_fine })

        // Task: contribuiscono SEMPRE a buildTimeline (così l'asse li
        // include anche se sforano la fase), ma le righe-task vengono
        // emesse SOLO se la fase è espansa.
        // Campi backend (verificati 19/05 su /api/gantt/strutturato):
        //   id, nome, stato, data_inizio, data_fine, dipendente_nome,
        //   ore_stimate, ore_consumate, profilo_richiesto, predecessore.
        ;(fase.tasks || []).forEach(task => {
          if (task.data_inizio && task.data_fine) {
            allBars.push({ start: task.data_inizio, end: task.data_fine })
          }
          if (setEspansione.has(fase.id)) {
            rows.push({
              kind: 'task',
              taskId: task.id,
              task,
              start: task.data_inizio,
              end: task.data_fine,
              stato: task.stato,
              progettoId: prog.id,
              progettoBg: palette.bg,
              height: ROW_TASK_H,
              faseId: fase.id,
            })
          }
        })
      })
    })

    return { rows, allBars, projectColors }
  }, [progetti, setEspansione])

  // ── Timeline (asse) ────────────────────────────────────────────────
  // NOTA (Debito #16 chiuso 19/05): il useMemo cacha l'asse temporale,
  // ma `oggiX` deve riflettere "ora" e non essere cachato. Lo calcoliamo
  // a parte sotto, dopo aver destrutturato il resto della timeline.
  const timeline = useMemo(() => buildTimeline(allBars), [allBars])

  // Tick: forza un re-render ogni 5 minuti per mantenere `oggiX` allineato
  // se la pagina sta aperta a lungo. 5 min è un compromesso tra reattività
  // e costo: il GANTT è una vista di lavoro che resta aperta ore.
  const [, setTick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 5 * 60 * 1000)
    return () => clearInterval(id)
  }, [])

  // Auto-scroll su "oggi" al primo render utile
  useEffect(() => {
    if (scrollRef.current && timeline) {
      const oggiPx = (new Date().getTime() - timeline.firstMonday.getTime())
        / (timeline.totalWeeks * 7 * 86400000) * timeline.totalWidth
      scrollRef.current.scrollLeft = Math.max(0, oggiPx - 300)
    }
  }, [timeline])

  // ── Toggle espansione fase ─────────────────────────────────────────
  function toggleFase(faseId) {
    setSetEspansione(prev => {
      const next = new Set(prev)
      if (next.has(faseId)) next.delete(faseId)
      else next.add(faseId)
      return next
    })
  }

  // ── Empty state ────────────────────────────────────────────────────
  if (!timeline || rows.length === 0) {
    return (
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-8 text-center text-gray-400">
        Nessuna fase da visualizzare.
      </div>
    )
  }

  const { firstMonday, totalWeeks, weekPx, totalWidth, weeks, months } = timeline
  const msPerPx = (totalWeeks * 7 * 86400000) / totalWidth

  // oggiX ricalcolato fresco a ogni render (vedi commento sopra al useMemo).
  // Ignoro `timeline.oggiX` proprio per evitare il valore cachato.
  const oggiX = (new Date().getTime() - firstMonday.getTime()) / msPerPx

  // Altezza totale = somma altezze righe visibili.
  // Usata per il layer di sfondo (grid settimane + linea oggi) che è
  // l'unico elemento absolute-positioned a tutta altezza nel body timeline.
  const totalHeight = rows.reduce((sum, r) => sum + r.height, 0)

  // Helper: posizione X+W di una barra dato start/end
  function barXW(start, end) {
    const x = (new Date(start).getTime() - firstMonday.getTime()) / msPerPx
    const w = Math.max(4, (new Date(end).getTime() - new Date(start).getTime()) / msPerPx)
    return { x, w }
  }

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
      <div className="flex">
        {/* ═══ COLONNA LABELS (sticky a sinistra) ═══════════════════════ */}
        <div className="flex-shrink-0 z-20 bg-gray-900" style={{ width: LABEL_W }}>
          {/* Header colonna labels */}
          <div
            className="border-b border-gray-700 flex items-end px-3 pb-1 bg-gray-900"
            style={{ height: HEADER_H }}
          >
            <span className="text-xs text-gray-500">Progetto / Fase / Task</span>
          </div>

          {/* Body labels (scroll verticale sincronizzato col timeline) */}
          <div ref={labelsRef} className="overflow-hidden" style={{ maxHeight: 600 }}>
            {rows.map((r, i) => {
              if (r.kind === 'project_header') {
                const tooltip = (r.cliente ? `${r.progettoNome} — ${r.cliente}` : r.progettoNome) + ' · Click per approfondire'
                return (
                  <div
                    key={`ph-${r.progettoId}`}
                    className="flex items-center gap-2 px-3 cursor-pointer hover:brightness-125 transition-all"
                    style={{
                      height: r.height,
                      backgroundColor: r.labelBg,
                      boxShadow: 'inset 0 1px 0 rgb(55 65 81)',
                    }}
                    title={tooltip}
                    onClick={() => onProgettoClick && onProgettoClick(r.progettoId)}
                  >
                    <div style={{ width: 3, height: 12, backgroundColor: r.accent, borderRadius: 2 }} />
                    <span
                      className="text-[10px] font-bold uppercase tracking-wider truncate"
                      style={{ color: r.accent }}
                    >
                      {r.progettoNome}
                    </span>
                  </div>
                )
              }
              if (r.kind === 'fase') {
                return (
                  <div
                    key={`fl-${r.faseId}`}
                    className="px-3 flex items-center gap-2 cursor-pointer hover:bg-gray-800/40 transition-colors"
                    style={{
                      height: r.height,
                      backgroundColor: r.progettoBg,
                      boxShadow: 'inset 0 -1px 0 rgb(55 65 81)',  // simula border-b senza occupare spazio
                    }}
                    onClick={() => toggleFase(r.faseId)}
                    title={r.isEspansa ? 'Click per chiudere' : 'Click per espandere i task'}
                  >
                    <span className="text-gray-500 text-xs w-3 flex-shrink-0">
                      {r.isEspansa ? '▼' : '▶'}
                    </span>
                    <span className="text-sm font-medium truncate">{r.faseNome}</span>
                    <span className="text-[10px] text-gray-500 ml-auto flex-shrink-0">{r.stato}</span>
                  </div>
                )
              }
              // r.kind === 'task'
              return (
                <div
                  key={`tl-${r.taskId}`}
                  className="px-3 flex items-center gap-2 cursor-pointer hover:bg-gray-800/40 transition-colors"
                  style={{
                    height: r.height,
                    backgroundColor: r.progettoBg,
                    paddingLeft: 28,
                    boxShadow: 'inset 0 -1px 0 rgb(55 65 81 / 0.6)',
                  }}
                  onClick={() => onTaskClick && onTaskClick(r.task)}
                >
                  <span className="text-[11px] text-gray-300 truncate">{r.task.nome}</span>
                  <span className="text-[10px] text-gray-500 ml-auto flex-shrink-0 truncate max-w-[100px]">
                    {r.task.dipendente_nome || ''}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        {/* ═══ PANNELLO TIMELINE (scroll orizzontale) ═══════════════════ */}
        <div className="flex-1 overflow-hidden">
          {/* Header settimane+mesi (scroll orizzontale sincronizzato) */}
          <div className="overflow-hidden" style={{ height: HEADER_H }}>
            <div className="overflow-x-auto" style={{ height: HEADER_H + 20, overscrollBehaviorX: 'contain' }}>
              <div style={{ width: totalWidth }}>
                {/* Riga mesi */}
                <div className="flex h-[26px] border-b border-gray-700/50">
                  {months.map((m, i) => (
                    <div
                      key={i}
                      className="flex-shrink-0 text-[11px] font-semibold text-gray-300 flex items-center px-2 border-r border-gray-700/40"
                      style={{
                        width: m.width,
                        minWidth: m.width,
                        backgroundColor: i % 2 === 0 ? 'rgba(30,35,50,0.6)' : 'rgba(25,30,42,0.6)',
                      }}
                    >
                      {m.width > 40 ? m.label : ''}
                    </div>
                  ))}
                </div>
                {/* Riga settimane */}
                <div className="flex h-[26px] border-b border-gray-700">
                  {weeks.map((w, i) => {
                    const day = w.monday.getDate()
                    const label = day <= 7
                      ? w.monday.toLocaleDateString('it-IT', { day: 'numeric', month: 'short' })
                      : `${day}`
                    return (
                      <div
                        key={i}
                        className="flex-shrink-0 text-[10px] text-gray-500 flex items-center justify-center border-r border-gray-800/40"
                        style={{ width: weekPx }}
                      >
                        {weekPx >= 30 ? label : (i % 2 === 0 ? label : '')}
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          </div>

          {/* Body timeline (scroll orizz+vert sincronizzato con labels) */}
          <div
            ref={scrollRef}
            className="overflow-x-auto overflow-y-auto"
            style={{ maxHeight: 600, overscrollBehaviorX: 'contain' }}
            onScroll={(e) => {
              const headerEl = e.target.previousElementSibling?.firstElementChild
              if (headerEl) headerEl.scrollLeft = e.target.scrollLeft
              if (labelsRef.current) labelsRef.current.scrollTop = e.target.scrollTop
            }}
          >
            {/* Container in flow naturale: stessa strategia della colonna labels.
                Garantisce allineamento al pixel per costruzione, senza calcoli
                cumulativi soggetti a drift di rendering. */}
            <div style={{ width: totalWidth, position: 'relative' }}>
              {/* Layer di sfondo: grid settimane + linea oggi.
                  position: absolute con height totale dinamica (= somma altezze righe). */}
              <div
                className="pointer-events-none"
                style={{
                  position: 'absolute',
                  top: 0, left: 0,
                  width: totalWidth, height: totalHeight,
                  zIndex: 0,
                }}
              >
                {weeks.map((w, i) => (
                  <div
                    key={i}
                    className={w.monday.getDate() <= 7 ? 'bg-gray-700/60' : 'bg-gray-800/30'}
                    style={{ position: 'absolute', left: w.x, top: 0, width: 1, height: '100%' }}
                  />
                ))}
                {oggiX > 0 && oggiX < totalWidth && (
                  <div
                    style={{
                      position: 'absolute',
                      left: oggiX, top: 0,
                      width: 2, height: '100%',
                      backgroundColor: 'rgba(239,68,68,0.7)',
                      zIndex: 5,
                    }}
                  />
                )}
              </div>

              {/* Righe in flow naturale, ognuna con la sua barra interna position:absolute */}
              {rows.map((r, i) => {
                if (r.kind === 'project_header') {
                  return (
                    <div
                      key={`ph-bar-${r.progettoId}`}
                      className="cursor-pointer hover:brightness-125 transition-all"
                      style={{
                        position: 'relative',
                        width: totalWidth,
                        height: r.height,
                        backgroundColor: r.labelBg,
                        boxShadow: 'inset 0 1px 0 rgb(55 65 81)',
                      }}
                      onClick={() => onProgettoClick && onProgettoClick(r.progettoId)}
                      title="Click per approfondire il progetto"
                    />
                  )
                }

                if (r.kind === 'fase') {
                  const { x, w } = barXW(r.start, r.end)
                  const color = COLORI_FASE[r.stato] || COLORI_FASE['Da iniziare']
                  return (
                    <div
                      key={`fb-${r.faseId}`}
                      style={{
                        position: 'relative',
                        width: totalWidth,
                        height: r.height,
                        backgroundColor: r.progettoBg,
                        boxShadow: 'inset 0 -1px 0 rgb(55 65 81)',
                      }}
                    >
                      <div
                        className="absolute rounded-[3px] hover:brightness-110 cursor-pointer z-10 transition-all"
                        style={{
                          left: x,
                          top: (r.height - BAR_FASE_H) / 2,
                          width: w,
                          height: BAR_FASE_H,
                          backgroundColor: color,
                          opacity: 0.9,
                          minWidth: 4,
                        }}
                        onClick={() => toggleFase(r.faseId)}
                        title={`${r.faseNome}\nStato: ${r.stato}\nClick per ${r.isEspansa ? 'chiudere' : 'espandere'}`}
                      >
                        {w > 70 && (
                          <span
                            className="text-[10px] text-white px-1.5 truncate block font-semibold"
                            style={{ lineHeight: `${BAR_FASE_H}px` }}
                          >
                            {r.faseNome}
                          </span>
                        )}
                      </div>
                    </div>
                  )
                }

                // r.kind === 'task'
                const { x, w } = barXW(r.start, r.end)
                const color = COLORI_TASK[r.stato] || COLORI_TASK['Da iniziare']
                return (
                  <div
                    key={`tb-${r.taskId}`}
                    style={{
                      position: 'relative',
                      width: totalWidth,
                      height: r.height,
                      backgroundColor: r.progettoBg,
                      boxShadow: 'inset 0 -1px 0 rgb(55 65 81 / 0.6)',
                    }}
                  >
                    <div
                      className="absolute rounded-[2px] hover:brightness-110 hover:opacity-100 cursor-pointer z-10 transition-all"
                      style={{
                        left: x,
                        top: (r.height - BAR_TASK_H) / 2,
                        width: w,
                        height: BAR_TASK_H,
                        backgroundColor: color,
                        opacity: 0.6,
                        minWidth: 4,
                      }}
                      onClick={() => onTaskClick && onTaskClick(r.task)}
                      title={`${r.task.nome}\n${r.task.dipendente_nome || 'Non assegnato'}\nClick per dettagli`}
                    />
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
