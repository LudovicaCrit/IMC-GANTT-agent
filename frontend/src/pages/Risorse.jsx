import React, { useState, useEffect } from 'react'
import { fetchDipendenti, fetchCaricoRisorse, fetchTasks, fetchProgetti } from '../api'

/* ── Saturation cell for heatmap ──────────────────────────────────── */
function SatCell({ value }) {
  let cls = 'text-green-300 bg-green-900/40'
  if (value > 100) cls = 'text-red-300 bg-red-900/50'
  else if (value > 75) cls = 'text-yellow-300 bg-yellow-900/40'
  else if (value > 50) cls = 'text-blue-300 bg-blue-900/30'
  return <td className={`px-2 py-1.5 text-center text-xs font-medium border border-gray-800 ${cls}`}>{value}%</td>
}

export default function Risorse() {
  const [dipendenti, setDipendenti] = useState([])
  const [carico, setCarico] = useState([])
  const [tasks, setTasks] = useState([])
  const [progetti, setProgetti] = useState([])
  const [loading, setLoading] = useState(true)
  const [filtroProfilo, setFiltroProfilo] = useState('')

  // Assignment
  const [assignTaskId, setAssignTaskId] = useState('')

  useEffect(() => {
    Promise.all([fetchDipendenti(), fetchCaricoRisorse(12), fetchTasks(), fetchProgetti()])
      .then(([d, c, t, p]) => { setDipendenti(d); setCarico(c); setTasks(t); setProgetti(p) })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-gray-400">Caricamento...</p>

  const profili = [...new Set(dipendenti.map(d => d.profilo))].sort()
  const dipFiltrati = filtroProfilo ? dipendenti.filter(d => d.profilo === filtroProfilo) : dipendenti
  const caricoFiltrato = filtroProfilo ? carico.filter(c => c.profilo === filtroProfilo) : carico
  const settLabels = carico.length > 0 ? carico[0].settimane.map(s => s.settimana_label) : []

  // Assignment logic
  const tasksAssegnabili = tasks.filter(t => ['In corso', 'Da iniziare'].includes(t.stato))
  const selectedTask = tasksAssegnabili.find(t => t.id === assignTaskId)
  const candidati = selectedTask ? dipendenti.filter(d => d.profilo === selectedTask.profilo_richiesto) : []

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">👥 Assegnazione Profili e Risorse</h1>

      {/* Filtro profilo */}
      <div className="mb-6">
        <select value={filtroProfilo} onChange={e => setFiltroProfilo(e.target.value)}
          className="bg-gray-800 border border-gray-600 rounded-lg px-4 py-2 text-sm">
          <option value="">Tutti i profili</option>
          {profili.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>

      {/* ═══ Barre disponibilità ═══ */}
      <h2 className="text-xl font-semibold mb-4">🔍 Disponibilità corrente</h2>
      <div className="space-y-3 mb-8">
        {dipFiltrati.sort((a, b) => b.saturazione_pct - a.saturazione_pct).map(d => {
          const occPct = Math.min(100, d.saturazione_pct)
          const dispPct = Math.max(0, 100 - occPct)
          const barColor = d.saturazione_pct > 100 ? 'bg-red-500' : d.saturazione_pct > 75 ? 'bg-yellow-500' : 'bg-blue-500'
          return (
            <div key={d.id} className="bg-gray-900 rounded-lg border border-gray-800 p-4">
              <div className="flex justify-between items-center mb-2">
                <div>
                  <span className="font-medium">{d.nome}</span>
                  <span className="text-gray-400 text-sm ml-2">({d.profilo})</span>
                </div>
                <div className="text-sm">
                  <span className={d.saturazione_pct > 100 ? 'text-red-400 font-bold' : 'text-gray-300'}>
                    {d.carico_corrente.toFixed(1)}h / {d.ore_sett}h
                  </span>
                  <span className="text-gray-500 ml-2">({d.saturazione_pct}%)</span>
                </div>
              </div>
              <div className="flex h-4 rounded-full overflow-hidden bg-gray-700">
                <div className={`${barColor} transition-all`} style={{ width: `${occPct}%` }} />
                <div className="bg-green-600 transition-all" style={{ width: `${dispPct}%` }} />
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {d.n_task_attivi} task su {d.progetti_attivi.length} progetti: {d.progetti_attivi.join(', ')}
              </p>
            </div>
          )
        })}
      </div>

      {/* ═══ Heatmap saturazione ═══ */}
      <h2 className="text-xl font-semibold mb-4">📊 Mappa saturazione (12 settimane)</h2>
      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-x-auto mb-8">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-800">
              <th className="text-left px-3 py-2 text-xs text-gray-400 min-w-[200px]">Dipendente</th>
              {settLabels.map(s => <th key={s} className="px-2 py-2 text-xs text-gray-400 text-center">{s}</th>)}
            </tr>
          </thead>
          <tbody>
            {caricoFiltrato.map(c => (
              <tr key={c.dipendente_id} className="hover:bg-gray-800/50">
                <td className="px-3 py-1.5 text-sm border border-gray-800">
                  <span className="font-medium">{c.nome}</span>
                  <span className="text-gray-500 text-xs ml-1">({c.profilo})</span>
                </td>
                {c.settimane.map((s, i) => <SatCell key={i} value={s.saturazione_pct} />)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ═══ Assegnazione task → profilo → persona ═══ */}
      <h2 className="text-xl font-semibold mb-4">🛠️ Assegna un task: da profilo a persona</h2>
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-8">
        <div className="mb-4">
          <label className="text-sm text-gray-400 block mb-1">Seleziona task</label>
          <select value={assignTaskId} onChange={e => setAssignTaskId(e.target.value)}
            className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm max-w-2xl">
            <option value="">Seleziona task...</option>
            {tasksAssegnabili.map(t => (
              <option key={t.id} value={t.id}>
                {t.nome} ({t.progetto_nome}) — richiede: {t.profilo_richiesto}
              </option>
            ))}
          </select>
        </div>

        {selectedTask && (
          <>
            <div className="grid grid-cols-3 gap-4 mb-4 text-sm">
              <div><p className="text-gray-400">Profilo richiesto</p><p className="font-medium">{selectedTask.profilo_richiesto}</p></div>
              <div><p className="text-gray-400">Ore stimate</p><p className="font-medium">{selectedTask.ore_stimate}h</p></div>
              <div><p className="text-gray-400">Assegnato a</p><p className="font-medium">{selectedTask.dipendente_nome}</p></div>
            </div>

            <h4 className="font-semibold mb-3">Candidati disponibili</h4>
            <div className="space-y-2 mb-4">
              {candidati.sort((a, b) => a.saturazione_pct - b.saturazione_pct).map(c => {
                const isCurrent = c.id === selectedTask.dipendente_id
                return (
                  <div key={c.id} className={`p-3 rounded-lg border text-sm ${
                    isCurrent ? 'border-blue-700 bg-blue-900/20' : 'border-gray-700 bg-gray-800/50'
                  }`}>
                    <div className="flex justify-between items-center">
                      <div>
                        <span className="font-medium">{c.nome}</span>
                        {isCurrent && <span className="text-blue-400 text-xs ml-2">← attuale</span>}
                      </div>
                      <span className={`text-xs font-medium ${
                        c.saturazione_pct > 100 ? 'text-red-400' : c.saturazione_pct > 75 ? 'text-yellow-400' : 'text-green-400'
                      }`}>
                        {c.saturazione_pct}% saturazione · {c.carico_corrente.toFixed(1)}h/{c.ore_sett}h
                      </span>
                    </div>
                    <p className="text-gray-400 text-xs mt-1">
                      {c.n_task_attivi} task su {c.progetti_attivi.length} progetti · Competenze: {c.competenze.join(', ')}
                    </p>
                  </div>
                )
              })}
            </div>

            <div className="flex gap-4 items-end">
              <div className="flex-1">
                <label className="text-sm text-gray-400 block mb-1">Riassegna a:</label>
                <select className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm">
                  <option value="">Seleziona...</option>
                  {candidati.map(c => <option key={c.id} value={c.id}>{c.nome} ({c.saturazione_pct}%)</option>)}
                </select>
              </div>
              <button className="px-6 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors">
                ✅ Conferma riassegnazione
              </button>
            </div>
          </>
        )}
      </div>

      {/* ═══ Anagrafica ═══ */}
      <h2 className="text-xl font-semibold mb-4">📋 Anagrafica Risorse</h2>
      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-800 text-gray-400">
            <tr>
              <th className="text-left px-4 py-2">Nome</th>
              <th className="text-left px-4 py-2">Profilo</th>
              <th className="text-right px-4 py-2">Ore/Sett</th>
              <th className="text-left px-4 py-2">Competenze</th>
              <th className="text-right px-4 py-2">Task Attivi</th>
              <th className="text-right px-4 py-2">Carico (h/sett)</th>
              <th className="text-right px-4 py-2">Disponibilità</th>
            </tr>
          </thead>
          <tbody>
            {dipendenti.map(d => {
              const disp = Math.max(0, d.ore_sett - d.carico_corrente)
              return (
                <tr key={d.id} className="border-t border-gray-800 hover:bg-gray-800/50">
                  <td className="px-4 py-2 font-medium">{d.nome}</td>
                  <td className="px-4 py-2 text-gray-400">{d.profilo}</td>
                  <td className="px-4 py-2 text-right">{d.ore_sett}</td>
                  <td className="px-4 py-2 text-gray-400 text-xs">{d.competenze.join(', ')}</td>
                  <td className="px-4 py-2 text-right">{d.n_task_attivi}</td>
                  <td className="px-4 py-2 text-right">{d.carico_corrente.toFixed(1)}h</td>
                  <td className={`px-4 py-2 text-right font-medium ${disp <= 0 ? 'text-red-400' : 'text-green-400'}`}>
                    {disp.toFixed(1)}h
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
