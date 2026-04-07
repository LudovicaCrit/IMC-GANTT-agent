import React, { useState, useEffect } from 'react'
import { fetchDipendenti, fetchCaricoRisorse, fetchTasks, fetchProgetti } from '../api'

/* ── Saturation cell for heatmap ──────────────────────────────────── */
function SatCell({ value, onClick, isSelected }) {
  let cls = 'text-green-300 bg-green-900/40'
  if (value > 100) cls = 'text-red-300 bg-red-900/50'
  else if (value > 75) cls = 'text-yellow-300 bg-yellow-900/40'
  else if (value > 50) cls = 'text-blue-300 bg-blue-900/30'
  return (
    <td onClick={onClick}
      className={`px-2 py-1.5 text-center text-xs font-medium border border-gray-800 cursor-pointer transition-all hover:brightness-125 ${cls} ${isSelected ? 'ring-2 ring-blue-400' : ''}`}>
      {value}%
    </td>
  )
}

export default function Risorse() {
  const [dipendenti, setDipendenti] = useState([])
  const [carico, setCarico] = useState([])
  const [tasks, setTasks] = useState([])
  const [progetti, setProgetti] = useState([])
  const [loading, setLoading] = useState(true)
  const [filtroProfilo, setFiltroProfilo] = useState('')

  // Vista dettaglio persona
  const [selectedPersona, setSelectedPersona] = useState(null)  // { dipendente_id, settimana_idx }

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

  // Calcola dettaglio task per persona selezionata
  function getDettaglioPersona() {
    if (!selectedPersona) return null
    const { dipendente_id, settimana_idx } = selectedPersona
    const dip = dipendenti.find(d => d.id === dipendente_id)
    const caricoPersona = carico.find(c => c.dipendente_id === dipendente_id)
    if (!dip || !caricoPersona) return null

    const settimanaInfo = caricoPersona.settimane[settimana_idx]
    if (!settimanaInfo) return null

    // Trova i task attivi di questa persona in questa settimana
    const settimanaStart = new Date(settimanaInfo.settimana)
    const settimanaEnd = new Date(settimanaStart)
    settimanaEnd.setDate(settimanaEnd.getDate() + 6)

    const taskAttivi = tasks.filter(t => {
      if (t.dipendente_id !== dipendente_id) return false
      if (['Completato', 'Sospeso'].includes(t.stato)) return false
      const tInizio = new Date(t.data_inizio)
      const tFine = new Date(t.data_fine)
      // Il task è attivo in questa settimana?
      return tFine >= settimanaStart && tInizio <= settimanaEnd
    })

    // Calcola ore settimanali per ogni task
    const taskConOre = taskAttivi.map(t => {
      const tInizio = new Date(t.data_inizio)
      const tFine = new Date(t.data_fine)
      const durataGiorni = Math.max(1, (tFine - tInizio) / 86400000)
      const durataSett = Math.max(1, durataGiorni / 7)
      const oreSett = (t.ore_stimate || 0) / durataSett
      const prog = progetti.find(p => p.id === t.progetto_id)
      return {
        ...t,
        ore_sett: oreSett,
        progetto_nome: prog?.nome || t.progetto_nome || '',
        progetto_cliente: prog?.cliente || '',
      }
    }).sort((a, b) => b.ore_sett - a.ore_sett)

    const totalOre = taskConOre.reduce((sum, t) => sum + t.ore_sett, 0)

    return {
      dip,
      settimana: settimanaInfo,
      settimanaLabel: settLabels[settimana_idx],
      taskConOre,
      totalOre,
    }
  }

  const dettaglio = getDettaglioPersona()

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">👥 Risorse</h1>
      <p className="text-sm text-gray-400 mb-6">Saturazione, disponibilità e dettaglio attività per persona.</p>

      {/* Filtro profilo */}
      <div className="mb-6">
        <select value={filtroProfilo} onChange={e => { setFiltroProfilo(e.target.value); setSelectedPersona(null) }}
          className="bg-gray-800 border border-gray-600 rounded-lg px-4 py-2 text-sm">
          <option value="">Tutti i profili</option>
          {profili.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>

      {/* ═══ Heatmap saturazione ═══ */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-x-auto mb-6">
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <h2 className="font-semibold">📊 Mappa saturazione (12 settimane)</h2>
          <p className="text-xs text-gray-500">Clicca su una cella per vedere il dettaglio attività</p>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-800">
              <th className="text-left px-3 py-2 text-xs text-gray-400 min-w-[200px]">Dipendente</th>
              {settLabels.map(s => <th key={s} className="px-2 py-2 text-xs text-gray-400 text-center">{s}</th>)}
            </tr>
          </thead>
          <tbody>
            {caricoFiltrato.map(c => (
              <tr key={c.dipendente_id} className="hover:bg-gray-800/30">
                <td className="px-3 py-1.5 text-sm border border-gray-800 cursor-pointer hover:bg-gray-800/50"
                  onClick={() => setSelectedPersona({ dipendente_id: c.dipendente_id, settimana_idx: 0 })}>
                  <span className="font-medium">{c.nome}</span>
                  <span className="text-gray-500 text-xs ml-1">({c.profilo})</span>
                </td>
                {c.settimane.map((s, i) => (
                  <SatCell key={i} value={s.saturazione_pct}
                    isSelected={selectedPersona?.dipendente_id === c.dipendente_id && selectedPersona?.settimana_idx === i}
                    onClick={() => setSelectedPersona({ dipendente_id: c.dipendente_id, settimana_idx: i })} />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ═══ Dettaglio persona/settimana (appare al click) ═══ */}
      {dettaglio && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5 mb-6 animate-fade-in">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold text-lg">{dettaglio.dip.nome}</h3>
              <p className="text-sm text-gray-400">{dettaglio.dip.profilo} · {dettaglio.dip.ore_sett}h/sett · Settimana del {dettaglio.settimanaLabel}</p>
            </div>
            <button onClick={() => setSelectedPersona(null)}
              className="text-gray-500 hover:text-white text-lg transition-colors">✕</button>
          </div>

          {/* Barra carico visiva */}
          <div className="mb-4">
            <div className="flex justify-between text-xs text-gray-400 mb-1">
              <span>Carico settimanale stimato</span>
              <span className={`font-medium ${dettaglio.totalOre > dettaglio.dip.ore_sett ? 'text-red-400' : 'text-green-400'}`}>
                {dettaglio.totalOre.toFixed(1)}h / {dettaglio.dip.ore_sett}h
              </span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-2.5">
              <div className={`h-2.5 rounded-full transition-all ${
                dettaglio.totalOre > dettaglio.dip.ore_sett ? 'bg-red-500' :
                dettaglio.totalOre > dettaglio.dip.ore_sett * 0.85 ? 'bg-yellow-500' : 'bg-green-500'
              }`} style={{ width: `${Math.min(100, (dettaglio.totalOre / dettaglio.dip.ore_sett) * 100)}%` }} />
            </div>
            {dettaglio.totalOre > dettaglio.dip.ore_sett && (
              <p className="text-xs text-red-400 mt-1">
                +{(dettaglio.totalOre - dettaglio.dip.ore_sett).toFixed(1)}h oltre le ore contrattuali
              </p>
            )}
          </div>

          {/* Lista task */}
          {dettaglio.taskConOre.length > 0 ? (
            <div className="space-y-2">
              {dettaglio.taskConOre.map(t => {
                const pctDelCarico = dettaglio.totalOre > 0 ? (t.ore_sett / dettaglio.totalOre * 100) : 0
                return (
                  <div key={t.id} className="flex items-center gap-3 p-3 bg-gray-800/50 rounded-lg">
                    {/* Barra proporzionale */}
                    <div className="w-16 bg-gray-700 rounded-full h-1.5 flex-shrink-0">
                      <div className="h-1.5 rounded-full bg-blue-500" style={{ width: `${pctDelCarico}%` }} />
                    </div>
                    {/* Info task */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium truncate">{t.nome}</span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                          t.stato === 'In corso' ? 'bg-blue-900/30 text-blue-300' : 'bg-gray-700 text-gray-400'
                        }`}>{t.stato}</span>
                      </div>
                      <p className="text-xs text-gray-500 truncate">
                        {t.progetto_nome}{t.progetto_cliente ? ` · ${t.progetto_cliente}` : ''} · {t.ore_stimate}h totali
                      </p>
                    </div>
                    {/* Ore settimanali */}
                    <div className="text-right flex-shrink-0">
                      <p className="text-sm font-medium font-data">~{t.ore_sett.toFixed(1)}h</p>
                      <p className="text-[10px] text-gray-500">{pctDelCarico.toFixed(0)}% del carico</p>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <p className="text-sm text-gray-500 text-center py-4">Nessun task attivo in questa settimana.</p>
          )}
        </div>
      )}

      {/* Hint se nessuna selezione */}
      {!selectedPersona && (
        <p className="text-xs text-gray-600 mb-6 text-center">Clicca su una cella della heatmap per vedere cosa fa una persona in quella settimana</p>
      )}

      {/* ═══ Barre disponibilità ═══ */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5 mb-6">
        <h2 className="font-semibold mb-4">🔍 Disponibilità corrente</h2>
        <div className="space-y-3">
          {dipFiltrati.sort((a, b) => b.saturazione_pct - a.saturazione_pct).map(d => {
            const occPct = Math.min(100, d.saturazione_pct)
            const dispPct = Math.max(0, 100 - occPct)
            const barColor = d.saturazione_pct > 100 ? 'bg-red-500' : d.saturazione_pct > 75 ? 'bg-yellow-500' : 'bg-blue-500'
            return (
              <div key={d.id} className="p-3 rounded-lg" style={{ backgroundColor: 'var(--color-surface-800)' }}>
                <div className="flex justify-between items-center mb-2">
                  <div>
                    <span className="font-medium text-sm">{d.nome}</span>
                    <span className="text-gray-500 text-xs ml-2">{d.profilo}</span>
                  </div>
                  <div className="text-sm font-data">
                    <span className={d.saturazione_pct > 100 ? 'text-red-400 font-bold' : 'text-gray-300'}>
                      {d.carico_corrente.toFixed(1)}h/{d.ore_sett}h
                    </span>
                    <span className="text-gray-500 ml-2">({d.saturazione_pct}%)</span>
                  </div>
                </div>
                <div className="flex h-2 rounded-full overflow-hidden bg-gray-700">
                  <div className={`${barColor} transition-all`} style={{ width: `${occPct}%` }} />
                  <div className="bg-green-600/60 transition-all" style={{ width: `${dispPct}%` }} />
                </div>
                <p className="text-[10px] text-gray-500 mt-1.5">
                  {d.n_task_attivi} task · {d.progetti_attivi.length} progetti: {d.progetti_attivi.join(', ')}
                </p>
              </div>
            )
          })}
        </div>
      </div>

      {/* ═══ Anagrafica ═══ */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-x-auto">
        <div className="p-4 border-b border-gray-800">
          <h2 className="font-semibold">📋 Anagrafica Risorse</h2>
        </div>
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
                  <td className="px-4 py-2 text-right font-data">{d.ore_sett}</td>
                  <td className="px-4 py-2 text-gray-400 text-xs">{d.competenze.join(', ')}</td>
                  <td className="px-4 py-2 text-right font-data">{d.n_task_attivi}</td>
                  <td className="px-4 py-2 text-right font-data">{d.carico_corrente.toFixed(1)}h</td>
                  <td className={`px-4 py-2 text-right font-medium font-data ${disp <= 0 ? 'text-red-400' : 'text-green-400'}`}>
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
