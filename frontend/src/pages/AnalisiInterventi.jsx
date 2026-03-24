import React, { useState, useEffect } from 'react'
import { fetchDipendenti, fetchProgetti, fetchTasks, fetchGantt, richiediAnalisiGantt, simulaRitardoMultiplo, fetchSegnalazioni } from '../api'
import { GanttChart } from './Gantt'

// ── Costanti ────────────────────────────────────────────────────────
const PRIORITA_COLORS = {
  alta:  'bg-red-900/30 border-red-700 text-red-300',
  media: 'bg-yellow-900/30 border-yellow-700 text-yellow-300',
  bassa: 'bg-gray-800 border-gray-700 text-gray-300',
}

const FATTIBILITA_BADGE = {
  alta:  'bg-green-600 text-white',
  media: 'bg-yellow-600 text-white',
  bassa: 'bg-red-600 text-white',
}

// ═════════════════════════════════════════════════════════════════════
//  PAGINA PRINCIPALE
// ═════════════════════════════════════════════════════════════════════

export default function AnalisiInterventi() {
  // Dati condivisi
  const [dipendenti, setDipendenti] = useState([])
  const [progetti, setProgetti] = useState([])
  const [allTasks, setAllTasks] = useState([])
  const [loadingData, setLoadingData] = useState(true)

  // ── Sezione Esplorazione ──
  const [ritardiList, setRitardiList] = useState([])
  const [addTaskId, setAddTaskId] = useState('')
  const [addGiorni, setAddGiorni] = useState(14)
  const [simResult, setSimResult] = useState(null)
  const [simLoading, setSimLoading] = useState(false)

  // ── Sezione Interventi ──
  const SEGNALAZIONI_DEFAULT = [
    {
      id: 'S001', tipo: 'sovraccarico', priorita: 'alta',
      dipendente_id: 'D005', dipendente: 'Alessandro Conte',
      dettaglio: 'Saturazione al 133%, 5 progetti attivi. Non riesce a lavorare sulla proposta tecnica Allerta.',
      timestamp: '2026-03-09 10:30',
    },
    {
      id: 'S002', tipo: 'richiesta_supporto', priorita: 'alta',
      dipendente_id: 'D001', dipendente: 'Marco Bianchi',
      dettaglio: 'Richiede supporto tecnico junior per Design architettura HL7 FHIR.',
      timestamp: '2026-03-09 11:15',
    },
    {
      id: 'S003', tipo: 'sovraccarico', priorita: 'media',
      dipendente_id: 'D007', dipendente: 'Roberto Esposito',
      dettaglio: 'Saturazione al 106%, gestisce 3 backend contemporaneamente.',
      timestamp: '2026-03-08 16:45',
    },
  ]
  const [segnalazioni, setSegnalazioni] = useState(SEGNALAZIONI_DEFAULT)
  const [selectedSegn, setSelectedSegn] = useState(null)
  const [analisiResult, setAnalisiResult] = useState(null)
  const [analisiLoading, setAnalisiLoading] = useState(false)

  // Segnalazione manuale
  const [segnTipo, setSegnTipo] = useState('sovraccarico')
  const [segnDip, setSegnDip] = useState('')
  const [segnDettaglio, setSegnDettaglio] = useState('')
  const [segnPriorita, setSegnPriorita] = useState('alta')

  // Sezione attiva (per scroll/navigazione)
  const [activeSection, setActiveSection] = useState('esplorazione')

  // ── Caricamento dati ──
  useEffect(() => {
    Promise.all([fetchDipendenti(), fetchProgetti(), fetchTasks()])
      .then(([d, p, t]) => { setDipendenti(d); setProgetti(p); setAllTasks(t) })
      .finally(() => setLoadingData(false))
    // Carica segnalazioni dal backend (chatbot) e merge con le default
    fetchSegnalazioni().then(backendSegn => {
      if (backendSegn && backendSegn.length > 0) {
        setSegnalazioni(prev => [...backendSegn, ...prev])
      }
    }).catch(() => {}) // silenzioso se il backend non ha ancora segnalazioni
  }, [])

  if (loadingData) return <p className="text-gray-400">Caricamento...</p>

  // ── Helper ──
  const tasksSim = allTasks.filter(t => !['Completato', 'Sospeso'].includes(t.stato))
  const ritardiTaskIds = new Set(ritardiList.map(r => r.task_id))

  function getTaskInfo(taskId) {
    return allTasks.find(t => t.id === taskId)
  }

  function getProgettoInfo(progettoId) {
    return progetti.find(p => p.id === progettoId)
  }

  // ── Esplorazione: gestione ritardi ──
  function addRitardo() {
    if (!addTaskId || ritardiTaskIds.has(addTaskId)) return
    setRitardiList(prev => [...prev, { task_id: addTaskId, giorni_ritardo: addGiorni }])
    setAddTaskId('')
    setAddGiorni(14)
  }

  function removeRitardo(taskId) {
    setRitardiList(prev => prev.filter(r => r.task_id !== taskId))
    setSimResult(null)
  }

  async function runSimulazione() {
    if (ritardiList.length === 0) return
    setSimLoading(true)
    try {
      const result = await simulaRitardoMultiplo(ritardiList)
      setSimResult(result)
    } catch (e) {
      console.error('Errore simulazione:', e)
    }
    setSimLoading(false)
  }

  function resetSimulazione() {
    setRitardiList([])
    setSimResult(null)
  }

  // ── Esplorazione → Interventi: passa all'agente ──
  function passaAllAgente() {
    if (!simResult) return
    // Costruisci una segnalazione sintetica dal risultato della simulazione
    const taskNomi = simResult.task_ritardati?.map(t => t.task_nome).join(', ') || ''
    const progettiCoinvolti = [...new Set(simResult.task_ritardati?.map(t => t.progetto) || [])].join(', ')
    const impatti = simResult.impatti?.length || 0
    const sovraccarichi = simResult.impatti?.filter(i => i.sovraccarico)?.length || 0

    // Trova il dipendente_id dal primo task ritardato (lo cerchiamo in allTasks)
    const primoTaskId = simResult.task_ritardati?.[0]?.task_id || ritardiList[0]?.task_id
    const primoTask = allTasks.find(t => t.id === primoTaskId)
    const dipId = primoTask?.dipendente_id || dipendenti[0]?.id || 'D001'
    const dipNome = primoTask?.dipendente_nome || 'Da simulazione'

    const segnSim = {
      id: `SIM-${Date.now()}`,
      tipo: 'simulazione_ritardo',
      priorita: sovraccarichi > 0 ? 'alta' : impatti > 2 ? 'media' : 'bassa',
      dipendente_id: dipId,
      dipendente: dipNome,
      dettaglio: `Simulazione ritardo su: ${taskNomi}. Progetti: ${progettiCoinvolti}. ${impatti} task impattati a cascata, ${sovraccarichi} sovraccarichi rilevati.`,
      timestamp: 'Ora',
      fromSimulation: true,
    }

    setSegnalazioni(prev => [segnSim, ...prev])
    setActiveSection('interventi')
    // Auto-analizza
    handleAnalizza(segnSim)
  }

  // ── Interventi: analisi agente ──
  async function handleAnalizza(segn) {
    setSelectedSegn(segn)
    setAnalisiLoading(true)
    setAnalisiResult(null)

    try {
      const result = await richiediAnalisiGantt({
        segnalazione_tipo: segn.tipo,
        segnalazione_dettaglio: segn.dettaglio,
        dipendente_id: segn.dipendente_id,
        priorita: segn.priorita,
      })
      setAnalisiResult(result)
    } catch (err) {
      setAnalisiResult({ error: err.message })
    } finally {
      setAnalisiLoading(false)
    }
  }

  async function handleAnalizzaManuale() {
    if (!segnDip || !segnDettaglio) return
    const dip = dipendenti.find(d => d.id === segnDip)
    const nuovaSegn = {
      id: `MAN-${Date.now()}`,
      tipo: segnTipo,
      priorita: segnPriorita,
      dipendente_id: segnDip,
      dipendente: dip?.nome || '',
      dettaglio: segnDettaglio,
      timestamp: 'Ora',
    }
    setSegnalazioni(prev => [nuovaSegn, ...prev])
    setSegnDettaglio('')
    await handleAnalizza(nuovaSegn)
  }

  // ── Budget alert helpers ──
  function calcBudgetAlerts() {
    if (!simResult?.gantt_dopo) return []
    const alerts = []
    const progettiIds = [...new Set(simResult.changed_ids?.map(tid => {
      const task = simResult.gantt_dopo.find(t => t.id === tid)
      return task ? progetti.find(p => p.nome === task.project)?.id : null
    }).filter(Boolean) || [])]

    for (const pid of progettiIds) {
      const proj = progetti.find(p => p.id === pid)
      if (!proj) continue
      // Calcola ore totali stimate dei task di questo progetto nel GANTT dopo
      const tasksDopo = simResult.gantt_dopo.filter(t => t.project === proj.nome)
      const oreTotali = tasksDopo.reduce((sum, t) => sum + (t.estimated_hours || 0), 0)
      if (oreTotali > proj.budget_ore) {
        alerts.push({
          tipo: 'budget_ore',
          progetto: proj.nome,
          ore_stimate: oreTotali,
          budget: proj.budget_ore,
          sforamento_pct: Math.round((oreTotali / proj.budget_ore - 1) * 100),
        })
      }
    }
    return alerts
  }

  function calcSaturazioneAlerts() {
    if (!simResult?.impatti) return []
    return simResult.impatti
      .filter(i => i.sovraccarico)
      .map(i => ({
        dipendente: i.dipendente,
        progetto: i.progetto,
        carico: i.carico,
        capacita: i.capacita,
        pct: Math.round((i.carico / i.capacita) * 100),
      }))
  }

  const budgetAlerts = calcBudgetAlerts()
  const saturazioneAlerts = calcSaturazioneAlerts()
  const proposte = analisiResult?.proposte

  // ═════════════════════════════════════════════════════════════════
  //  RENDER
  // ═════════════════════════════════════════════════════════════════

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">🔬 Analisi e Interventi</h1>
      <p className="text-sm text-yellow-400 mb-6">🔒 Riservato al management — Esplora scenari, analizza impatti, decidi interventi.</p>

      {/* Tab di navigazione sezioni */}
      <div className="flex gap-2 mb-6">
        <button onClick={() => setActiveSection('esplorazione')}
          className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
            activeSection === 'esplorazione' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
          }`}>
          🔍 Esplorazione
        </button>
        <button onClick={() => setActiveSection('interventi')}
          className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
            activeSection === 'interventi' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
          }`}>
          🛠️ Interventi
          {segnalazioni.length > 0 && (
            <span className="ml-2 px-1.5 py-0.5 bg-red-600 text-white text-[10px] rounded-full">{segnalazioni.length}</span>
          )}
        </button>
      </div>

      {/* ═══════════════════════════════════════════════════════════ */}
      {/*  SEZIONE ESPLORAZIONE                                      */}
      {/* ═══════════════════════════════════════════════════════════ */}

      {activeSection === 'esplorazione' && (
        <div className="space-y-6">
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h2 className="text-lg font-semibold mb-4">⏰ Simulazione Ritardi</h2>
            <p className="text-sm text-gray-400 mb-4">
              Seleziona uno o più task, imposta i giorni di ritardo per ciascuno, e visualizza l'impatto complessivo su progetti e risorse.
            </p>

            {/* Form aggiunta ritardo */}
            <div className="flex gap-3 items-end mb-4 flex-wrap">
              <div className="flex-1 min-w-[300px]">
                <label className="text-sm text-gray-400 block mb-1">Task</label>
                <select value={addTaskId} onChange={e => setAddTaskId(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm">
                  <option value="">Seleziona un task...</option>
                  {tasksSim.filter(t => !ritardiTaskIds.has(t.id)).map(t => (
                    <option key={t.id} value={t.id}>
                      {t.nome} — {t.progetto_nome} ({t.dipendente_nome})
                    </option>
                  ))}
                </select>
              </div>
              <div className="w-28">
                <label className="text-sm text-gray-400 block mb-1">Giorni</label>
                <input type="number" min="1" value={addGiorni}
                  onChange={e => setAddGiorni(parseInt(e.target.value) || 1)}
                  className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm" />
              </div>
              <button onClick={addRitardo} disabled={!addTaskId}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-600 rounded-lg text-sm font-medium">
                + Aggiungi
              </button>
            </div>

            {/* Lista ritardi */}
            {ritardiList.length > 0 && (
              <div className="mb-4 space-y-2">
                <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">
                  Ritardi da simulare ({ritardiList.length})
                </p>
                {ritardiList.map(r => {
                  const info = getTaskInfo(r.task_id)
                  return (
                    <div key={r.task_id} className="flex items-center justify-between p-3 bg-gray-800/60 rounded-lg border border-gray-700">
                      <div className="flex-1">
                        <span className="text-sm font-medium">{info?.nome || r.task_id}</span>
                        <span className="text-xs text-gray-400 ml-2">{info?.progetto_nome} · {info?.dipendente_nome}</span>
                      </div>
                      <span className="text-sm text-amber-300 font-semibold mx-4">+{r.giorni_ritardo}gg</span>
                      <button onClick={() => removeRitardo(r.task_id)} className="text-gray-500 hover:text-red-400 text-sm px-2">✕</button>
                    </div>
                  )
                })}
                <div className="flex gap-3 pt-2">
                  <button onClick={runSimulazione} disabled={simLoading}
                    className="px-6 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 rounded-lg text-sm font-medium">
                    {simLoading ? '⏳ Simulazione...' : '▶️ Simula tutto'}
                  </button>
                  <button onClick={resetSimulazione} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm">
                    🗑️ Pulisci tutto
                  </button>
                </div>
              </div>
            )}

            {ritardiList.length === 0 && !simResult && (
              <p className="text-gray-500 text-sm italic">
                Aggiungi uno o più task con i rispettivi giorni di ritardo, poi clicca "Simula tutto".
              </p>
            )}
          </div>

          {/* ── Risultato simulazione ── */}
          {simResult && (
            <div className="space-y-4">

              {/* Riepilogo ritardi applicati */}
              <div className="p-4 bg-amber-900/20 border border-amber-800/40 rounded-xl">
                <p className="text-amber-300 font-semibold mb-2">⚡ {simResult.task_ritardati?.length || 0} task ritardati</p>
                {simResult.task_ritardati?.map((tr, i) => (
                  <p key={i} className="text-sm text-amber-200/80">
                    • <strong>{tr.task_nome}</strong>
                    <span className="text-gray-400"> ({tr.progetto})</span>
                    {' → '}nuova fine: {new Date(tr.nuova_fine).toLocaleDateString('it-IT')}
                    <span className="text-amber-400"> (+{tr.giorni}gg)</span>
                  </p>
                ))}
              </div>

              {/* Alert: budget e saturazione */}
              {(budgetAlerts.length > 0 || saturazioneAlerts.length > 0) && (
                <div className="grid grid-cols-2 gap-4">
                  {budgetAlerts.length > 0 && (
                    <div className="p-4 bg-red-900/20 border border-red-800/40 rounded-xl">
                      <p className="text-red-300 font-semibold mb-2">💰 Sforamento budget</p>
                      {budgetAlerts.map((a, i) => (
                        <p key={i} className="text-sm text-red-200/80">
                          <strong>{a.progetto}</strong>: {a.ore_stimate}h / {a.budget}h budget
                          <span className="text-red-400"> (+{a.sforamento_pct}%)</span>
                        </p>
                      ))}
                    </div>
                  )}
                  {saturazioneAlerts.length > 0 && (
                    <div className="p-4 bg-orange-900/20 border border-orange-800/40 rounded-xl">
                      <p className="text-orange-300 font-semibold mb-2">👥 Risorse in sovraccarico</p>
                      {saturazioneAlerts.map((a, i) => (
                        <p key={i} className="text-sm text-orange-200/80">
                          <strong>{a.dipendente}</strong> ({a.progetto}): {a.carico.toFixed(0)}h / {a.capacita}h
                          <span className="text-orange-400"> ({a.pct}%)</span>
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Impatti a cascata */}
              {simResult.impatti?.length > 0 && (
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
                  <p className="text-sm font-semibold mb-2">🔗 Impatti a cascata ({simResult.impatti.length} task coinvolti)</p>
                  <div className="space-y-2 max-h-[200px] overflow-y-auto">
                    {simResult.impatti.map((imp, i) => (
                      <div key={i} className={`text-sm p-3 rounded-lg border ${
                        imp.sovraccarico ? 'bg-red-900/30 border-red-800 text-red-300' : 'bg-yellow-900/20 border-yellow-800 text-yellow-200'
                      }`}>
                        {imp.sovraccarico ? '🔴' : '🟡'}{' '}
                        <strong>{imp.task_nome}</strong>
                        <span className="text-gray-400"> ({imp.progetto})</span>
                        {' · '}{imp.dipendente}:{' '}
                        {new Date(imp.nuovo_inizio).toLocaleDateString('it-IT')} → {new Date(imp.nuova_fine).toLocaleDateString('it-IT')}
                        {imp.sovraccarico && <span className="text-red-400 ml-1">SOVRACCARICO ({imp.carico.toFixed(0)}h/{imp.capacita}h)</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {simResult.impatti?.length === 0 && (
                <p className="text-green-300 text-sm p-4 bg-green-900/20 border border-green-800/40 rounded-xl">✅ Nessun impatto a cascata.</p>
              )}

              {/* GANTT Prima vs Dopo */}
              <div className="space-y-3">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 bg-gray-800 px-2 py-1 rounded">📊 Prima</span>
                  </div>
                  <GanttChart tasks={simResult.gantt_prima} compact />
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-amber-300 bg-amber-900/30 px-2 py-1 rounded">📊 Dopo</span>
                    <span className="text-[10px] text-gray-500">Le barre evidenziate in ambra sono i task modificati</span>
                  </div>
                  <GanttChart tasks={simResult.gantt_dopo} changedIds={simResult.changed_ids} compact />
                </div>
              </div>

              {/* Ponte verso Interventi */}
              <div className="flex justify-end pt-2">
                <button onClick={passaAllAgente}
                  className="px-6 py-2.5 bg-purple-600 hover:bg-purple-500 rounded-lg text-sm font-medium transition-colors">
                  🧠 Passa all'agente per proposte di intervento →
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════ */}
      {/*  SEZIONE INTERVENTI                                        */}
      {/* ═══════════════════════════════════════════════════════════ */}

      {activeSection === 'interventi' && (
        <div className="grid grid-cols-5 gap-6">
          {/* Colonna sinistra: segnalazioni */}
          <div className="col-span-2">
            <h2 className="text-lg font-semibold mb-3">📥 Segnalazioni</h2>

            <div className="space-y-2 mb-6 max-h-[400px] overflow-y-auto">
              {segnalazioni.map(s => (
                <div key={s.id}
                  onClick={() => handleAnalizza(s)}
                  className={`p-4 rounded-xl border cursor-pointer transition-all ${
                    selectedSegn?.id === s.id ? 'ring-2 ring-blue-500' : ''
                  } ${PRIORITA_COLORS[s.priorita]} ${s.fromSimulation ? 'border-l-4 border-l-purple-500' : ''}`}>
                  <div className="flex justify-between items-start mb-1">
                    <span className="text-xs font-medium uppercase">
                      {s.fromSimulation ? '🔬 Da simulazione' : s.tipo.replace('_', ' ')}
                    </span>
                    <span className="text-xs opacity-70">{s.timestamp}</span>
                  </div>
                  <p className="font-medium text-sm">{s.dipendente}</p>
                  <p className="text-xs mt-1 opacity-80">{s.dettaglio}</p>
                </div>
              ))}
            </div>

            {/* Segnalazione manuale */}
            <details className="mb-4">
              <summary className="cursor-pointer text-sm text-gray-400 hover:text-white">➕ Inserisci segnalazione manuale</summary>
              <div className="mt-3 bg-gray-900 rounded-xl border border-gray-800 p-4 space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <select value={segnTipo} onChange={e => setSegnTipo(e.target.value)}
                    className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm">
                    <option value="sovraccarico">Sovraccarico</option>
                    <option value="richiesta_supporto">Richiesta supporto</option>
                    <option value="blocco_task">Task bloccato</option>
                    <option value="scadenza_anticipata">Scadenza anticipata</option>
                    <option value="cambio_priorita">Cambio priorità</option>
                    <option value="espansione_progetto">Espansione progetto</option>
                  </select>
                  <select value={segnPriorita} onChange={e => setSegnPriorita(e.target.value)}
                    className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm">
                    <option value="alta">Priorità alta</option>
                    <option value="media">Priorità media</option>
                    <option value="bassa">Priorità bassa</option>
                  </select>
                </div>
                <select value={segnDip} onChange={e => setSegnDip(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm">
                  <option value="">Seleziona dipendente coinvolto...</option>
                  {dipendenti.map(d => <option key={d.id} value={d.id}>{d.nome} ({d.saturazione_pct}%)</option>)}
                </select>
                <textarea value={segnDettaglio} onChange={e => setSegnDettaglio(e.target.value)}
                  placeholder="Descrivi la segnalazione o l'evento (es: 'Sparkasse ha anticipato la scadenza al 15 aprile')..."
                  className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm h-20 placeholder-gray-500" />
                <button onClick={handleAnalizzaManuale} disabled={!segnDip || !segnDettaglio}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 rounded-lg text-sm font-medium">
                  🧠 Analizza
                </button>
              </div>
            </details>
          </div>

          {/* Colonna destra: analisi agente */}
          <div className="col-span-3">
            {!selectedSegn && !analisiLoading && (
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-12 text-center text-gray-400">
                <p className="text-lg mb-2">Seleziona una segnalazione</p>
                <p className="text-sm">L'agente analizzerà la situazione e proporrà opzioni di redistribuzione.</p>
              </div>
            )}

            {analisiLoading && (
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-12 text-center">
                <p className="text-lg text-blue-400 animate-pulse">🧠 L'agente sta analizzando...</p>
                <p className="text-sm text-gray-400 mt-2">Valuto carichi, disponibilità e dipendenze.</p>
              </div>
            )}

            {analisiResult && !analisiLoading && (
              <div className="space-y-4">
                {analisiResult.error && (
                  <div className="bg-red-900/20 border border-red-800 rounded-xl p-4 text-red-300">⚠️ {analisiResult.error}</div>
                )}

                {proposte?.parse_error && (
                  <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
                    <p className="text-yellow-400 text-sm mb-2">⚠️ Risposta non strutturata dall'agente:</p>
                    <pre className="text-xs text-gray-300 whitespace-pre-wrap">{proposte.raw_response}</pre>
                  </div>
                )}

                {proposte && !proposte.parse_error && !analisiResult.error && (
                  <>
                    {/* Analisi */}
                    <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
                      <h3 className="font-semibold mb-2">📊 Analisi della situazione</h3>
                      <p className="text-sm text-gray-300">{proposte.analisi}</p>
                      {proposte.urgenza && (
                        <span className={`inline-block mt-2 px-3 py-1 rounded-full text-xs font-medium ${
                          proposte.urgenza === 'alta' ? 'bg-red-600' : proposte.urgenza === 'media' ? 'bg-yellow-600' : 'bg-gray-600'
                        } text-white`}>
                          Urgenza: {proposte.urgenza}
                        </span>
                      )}
                    </div>

                    {/* Proposte A/B/C */}
                    {proposte.proposte?.map((p, i) => (
                      <div key={i} className="bg-gray-900 rounded-xl border border-gray-800 p-5">
                        <div className="flex justify-between items-start mb-3">
                          <h3 className="font-semibold">Opzione {p.id}: {p.titolo}</h3>
                          {p.impatto?.fattibilita && (
                            <span className={`px-3 py-1 rounded-full text-xs font-medium ${FATTIBILITA_BADGE[p.impatto.fattibilita] || 'bg-gray-600 text-white'}`}>
                              Fattibilità: {p.impatto.fattibilita}
                            </span>
                          )}
                        </div>
                        <div className="space-y-2 mb-3">
                          {p.azioni?.map((a, j) => (
                            <div key={j} className="bg-gray-800 rounded-lg p-3 text-sm">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-xs font-medium uppercase text-blue-400">{a.tipo?.replace('_', ' ')}</span>
                                <span className="font-medium">{a.task_nome}</span>
                              </div>
                              {a.da_dipendente && <p className="text-gray-400">Da: {a.da_dipendente} → A: {a.a_dipendente}</p>}
                              {a.nuova_data_inizio && <p className="text-gray-400">Nuove date: {a.nuova_data_inizio} → {a.nuova_data_fine}</p>}
                              {a.motivazione && <p className="text-gray-500 text-xs mt-1">{a.motivazione}</p>}
                            </div>
                          ))}
                        </div>
                        {p.impatto && (
                          <div className="grid grid-cols-2 gap-3 text-xs">
                            <div>
                              <p className="text-green-400 font-medium mb-1">✅ Benefici</p>
                              {p.impatto.benefici?.map((b, k) => <p key={k} className="text-gray-300">• {b}</p>)}
                            </div>
                            <div>
                              <p className="text-red-400 font-medium mb-1">⚠️ Rischi</p>
                              {p.impatto.rischi?.map((r, k) => <p key={k} className="text-gray-300">• {r}</p>)}
                            </div>
                          </div>
                        )}
                        <button className="mt-4 px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg text-sm font-medium transition-colors"
                          onClick={() => alert(`In produzione: applica Opzione ${p.id} e ridisegna il GANTT.`)}>
                          ✅ Applica questa opzione
                        </button>
                      </div>
                    ))}

                    {proposte.conflitti && (
                      <div className="bg-red-900/20 border border-red-800 rounded-xl p-4">
                        <p className="text-red-300 font-semibold">⚠️ Conflitti irrisolvibili</p>
                        <p className="text-sm text-red-200 mt-1">{proposte.conflitti}</p>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
