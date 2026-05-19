import React, { useState, useEffect, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchGanttStrutturato, fetchProgetti, fetchDipendenti, fetchCaricoRisorse, exportGanttPdf } from '../api'
import GanttChartFasi from '../components/_shared/GanttChartFasi'

// ── Colori stati ────────────────────────────────────────────────────
const STATUS_COLORS = {
  'Completato': { bar: '#22c55e', bg: 'bg-green-900/30', text: 'text-green-300' },
  'In corso':   { bar: '#3b82f6', bg: 'bg-blue-900/30',  text: 'text-blue-300'  },
  'Da iniziare':{ bar: '#9ca3af', bg: 'bg-gray-700/30',  text: 'text-gray-300'  },
  'Sospeso':    { bar: '#d97706', bg: 'bg-amber-900/30', text: 'text-amber-300'  },
}

// ── Utility data corrente ───────────────────────────────────────────
// IMPORTANTE: calcoliamo "oggi" on-demand, non come costante al modulo.
// Una `const OGGI = new Date()` valutata al primo import resterebbe
// congelata finché la pagina non viene refreshata, e la linea rossa
// "oggi" diventerebbe disallineata (Debito #16 chiuso 19/05).
function getOggi() { return new Date() }
const LABEL_W = 300
const WEEK_PX_DEFAULT = 48
const WEEK_PX_MAX = 80
const ROW_H = 40

// ── Utility date ────────────────────────────────────────────────────
function getMonday(d) {
  const date = new Date(d)
  const day = date.getDay()
  const diff = day === 0 ? -6 : 1 - day
  date.setDate(date.getDate() + diff)
  date.setHours(0, 0, 0, 0)
  return date
}
function addDays(d, n) { const r = new Date(d); r.setDate(r.getDate() + n); return r }
function weeksBetween(a, b) { return Math.round((b.getTime() - a.getTime()) / (7 * 86400000)) }
function fmtMonth(d) { return d.toLocaleDateString('it-IT', { month: 'short', year: '2-digit' }) }

