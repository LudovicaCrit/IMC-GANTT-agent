// ═════════════════════════════════════════════════════════════════════════
// Archivio.jsx — Pagina lista progetti chiusi (URL /archivio)
//
// Scopo (Step 2.6, 19/05/2026):
//   Mostra i progetti con stato "Completato" o "Annullato". Stessa filosofia
//   dell'Elenco GANTT (lista compatta minimalista) ma con stati distinti.
//   Click su una card → /elenco/{id} per l'approfondimento read-only completo.
//
//   Toggle per filtrare: tutti | solo completati | solo annullati.
//   Conteggio in alto per dare il colpo d'occhio.
//
// Backend consumati (sola lettura):
//   GET /api/gantt/strutturato?stato=all  → tutti i progetti
//   Filtro Completato/Annullato lato client per indipendenza dal backend.
//   In R2 si può ottimizzare con un parametro stato='chiusi' dedicato.
//
// ═════════════════════════════════════════════════════════════════════════

import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchGanttStrutturato } from '../api'
import StatoBadge from '../components/_shared/StatoBadge'


export default function ArchivioPage() {
  const navigate = useNavigate()
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [errore, setErrore] = useState(null)
  const [filtro, setFiltro] = useState('tutti')  // tutti | completato | annullato

  useEffect(() => {
    setLoading(true)
    setErrore(null)
    fetchGanttStrutturato({ stato: 'all' })
      .then(d => setData(d || []))
      .catch(e => setErrore(e.message || 'Errore di caricamento'))
      .finally(() => setLoading(false))
  }, [])

  // Filtra solo i progetti chiusi (Completato + Annullato)
  const progettiChiusi = useMemo(() => {
    return data.filter(p => p.stato === 'Completato' || p.stato === 'Annullato')
  }, [data])

  const progettiFiltrati = useMemo(() => {
    if (filtro === 'tutti') return progettiChiusi
    if (filtro === 'completato') return progettiChiusi.filter(p => p.stato === 'Completato')
    if (filtro === 'annullato') return progettiChiusi.filter(p => p.stato === 'Annullato')
    return progettiChiusi
  }, [progettiChiusi, filtro])

  const nCompletati = progettiChiusi.filter(p => p.stato === 'Completato').length
  const nAnnullati = progettiChiusi.filter(p => p.stato === 'Annullato').length

  return (
    <div className="max-w-6xl">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold flex items-center gap-3">
          <span>📦</span> Archivio
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Progetti chiusi (completati o annullati). Approfondimento e storico delle ore.
        </p>
      </div>

      {/* Contatori KPI */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
        <ContatoreKpi label="Totale archiviati" valore={progettiChiusi.length} />
        <ContatoreKpi label="Completati" valore={nCompletati} colore="green" />
        <ContatoreKpi label="Annullati" valore={nAnnullati} colore="red" />
      </div>

      {/* Filtri */}
      <div className="flex gap-2 mb-4">
        <FiltroBtn attivo={filtro === 'tutti'} onClick={() => setFiltro('tutti')}>
          Tutti ({progettiChiusi.length})
        </FiltroBtn>
        <FiltroBtn attivo={filtro === 'completato'} onClick={() => setFiltro('completato')}>
          Completati ({nCompletati})
        </FiltroBtn>
        <FiltroBtn attivo={filtro === 'annullato'} onClick={() => setFiltro('annullato')}>
          Annullati ({nAnnullati})
        </FiltroBtn>
      </div>

      {/* Contenuto */}
      {loading ? (
        <p className="text-gray-400 py-8">Caricamento archivio…</p>
      ) : errore ? (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4">
          <p className="text-red-300">Errore: {errore}</p>
        </div>
      ) : progettiFiltrati.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center">
          <div className="text-3xl mb-2">📭</div>
          <p className="text-gray-400">
            {filtro === 'tutti'
              ? 'Nessun progetto in archivio.'
              : `Nessun progetto ${filtro === 'completato' ? 'completato' : 'annullato'}.`}
          </p>
        </div>
      ) : (
        <div>
          {progettiFiltrati.map(p => (
            <ProgettoCardArchivio key={p.id} progetto={p} navigate={navigate} />
          ))}
        </div>
      )}
    </div>
  )
}


function ProgettoCardArchivio({ progetto, navigate }) {
  const sforamento = progetto.ore_vendute_totali > 0 && progetto.ore_consumate_totali > progetto.ore_vendute_totali
  const nTaskTot = (progetto.fasi || []).reduce((s, f) => s + (f.tasks?.length || 0), 0)

  // Periodo aggregato dalle fasi
  const date = (progetto.fasi || [])
    .flatMap(f => [f.data_inizio, f.data_fine])
    .filter(Boolean)
  const periodoMin = date.length ? date.reduce((a, b) => a < b ? a : b) : null
  const periodoMax = date.length ? date.reduce((a, b) => a > b ? a : b) : null

  // Banda colorata in base allo stato chiuso
  const accentColor = progetto.stato === 'Completato' ? '#22c55e' : '#ef4444'

  return (
    <button
      onClick={() => navigate(`/elenco/${progetto.id}`)}
      className="w-full text-left bg-gray-900 rounded-xl border border-gray-800 hover:border-gray-700 hover:bg-gray-900/80 mb-3 overflow-hidden transition-colors"
      title="Apri approfondimento del progetto"
    >
      <div className="flex">
        {/* Bandina laterale colorata (verde=Completato, rosso=Annullato) */}
        <div style={{ width: 4, backgroundColor: accentColor }} />

        <div className="flex-1 px-4 py-3 flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3 min-w-0 flex-1">
            <span className="text-lg font-semibold text-gray-200 truncate">
              {progetto.nome}
            </span>
            <span className="text-xs text-gray-500 font-mono flex-shrink-0">{progetto.id}</span>
            <StatoBadge stato={progetto.stato} />
          </div>
          <div className="text-xs text-gray-400 flex items-center gap-3 flex-wrap">
            <span>Cliente: <span className="text-gray-200">{progetto.cliente || '—'}</span></span>
            <span className="text-gray-700">|</span>
            <span>Ore: <span className={sforamento ? 'text-red-400 font-medium' : 'text-gray-200'}>
              {progetto.ore_consumate_totali}h
            </span>
            <span className="text-gray-600"> / {progetto.ore_vendute_totali}h</span></span>
            <span className="text-gray-700">|</span>
            <span>{progetto.n_fasi} {progetto.n_fasi === 1 ? 'fase' : 'fasi'} · {nTaskTot} task</span>
            {periodoMin && periodoMax && (
              <>
                <span className="text-gray-700">|</span>
                <span className="text-gray-500">{periodoMin} → {periodoMax}</span>
              </>
            )}
          </div>
        </div>
      </div>
    </button>
  )
}


function ContatoreKpi({ label, valore, colore = 'gray' }) {
  const colori = {
    gray: 'text-gray-100',
    green: 'text-green-400',
    red: 'text-red-400',
  }
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</div>
      <div className={`text-2xl font-semibold ${colori[colore]}`}>{valore}</div>
    </div>
  )
}


function FiltroBtn({ attivo, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
        attivo
          ? 'bg-blue-600 text-white font-semibold'
          : 'bg-gray-800 text-gray-400 hover:text-gray-200 hover:bg-gray-700'
      }`}
    >
      {children}
    </button>
  )
}
