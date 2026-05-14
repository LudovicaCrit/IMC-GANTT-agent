import React, { useState, useEffect, useMemo } from 'react'
import { fetchDipendenti, fetchProgetti, fetchTasks, anteprimaImpatto, applicaModifiche, salvaBozza, caricaBozza, suggerisciTask, verificaPianificazione } from '../api'

const OGGI = new Date()
const PROFILI = ['AD', 'Manager IT', 'Senior IT Consultant', 'IT Consultant', 'Senior Consultant', 'Consultant', 'PM', 'Manager HR', 'Responsabile amministrazione', 'Addetto amministrazione']
const DEP_TYPES = ['FS', 'SS', 'FF']

function formatDateShort(d) { return new Date(d).toLocaleDateString('it-IT') }

// ═══════════════════════════════════════════════════════════════
//  COMPONENTE: Pianificazione per Fasi → Deliverable
// ═══════════════════════════════════════════════════════════════

function PianificazioneProgetto({ progetto, dipendenti, isBando = false }) {
  // Fasi del progetto
  const [fasiDisponibili, setFasiDisponibili] = useState([])
  const [planFasi, setPlanFasi] = useState([])
  const [nextFaseId, setNextFaseId] = useState(1)

  // Task/deliverable (dentro le fasi)
  const [planTasks, setPlanTasks] = useState([])
  const [nextTaskId, setNextTaskId] = useState(1)

  // UI state
  const [step, setStep] = useState('fasi') // 'fasi' | 'deliverable'
  const [faseAperta, setFaseAperta] = useState(null) // quale fase è espansa
  const [showGantt, setShowGantt] = useState(false)
  const [confermato, setConfermato] = useState(false)
  const [salvataggioMsg, setSalvataggioMsg] = useState('')

  // IA
  const [suggerisciOpen, setSuggerisciOpen] = useState(false)
  const [suggerisciDesc, setSuggerisciDesc] = useState('')
  const [suggerisciLoading, setSuggerisciLoading] = useState(false)

  // Carica fasi disponibili da Configurazione
  useEffect(() => {
    fetch('/api/config/fasi-catalogo')
      .then(r => r.json())
      .then(data => setFasiDisponibili(Array.isArray(data) ? data : []))
      .catch(() => {})
  }, [])

  // Carica bozza al mount
  // ⚠️ DEPRECATO Step 2.0 (13 mag 2026): caricaBozza non funziona più, le bozze
  // sono ora progetti con stato='Bozza'. Pipeline.jsx verrà eliminata a Step 2.7.
  // Lasciamo l'useEffect ma silenzioso: niente bozze caricate, l'utente parte
  // sempre da pagina vuota in attesa di Cantiere.
  useEffect(() => {
    // no-op: caricaBozza disabilitata fino a Step 2.7
  }, [progetto.id])

  // ── Gestione Fasi ──

  function aggiungiFase(nome) {
    if (planFasi.find(f => f.nome === nome)) return // già aggiunta
    setPlanFasi(prev => [...prev, {
      tempId: `fase-${nextFaseId}`,
      nome,
      ore_vendute: 0,
      data_inizio: progetto.data_inizio,
      data_fine: progetto.data_fine,
      ordine: prev.length + 1,
    }])
    setNextFaseId(n => n + 1)
  }

  function aggiungiFaseCustom() {
    const nome = prompt('Nome della nuova fase:')
    if (!nome || !nome.trim()) return
    aggiungiFase(nome.trim())
  }

  function updateFase(tempId, field, value) {
    setPlanFasi(prev => prev.map(f => f.tempId === tempId ? { ...f, [field]: value } : f))
  }

  function removeFase(tempId) {
    setPlanFasi(prev => prev.filter(f => f.tempId !== tempId))
    // Rimuovi anche i task associati
    setPlanTasks(prev => prev.filter(t => t.faseId !== tempId))
  }

  function moveFase(tempId, dir) {
    setPlanFasi(prev => {
      const idx = prev.findIndex(f => f.tempId === tempId)
      if (idx < 0) return prev
      const ni = idx + dir
      if (ni < 0 || ni >= prev.length) return prev
      const c = [...prev]; const [m] = c.splice(idx, 1); c.splice(ni, 0, m)
      return c.map((f, i) => ({ ...f, ordine: i + 1 }))
    })
  }

  // ── Gestione Task/Deliverable dentro una fase ──

  function addTask(faseId) {
    setPlanTasks(prev => [...prev, {
      tempId: `task-${nextTaskId}`,
      faseId,
      nome: '',
      ore: 0,
      profilo: 'Senior Consultant',
      assegnato: '',
      dipendenze: [],
    }])
    setNextTaskId(n => n + 1)
  }

  function updateTask(tempId, field, value) {
    setPlanTasks(prev => prev.map(t => t.tempId === tempId ? { ...t, [field]: value } : t))
  }

  function removeTask(tempId) {
    setPlanTasks(prev => prev
      .filter(t => t.tempId !== tempId)
      .map(t => ({ ...t, dipendenze: t.dipendenze.filter(d => d.taskId !== tempId) }))
    )
  }

  function moveTask(tempId, dir) {
    setPlanTasks(prev => {
      const task = prev.find(t => t.tempId === tempId)
      if (!task) return prev
      const faseTasks = prev.filter(t => t.faseId === task.faseId)
      const altriTasks = prev.filter(t => t.faseId !== task.faseId)
      const idx = faseTasks.findIndex(t => t.tempId === tempId)
      const ni = idx + dir
      if (ni < 0 || ni >= faseTasks.length) return prev
      const c = [...faseTasks]; const [m] = c.splice(idx, 1); c.splice(ni, 0, m)
      return [...altriTasks, ...c]
    })
  }

  // Candidati per assegnazione
  function getCandidati(profilo) {
    return dipendenti
      .filter(d => d.profilo === profilo || (d.competenze && d.competenze.includes(profilo)))
      .sort((a, b) => a.saturazione_pct - b.saturazione_pct)
  }

  // ── Salvataggio ──
  // ⚠️ DEPRECATO Step 2.0 (13 mag 2026): salvaBozza disabilitata.
  // Da Step 2.7 (Cantiere) le bozze saranno gestite come progetti stato='Bozza'.

  async function salva() {
    setSalvataggioMsg('⏳ Salva bozza in migrazione — disponibile in Cantiere a breve')
    setTimeout(() => setSalvataggioMsg(''), 4000)
  }

  // ── Conferma e avvia progetto ──

  async function confermaProgetto() {
    const taskValidi = planTasks.filter(t => t.nome && t.ore > 0)
    if (planFasi.length === 0) { alert('Aggiungi almeno una fase.'); return }
    if (taskValidi.length === 0) { alert('Aggiungi almeno un deliverable con nome e ore.'); return }

    const msg = `Stai per avviare "${progetto.nome}" con ${planFasi.length} fasi e ${taskValidi.length} deliverable. Il progetto passerà a "In esecuzione". Procedere?`
    if (!confirm(msg)) return

    try {
      // Crea i task con la fase associata
      const nuoviTask = taskValidi.map(t => {
        const fase = planFasi.find(f => f.tempId === t.faseId)
        const dipMatch = dipendenti.find(d => d.nome === t.assegnato)
        return {
          nome: t.nome,
          fase: fase?.nome || '',
          ore_stimate: t.ore,
          data_inizio: fase?.data_inizio || progetto.data_inizio,
          data_fine: fase?.data_fine || progetto.data_fine,
          profilo_richiesto: t.profilo,
          dipendente_id: dipMatch ? dipMatch.id : '',
          stato: 'Da iniziare',
        }
      })

      // Crea anche le fasi nel backend
      for (const fase of planFasi) {
        await fetch('/api/fasi', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            progetto_id: progetto.id,
            nome: fase.nome,
            ordine: fase.ordine,
            data_inizio: fase.data_inizio,
            data_fine: fase.data_fine,
            ore_vendute: fase.ore_vendute,
          }),
        })
      }

      const res = await applicaModifiche({
        modifiche: [],
        nuovi_task: nuoviTask,
        progetto_id: progetto.id,
        cambia_stato_progetto: 'In esecuzione',
      })
      if (res.stato_progetto_cambiato) {
        setConfermato(true)
      }
    } catch (err) {
      alert('Errore: ' + err.message)
    }
  }

  // ── IA: suggerisci struttura per fasi ──

  async function handleSuggerisci() {
    if (!suggerisciDesc.trim()) return
    setSuggerisciLoading(true)
    try {
      const res = await suggerisciTask({
        progetto_nome: progetto.nome,
        progetto_cliente: progetto.cliente,
        descrizione: suggerisciDesc,
        budget_ore: progetto.budget_ore,
        data_inizio: progetto.data_inizio,
        data_fine: progetto.data_fine,
      })
      if (res.task_suggeriti && res.task_suggeriti.length > 0) {
        // Raggruppa i task suggeriti per fase
        const fasiMap = {}
        res.task_suggeriti.forEach(t => {
          const faseNome = t.fase || 'Generale'
          if (!fasiMap[faseNome]) fasiMap[faseNome] = []
          fasiMap[faseNome].push(t)
        })

        // Crea le fasi
        const nuoveFasi = Object.keys(fasiMap).map((nome, i) => ({
          tempId: `fase-${nextFaseId + i}`,
          nome,
          ore_vendute: fasiMap[nome].reduce((s, t) => s + (t.ore || 0), 0),
          data_inizio: progetto.data_inizio,
          data_fine: progetto.data_fine,
          ordine: i + 1,
        }))

        // Crea i task dentro le fasi
        let taskIdCounter = nextTaskId
        const nuoviTasks = []
        nuoveFasi.forEach(fase => {
          fasiMap[fase.nome].forEach(t => {
            nuoviTasks.push({
              tempId: `task-${taskIdCounter}`,
              faseId: fase.tempId,
              nome: t.nome,
              ore: t.ore || 40,
              profilo: (t.profilo || 'Senior Consultant').split(',')[0].trim(),
              assegnato: '',
              dipendenze: [],
            })
            taskIdCounter++
          })
        })

        setPlanFasi(nuoveFasi)
        setPlanTasks(nuoviTasks)
        setNextFaseId(n => n + nuoveFasi.length)
        setNextTaskId(taskIdCounter)
        setStep('deliverable')
        setSuggerisciOpen(false)
        setSuggerisciDesc('')
      }
    } catch (err) {
      alert('Errore: ' + err.message)
    } finally {
      setSuggerisciLoading(false)
    }
  }

  // ── Calcoli ──

  const totaleOreFasi = planFasi.reduce((s, f) => s + (f.ore_vendute || 0), 0)
  const totaleOreTask = planTasks.reduce((s, t) => s + (t.ore || 0), 0)
  const deltaOre = totaleOreFasi - progetto.budget_ore

  function oreTaskInFase(faseId) {
    return planTasks.filter(t => t.faseId === faseId).reduce((s, t) => s + (t.ore || 0), 0)
  }

  // ═══════════════════════════════════════════════════════════════
  //  RENDER
  // ═══════════════════════════════════════════════════════════════

  if (confermato) {
    return (
      <div className="bg-green-900/20 border border-green-700 rounded-xl p-8 text-center">
        <p className="text-3xl mb-3">🚀</p>
        <p className="text-xl font-semibold text-green-300 mb-2">Progetto avviato!</p>
        <p className="text-sm text-gray-400">"{progetto.nome}" è ora in esecuzione con {planFasi.length} fasi e {planTasks.filter(t => t.nome).length} deliverable.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header progetto */}
      <div className="flex justify-between items-start">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h2 className="text-lg font-semibold">{progetto.nome}</h2>
            <span className={`text-xs px-2 py-1 rounded-full font-medium ${isBando ? 'bg-blue-900/30 text-blue-300' : 'bg-green-900/30 text-green-300'}`}>
              {isBando ? '📨 In bando' : '🎉 Vinto'}
            </span>
          </div>
          <p className="text-sm text-gray-400">{progetto.cliente} · €{(progetto.valore_contratto / 1000).toFixed(0)}k</p>
        </div>
        <div className="flex items-center gap-2">
          {salvataggioMsg && <span className="text-xs text-green-400">{salvataggioMsg}</span>}
          <button onClick={salva} title="Funzionalità in migrazione — disponibile in Cantiere a breve" className="px-3 py-1.5 bg-gray-800 text-gray-500 rounded-lg text-xs cursor-not-allowed">💾 Salva bozza (in migrazione)</button>
        </div>
      </div>

      {/* KPI */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-3">
          <p className="text-xs text-gray-400">Budget ore</p>
          <p className="text-lg font-bold">{progetto.budget_ore}h</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-3">
          <p className="text-xs text-gray-400">Ore assegnate a fasi</p>
          <p className={`text-lg font-bold ${deltaOre > 0 ? 'text-red-400' : 'text-green-400'}`}>
            {totaleOreFasi}h {deltaOre !== 0 && <span className="text-xs">({deltaOre > 0 ? '+' : ''}{deltaOre}h)</span>}
          </p>
        </div>
        <div className="bg-gray-800 rounded-lg p-3">
          <p className="text-xs text-gray-400">Periodo</p>
          <p className="text-sm font-bold">{formatDateShort(progetto.data_inizio)} → {formatDateShort(progetto.data_fine)}</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-3">
          <p className="text-xs text-gray-400">Fasi / Deliverable</p>
          <p className="text-lg font-bold">{planFasi.length} fasi · {planTasks.filter(t => t.nome).length} deliv.</p>
        </div>
      </div>

      {deltaOre > 0 && (
        <div className="p-3 bg-red-900/20 border border-red-800 rounded-lg text-sm text-red-300">
          ⚠️ Le ore assegnate alle fasi ({totaleOreFasi}h) superano il budget ({progetto.budget_ore}h) di {deltaOre}h.
        </div>
      )}

      {/* Tab Step */}
      <div className="flex gap-2">
        <button onClick={() => setStep('fasi')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            step === 'fasi' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
          }`}>
          1. Definisci fasi
        </button>
        <button onClick={() => setStep('deliverable')}
          disabled={planFasi.length === 0}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            step === 'deliverable' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white disabled:text-gray-600'
          }`}>
          2. Aggiungi deliverable
        </button>
      </div>

      {/* IA suggerisci */}
      <div className="bg-purple-900/10 rounded-xl border border-purple-800/40 p-4">
        <button onClick={() => setSuggerisciOpen(!suggerisciOpen)} className="flex items-center gap-2 w-full text-left">
          <span>🧠</span>
          <span className="font-medium text-sm">Suggerisci struttura con IA</span>
          <span className="text-xs text-gray-500 ml-2">Descrivi il progetto → l'IA propone fasi e deliverable</span>
          <span className="ml-auto text-gray-400 text-sm">{suggerisciOpen ? '▼' : '▶'}</span>
        </button>
        {suggerisciOpen && (
          <div className="mt-3">
            <div className="flex gap-3">
              <textarea value={suggerisciDesc} onChange={e => setSuggerisciDesc(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSuggerisci() } }}
                placeholder="Es: Framework per il reporting ESG, raccolta KPI ambientali, piattaforma raccolta dati, dashboard reporting..."
                rows={2} disabled={suggerisciLoading}
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-sm placeholder-gray-500 focus:border-purple-500 focus:outline-none resize-none disabled:opacity-50" />
              <button onClick={handleSuggerisci} disabled={!suggerisciDesc.trim() || suggerisciLoading}
                className="self-end px-5 py-3 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-700 rounded-lg text-sm font-medium transition-colors whitespace-nowrap">
                {suggerisciLoading ? '⏳ Genero...' : '→ Suggerisci'}
              </button>
            </div>
            {suggerisciDesc && <p className="text-xs text-gray-500 mt-2">⚠️ Le fasi e i deliverable attuali verranno sostituiti. Salva la bozza prima se vuoi conservarli.</p>}
          </div>
        )}
      </div>

      {/* ═══ STEP 1: DEFINIZIONE FASI ═══ */}
      {step === 'fasi' && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">📐 Definizione fasi</h3>
          </div>

          {/* Selezione fasi dal catalogo */}
          <div className="mb-4">
            <p className="text-xs text-gray-400 mb-2">Seleziona le fasi per questo progetto:</p>
            <div className="flex flex-wrap gap-2 mb-3">
              {fasiDisponibili.map(f => {
                const giàAggiunta = planFasi.find(pf => pf.nome === (f.nome || f.fase_nome))
                return (
                  <button key={f.id} onClick={() => !giàAggiunta && aggiungiFase(f.nome || f.fase_nome)}
                    className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${
                      giàAggiunta
                        ? 'bg-blue-600 border-blue-500 text-white'
                        : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-blue-500 hover:text-white'
                    }`}>
                    {giàAggiunta ? '✓ ' : '+ '}{f.nome || f.fase_nome}
                  </button>
                )
              })}
              <button onClick={aggiungiFaseCustom}
                className="px-3 py-1.5 rounded-lg text-xs border border-dashed border-gray-600 text-gray-500 hover:text-white hover:border-gray-400 transition-colors">
                + Fase personalizzata...
              </button>
            </div>
          </div>

          {/* Tabella fasi con ore e date */}
          {planFasi.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-800 text-gray-400">
                  <tr>
                    <th className="text-left px-3 py-2 w-8">#</th>
                    <th className="text-left px-3 py-2">Fase</th>
                    <th className="text-right px-3 py-2 w-24">Ore vendute</th>
                    <th className="text-left px-3 py-2 w-36">Data inizio</th>
                    <th className="text-left px-3 py-2 w-36">Data fine</th>
                    <th className="text-center px-3 py-2 w-20"></th>
                  </tr>
                </thead>
                <tbody>
                  {planFasi.map((fase, idx) => (
                    <tr key={fase.tempId} className="border-t border-gray-800 hover:bg-gray-800/30">
                      <td className="px-3 py-2 text-gray-500 text-xs">{idx + 1}</td>
                      <td className="px-3 py-2 font-medium">{fase.nome}</td>
                      <td className="px-3 py-2">
                        <input type="number" min="0" value={fase.ore_vendute || ''}
                          onChange={e => updateFase(fase.tempId, 'ore_vendute', e.target.value === '' ? 0 : parseInt(e.target.value))}
                          className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-right" />
                      </td>
                      <td className="px-3 py-2">
                        <input type="date" value={fase.data_inizio || ''}
                          onChange={e => updateFase(fase.tempId, 'data_inizio', e.target.value)}
                          className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs w-full" />
                      </td>
                      <td className="px-3 py-2">
                        <input type="date" value={fase.data_fine || ''}
                          onChange={e => updateFase(fase.tempId, 'data_fine', e.target.value)}
                          className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs w-full" />
                      </td>
                      <td className="px-3 py-2 text-center">
                        <div className="flex items-center gap-1 justify-center">
                          <button onClick={() => moveFase(fase.tempId, -1)} disabled={idx === 0}
                            className="text-gray-500 hover:text-white disabled:text-gray-700 text-xs">▲</button>
                          <button onClick={() => moveFase(fase.tempId, 1)} disabled={idx === planFasi.length - 1}
                            className="text-gray-500 hover:text-white disabled:text-gray-700 text-xs">▼</button>
                          <button onClick={() => removeFase(fase.tempId)}
                            className="text-gray-500 hover:text-red-400 text-sm">🗑️</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {planFasi.length > 0 && (
            <div className="flex justify-end mt-4">
              <button onClick={() => setStep('deliverable')}
                className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors">
                Avanti → Aggiungi deliverable
              </button>
            </div>
          )}
        </div>
      )}

      {/* ═══ STEP 2: DELIVERABLE PER FASE (fisarmonica) ═══ */}
      {step === 'deliverable' && (
        <div className="space-y-3">
          {planFasi.map((fase, faseIdx) => {
            const tasksFase = planTasks.filter(t => t.faseId === fase.tempId)
            const oreTaskTot = tasksFase.reduce((s, t) => s + (t.ore || 0), 0)
            const isOpen = faseAperta === fase.tempId

            return (
              <div key={fase.tempId} className="bg-gray-900 rounded-xl border border-gray-800">
                {/* Header fase (cliccabile) */}
                <button onClick={() => setFaseAperta(isOpen ? null : fase.tempId)}
                  className="w-full p-4 flex items-center justify-between hover:bg-gray-800/30 rounded-xl transition-colors">
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-500">{faseIdx + 1}.</span>
                    <span className="font-semibold">{fase.nome}</span>
                    <span className="text-xs text-gray-500">
                      {fase.ore_vendute}h vendute · {oreTaskTot}h pianificate · {tasksFase.length} deliverable
                    </span>
                    {oreTaskTot > (fase.ore_vendute || 0) && fase.ore_vendute > 0 && (
                      <span className="text-xs text-red-400">⚠️ +{oreTaskTot - fase.ore_vendute}h</span>
                    )}
                  </div>
                  <span className="text-gray-400">{isOpen ? '▼' : '▶'}</span>
                </button>

                {/* Contenuto fase (espandibile) */}
                {isOpen && (
                  <div className="px-4 pb-4 border-t border-gray-800">
                    {/* Tabella task dentro la fase */}
                    <table className="w-full text-sm mt-3">
                      <thead className="text-gray-500 text-xs">
                        <tr>
                          <th className="text-left px-2 py-1 w-8">#</th>
                          <th className="text-left px-2 py-1">Deliverable</th>
                          <th className="text-right px-2 py-1 w-20">Ore</th>
                          <th className="text-left px-2 py-1 w-36">Profilo</th>
                          <th className="text-left px-2 py-1 w-40">Assegnato a</th>
                          <th className="text-center px-2 py-1 w-16"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {tasksFase.map((task, tIdx) => (
                          <tr key={task.tempId} className="border-t border-gray-800/50 hover:bg-gray-800/20">
                            <td className="px-2 py-1.5 text-gray-600 text-xs">{tIdx + 1}</td>
                            <td className="px-2 py-1.5">
                              <input type="text" value={task.nome}
                                onChange={e => updateTask(task.tempId, 'nome', e.target.value)}
                                placeholder="Nome del deliverable..."
                                className="w-full bg-transparent border-b border-gray-700 focus:border-blue-500 outline-none py-1 text-sm placeholder-gray-600" />
                            </td>
                            <td className="px-2 py-1.5">
                              <input type="number" min="0" value={task.ore || ''}
                                onChange={e => updateTask(task.tempId, 'ore', e.target.value === '' ? 0 : parseInt(e.target.value))}
                                className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-right" />
                            </td>
                            <td className="px-2 py-1.5">
                              <select value={task.profilo} onChange={e => updateTask(task.tempId, 'profilo', e.target.value)}
                                className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs w-full">
                                {PROFILI.map(p => <option key={p} value={p}>{p}</option>)}
                              </select>
                            </td>
                            <td className="px-2 py-1.5">
                              {(() => {
                                const candidati = getCandidati(task.profilo)
                                return (
                                  <select value={task.assegnato} onChange={e => updateTask(task.tempId, 'assegnato', e.target.value)}
                                    className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs w-full">
                                    <option value="">— Seleziona —</option>
                                    {candidati.map(d => (
                                      <option key={d.id} value={d.nome}
                                        style={{ color: d.saturazione_pct > 100 ? '#f87171' : d.saturazione_pct > 85 ? '#fbbf24' : '#86efac' }}>
                                        {d.nome} ({d.saturazione_pct}%)
                                      </option>
                                    ))}
                                  </select>
                                )
                              })()}
                            </td>
                            <td className="px-2 py-1.5 text-center">
                              <div className="flex items-center gap-1 justify-center">
                                <button onClick={() => moveTask(task.tempId, -1)} disabled={tIdx === 0}
                                  className="text-gray-500 hover:text-white disabled:text-gray-700 text-xs">▲</button>
                                <button onClick={() => moveTask(task.tempId, 1)} disabled={tIdx === tasksFase.length - 1}
                                  className="text-gray-500 hover:text-white disabled:text-gray-700 text-xs">▼</button>
                                <button onClick={() => removeTask(task.tempId)}
                                  className="text-gray-500 hover:text-red-400 text-sm">🗑️</button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>

                    <button onClick={() => addTask(fase.tempId)}
                      className="mt-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-dashed border-gray-600 rounded-lg text-xs text-gray-400 hover:text-white transition-colors">
                      + Aggiungi deliverable a {fase.nome}
                    </button>
                  </div>
                )}
              </div>
            )
          })}

          <div className="flex justify-between items-center mt-4">
            <button onClick={() => setStep('fasi')}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm text-gray-400 hover:text-white transition-colors">
              ← Torna alle fasi
            </button>
            <button onClick={confermaProgetto}
              className="px-5 py-2.5 bg-green-600 hover:bg-green-500 rounded-lg text-sm font-medium transition-colors">
              🚀 Conferma e avvia progetto
            </button>
          </div>
        </div>
      )}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════
//  Funzioni helper (invariate)
// ═══════════════════════════════════════════════════════════════

function ProgressBar({ value, max, label, color = 'bg-blue-500' }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-400 mb-1"><span>{label}</span><span>{pct.toFixed(0)}%</span></div>
      <div className="h-2 bg-gray-700 rounded-full"><div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} /></div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════
//  PAGINA PRINCIPALE — PIPELINE
// ═══════════════════════════════════════════════════════════════

export default function Pipeline() {
  const [progetti, setProgetti] = useState([])
  const [allTasks, setAllTasks] = useState([])
  const [dipendenti, setDipendenti] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('bandi')
  const [pianificazioneAttiva, setPianificazioneAttiva] = useState(null)

  useEffect(() => {
    Promise.all([fetchProgetti(), fetchTasks(), fetchDipendenti()])
      .then(([p, t, d]) => { setProgetti(p); setAllTasks(t); setDipendenti(d) })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-gray-400">Caricamento...</p>

  const bandi = progetti.filter(p => p.stato === 'In bando')
  const daPianificare = progetti.filter(p => p.stato === 'Vinto - Da pianificare')
  const archivio = progetti.filter(p => ['Sospeso', 'Completato'].includes(p.stato))

  function getTasksProgetto(pid) { return allTasks.filter(t => t.progetto_id === pid) }
  function getPersoneProgetto(pid) {
    const tp = getTasksProgetto(pid)
    const ids = [...new Set(tp.map(t => t.dipendente_id))]
    return ids.map(id => {
      const d = dipendenti.find(x => x.id === id)
      const tt = tp.filter(t => t.dipendente_id === id)
      return { id, nome: d?.nome || id, profilo: d?.profilo || '', saturazione: d?.saturazione_pct || 0, ore: tt.reduce((s, t) => s + t.ore_stimate, 0), nTask: tt.length }
    })
  }
  function getOreConsumate(pid) {
    return getTasksProgetto(pid).filter(t => ['Completato', 'In corso'].includes(t.stato)).reduce((s, t) => s + t.ore_stimate, 0)
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">📋 Pipeline</h1>
      <p className="text-sm text-gray-400 mb-6">Bandi attivi, progetti da pianificare, archivio storico.</p>

      <div className="flex gap-2 mb-6">
        <button onClick={() => { setActiveTab('bandi'); setPianificazioneAttiva(null) }}
          className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-colors ${activeTab === 'bandi' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'}`}>
          📨 Bandi attivi {bandi.length > 0 && <span className="ml-2 px-1.5 py-0.5 bg-blue-500 text-white text-[10px] rounded-full">{bandi.length}</span>}
        </button>
        <button onClick={() => { setActiveTab('pianificare'); setPianificazioneAttiva(null) }}
          className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-colors ${activeTab === 'pianificare' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'}`}>
          🎯 Da pianificare {daPianificare.length > 0 && <span className="ml-2 px-1.5 py-0.5 bg-green-500 text-white text-[10px] rounded-full">{daPianificare.length}</span>}
        </button>
        <button onClick={() => { setActiveTab('archivio'); setPianificazioneAttiva(null) }}
          className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-colors ${activeTab === 'archivio' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'}`}>
          📦 Archivio {archivio.length > 0 && <span className="ml-2 px-1.5 py-0.5 bg-gray-500 text-white text-[10px] rounded-full">{archivio.length}</span>}
        </button>
      </div>

      {/* ═══ BANDI ═══ */}
      {activeTab === 'bandi' && (
        <div className="space-y-6">
          {bandi.length === 0 && <div className="bg-gray-900 rounded-xl border border-gray-800 p-8 text-center text-gray-400">Nessun bando attivo.</div>}

          {pianificazioneAttiva && pianificazioneAttiva._fromBando && (
            <>
              <button onClick={() => setPianificazioneAttiva(null)} className="text-sm text-gray-400 hover:text-white mb-2">← Torna ai bandi</button>
              <PianificazioneProgetto progetto={pianificazioneAttiva} dipendenti={dipendenti} isBando={true} />
            </>
          )}

          {(!pianificazioneAttiva || !pianificazioneAttiva._fromBando) && bandi.map(p => (
            <div key={p.id} className="bg-gray-900 rounded-xl border border-gray-800 p-6">
              <div className="flex justify-between items-start">
                <div>
                  <div className="flex items-center gap-3 mb-1">
                    <h2 className="text-lg font-semibold">{p.nome}</h2>
                    <span className="text-xs px-2 py-1 bg-blue-900/30 text-blue-300 rounded-full font-medium">📨 In bando</span>
                  </div>
                  <p className="text-sm text-gray-400">{p.cliente} · €{(p.valore_contratto / 1000).toFixed(0)}k · {p.budget_ore}h budget</p>
                  {p.descrizione && <p className="text-sm text-gray-500 mt-2 line-clamp-2">{p.descrizione}</p>}
                </div>
                <button onClick={() => setPianificazioneAttiva({ ...p, _fromBando: true })}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium">
                  📝 Pianifica
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ═══ DA PIANIFICARE ═══ */}
      {activeTab === 'pianificare' && (
        <div className="space-y-6">
          {!pianificazioneAttiva && (
            <>
              {daPianificare.length === 0 && <div className="bg-gray-900 rounded-xl border border-gray-800 p-8 text-center text-gray-400">Nessun progetto in attesa.</div>}
              {daPianificare.map(p => (
                <div key={p.id} className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                  <div className="flex justify-between items-center">
                    <div>
                      <div className="flex items-center gap-3 mb-1">
                        <h2 className="text-lg font-semibold">{p.nome}</h2>
                        <span className="text-xs px-2 py-1 bg-green-900/30 text-green-300 rounded-full font-medium">🎉 Vinto</span>
                      </div>
                      <p className="text-sm text-gray-400">{p.cliente} · €{(p.valore_contratto / 1000).toFixed(0)}k · {p.budget_ore}h budget</p>
                    </div>
                    <button onClick={() => setPianificazioneAttiva(p)}
                      className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium">
                      🚀 Avvia pianificazione
                    </button>
                  </div>
                </div>
              ))}
            </>
          )}
          {pianificazioneAttiva && (
            <>
              <button onClick={() => setPianificazioneAttiva(null)} className="text-sm text-gray-400 hover:text-white mb-2">← Torna alla lista</button>
              <PianificazioneProgetto progetto={pianificazioneAttiva} dipendenti={dipendenti} />
            </>
          )}
        </div>
      )}

      {/* ═══ ARCHIVIO ═══ */}
      {activeTab === 'archivio' && (
        <div className="space-y-6">
          {archivio.length === 0 && <div className="bg-gray-900 rounded-xl border border-gray-800 p-8 text-center text-gray-400">Nessun progetto in archivio.</div>}
          {archivio.map(p => {
            const tasks = getTasksProgetto(p.id)
            const persone = getPersoneProgetto(p.id)
            const oreConsumate = getOreConsumate(p.id)
            const taskComp = tasks.filter(t => t.stato === 'Completato').length
            const isSospeso = p.stato === 'Sospeso'
            return (
              <div key={p.id} className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <div className="flex items-center gap-3 mb-1">
                      <h2 className="text-lg font-semibold">{p.nome}</h2>
                      <span className={`text-xs px-2 py-1 rounded-full font-medium ${isSospeso ? 'bg-amber-900/30 text-amber-300' : 'bg-gray-700 text-gray-300'}`}>
                        {isSospeso ? '⏸️ Sospeso' : '✅ Completato'}
                      </span>
                    </div>
                    <p className="text-sm text-gray-400">{p.cliente}</p>
                  </div>
                  <p className="text-xl font-bold">€{(p.valore_contratto / 1000).toFixed(0)}k</p>
                </div>
                <div className="grid grid-cols-3 gap-4 text-sm mb-4">
                  <div className="bg-gray-800 rounded-lg p-3"><p className="text-xs text-gray-400">Budget</p><p className="text-lg font-bold">{p.budget_ore}h</p></div>
                  <div className="bg-gray-800 rounded-lg p-3"><p className="text-xs text-gray-400">Consumate</p><p className={`text-lg font-bold ${oreConsumate > p.budget_ore ? 'text-red-400' : 'text-green-400'}`}>{oreConsumate}h</p></div>
                  <div className="bg-gray-800 rounded-lg p-3"><p className="text-xs text-gray-400">Task</p><p className="text-lg font-bold">{taskComp}/{tasks.length}</p></div>
                </div>
                <ProgressBar value={oreConsumate} max={p.budget_ore} label="Ore vs budget" color={oreConsumate > p.budget_ore ? 'bg-red-500' : 'bg-blue-500'} />
                {isSospeso && <div className="p-3 bg-amber-900/20 border border-amber-800/40 rounded-lg text-sm text-amber-200 mt-3">⏸️ <strong>Motivo:</strong> {p.fase_corrente || 'Non specificato'}</div>}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
