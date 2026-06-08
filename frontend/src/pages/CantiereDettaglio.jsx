// ═════════════════════════════════════════════════════════════════════════
// CantiereDettaglio.jsx — Scheda del singolo progetto (URL /cantiere/{id})
//
// È la "pagina dettaglio" del Cantiere: viene aperta cliccando su un
// progetto nella vista GANTT (futuro) o nella pagina-lista Cantiere.jsx
// (Step 2.7, da creare). Il nome "Dettaglio" è coerente con questa
// distinzione padre/figlio.
//
// Struttura (handoff v16 §2.4 + §3.5):
//   - Header anagrafica + breadcrumb
//   - Banner stato (Bozza / In esecuzione / Sospeso / Completato / Annullato)
//   - Tab "Design" (default): KPI sintetici + Anagrafica + Persone +
//     Fasi/Task con drill-down editabile + 3 modali
//   - Tab "Scenari": snapshot deterministico criticità + placeholder
//     ChatbotEstraibile (IA propositiva, R2)
//
// Backend consumati:
//   GET /api/gantt/strutturato?progetto_id={id}  → gerarchia + aggregati
//   PATCH /api/progetti/{id}                     → anagrafica + stato
//   DELETE /api/progetti/{id}                    → solo bozze
//   POST/PATCH/DELETE /api/fasi[/...]            → CRUD fasi (con cascade
//                                                  Step 2.4-bis B §14.1)
//   POST/PATCH /api/tasks[/...]                  → CRUD task
//   PATCH /api/tasks/{id}/elimina                → soft delete task
//   GET /api/risorse/saturazione-periodo         → PannelloSaturazione modale
//
// Note di design:
// - Stesso file React, due tab in cima → si naviga rapidamente senza perdere
//   il contesto progetto (handoff: "stessa lente, due zoom").
// - Tab Scenari NON parte da pagina vuota (handoff §3.5 punto 14): mostra
//   subito uno snapshot deterministico utile, IA è opzionale.
// - I componenti visuali (KpiSintetici, BannerStato, SezioneAnagrafica,
//   SezionePersone, SezioneFasiTask) sono estratti in components/cantiere/
//   per essere riutilizzati in modalità readonly dal GANTT accordion
//   (Step 2.3-bis 4c) e dalla pagina Archivio (Step 2.6).
//   Resta in questo file solo la logica di pagina: routing, caricamento
//   dati, callback, switcher tab, tab Scenari (specifico del Cantiere).
//
// Step 2.3-bis 4a — Estrazione componenti riusabili: 18 mag 2026.
// ═════════════════════════════════════════════════════════════════════════

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  fetchGanttStrutturato,
  fetchDipendenti,
  fetchRuoli,
  updateProgetto,
  deleteProgetto,
  createFase,
  updateFase,
  deleteFase,
  createTask,
  updateTask,
  deleteTask,
} from '../api'


// ── Costanti stati ───────────────────────────────────────────────────────

import { STATI_FASE, STATI_TASK, COLORI_STATO } from '../components/cantiere/_costanti'

// ─── Componenti utility ───────────────────────────────────────────────────

import { FormRow, FormInput, FormInputDate, FormSelect } from '../components/_shared/Form'
import StatoBadge from '../components/_shared/StatoBadge'
import BannerStato from '../components/cantiere/BannerStato'
import KpiSintetici from '../components/cantiere/KpiSintetici'
import SezioneAnagrafica from '../components/cantiere/SezioneAnagrafica'
import SezionePersone from '../components/cantiere/SezionePersone'
import SezioneFasiTask from '../components/cantiere/SezioneFasiTask'

// ─── Tab Scenari: snapshot deterministico ───────────────────────────────

/**
 * Calcola le criticità del progetto dai dati attuali, lato frontend.
 * Niente IA. Niente backend dedicato (verrà fatto in R2 con
 * /api/cantiere/{id}/scenario-snapshot, handoff §2.2 punto 3).
 *
 * Le criticità sono "domande che la prossima IA dovrebbe saper rispondere":
 * questo è il MVP "stupido" che fa già il 70% del valore.
 */
