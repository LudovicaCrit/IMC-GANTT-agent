import React, { useState, useEffect, useMemo, useRef } from 'react'
import { fetchGantt, fetchProgetti, fetchDipendenti, fetchCaricoRisorse, exportGanttPdf } from '../api'

// ── Colori stati ────────────────────────────────────────────────────
const STATUS_COLORS = {
  'Completato': { bar: '#22c55e', bg: 'bg-green-900/30', text: 'text-green-300' },
  'In corso':   { bar: '#3b82f6', bg: 'bg-blue-900/30',  text: 'text-blue-300'  },
  'Da iniziare':{ bar: '#9ca3af', bg: 'bg-gray-700/30',  text: 'text-gray-300'  },
  'Sospeso':    { bar: '#d97706', bg: 'bg-amber-900/30', text: 'text-amber-300'  },
}

const OGGI = new Date()
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

  const oggiX = ((OGGI.getTime() - firstMonday.getTime()) / (totalWeeks * 7 * 86400000)) * totalWidth
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

// ── Pannello dettaglio task (appare al click) ───────────────────────
function TaskDetailPanel({ task, allTasks, progetti, dipendenti, onClose, onElimina }) {
  const [showCarico, setShowCarico] = useState(false)

  if (!task) return null

  // Info progetto
  const progetto = progetti?.find(p => p.nome === task.project || p.id === task.project_id)
  const budgetOre = progetto?.budget_ore || 0
  const pesoPercentuale = budgetOre > 0 ? ((task.estimated_hours || 0) / budgetOre * 100).toFixed(1) : '?'

  // Percentuale completamento task — da dati reali se disponibili
  const progressPct = task.progress ?? (task.status === 'Completato' ? 100 : task.status === 'In corso' ? 50 : 0)
  const hoursDone = task.hours_done ?? 0
  const sc = STATUS_COLORS[task.status] || STATUS_COLORS['Da iniziare']

  // Predecessore e successori
  const predecessore = task.predecessor_name || null
  const successori = allTasks?.filter(t => {
    return t.dependencies === task.id
  }) || []

  // Task della stessa persona (per mostrare il carico)
  const taskStessaPersona = allTasks?.filter(t =>
    t.assignee === task.assignee &&
    t.id !== task.id &&
    t.status !== 'Completato' &&
    t.status !== 'Sospeso'
  ) || []

  // Calcolo carico approssimativo della persona
  const calcolaOreSett = (t) => {
    const inizio = new Date(t.start)
    const fine = new Date(t.end)
    const durataGiorni = Math.max(1, (fine - inizio) / 86400000)
    const durataSett = Math.max(1, durataGiorni / 7)
    return ((t.estimated_hours || 0) / durataSett).toFixed(1)
  }

  const oreSettTask = calcolaOreSett(task)
  const caricoTotale = [task, ...taskStessaPersona].reduce((sum, t) => sum + parseFloat(calcolaOreSett(t)), 0)

  // Durata in giorni lavorativi (approssimativa)
  const durataGiorni = Math.round((new Date(task.end) - new Date(task.start)) / 86400000)
  const durataSett = Math.round(durataGiorni / 7)

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-5 mt-3 relative">
      {/* Chiudi */}
      <button onClick={onClose}
        className="absolute top-3 right-3 text-gray-500 hover:text-white text-lg transition-colors">✕</button>

      {/* Header */}
      <div className="mb-4">
        <h3 className="font-semibold text-lg">{task.name}</h3>
        <p className="text-sm text-gray-400">{task.project} {progetto?.cliente ? `· ${progetto.cliente}` : ''}</p>
      </div>

      {/* Info principali — grid compatto */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <div className="bg-gray-800/60 rounded-lg p-3">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Ore</p>
          <p className="text-lg font-bold">{hoursDone > 0 ? `${hoursDone}` : '0'}<span className="text-sm text-gray-500 font-normal">/{task.estimated_hours || '?'}h</span></p>
          <p className="text-[10px] text-gray-500">{pesoPercentuale}% del budget progetto</p>
        </div>
        <div className="bg-gray-800/60 rounded-lg p-3">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Avanzamento</p>
          <div className="flex items-center gap-2 mt-1">
            <span className="w-3 h-3 rounded" style={{ backgroundColor: sc.bar }} />
            <span className="text-sm font-medium">{task.status}</span>
          </div>
          {/* Barra completamento */}
          <div className="w-full bg-gray-700 rounded-full h-1.5 mt-2">
            <div className="h-1.5 rounded-full transition-all" style={{ width: `${progressPct}%`, backgroundColor: sc.bar }} />
          </div>
          <p className="text-[10px] text-gray-500 mt-1">{progressPct}% completato</p>
        </div>
        <div className="bg-gray-800/60 rounded-lg p-3">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Periodo</p>
          <p className="text-sm font-medium">{new Date(task.start).toLocaleDateString('it-IT', { day: 'numeric', month: 'short' })}</p>
          <p className="text-[10px] text-gray-500">→ {new Date(task.end).toLocaleDateString('it-IT', { day: 'numeric', month: 'short', year: 'numeric' })}</p>
          <p className="text-[10px] text-gray-500 mt-1">~{durataSett} settimane ({durataGiorni}gg)</p>
        </div>
        <div className="bg-gray-800/60 rounded-lg p-3">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Carico settimanale</p>
          <p className="text-lg font-bold">~{oreSettTask}h<span className="text-sm text-gray-500 font-normal">/sett</span></p>
        </div>
      </div>

      {/* Dipendenze */}
      {(predecessore || successori.length > 0) && (
        <div className="flex gap-4 mb-4 text-sm">
          {predecessore && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-gray-500 uppercase">Dipende da:</span>
              <span className="text-gray-300">{predecessore}</span>
            </div>
          )}
          {successori.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-gray-500 uppercase">Successori:</span>
              <span className="text-gray-300">{successori.map(s => s.name).join(', ')}</span>
            </div>
          )}
        </div>
      )}

      {/* Persona assegnata — riga compatta con espansione */}
      <div className="bg-gray-800/40 rounded-lg p-3">
        <button onClick={() => setShowCarico(!showCarico)}
          className="w-full flex items-center justify-between text-sm">
          <div className="flex items-center gap-3">
            <span className="text-gray-300 font-medium">{task.assignee}</span>
            <span className={`text-xs font-mono ${caricoTotale > 40 ? 'text-red-400' : caricoTotale > 32 ? 'text-yellow-400' : 'text-green-400'}`}>
              {caricoTotale.toFixed(0)}h/40h
            </span>
            <span className="text-xs text-gray-500">{taskStessaPersona.length + 1} task attivi</span>
          </div>
          <span className="text-gray-500 text-xs">{showCarico ? '▼ nascondi' : '▶ vedi cosa fa'}</span>
        </button>

        {showCarico && (
          <div className="mt-3 space-y-1.5 pt-3 border-t border-gray-700/50">
            {/* Task corrente */}
            <div className="flex items-center justify-between text-xs bg-blue-900/20 rounded px-2 py-1.5">
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 flex-shrink-0" />
                <span className="text-blue-200 font-medium truncate">{task.name}</span>
                <span className="text-blue-300/50 truncate flex-shrink-0">({task.project})</span>
              </div>
              <span className="text-blue-300 font-mono ml-2">~{oreSettTask}h/sett</span>
            </div>
            {/* Altri task */}
            {taskStessaPersona.map(t => {
              const ore = calcolaOreSett(t)
              return (
                <div key={t.id} className="flex items-center justify-between text-xs px-2 py-1.5">
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <span className="w-1.5 h-1.5 rounded-full bg-gray-500 flex-shrink-0" />
                    <span className="text-gray-300 truncate">{t.name}</span>
                    <span className="text-gray-500 truncate flex-shrink-0">({t.project})</span>
                  </div>
                  <span className="text-gray-400 font-mono ml-2">~{ore}h/sett</span>
                </div>
              )
            })}
            {/* Totale */}
            <div className="flex items-center justify-between text-xs px-2 pt-2 border-t border-gray-700/30">
              <span className="text-gray-400">Totale stimato</span>
              <span className={`font-mono font-bold ${caricoTotale > 40 ? 'text-red-400' : 'text-green-400'}`}>
                ~{caricoTotale.toFixed(0)}h/sett
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Bottone elimina */}
      <div className="mt-4 pt-3 border-t border-gray-800 flex justify-end">
        <button onClick={() => {
          if (confirm(`Eliminare il task "${task.name}"? L'operazione è reversibile dal database.`)) {
            onElimina(task.id)
          }
        }}
          className="px-3 py-1.5 text-xs bg-red-900/30 border border-red-800 text-red-400 hover:bg-red-900/50 hover:text-red-300 rounded-lg transition-colors">
          🗑 Elimina task
        </button>
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
export default function GanttPage() {
  const [ganttData, setGanttData] = useState([])
  const [progetti, setProgetti] = useState([])
  const [dipendenti, setDipendenti] = useState([])
  const [loading, setLoading] = useState(true)
  const [filtroProgetto, setFiltroProgetto] = useState('')
  const [filtroProfilo, setFiltroProfilo] = useState('')
  const [selectedTask, setSelectedTask] = useState(null)

  useEffect(() => {
    Promise.all([fetchGantt(), fetchProgetti(), fetchDipendenti()])
      .then(([g, p, d]) => { setGanttData(g); setProgetti(p); setDipendenti(d) })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchGantt(filtroProgetto || null).then(data => {
      setGanttData(filtroProfilo ? data.filter(t => t.profile === filtroProfilo) : data)
      setSelectedTask(null) // chiudi pannello quando cambia filtro
    })
  }, [filtroProgetto, filtroProfilo])

  if (loading) return <p className="text-gray-400">Caricamento...</p>

  const profili = [...new Set(dipendenti.map(d => d.profilo))].sort()
  const progettiAttivi = progetti.filter(p => ['In esecuzione', 'In bando'].includes(p.stato))

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">📅 GANTT Interattivo</h1>

      <div className="flex gap-4 mb-4 flex-wrap items-center">
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

      <GanttChart
        tasks={ganttData}
        onTaskClick={setSelectedTask}
      />

      {/* Pannello dettaglio al click */}
      {selectedTask && (
        <TaskDetailPanel
          task={selectedTask}
          allTasks={ganttData}
          progetti={progetti}
          dipendenti={dipendenti}
          onClose={() => setSelectedTask(null)}
          onElimina={async (taskId) => {
            try {
              const res = await fetch(`/api/tasks/${taskId}/elimina`, { method: 'PATCH' })
              if (!res.ok) throw new Error('Errore')
              setSelectedTask(null)
              // Ricarica GANTT
              const newData = await fetchGantt(filtroProgetto || null)
              setGanttData(filtroProfilo ? newData.filter(t => t.profile === filtroProfilo) : newData)
            } catch (err) {
              alert('Errore nell\'eliminazione: ' + err.message)
            }
          }}
        />
      )}

      {/* Hint se nessun task selezionato */}
      {!selectedTask && ganttData.length > 0 && (
        <p className="text-xs text-gray-600 mt-3 text-center">Clicca su un task nel GANTT per vedere i dettagli</p>
      )}
    </div>
  )
}