// ── Timeline builder (riusato anche da AnalisiInterventi) ───────────
export function buildTimeline(tasks) {
  if (!tasks || tasks.length === 0) return null
  const starts = tasks.map(t => new Date(t.start).getTime())
  const ends = tasks.map(t => new Date(t.end).getTime())
  const minDate = addDays(new Date(Math.min(...starts)), -7)
  const maxDate = addDays(new Date(Math.max(...ends)), 7)
  const firstMonday = getMonday(minDate)
  const lastMonday = getMonday(maxDate)
  const totalWeeks = weeksBetween(firstMonday, lastMonday) + 1
  const weekPx = Math.min(WEEK_PX_MAX, Math.max(WEEK_PX_DEFAULT, Math.floor(900 / totalWeeks)))
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

// ── Componente GANTT riutilizzabile ─────────────────────────────────
export function GanttChart({ tasks, title, changedIds, compact, onTaskClick }) {
  const scrollRef = useRef(null)
  const labelsRef = useRef(null)
  const timeline = useMemo(() => buildTimeline(tasks), [tasks])

  useEffect(() => {
    if (scrollRef.current && timeline) {
      scrollRef.current.scrollLeft = Math.max(0, timeline.oggiX - 300)
    }
  }, [timeline])

  if (!timeline || !tasks || tasks.length === 0) {
    return <div className="bg-gray-900 rounded-xl border border-gray-800 p-8 text-center text-gray-400">Nessun task da visualizzare.</div>
  }

  const { firstMonday, totalWeeks, weekPx, totalWidth, weeks, months, oggiX } = timeline
  const changedSet = new Set(changedIds || [])
  const rowH = compact ? 32 : ROW_H
  const headerH = 52

  function taskBar(task) {
    const msPerPx = (totalWeeks * 7 * 86400000) / totalWidth
    const x = (new Date(task.start).getTime() - firstMonday.getTime()) / msPerPx
    const w = Math.max(4, (new Date(task.end).getTime() - new Date(task.start).getTime()) / msPerPx)
    return { x, w }
  }

  // Bande cromatiche per progetto (dark mode)
  const projectColors = useMemo(() => {
    const projects = []
    tasks.forEach(t => { if (!projects.includes(t.project)) projects.push(t.project) })
    const palettes = [
      { bg: 'rgba(59, 130, 246, 0.08)', label: 'rgba(59, 130, 246, 0.15)' },
      { bg: 'rgba(139, 92, 246, 0.08)', label: 'rgba(139, 92, 246, 0.15)' },
      { bg: 'rgba(16, 185, 129, 0.08)', label: 'rgba(16, 185, 129, 0.15)' },
      { bg: 'rgba(245, 158, 11, 0.08)', label: 'rgba(245, 158, 11, 0.15)' },
      { bg: 'rgba(236, 72, 153, 0.08)', label: 'rgba(236, 72, 153, 0.15)' },
      { bg: 'rgba(6, 182, 212, 0.08)', label: 'rgba(6, 182, 212, 0.15)' },
      { bg: 'rgba(249, 115, 22, 0.08)', label: 'rgba(249, 115, 22, 0.15)' },
      { bg: 'rgba(99, 102, 241, 0.08)', label: 'rgba(99, 102, 241, 0.15)' },
    ]
    const colors = {}
    projects.forEach((p, i) => { colors[p] = palettes[i % palettes.length] })
    return colors
  }, [tasks])

  const projectAccent = useMemo(() => {
    const projects = []
    tasks.forEach(t => { if (!projects.includes(t.project)) projects.push(t.project) })
    const accents = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ec4899', '#06b6d4', '#f97316', '#6366f1']
    const map = {}
    projects.forEach((p, i) => { map[p] = accents[i % accents.length] })
    return map
  }, [tasks])

  function isNewProject(i) {
    return i === 0 || tasks[i].project !== tasks[i - 1].project
  }

  function handleBarClick(task) {
    if (onTaskClick) onTaskClick(task)
  }

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
      {title && <h3 className="font-semibold p-4 pb-2 text-sm">{title}</h3>}
      <div className="flex">
        {/* Labels (sticky) */}
        <div className="flex-shrink-0 z-20 bg-gray-900" style={{ width: LABEL_W }}>
          <div className="border-b border-gray-700 flex items-end px-3 pb-1 bg-gray-900" style={{ height: headerH }}>
            <span className="text-xs text-gray-500">Task / Risorsa</span>
          </div>
          <div ref={labelsRef} className="overflow-hidden" style={{ maxHeight: compact ? 400 : 600 }}>
            {tasks.map((task, i) => {
              const isChanged = changedSet.has(task.id)
              const projColor = projectColors[task.project]?.bg || 'transparent'
              const newProj = isNewProject(i)
              const accent = projectAccent[task.project] || '#3b82f6'
              return (
                <React.Fragment key={task.id || i}>
                  {newProj && !compact && (
                    <div className="flex items-center gap-2 px-3 border-t border-gray-700"
                      style={{ height: 22, backgroundColor: projectColors[task.project]?.label }}>
                      <div style={{ width: 3, height: 12, backgroundColor: accent, borderRadius: 2 }} />
                      <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: accent }}>{task.project}</span>
                    </div>
                  )}
                  <div className={`border-b border-gray-800/50 px-3 flex flex-col justify-center cursor-pointer hover:bg-gray-800/40 transition-colors ${isChanged ? 'bg-amber-900/20' : ''}`}
                    style={{ height: rowH, backgroundColor: isChanged ? undefined : projColor }}
                    onClick={() => handleBarClick(task)}>
                    <p className={`text-sm font-medium truncate ${isChanged ? 'text-amber-200' : ''}`}>{task.name}</p>
                    <p className="text-[11px] text-gray-500 truncate">{task.assignee}</p>
                  </div>
                </React.Fragment>
              )
            })}
          </div>
        </div>

        {/* Timeline area */}
        <div className="flex-1 overflow-hidden">
          <div className="overflow-hidden" style={{ height: headerH }}>
            <div className="overflow-x-auto" style={{ height: headerH + 20 }}>
              <div style={{ width: totalWidth }}>
                <div className="flex h-[26px] border-b border-gray-700/50">
                  {months.map((m, i) => (
                    <div key={i} className="flex-shrink-0 text-[11px] font-semibold text-gray-300 flex items-center px-2 border-r border-gray-700/40"
                      style={{ width: m.width, minWidth: m.width, backgroundColor: i % 2 === 0 ? 'rgba(30,35,50,0.6)' : 'rgba(25,30,42,0.6)' }}>
                      {m.width > 40 ? m.label : ''}
                    </div>
                  ))}
                </div>
                <div className="flex h-[26px] border-b border-gray-700">
                  {weeks.map((w, i) => {
                    const day = w.monday.getDate()
                    const label = day <= 7 ? w.monday.toLocaleDateString('it-IT', { day: 'numeric', month: 'short' }) : `${day}`
                    return (
                      <div key={i} className="flex-shrink-0 text-[10px] text-gray-500 flex items-center justify-center border-r border-gray-800/40"
                        style={{ width: weekPx }}>
                        {weekPx >= 30 ? label : (i % 2 === 0 ? label : '')}
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          </div>

          <div ref={scrollRef} className="overflow-x-auto overflow-y-auto" style={{ maxHeight: compact ? 400 : 600 }}
            onScroll={(e) => {
              const headerEl = e.target.previousElementSibling?.firstElementChild
              if (headerEl) headerEl.scrollLeft = e.target.scrollLeft
              if (labelsRef.current) labelsRef.current.scrollTop = e.target.scrollTop
            }}>
            <div style={{ width: totalWidth, position: 'relative' }}>
              <div className="absolute pointer-events-none z-0" style={{ width: totalWidth, height: tasks.length * rowH }}>
                {weeks.map((w, i) => (
                  <div key={i} className={w.monday.getDate() <= 7 ? 'bg-gray-700/60' : 'bg-gray-800/30'}
                    style={{ position: 'absolute', left: w.x, top: 0, width: 1, height: tasks.length * rowH }} />
                ))}
                {oggiX > 0 && oggiX < totalWidth && (
                  <div style={{ position: 'absolute', left: oggiX, top: 0, width: 2, height: tasks.length * rowH, backgroundColor: 'rgba(239,68,68,0.7)', zIndex: 5 }} />
                )}
              </div>

              {tasks.map((task, i) => {
                const { x, w } = taskBar(task)
                const c = STATUS_COLORS[task.status] || STATUS_COLORS['Da iniziare']
                const isChanged = changedSet.has(task.id)
                const projBg = projectColors[task.project]?.bg || 'transparent'
                const newProj = isNewProject(i)
                return (
                  <React.Fragment key={task.id || i}>
                    {newProj && !compact && (
                      <div className="border-t border-gray-700"
                        style={{ height: 22, width: totalWidth, backgroundColor: projectColors[task.project]?.label }} />
                    )}
                    <div className={`relative border-b border-gray-800/50 ${isChanged ? 'bg-amber-900/10' : ''}`}
                      style={{ height: rowH, width: totalWidth, backgroundColor: isChanged ? undefined : projBg }}>
                      <div className={`absolute rounded-[3px] hover:brightness-110 cursor-pointer z-10 transition-all ${isChanged ? 'ring-2 ring-amber-400/60' : ''}`}
                        style={{ left: x, width: w, top: compact ? 5 : 8, height: compact ? 22 : 24, backgroundColor: c.bar, opacity: isChanged ? 1 : 0.85, minWidth: 4 }}
                        onClick={() => handleBarClick(task)}
                        title={`${task.name}\n${task.assignee} · ${task.project}\nClicca per dettagli`}>
                        {w > 70 && <span className="text-[10px] text-white px-1.5 truncate block font-medium"
                          style={{ lineHeight: compact ? '22px' : '24px' }}>{task.name}</span>}
                      </div>
                    </div>
                  </React.Fragment>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}


// ── Legenda ─────────────────────────────────────────────────────────
export function StatusLegend() {
  return (
    <div className="flex gap-4 text-xs">
      {Object.entries(STATUS_COLORS).map(([st, c]) => (
        <span key={st} className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded" style={{ backgroundColor: c.bar }} />{st}
        </span>
      ))}
    </div>
  )
}

// ── Pagina GANTT ────────────────────────────────────────────────────
// ═════════════════════════════════════════════════════════════════════════
// VISTA ELENCO — drill-down gerarchico Progetto → Fase → Task
//
// Step 2.3 del Blocco 2 esteso (handoff v15 §2.3).
// Consumiamo /api/gantt/strutturato e mostriamo la gerarchia come accordion.
// Default apertura: fasi "In corso" aperte, le altre chiuse (handoff §2.3).
// Sola lettura (no edit qui — gli edit vivono in /cantiere e l'approfondimento in /elenco/{id}).
// ═════════════════════════════════════════════════════════════════════════

function StatoBadge({ stato }) {
  // Map stato → colore Tailwind. Coerente con la legenda della Timeline.
  const colori = {
    // Stati Fase
    'Da iniziare': 'bg-gray-700 text-gray-300',
    'In corso': 'bg-blue-700 text-blue-100',
    'Completata': 'bg-green-700 text-green-100',
    'Sospesa': 'bg-yellow-700 text-yellow-100',
    'Annullata': 'bg-red-900 text-red-200',
    // Stati Task
    'Completato': 'bg-green-700 text-green-100',
    'In corso (task)': 'bg-blue-700 text-blue-100',  // se mai usato
    'Da fare': 'bg-gray-700 text-gray-300',
    'Bloccato': 'bg-red-700 text-red-100',
    'Eliminato': 'bg-red-950 text-red-300',
    // Stati Progetto
    'Bozza': 'bg-amber-800 text-amber-100',
    'In esecuzione': 'bg-blue-700 text-blue-100',
    'Sospeso': 'bg-yellow-700 text-yellow-100',
    'Annullato': 'bg-red-900 text-red-200',
  }
  const cls = colori[stato] || 'bg-gray-700 text-gray-300'
  return <span className={`text-xs px-2 py-0.5 rounded ${cls}`}>{stato}</span>
}

// 19/05/2026 (Step 2.3-bis 4d, C1): TaskRow + FaseAccordion rimossi.
// L'Elenco GANTT è ora minimal — una riga per progetto. Il drill-down
// fasi+task vive solo in /elenco/{id} (SezioneFasiTask), che è la
// fonte unica di approfondimento.


// 19/05/2026 (Step 2.3-bis 4d): ProgettoCard + VistaElenco rimossi.
// La vista Elenco minimalista è stata eliminata: il GANTT è solo Timeline.
// La selezione progetto avviene tramite la tendina "Progetto" in alto,
// il click sulle barre porta a /elenco/{id} per l'approfondimento.



// ═════════════════════════════════════════════════════════════════════════
// PAGINA GANTT — toggle Timeline / Elenco
// ═════════════════════════════════════════════════════════════════════════

// 19/05/2026: toLegacyTask rimosso insieme a TaskDetailPanel.
// L'approfondimento del task vive ora in /elenco/{progettoId} e consuma
// direttamente lo schema strutturato (snake_case italiano), senza adapter.


export default function GanttPage() {
  const navigate = useNavigate()

  // Step 2.3-bis 4d (19/05/2026): rimosso state `vista`. GANTT è solo Timeline.
  const [filtroStato, setFiltroStato] = useState('attivi')  // attivi | in esecuzione | sospeso

  // State legacy (per la vista timeline)
  const [ganttStrutturato, setGanttStrutturato] = useState([])
  const [progetti, setProgetti] = useState([])
  const [dipendenti, setDipendenti] = useState([])
  const [loading, setLoading] = useState(true)
  const [filtroProgetto, setFiltroProgetto] = useState('')
  const [filtroProfilo, setFiltroProfilo] = useState('')

  // Mount: anagrafica progetti+dipendenti (per filtri dropdown).
  // La gerarchia ganttStrutturato è gestita dal useEffect successivo.
  useEffect(() => {
    Promise.all([fetchProgetti(), fetchDipendenti()])
      .then(([p, d]) => { setProgetti(p); setDipendenti(d) })
      .finally(() => setLoading(false))
  }, [])

  // Carica gerarchia al cambio di filtri (progetto/stato).
  // filtroProfilo si applica client-side (vedi useMemo sotto).
  useEffect(() => {
    const params = { stato: filtroStato }
    if (filtroProgetto) params.progettoId = filtroProgetto
    fetchGanttStrutturato(params).then(data => {
      setGanttStrutturato(data)
    })
  }, [filtroProgetto, filtroStato])

  // Filtro profilo applicato client-side sulla gerarchia.
  // Filtra task dentro le fasi; mantiene fasi anche se diventano vuote
  // (così l'utente vede subito l'effetto del filtro). Se vuoi nascondere
  // le fasi vuote, decommenta il .filter sotto. Da rivalutare in 4b-3.
  const ganttFiltrato = useMemo(() => {
    if (!filtroProfilo) return ganttStrutturato
    return ganttStrutturato.map(prog => ({
      ...prog,
      fasi: (prog.fasi || []).map(fase => ({
        ...fase,
        tasks: (fase.tasks || []).filter(t => t.profilo_richiesto === filtroProfilo),
      }))
      // .filter(fase => (fase.tasks || []).length > 0)
    }))
  }, [ganttStrutturato, filtroProfilo])

  if (loading) return <p className="text-gray-400">Caricamento...</p>

  const profili = [...new Set(dipendenti.map(d => d.profilo))].sort()
  const progettiAttivi = progetti.filter(p => ['In esecuzione', 'In bando'].includes(p.stato))

  return (
    <div>
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <h1 className="text-3xl font-bold">📅 GANTT</h1>
      </div>

      {/* ═══════════════════════════════════════════════════════════════ */}
      {/* VISTA TIMELINE — GANTT gerarchico fase→task                     */}
      {/* (19/05/2026 4d: toggle Elenco/Timeline rimosso. La lista dei    */}
      {/* progetti non aggiungeva valore essendo già selezionabili dalla  */}
      {/* tendina "Progetto" qui sotto e accessibili dal click sulle      */}
      {/* barre. Approfondimento read-only completo: /elenco/{id}.)       */}
      {/* ═══════════════════════════════════════════════════════════════ */}
      <>
          <div className="flex gap-4 mb-4 flex-wrap items-center">
            <label className="text-sm text-gray-400">Stato:</label>
            <select
              value={filtroStato}
              onChange={e => setFiltroStato(e.target.value)}
              className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-sm"
            >
              <option value="attivi">Attivi (In esecuzione + Sospeso)</option>
              <option value="in esecuzione">Solo In esecuzione</option>
              <option value="sospeso">Solo Sospeso</option>
            </select>
            <select value={filtroProgetto} onChange={e => setFiltroProgetto(e.target.value)}
              className="bg-gray-800 border border-gray-600 rounded-lg px-4 py-2 text-sm">
              <option value="">Tutti i progetti</option>
              {progettiAttivi.map(p => <option key={p.id} value={p.id}>{p.nome}</option>)}
            </select>
            <select value={filtroProfilo} onChange={e => setFiltroProfilo(e.target.value)}
              className="bg-gray-800 border border-gray-600 rounded-lg px-4 py-2 text-sm">
              <option value="">Tutti i profili</option>
              {profili.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
            <StatusLegend />
            <div className="ml-auto flex gap-2">
              <button onClick={() => exportGanttPdf(filtroProgetto || null)}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors">
                📥 PDF
              </button>
              <button onClick={() => {
                const params = filtroProgetto ? `?progetto_id=${filtroProgetto}` : '';
                fetch(`/api/gantt/export-png${params}`)
                  .then(res => res.blob())
                  .then(blob => {
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `gantt_${filtroProgetto || 'tutti'}_${new Date().toISOString().slice(0,10)}.png`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                  })
                  .catch(() => alert('Errore nella generazione PNG'))
              }}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors">
                🖼️ PNG
              </button>
              <button onClick={() => {
                const params = filtroProgetto ? `?progetto_id=${filtroProgetto}` : '';
                fetch(`/api/gantt/export-excel${params}`)
                  .then(res => res.blob())
                  .then(blob => {
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `gantt_${filtroProgetto || 'tutti'}_${new Date().toISOString().slice(0,10)}.xlsx`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                  })
                  .catch(() => alert('Errore nella generazione Excel'))
              }}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors">
                📊 Excel
              </button>
            </div>
          </div>

          <GanttChartFasi
            progetti={ganttFiltrato}
            onProgettoClick={(progettoId) => navigate(`/elenco/${progettoId}`)}
            onTaskClick={(task) => {
              // Click su barra task → naviga all'approfondimento del progetto.
              const prog = ganttFiltrato.find(p =>
                (p.fasi || []).some(f => (f.tasks || []).some(t => t.id === task.id))
              )
              if (prog) navigate(`/elenco/${prog.id}`)
            }}
          />

          {ganttFiltrato.length > 0 && (
            <p className="text-xs text-gray-600 mt-3 text-center">
              Clicca su una barra per aprire l'approfondimento del progetto
            </p>
          )}
      </>
    </div>
  )
}