function calcolaCriticita(progetto) {
  const crit = []

  // 1. Nessuna fase
  if (!progetto.fasi || progetto.fasi.length === 0) {
    crit.push({ tipo: 'struttura', livello: 'alto', msg: 'Il progetto non ha nessuna fase. Crea almeno una fase per iniziare a pianificare.' })
  }

  // 2. Fasi senza task
  progetto.fasi?.forEach(f => {
    if (f.tasks.length === 0 && f.stato !== 'Annullata') {
      crit.push({ tipo: 'struttura', livello: 'medio', msg: `La fase "${f.nome}" non ha task.` })
    }
  })

  // 3. Sforamenti ore a livello fase
  progetto.fasi?.forEach(f => {
    if (f.ore_vendute > 0 && f.ore_consumate > f.ore_vendute) {
      const exc = Math.round(f.ore_consumate - f.ore_vendute)
      crit.push({ tipo: 'ore', livello: 'alto', msg: `La fase "${f.nome}" ha sforato di ${exc}h (${f.ore_consumate}h vs ${f.ore_vendute}h vendute).` })
    }
  })

  // 4. Sforamento globale progetto
  if (progetto.ore_vendute_totali > 0 && progetto.ore_consumate_totali > progetto.ore_vendute_totali) {
    const exc = Math.round(progetto.ore_consumate_totali - progetto.ore_vendute_totali)
    crit.push({ tipo: 'ore', livello: 'alto', msg: `Il progetto ha sforato globalmente di ${exc}h (${progetto.ore_consumate_totali}h vs ${progetto.ore_vendute_totali}h).` })
  }

  // 5. Task con date fuori dalla fase
  progetto.fasi?.forEach(f => {
    if (!f.data_inizio || !f.data_fine) return
    f.tasks.forEach(t => {
      if (t.data_inizio && t.data_inizio < f.data_inizio) {
        crit.push({ tipo: 'date', livello: 'medio', msg: `Task "${t.nome}" inizia (${t.data_inizio}) prima della fase "${f.nome}" (${f.data_inizio}).` })
      }
      if (t.data_fine && t.data_fine > f.data_fine) {
        crit.push({ tipo: 'date', livello: 'medio', msg: `Task "${t.nome}" finisce (${t.data_fine}) dopo la fase "${f.nome}" (${f.data_fine}).` })
      }
    })
  })

  // 6. Incoerenze stato fase
  progetto.fasi?.forEach(f => {
    const taskAttivi = f.tasks.length
    if (taskAttivi === 0) return
    const tuttiComp = f.tasks.every(t => t.stato === 'Completato')
    const almenoUnoCorso = f.tasks.some(t => t.stato === 'In corso')
    if (f.stato === 'Da iniziare' && almenoUnoCorso) {
      crit.push({ tipo: 'stato', livello: 'basso', msg: `Fase "${f.nome}" è "Da iniziare" ma ha task in corso.` })
    }
    if (f.stato === 'In corso' && tuttiComp) {
      crit.push({ tipo: 'stato', livello: 'basso', msg: `Fase "${f.nome}" è "In corso" ma tutti i task sono Completati. Aggiornala a "Completata"?` })
    }
  })

  // 7. Divergenza stato derivato
  if (progetto.stato !== progetto.stato_derivato && progetto.stato !== 'Bozza' && progetto.stato !== 'Completato' && progetto.stato !== 'Annullato') {
    crit.push({ tipo: 'stato', livello: 'basso', msg: `Stato progetto ("${progetto.stato}") diverge dallo stato derivato dalle fasi ("${progetto.stato_derivato}").` })
  }

  return crit
}

