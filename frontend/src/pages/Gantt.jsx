import React, { useState, useEffect, useMemo, useRef } from 'react'
import { fetchGantt, fetchProgetti, fetchDipendenti, exportGanttPdf } from '../api'

// ── Colori stati ────────────────────────────────────────────────────
const STATUS_COLORS = {
  'Completato': { bar: '#22c55e', bg: 'bg-green-900/30', text: 'text-green-300' },
  'In corso':   { bar: '#3b82f6', bg: 'bg-blue-900/30',  text: 'text-blue-300'  },
  'Da iniziare':{ bar: '#9ca3af', bg: 'bg-gray-700/30',  text: 'text-gray-300'  },
  'Sospeso':    { bar: '#d97706', bg: 'bg-amber-900/30', text: 'text-amber-300'  },
}

const OGGI = new Date('2026-03-09')
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
export function GanttChart({ tasks, title, changedIds, compact }) {
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
              return (
                <div key={task.id || i}
                  className={`border-b border-gray-800/50 px-3 flex flex-col justify-center ${isChanged ? 'bg-amber-900/20' : 'hover:bg-gray-800/30'}`}
                  style={{ height: rowH }}>
                  <p className={`text-sm font-medium truncate ${isChanged ? 'text-amber-200' : ''}`}>{task.name}</p>
                  <p className="text-[11px] text-gray-500 truncate">{task.assignee} · {task.project}</p>
                </div>
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
                return (
                  <div key={task.id || i} className={`relative border-b border-gray-800/50 ${isChanged ? 'bg-amber-900/10' : 'hover:bg-gray-800/20'}`}
                    style={{ height: rowH, width: totalWidth }}>
                    <div className={`absolute rounded-[3px] hover:opacity-100 cursor-default z-10 ${isChanged ? 'ring-2 ring-amber-400/60' : ''}`}
                      style={{ left: x, width: w, top: compact ? 5 : 8, height: compact ? 22 : 24, backgroundColor: c.bar, opacity: isChanged ? 1 : 0.85, minWidth: 4 }}
                      title={`${task.name}\n${task.assignee} · ${task.project}\n${new Date(task.start).toLocaleDateString('it-IT')} → ${new Date(task.end).toLocaleDateString('it-IT')}\nStato: ${task.status}`}>
                      {w > 70 && <span className="text-[10px] text-white px-1.5 truncate block font-medium"
                        style={{ lineHeight: compact ? '22px' : '24px' }}>{task.name}</span>}
                    </div>
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

// ── Legenda ─────────────────────────────────────────────────────────
function StatusLegend() {
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

// ── Pagina GANTT (solo visualizzazione) ─────────────────────────────
export default function GanttPage() {
  const [ganttData, setGanttData] = useState([])
  const [progetti, setProgetti] = useState([])
  const [dipendenti, setDipendenti] = useState([])
  const [loading, setLoading] = useState(true)
  const [filtroProgetto, setFiltroProgetto] = useState('')
  const [filtroProfilo, setFiltroProfilo] = useState('')

  useEffect(() => {
    Promise.all([fetchGantt(), fetchProgetti(), fetchDipendenti()])
      .then(([g, p, d]) => { setGanttData(g); setProgetti(p); setDipendenti(d) })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchGantt(filtroProgetto || null).then(data => {
      setGanttData(filtroProfilo ? data.filter(t => t.profile === filtroProfilo) : data)
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
        <button onClick={() => exportGanttPdf(filtroProgetto || null)}
          className="ml-auto px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors">
          📥 Esporta PDF
        </button>
      </div>

      <GanttChart tasks={ganttData} />

      <details className="mt-4">
        <summary className="cursor-pointer text-gray-400 hover:text-white text-sm font-medium">
          📋 Dettaglio ({ganttData.length} task)
        </summary>
        <div className="mt-2 bg-gray-900 rounded-xl border border-gray-800 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-800 text-gray-400">
              <tr>
                <th className="text-left px-4 py-2">Task</th>
                <th className="text-left px-4 py-2">Progetto</th>
                <th className="text-left px-4 py-2">Assegnato</th>
                <th className="text-left px-4 py-2">Stato</th>
                <th className="text-right px-4 py-2">Ore</th>
                <th className="text-left px-4 py-2">Inizio</th>
                <th className="text-left px-4 py-2">Fine</th>
              </tr>
            </thead>
            <tbody>
              {ganttData.map(t => {
                const sc = STATUS_COLORS[t.status] || {}
                return (
                  <tr key={t.id} className="border-t border-gray-800 hover:bg-gray-800/50">
                    <td className="px-4 py-2 font-medium">{t.name}</td>
                    <td className="px-4 py-2 text-gray-400">{t.project}</td>
                    <td className="px-4 py-2">{t.assignee}</td>
                    <td className="px-4 py-2"><span className={`px-2 py-0.5 rounded text-xs ${sc.bg} ${sc.text}`}>{t.status}</span></td>
                    <td className="px-4 py-2 text-right">{t.estimated_hours}h</td>
                    <td className="px-4 py-2 text-gray-400">{new Date(t.start).toLocaleDateString('it-IT')}</td>
                    <td className="px-4 py-2 text-gray-400">{new Date(t.end).toLocaleDateString('it-IT')}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}
