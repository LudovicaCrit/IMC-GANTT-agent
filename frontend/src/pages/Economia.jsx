import React, { useState, useEffect, useMemo } from 'react'
import { fetchProgetti, fetchTasks, fetchDipendenti } from '../api'

const API_BASE = '/api'

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

/* ── Barra margine ──────────────────────────────────────────────── */
function MarginBar({ margine_pct }) {
  const color = margine_pct >= 40 ? 'bg-green-500' : margine_pct >= 20 ? 'bg-yellow-500' : margine_pct >= 0 ? 'bg-orange-500' : 'bg-red-500'
  const textColor = margine_pct >= 40 ? 'text-green-400' : margine_pct >= 20 ? 'text-yellow-400' : margine_pct >= 0 ? 'text-orange-400' : 'text-red-400'
  const width = Math.min(100, Math.max(2, Math.abs(margine_pct)))

  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 bg-gray-700 rounded-full h-2.5">
        <div className={`h-2.5 rounded-full ${color} transition-all duration-500`}
          style={{ width: `${width}%` }} />
      </div>
      <span className={`text-sm font-bold w-14 text-right ${textColor}`}>
        {margine_pct.toFixed(0)}%
      </span>
    </div>
  )
}

export default function Economia() {
  const [progetti, setProgetti] = useState([])
  const [allTasks, setAllTasks] = useState([])
  const [dipendenti, setDipendenti] = useState([])
  const [margini, setMargini] = useState([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('margini')
  const [dettaglioAperto, setDettaglioAperto] = useState(null)

  useEffect(() => {
    Promise.all([
      fetchProgetti(),
      fetchTasks(),
      fetchDipendenti(),
      fetch(`${API_BASE}/economia/margini`).then(r => r.json()).catch(() => []),
    ])
      .then(([p, t, d, m]) => {
        setProgetti(p)
        setAllTasks(t)
        setDipendenti(d)
        setMargini(m)
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-gray-400">Caricamento...</p>

  const attivi = progetti.filter(p => p.stato === 'In esecuzione')
  const valoreTotale = attivi.reduce((s, p) => s + p.valore_contratto, 0)
  const oreTotaliCons = attivi.reduce((s, p) => s + p.ore_consuntivate, 0)

  // Totali margine
  const costoTotale = margini.reduce((s, m) => s + (m.costo_effettivo || 0), 0)
  const margineTotale = margini
    .filter(m => m.stato === 'In esecuzione')
    .reduce((s, m) => s + (m.margine_attuale || 0), 0)
  const margineStimatoTotale = margini
    .filter(m => m.stato === 'In esecuzione')
    .reduce((s, m) => s + (m.margine_stimato || 0), 0)

  // Dati avanzamento
  const oggi = new Date()
  const ecoData = attivi.map(p => {
    const durata = (new Date(p.data_fine) - new Date(p.data_inizio)) / (1000 * 60 * 60 * 24)
    const trascorsi = (oggi - new Date(p.data_inizio)) / (1000 * 60 * 60 * 24)
    const progressoTempo = Math.min(100, Math.max(0, (trascorsi / durata) * 100))
    const progressoOre = p.budget_ore > 0 ? (p.ore_consuntivate / p.budget_ore) * 100 : 0
    const budgetUsato = p.budget_ore > 0 ? (p.ore_consuntivate / p.budget_ore) * 100 : 0
    return { ...p, progressoTempo, progressoOre, budgetUsato }
  })

  const fmt = (n) => n.toLocaleString('it-IT', { maximumFractionDigits: 0 })

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">💰 Dashboard Economica</h1>
      <p className="text-sm text-yellow-400 mb-6">🔒 Sezione riservata al management</p>

      {/* KPI portafoglio */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Valore portafoglio</p>
          <p className="text-2xl font-bold mt-1">€{fmt(valoreTotale)}</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Costo sostenuto</p>
          <p className="text-2xl font-bold mt-1 text-orange-400">€{fmt(costoTotale)}</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Margine attuale</p>
          <p className={`text-2xl font-bold mt-1 ${margineTotale >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            €{fmt(margineTotale)}
          </p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Margine stimato a fine</p>
          <p className={`text-2xl font-bold mt-1 ${margineStimatoTotale >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            €{fmt(margineStimatoTotale)}
          </p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Progetti attivi</p>
          <p className="text-2xl font-bold mt-1">{attivi.length}</p>
        </div>
      </div>

      {/* Tab switch */}
      <div className="flex gap-2 mb-6">
        <button onClick={() => setTab('margini')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === 'margini' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
          }`}>
          💶 Costi e Margini
        </button>
        <button onClick={() => setTab('avanzamento')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === 'avanzamento' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
          }`}>
          📈 Avanzamento
        </button>
      </div>

      {/* ═══ TAB: COSTI E MARGINI ═══ */}
      {tab === 'margini' && (
        <div className="space-y-4">
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-800 text-gray-400">
                <tr>
                  <th className="text-left px-4 py-3">Progetto</th>
                  <th className="text-right px-4 py-3">Valore contratto</th>
                  <th className="text-right px-4 py-3">Ore cons.</th>
                  <th className="text-right px-4 py-3">Costo effettivo</th>
                  <th className="text-right px-4 py-3">Margine attuale</th>
                  <th className="text-center px-4 py-3 w-48">Margine %</th>
                  <th className="text-right px-4 py-3">Stima a fine</th>
                  <th className="text-center px-3 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {margini.map(m => (
                  <React.Fragment key={m.progetto_id}>
                    <tr className={`border-t border-gray-800 hover:bg-gray-800/50 transition-colors ${
                      m.margine_stimato_pct < 20 ? 'bg-red-900/10' : ''
                    }`}>
                      <td className="px-4 py-3">
                        <p className="font-medium">{m.nome}</p>
                        <p className="text-xs text-gray-500">{m.cliente} · {m.stato}</p>
                      </td>
                      <td className="px-4 py-3 text-right font-medium">€{fmt(m.valore_contratto)}</td>
                      <td className="px-4 py-3 text-right">{m.ore_consuntivate}h / {m.budget_ore}h</td>
                      <td className="px-4 py-3 text-right text-orange-400">€{fmt(m.costo_effettivo)}</td>
                      <td className={`px-4 py-3 text-right font-bold ${m.margine_attuale >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        €{fmt(m.margine_attuale)}
                      </td>
                      <td className="px-4 py-3">
                        <MarginBar margine_pct={m.margine_pct} />
                      </td>
                      <td className={`px-4 py-3 text-right text-xs ${m.margine_stimato >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        €{fmt(m.margine_stimato)}
                        <br /><span className="text-gray-500">({m.margine_stimato_pct.toFixed(0)}%)</span>
                      </td>
                      <td className="px-3 py-3 text-center">
                        <button onClick={() => setDettaglioAperto(dettaglioAperto === m.progetto_id ? null : m.progetto_id)}
                          className="text-gray-400 hover:text-white text-xs px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 transition-colors">
                          {dettaglioAperto === m.progetto_id ? '▼' : '▶'}
                        </button>
                      </td>
                    </tr>

                    {/* Dettaglio persone */}
                    {dettaglioAperto === m.progetto_id && m.dettaglio_persone && (
                      <tr>
                        <td colSpan={8} className="px-4 py-3 bg-gray-800/30">
                          <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">
                            Dettaglio costi per persona — costo medio ora: €{m.costo_medio_ora}/h
                          </p>
                          <div className="grid grid-cols-2 gap-2">
                            {m.dettaglio_persone.map((dp, i) => (
                              <div key={i} className="flex items-center justify-between bg-gray-800 rounded-lg px-3 py-2 text-xs">
                                <div>
                                  <span className="font-medium">{dp.nome}</span>
                                  <span className="text-gray-500 ml-2">{dp.profilo} · €{dp.costo_ora}/h</span>
                                </div>
                                <div className="text-right">
                                  <span className="text-gray-300">{dp.ore.toFixed(0)}h</span>
                                  <span className="text-orange-400 ml-3 font-medium">€{fmt(dp.costo)}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>

          {/* Alert margine */}
          {margini.filter(m => m.margine_stimato_pct < 20 && m.stato === 'In esecuzione').length > 0 && (
            <div className="bg-red-900/20 border border-red-800 rounded-xl p-4">
              <p className="text-sm text-red-300 font-medium mb-2">⚠️ Attenzione: progetti a rischio margine</p>
              <div className="space-y-1">
                {margini
                  .filter(m => m.margine_stimato_pct < 20 && m.stato === 'In esecuzione')
                  .map(m => (
                    <p key={m.progetto_id} className="text-xs text-red-400">
                      {m.nome} ({m.cliente}): margine stimato {m.margine_stimato_pct.toFixed(0)}% — costo medio €{m.costo_medio_ora}/h su {m.ore_consuntivate}h
                    </p>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══ TAB: AVANZAMENTO ═══ */}
      {tab === 'avanzamento' && (
        <div className="space-y-6">
          {ecoData.map(p => {
            const deltaTL = p.progressoTempo - p.progressoOre
            let agentMsg = '', agentBg = 'bg-green-900/20 border-green-800'
            if (deltaTL > 15) {
              agentMsg = `Il progetto è in ritardo. L'avanzamento temporale (${p.progressoTempo.toFixed(0)}%) supera quello lavorativo (${p.progressoOre.toFixed(0)}%) di ${deltaTL.toFixed(0)} punti.`
              agentBg = 'bg-red-900/20 border-red-800'
            } else if (deltaTL > 5) {
              agentMsg = 'Lieve disallineamento tra tempo trascorso e lavoro completato. Monitorare.'
              agentBg = 'bg-yellow-900/20 border-yellow-800'
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

                <div className="grid grid-cols-3 gap-6 mb-4">
                  <Gauge value={p.progressoTempo} label="Avanzamento Temporale"
                    colorThresholds={{ yellow: 70, red: 90 }} />
                  <Gauge value={p.progressoOre} label="Avanzamento Lavoro"
                    colorThresholds={{ yellow: 70, red: 90 }} />
                  <Gauge value={p.budgetUsato} label="Budget Utilizzato"
                    colorThresholds={{ yellow: 60, red: 80 }} />
                </div>

                <div className="grid grid-cols-4 gap-4 text-sm mb-4">
                  <div><p className="text-gray-400">Ore consuntivate</p><p className="font-medium">{p.ore_consuntivate.toLocaleString('it-IT')}h / {p.budget_ore}h</p></div>
                  <div><p className="text-gray-400">Budget ore usato</p><p className="font-medium">{p.budgetUsato.toFixed(0)}%</p></div>
                  <div><p className="text-gray-400">Compilazione</p><p className="font-medium">{p.tasso_compilazione.toFixed(0)}%</p></div>
                  <div><p className="text-gray-400">Task</p><p className="font-medium">{p.task_completati}/{p.task_totali}</p></div>
                </div>

                <div className={`p-3 rounded-lg border text-sm ${agentBg}`}>
                  <span>🤖 <strong>Agente:</strong> {agentMsg}</span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
