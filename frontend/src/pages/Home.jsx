import React, { useState, useEffect } from 'react'
import { fetchProgetti, fetchDipendenti, fetchTasks } from '../api'
import { useNavigate } from 'react-router-dom'

export default function Home() {
  const [progetti, setProgetti] = useState([])
  const [dipendenti, setDipendenti] = useState([])
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    Promise.all([fetchProgetti(), fetchDipendenti(), fetchTasks()])
      .then(([p, d, t]) => { setProgetti(p); setDipendenti(d); setTasks(t) })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-gray-400">Caricamento...</p>

  const attivi = progetti.filter(p => p.stato === 'In esecuzione' && p.id !== 'P010')
  const inBando = progetti.filter(p => p.stato === 'In bando')
  const daPianificare = progetti.filter(p => p.stato === 'Vinto - Da pianificare')
  const sospesi = progetti.filter(p => p.stato === 'Sospeso')
  const sovraccarichi = dipendenti.filter(d => d.saturazione_pct > 100)
  const tasksProgetto = tasks.filter(t => t.progetto_id !== 'P010')
  const mediaCompilazione = attivi.length > 0
    ? Math.round(attivi.reduce((s, p) => s + p.tasso_compilazione, 0) / attivi.length) : 0

  const oggi = new Date()
  const taskInRitardo = tasksProgetto.filter(t => t.stato === 'In corso' && new Date(t.data_fine) < oggi)

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">📊 IMC-Group GANTT Agent</h1>
      <p className="text-gray-400 mb-6">Sistema intelligente di gestione progetti, risorse e consuntivazione</p>

      {/* KPI */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 cursor-pointer hover:border-blue-600 transition-colors"
          onClick={() => navigate('/gantt')}>
          <p className="text-sm text-gray-400">Progetti attivi</p>
          <p className="text-3xl font-bold mt-1">{attivi.length}</p>
          <p className="text-xs text-gray-500 mt-1">{inBando.length} in bando, {sospesi.length} sospesi</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 cursor-pointer hover:border-blue-600 transition-colors"
          onClick={() => navigate('/risorse')}>
          <p className="text-sm text-gray-400">Dipendenti</p>
          <p className="text-3xl font-bold mt-1">{dipendenti.length}</p>
          <p className="text-xs text-gray-500 mt-1">{sovraccarichi.length > 0 ? `${sovraccarichi.length} sovraccaricati` : 'Nessun sovraccarico'}</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Task totali</p>
          <p className="text-3xl font-bold mt-1">{tasksProgetto.length}</p>
          <p className="text-xs text-gray-500 mt-1">{taskInRitardo.length > 0 ? `${taskInRitardo.length} in ritardo` : 'Nessuno in ritardo'}</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 cursor-pointer hover:border-blue-600 transition-colors"
          onClick={() => navigate('/consuntivazione')}>
          <p className="text-sm text-gray-400">Compilazione media</p>
          <p className="text-3xl font-bold mt-1">{mediaCompilazione}%</p>
        </div>
      </div>

      {/* Panoramica progetti */}
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold">Panoramica Progetti</h2>
        <button onClick={() => navigate('/gantt')} className="text-sm text-blue-400 hover:text-blue-300">
          Vedi GANTT completo →
        </button>
      </div>
      <div className="space-y-3 mb-8">
        {attivi.map(p => {
          const pct = p.task_totali > 0 ? Math.round((p.task_completati / p.task_totali) * 100) : 0
          return (
            <div key={p.id} className="bg-gray-800 rounded-xl p-5 border border-gray-700">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <h3 className="font-semibold text-lg">{p.nome}</h3>
                  <p className="text-sm text-gray-400">{p.cliente} — {p.fase_corrente}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-gray-400">Scadenza: {new Date(p.data_fine).toLocaleDateString('it-IT')}</p>
                </div>
              </div>
              <div className="flex justify-between text-sm mb-1">
                <span>{p.task_completati}/{p.task_totali} task completati</span>
                <span className="text-gray-400">{pct}%</span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-2.5">
                <div className="bg-blue-500 h-2.5 rounded-full transition-all" style={{ width: `${pct}%` }} />
              </div>
            </div>
          )
        })}
      </div>

      {/* Alert */}
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold">🚨 Alert</h2>
        {(sovraccarichi.length > 0 || taskInRitardo.length > 0) && (
          <button onClick={() => navigate('/analisi')} className="text-sm text-blue-400 hover:text-blue-300">
            Vai al Tavolo di Lavoro →
          </button>
        )}
      </div>
      <div className="space-y-3 mb-8">
        {sovraccarichi.length > 0 && (
          <div className="p-4 bg-red-900/20 border border-red-800 rounded-xl cursor-pointer hover:border-red-600 transition-colors"
            onClick={() => navigate('/analisi')}>
            <p className="text-red-300 font-semibold">🔴 Risorse sovraccaricate</p>
            <p className="text-sm text-red-200 mt-1">
              {sovraccarichi.map(d => `${d.nome} (${d.saturazione_pct}%, ${d.progetti_attivi.length} progetti)`).join(' · ')}
            </p>
            <p className="text-xs text-red-400 mt-2">Clicca per aprire il Tavolo di Lavoro</p>
          </div>
        )}

        {taskInRitardo.map(t => {
          const giorni = Math.round((oggi - new Date(t.data_fine)) / (1000 * 60 * 60 * 24))
          return (
            <div key={t.id} className="p-4 bg-red-900/20 border border-red-800 rounded-xl cursor-pointer hover:border-red-600 transition-colors"
              onClick={() => navigate('/analisi')}>
              <p className="text-red-300 font-semibold">🔴 Task in ritardo: "{t.nome}"</p>
              <p className="text-sm text-red-200 mt-1">{giorni} giorni oltre la scadenza — {t.dipendente_nome} ({t.progetto_nome})</p>
            </div>
          )
        })}

        <div className="p-4 bg-yellow-900/20 border border-yellow-800 rounded-xl cursor-pointer hover:border-yellow-600 transition-colors"
          onClick={() => navigate('/consuntivazione')}>
          <p className="text-yellow-300 font-semibold">⚠️ Consuntivi settimanali</p>
          <p className="text-sm text-yellow-200 mt-1">
            Compilazione media: {mediaCompilazione}%.
          </p>
          <p className="text-xs text-yellow-400 mt-2">Vai alla consuntivazione</p>
        </div>

        {sovraccarichi.length === 0 && taskInRitardo.length === 0 && (
          <div className="p-4 bg-green-900/20 border border-green-800 rounded-xl">
            <p className="text-green-300 font-semibold">✅ Nessuna criticità rilevata</p>
          </div>
        )}
      </div>

      {/* Pipeline */}
      <div className="grid grid-cols-2 gap-6">
        {/* Bandi */}
        {inBando.length > 0 && (
          <div>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">📨 Bandi in corso</h2>
              <button onClick={() => navigate('/pipeline')} className="text-sm text-blue-400 hover:text-blue-300">
                Vai a Pipeline →
              </button>
            </div>
            <div className="space-y-3">
              {inBando.map(p => (
                <div key={p.id} className="bg-yellow-900/20 border border-yellow-700 rounded-xl p-4 cursor-pointer hover:border-yellow-500 transition-colors"
                  onClick={() => navigate('/pipeline')}>
                  <div className="flex justify-between">
                    <div>
                      <h3 className="font-semibold">{p.nome}</h3>
                      <p className="text-sm text-gray-400">{p.cliente}</p>
                    </div>
                    <p className="text-sm text-yellow-300">€{(p.valore_contratto / 1000).toFixed(0)}k</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Da pianificare */}
        {daPianificare.length > 0 && (
          <div>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">🎯 Vinti — Da pianificare</h2>
              <button onClick={() => navigate('/pipeline')} className="text-sm text-blue-400 hover:text-blue-300">
                Vai a Pipeline →
              </button>
            </div>
            <div className="space-y-3">
              {daPianificare.map(p => (
                <div key={p.id} className="bg-blue-900/20 border border-blue-700 rounded-xl p-4 cursor-pointer hover:border-blue-500 transition-colors"
                  onClick={() => navigate('/pipeline')}>
                  <div className="flex justify-between">
                    <div>
                      <h3 className="font-semibold">{p.nome}</h3>
                      <p className="text-sm text-gray-400">{p.cliente}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-blue-300">€{(p.valore_contratto / 1000).toFixed(0)}k</p>
                      <p className="text-xs text-gray-500">{p.budget_ore}h budget</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
