import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchGanttStrutturato, fetchProgetti, fetchDipendenti, fetchExcelGantt } from '../api'
import GanttChartFasi from '../components/_shared/GanttChartFasi'
import { vociLegenda } from '../components/_shared/statiColori'
import { disegnaGantt, titoloGantt } from '../components/_shared/ganttSvg'

// ── Legenda ─────────────────────────────────────────────────────────
// Gli stati presenti nei progetti filtrati, fasi e task separati: «Completata»
// e «Completato» sono due stati, non uno scritto in due modi.
function StatusLegend({ progetti }) {
  const fasi = progetti.flatMap(p => p.fasi || [])
  const gruppi = [
    ['Fasi', vociLegenda('fase', fasi.map(f => f.stato))],
    ['Task', vociLegenda('task', fasi.flatMap(f => (f.tasks || []).map(t => t.stato)))],
  ]
  return (
    <div className="flex gap-4 text-xs flex-wrap">
      {gruppi.filter(([, voci]) => voci.length > 0).map(([gruppo, voci]) => (
        <span key={gruppo} className="flex items-center gap-3">
          <span className="text-gray-500">{gruppo}:</span>
          {voci.map(v => (
            <span key={v.stato} className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded" style={{ backgroundColor: v.colore }} />{v.etichetta}
            </span>
          ))}
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
  const [esportando, setEsportando] = useState(false)

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

  // L'export disegna ciò che la pagina ha filtrato (stato, progetto, profilo),
  // con tutte le fasi aperte. Le librerie PDF e ZIP arrivano solo al primo
  // clic. L'Excel lo fa il server, con gli stessi tre filtri.
  async function esporta(formato) {
    setEsportando(true)
    try {
      const modulo = await import('../components/_shared/esportaGantt')
      const nomeBase = modulo.nomeBaseFile(filtroProgetto)
      if (formato === 'excel') {
        const excel = await fetchExcelGantt({ stato: filtroStato, progettoId: filtroProgetto, profilo: filtroProfilo })
        modulo.scaricaBlob(excel, `${nomeBase}.xlsx`)
        return
      }
      const nomeProgetto = filtroProgetto ? ganttFiltrato.find(p => p.id === filtroProgetto)?.nome : null
      const pagine = disegnaGantt(ganttFiltrato, { titolo: titoloGantt(nomeProgetto) })
      if (formato === 'pdf') await modulo.esportaPdf(pagine, nomeBase)
      else await modulo.esportaPng(pagine, nomeBase)
    } catch (e) {
      alert(`Errore nella generazione ${formato.toUpperCase()}: ${e.message}`)
    } finally {
      setEsportando(false)
    }
  }

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
            <StatusLegend progetti={ganttFiltrato} />
            <div className="ml-auto flex gap-2">
              <button onClick={() => esporta('pdf')} disabled={esportando}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors disabled:opacity-50">
                📥 PDF
              </button>
              <button onClick={() => esporta('png')} disabled={esportando}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors disabled:opacity-50">
                🖼️ PNG
              </button>
              <button onClick={() => esporta('excel')} disabled={esportando}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors disabled:opacity-50">
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
