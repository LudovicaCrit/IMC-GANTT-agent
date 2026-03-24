import React, { useState, useEffect } from 'react'
import { fetchProgetti, fetchTasks, fetchDipendenti } from '../api'

/* ── Gauge component ──────────────────────────────────────────────── */
function Gauge({ value, label, max = 100, colorThresholds }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  let color = 'text-green-400'
  if (colorThresholds) {
    if (value > colorThresholds.red) color = 'text-red-400'
    else if (value > colorThresholds.yellow) color = 'text-yellow-400'
  }

  const radius = 45
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (pct / 100) * circumference

  return (
    <div className="flex flex-col items-center">
      <svg width="120" height="120" className="transform -rotate-90">
        <circle cx="60" cy="60" r={radius} fill="none" stroke="#374151" strokeWidth="10" />
        <circle cx="60" cy="60" r={radius} fill="none" stroke="currentColor"
          strokeWidth="10" strokeDasharray={circumference} strokeDashoffset={offset}
          strokeLinecap="round" className={`${color} transition-all duration-500`} />
      </svg>
      <p className={`text-2xl font-bold -mt-16 mb-8 ${color}`}>{value.toFixed(0)}%</p>
      <p className="text-xs text-gray-400 text-center">{label}</p>
    </div>
  )
}

