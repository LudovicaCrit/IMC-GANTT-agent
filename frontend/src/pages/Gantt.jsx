import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchGanttStrutturato, fetchProgetti, fetchDipendenti, exportGanttPdf } from '../api'
import GanttChartFasi from '../components/_shared/GanttChartFasi'

// ── Colori stati ────────────────────────────────────────────────────
const STATUS_COLORS = {
  'Completato': { bar: '#22c55e', bg: 'bg-green-900/30', text: 'text-green-300' },
  'In corso':   { bar: '#3b82f6', bg: 'bg-blue-900/30',  text: 'text-blue-300'  },
  'Da iniziare':{ bar: '#9ca3af', bg: 'bg-gray-700/30',  text: 'text-gray-300'  },
  'Sospeso':    { bar: '#d97706', bg: 'bg-amber-900/30', text: 'text-amber-300'  },
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

// ── Pagina GANTT ────────────────────────────────────────────────────
// ═════════════════════════════════════════════════════════════════════════
// VISTA ELENCO — drill-down gerarchico Progetto → Fase → Task
//
// Step 2.3 del Blocco 2 esteso (handoff v15 §2.3).
// Consumiamo /api/gantt/strutturato e mostriamo la gerarchia come accordion.
// Default apertura: fasi "In corso" aperte, le altre chiuse (handoff §2.3).
// Sola lettura (no edit qui — gli edit vivono in /cantiere e l'approfondimento in /elenco/{id}).
// ═════════════════════════════════════════════════════════════════════════

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