function TabScenari({ progetto }) {
  const criticita = useMemo(() => calcolaCriticita(progetto), [progetto])

  const livelliOrdine = { alto: 0, medio: 1, basso: 2 }
  const sorted = [...criticita].sort((a, b) => livelliOrdine[a.livello] - livelliOrdine[b.livello])

  const coloreLivello = {
    alto: 'bg-red-900/40 border-red-700 text-red-200',
    medio: 'bg-yellow-900/30 border-yellow-700 text-yellow-200',
    basso: 'bg-gray-800/60 border-gray-700 text-gray-300',
  }

  return (
    <div>
      <section className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <h2 className="text-xl font-semibold mb-1">🔍 Criticità rilevate</h2>
        <p className="text-xs text-gray-500 mb-4 italic">
          Snapshot deterministico calcolato dai dati attuali. Nessuna IA conversazionale ancora —
          arriverà come "lente prospettica" propositiva (handoff v15 §5.3.3, anticipo R2).
        </p>
        {sorted.length === 0 ? (
          <div className="bg-green-900/30 border border-green-700 rounded-lg p-4 text-sm text-green-200">
            ✅ Nessuna criticità rilevata. Il progetto è coerente con i dati attuali.
          </div>
        ) : (
          <ul className="space-y-2">
            {sorted.map((c, i) => (
              <li key={i} className={`border rounded-lg p-3 text-sm ${coloreLivello[c.livello]}`}>
                <span className="text-xs uppercase tracking-wide opacity-70 mr-2">{c.livello}</span>
                {c.msg}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <h2 className="text-xl font-semibold mb-2">💬 Assistente IA</h2>
        <p className="text-sm text-gray-500 italic">
          In arrivo: chatbot conversazionale per esplorare scenari ("Cosa succede se sposto la data fine?",
          "Cosa succede se aggiungo un task?"). Richiede integrazione con le funzioni di saturazione
          e marginalità (handoff §5.3.3 - 3° livello).
        </p>
      </section>
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════════
// PAGINA CANTIERE DETTAGLIO — entry point
// ═════════════════════════════════════════════════════════════════════════

export default function CantiereDettaglioPage() {
  const { progettoId } = useParams()
  const navigate = useNavigate()
  const [progetto, setProgetto] = useState(null)
  const [dipendenti, setDipendenti] = useState([])
  const [ruoli, setRuoli] = useState([])
  const [loading, setLoading] = useState(true)
  const [errore, setErrore] = useState(null)
  const [tab, setTab] = useState('design')
  // Traccia se l'utente ha modificato qualcosa: decide dove tornare indietro.
  // Nessuna modifica -> /cantiere (lista). Con modifiche -> /gantt (vede il risultato).
  const [modificato, setModificato] = useState(false)

  // Destinazione del "torna indietro" coerente con il flusso del DESIGN_Cantiere.
  const tornaIndietro = () => navigate(modificato ? '/gantt' : '/cantiere')

  const ricarica = useCallback(async () => {
    try {
      const [data, dips, rls] = await Promise.all([
        fetchGanttStrutturato({ progettoId }),
        fetchDipendenti(),
        fetchRuoli(),
      ])
      if (!data || data.length === 0) {
        setErrore('Progetto non trovato')
        setProgetto(null)
      } else {
        setProgetto(data[0])
        setDipendenti(dips || [])
        setRuoli(rls || [])
        setErrore(null)
      }
    } catch (e) {
      setErrore(e.message || 'Errore di caricamento')
    } finally {
      setLoading(false)
    }
  }, [progettoId])

  useEffect(() => {
    setLoading(true)
    ricarica()
  }, [ricarica])

  // ── Azioni progetto ────────────────────────────────────────────────────

  const salvaAnagrafica = async (dati) => {
    await updateProgetto(progettoId, dati)
    setModificato(true)
    await ricarica()
  }

  const eliminaBozza = async () => {
    if (!confirm(`Eliminare definitivamente la bozza "${progetto.nome}"? L'operazione non è reversibile.`)) return
    try {
      await deleteProgetto(progettoId)
      navigate('/gantt')
    } catch (e) { alert('Errore: ' + e.message) }
  }

  const avviaProgetto = async () => {
    if (!confirm(`Avviare il progetto "${progetto.nome}"? Lo stato passerà a "In esecuzione".`)) return
    try { await updateProgetto(progettoId, { stato: 'In esecuzione' }); await ricarica() }
    catch (e) { alert('Errore: ' + e.message) }
  }

  const cambiaStato = async (nuovoStato) => {
    if (!confirm(`Cambiare lo stato del progetto in "${nuovoStato}"?`)) return
    try { await updateProgetto(progettoId, { stato: nuovoStato }); await ricarica() }
    catch (e) { alert('Errore: ' + e.message) }
  }

  // ── Azioni fasi ────────────────────────────────────────────────────────

  const aggiornaFase = async (faseId, dati, cascade = false) => {
    try {
      const res = await updateFase(faseId, dati, cascade)
      setModificato(true)
      await ricarica()
      // Toast post-cascata: avvisa l'utente di quanti task sono stati toccati
      if (cascade && res?.task_aggiornati?.length > 0) {
        const n = res.task_aggiornati.length
        alert(`Aggiornati ${n} ${n === 1 ? 'task' : 'task'} a "${res.task_aggiornati[0].nuovo_stato}".`)
      }
    } catch (e) {
      alert('Errore: ' + e.message)
    }
  }
  
  const eliminaFase = async (fase) => {
    if (!confirm(`Eliminare la fase "${fase.nome}"? Non sarà possibile se ha task agganciati.`)) return
    try { await deleteFase(fase.id); setModificato(true); await ricarica() }
    catch (e) { alert(e.message || 'Errore') }
  }

  const aggiungiFase = async (dati) => { await createFase(dati); setModificato(true); await ricarica() }

  // ── Azioni task ────────────────────────────────────────────────────────

  const aggiungiTask = async (dati) => { await createTask(dati); setModificato(true); await ricarica() }

  const aggiornaTask = async (taskId, dati) => { await updateTask(taskId, dati); setModificato(true); await ricarica() }

  const eliminaTask = async (task) => {
    if (!confirm(`Eliminare il task "${task.nome}"? Verrà marcato come Eliminato (soft delete).`)) return
    try { await deleteTask(task.id); setModificato(true); await ricarica() }
    catch (e) { alert(e.message || 'Errore') }
  }

  // ── Render ────────────────────────────────────────────────────────────

  if (loading) return <p className="text-gray-400">Caricamento scheda progetto…</p>
  if (errore) {
    return (
      <div className="max-w-2xl">
        <Link to="/gantt" className="text-sm text-blue-400 hover:text-blue-300">← Torna a GANTT</Link>
        <div className="mt-4 bg-red-900/30 border border-red-700 rounded-lg p-6">
          <h2 className="text-xl font-semibold text-red-200 mb-2">Errore</h2>
          <p className="text-red-300">{errore}</p>
        </div>
      </div>
    )
  }
  if (!progetto) return null

  return (
    <div className="max-w-5xl">
      {/* Breadcrumb — destinazione dipende da se ci sono state modifiche */}
      <div className="mb-4">
        <button
          onClick={tornaIndietro}
          className="text-sm text-blue-400 hover:text-blue-300"
          title={modificato ? 'Vedi le modifiche nel GANTT' : 'Torna alla lista Cantiere'}
        >
          {modificato ? '← Vedi modifiche nel GANTT' : '← Torna a Cantiere'}
        </button>
      </div>

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-1">{progetto.nome}</h1>
        <div className="text-sm text-gray-500">
          <span className="font-mono">{progetto.id}</span>
          {progetto.cliente && <span> · {progetto.cliente}</span>}
        </div>
      </div>

      {/* Banner stato */}
      <BannerStato progetto={progetto} onAvvia={avviaProgetto} onCambiaStato={cambiaStato} />

      {/* Tab switcher */}
      <div className="border-b border-gray-800 mb-6">
        <div className="flex gap-1">
          <TabButton attivo={tab === 'design'} onClick={() => setTab('design')}>
            ⚙ Design
          </TabButton>
          <TabButton attivo={tab === 'scenari'} onClick={() => setTab('scenari')}>
            🔍 Scenari
          </TabButton>
        </div>
      </div>

      {/* Contenuto tab */}
      {tab === 'design' && (
        <>
          <KpiSintetici progetto={progetto} />
          <SezioneAnagrafica progetto={progetto} onSalva={salvaAnagrafica} onEliminaBozza={eliminaBozza} />
          <SezionePersone progetto={progetto} dipendenti={dipendenti} />
          <SezioneFasiTask
            progetto={progetto}
            dipendenti={dipendenti}
            ruoli={ruoli}
            onAggiornaFase={aggiornaFase}
            onEliminaFase={eliminaFase}
            onAggiungiFase={aggiungiFase}
            onAggiungiTask={aggiungiTask}
            onAggiornaTask={aggiornaTask}
            onEliminaTask={eliminaTask}
          />
        </>
      )}

      {tab === 'scenari' && <TabScenari progetto={progetto} />}
    </div>
  )
}

function TabButton({ attivo, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`px-5 py-2.5 text-sm font-medium border-b-2 transition-colors ${
        attivo
          ? 'border-blue-500 text-blue-300'
          : 'border-transparent text-gray-500 hover:text-gray-300'
      }`}
    >
      {children}
    </button>
  )
}