export default function Economia() {
  const [progetti, setProgetti] = useState([])
  const [allTasks, setAllTasks] = useState([])
  const [dipendenti, setDipendenti] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([fetchProgetti(), fetchTasks(), fetchDipendenti()])
      .then(([p, t, d]) => { setProgetti(p); setAllTasks(t); setDipendenti(d) })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-gray-400">Caricamento...</p>

  const attivi = progetti.filter(p => p.stato === 'In esecuzione')
  const valoreTotale = attivi.reduce((s, p) => s + p.valore_contratto, 0)
  const oreTotaliCons = attivi.reduce((s, p) => s + p.ore_consuntivate, 0)

  // Calcola dati economici per progetto
  const oggi = new Date('2026-03-09')
  const ecoData = attivi.map(p => {
    const durata = (new Date(p.data_fine) - new Date(p.data_inizio)) / (1000 * 60 * 60 * 24)
    const trascorsi = (oggi - new Date(p.data_inizio)) / (1000 * 60 * 60 * 24)
    const progressoTempo = Math.min(100, Math.max(0, (trascorsi / durata) * 100))
    const progressoOre = p.budget_ore > 0 ? (p.ore_consuntivate / p.budget_ore) * 100 : 0
    const budgetUsato = p.budget_ore > 0 ? (p.ore_consuntivate / p.budget_ore) * 100 : 0

    return { ...p, progressoTempo, progressoOre, budgetUsato }
  })

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">💰 Dashboard Economica</h1>
      <p className="text-sm text-yellow-400 mb-6">🔒 Sezione riservata al management</p>

      {/* KPI portafoglio */}
      <h2 className="text-xl font-semibold mb-4">Riepilogo Portafoglio</h2>
      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Valore portafoglio</p>
          <p className="text-3xl font-bold mt-1">€{valoreTotale.toLocaleString('it-IT')}</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Progetti attivi</p>
          <p className="text-3xl font-bold mt-1">{attivi.length}</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Ore consuntivate</p>
          <p className="text-3xl font-bold mt-1">{oreTotaliCons.toLocaleString('it-IT')}h</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Compilazione media</p>
          <p className="text-3xl font-bold mt-1">
            {attivi.length > 0 ? Math.round(attivi.reduce((s, p) => s + p.tasso_compilazione, 0) / attivi.length) : 0}%
          </p>
        </div>
      </div>

      {/* Analisi per progetto con gauge */}
      <h2 className="text-xl font-semibold mb-4">📈 Analisi Avanzamento</h2>
      <div className="space-y-6 mb-8">
        {ecoData.map(p => {
          const deltaTL = p.progressoTempo - p.progressoOre
          let agentMsg = '', agentColor = 'text-green-300', agentBg = 'bg-green-900/20 border-green-800'
          if (deltaTL > 15) {
            agentMsg = `Il progetto è in ritardo. L'avanzamento temporale (${p.progressoTempo.toFixed(0)}%) supera quello lavorativo (${p.progressoOre.toFixed(0)}%) di ${deltaTL.toFixed(0)} punti.`
            agentColor = 'text-red-300'; agentBg = 'bg-red-900/20 border-red-800'
          } else if (deltaTL > 5) {
            agentMsg = 'Lieve disallineamento tra tempo trascorso e lavoro completato. Monitorare.'
            agentColor = 'text-yellow-300'; agentBg = 'bg-yellow-900/20 border-yellow-800'
          } else {
            agentMsg = 'Il progetto procede in linea con le tempistiche.'
          }

          return (
            <div key={p.id} className="bg-gray-900 rounded-xl border border-gray-800 p-6">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="font-semibold text-lg">{p.nome}</h3>
                  <p className="text-sm text-gray-400">{p.cliente}</p>
                </div>
                <p className="text-xl font-bold">€{p.valore_contratto.toLocaleString('it-IT')}</p>
              </div>

              {/* 3 gauge */}
              <div className="grid grid-cols-3 gap-6 mb-4">
                <Gauge value={p.progressoTempo} label="Avanzamento Temporale"
                  colorThresholds={{ yellow: 70, red: 90 }} />
                <Gauge value={p.progressoOre} label="Avanzamento Lavoro"
                  colorThresholds={{ yellow: 70, red: 90 }} />
                <Gauge value={p.budgetUsato} label="Budget Utilizzato"
                  colorThresholds={{ yellow: 60, red: 80 }} />
              </div>

              {/* Dettagli numerici */}
              <div className="grid grid-cols-4 gap-4 text-sm mb-4">
                <div><p className="text-gray-400">Ore consuntivate</p><p className="font-medium">{p.ore_consuntivate.toLocaleString('it-IT')}h / {p.budget_ore}h</p></div>
                <div><p className="text-gray-400">Budget ore usato</p><p className="font-medium">{p.budgetUsato.toFixed(0)}%</p></div>
                <div><p className="text-gray-400">Compilazione</p><p className="font-medium">{p.tasso_compilazione.toFixed(0)}%</p></div>
                <div><p className="text-gray-400">Task</p><p className="font-medium">{p.task_completati}/{p.task_totali}</p></div>
              </div>

              {/* Analisi agente */}
              <div className={`p-3 rounded-lg border text-sm ${agentBg}`}>
                <span className={agentColor}>🤖 <strong>Agente:</strong> {agentMsg}</span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Tabella riepilogativa */}
      <h2 className="text-xl font-semibold mb-4">📋 Riepilogo Numerico</h2>
      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-800 text-gray-400">
            <tr>
              <th className="text-left px-4 py-2">Progetto</th>
              <th className="text-right px-4 py-2">Valore</th>
              <th className="text-right px-4 py-2">Ore Stimate</th>
              <th className="text-right px-4 py-2">Ore Consuntivate</th>
              <th className="text-right px-4 py-2">Budget %</th>
              <th className="text-right px-4 py-2">Compilazione</th>
            </tr>
          </thead>
          <tbody>
            {ecoData.map(p => (
              <tr key={p.id} className="border-t border-gray-800 hover:bg-gray-800/50">
                <td className="px-4 py-2 font-medium">{p.nome}</td>
                <td className="px-4 py-2 text-right">€{p.valore_contratto.toLocaleString('it-IT')}</td>
                <td className="px-4 py-2 text-right">{p.budget_ore}h</td>
                <td className="px-4 py-2 text-right">{p.ore_consuntivate.toLocaleString('it-IT')}h</td>
                <td className={`px-4 py-2 text-right font-medium ${p.budgetUsato > 80 ? 'text-red-400' : 'text-green-400'}`}>
                  {p.budgetUsato.toFixed(0)}%
                </td>
                <td className="px-4 py-2 text-right">{p.tasso_compilazione.toFixed(0)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
