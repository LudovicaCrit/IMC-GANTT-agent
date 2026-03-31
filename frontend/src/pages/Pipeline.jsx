import React, { useState, useEffect, useMemo } from 'react'
import { fetchProgetti, fetchTasks, fetchDipendenti, anteprimaImpatto, applicaModifiche, salvaBozza, caricaBozza, verificaPianificazione, suggerisciTask } from '../api'
import { GanttChart } from './Gantt'

// ── Costanti ────────────────────────────────────────────────────────
const OGGI = new Date('2026-03-09')
const SCADENZE_BANDI = { 'P008': new Date('2026-04-15'), 'P009': new Date('2026-04-30') }
const DEP_TYPES = ['FS', 'SS', 'FF']
const DEP_LABELS = { FS: 'Fine → Inizio', SS: 'Inizio → Inizio', FF: 'Fine → Fine' }
const PROFILI = ['Tecnico Senior', 'Tecnico Mid', 'Tecnico Junior', 'Project Manager', 'UX/UI Designer', 'Amministrativo', 'Commerciale/Pre-sales']

function giorniRimanenti(s) { return Math.ceil((s.getTime() - OGGI.getTime()) / 86400000) }
function formatDate(d) { return new Date(d).toLocaleDateString('it-IT', { day: 'numeric', month: 'long', year: 'numeric' }) }
function formatDateShort(d) { return new Date(d).toLocaleDateString('it-IT') }
function addDays(d, n) { const r = new Date(d); r.setDate(r.getDate() + n); return r }

// ── Countdown badge ─────────────────────────────────────────────────
function CountdownBadge({ scadenza }) {
  const g = giorniRimanenti(scadenza)
  const c = g <= 7 ? 'bg-red-600' : g <= 14 ? 'bg-yellow-600' : 'bg-green-600'
  return <span className={`${c} text-white text-xs font-bold px-3 py-1 rounded-full`}>{g > 0 ? `${g} giorni` : 'Scaduto'}</span>
}

// ── Progress bar ────────────────────────────────────────────────────
function ProgressBar({ value, max, label, color = 'bg-blue-500' }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0
  return (
    <div>
      {label && <div className="flex justify-between text-xs text-gray-400 mb-1"><span>{label}</span><span>{value}/{max}h ({pct.toFixed(0)}%)</span></div>}
      <div className="w-full bg-gray-700 rounded-full h-2"><div className={`${color} rounded-full h-2 transition-all`} style={{ width: `${pct}%` }} /></div>
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════
//  STRUMENTO DI PIANIFICAZIONE — calcolo date con dipendenze
// ═════════════════════════════════════════════════════════════════════

function calcolaGanttDaPlan(planTasks, dataInizio, oreSett = 40) {
  // Calcola date per ogni task in base a ore, dipendenze e tipo dipendenza
  // Restituisce array compatibile con GanttChart
  if (!planTasks || planTasks.length === 0) return []

  const taskMap = {}
  planTasks.forEach(t => { taskMap[t.tempId] = { ...t, startDate: null, endDate: null } })

  // Calcola durata in giorni lavorativi da ore stimate
  function durataDays(ore, profilo) {
    // Assumiamo 8h/giorno lavorativo, proporzionale alle ore settimanali
    const oreGiorno = 8
    return Math.max(1, Math.ceil(ore / oreGiorno))
  }

  // Risolvi ricorsivamente le date
  function risolvi(tempId, visited = new Set()) {
    if (visited.has(tempId)) return // ciclo
    visited.add(tempId)
    const task = taskMap[tempId]
    if (!task || task.startDate) return // già risolto

    const durGiorni = durataDays(task.ore, task.profilo)

    if (!task.dipendenze || task.dipendenze.length === 0) {
      // Nessuna dipendenza: parte dalla data inizio progetto
      task.startDate = new Date(dataInizio)
      task.endDate = addDays(task.startDate, durGiorni)
      return
    }

    // Risolvi prima i predecessori
    let latestConstraint = new Date(dataInizio)
    for (const dep of task.dipendenze) {
      risolvi(dep.taskId, visited)
      const pred = taskMap[dep.taskId]
      if (!pred || !pred.startDate) continue

      let constraintDate
      switch (dep.tipo) {
        case 'FS': // Fine predecessore → Inizio questo
          constraintDate = addDays(pred.endDate, 1)
          break
        case 'SS': // Inizio predecessore → Inizio questo
          constraintDate = new Date(pred.startDate)
          break
        case 'FF': // Fine predecessore → Fine questo (calcola indietro)
          constraintDate = addDays(pred.endDate, -durGiorni + 1)
          break
        default:
          constraintDate = addDays(pred.endDate, 1)
      }
      if (constraintDate > latestConstraint) latestConstraint = constraintDate
    }

    task.startDate = latestConstraint
    task.endDate = addDays(task.startDate, durGiorni)
  }

  // Risolvi tutti
  Object.keys(taskMap).forEach(id => risolvi(id, new Set()))

  // Converti in formato GanttChart
  return Object.values(taskMap)
    .filter(t => t.startDate && t.endDate)
    .map(t => ({
      id: t.tempId,
      name: t.nome || 'Task senza nome',
      start: t.startDate.toISOString().split('T')[0],
      end: t.endDate.toISOString().split('T')[0],
      status: 'Da iniziare',
      assignee: t.assegnato || t.profilo || 'Non assegnato',
      project: 'Nuovo progetto',
      estimated_hours: t.ore,
    }))
}

// ═════════════════════════════════════════════════════════════════════
//  COMPONENTE PIANIFICAZIONE
// ═════════════════════════════════════════════════════════════════════

function PianificazioneProgetto({ progetto, dipendenti, isBando = false }) {
  const [planTasks, setPlanTasks] = useState([
    { tempId: 'new-1', nome: '', fase: 'Analisi', ore: 40, profilo: 'Tecnico Senior', assegnato: '', dipendenze: [] },
  ])
  const [nextId, setNextId] = useState(2)
  const [showGantt, setShowGantt] = useState(false)
  const [impatto, setImpatto] = useState(null)      // anteprima impatto
  const [impattoLoading, setImpattoLoading] = useState(false)
  const [confermato, setConfermato] = useState(false)
  const [salvataggioMsg, setSalvataggioMsg] = useState('')
  const [verificaIA, setVerificaIA] = useState(null)
  const [verificaLoading, setVerificaLoading] = useState(false)
  const [suggerisciOpen, setSuggerisciOpen] = useState(false)
  const [suggerisciDesc, setSuggerisciDesc] = useState('')
  const [suggerisciLoading, setSuggerisciLoading] = useState(false)

  // Aggiungi task in coda
  function addTask() {
    setPlanTasks(prev => [...prev, {
      tempId: `new-${nextId}`,
      nome: '',
      fase: 'Sviluppo',
      ore: 40,
      profilo: 'Tecnico Senior',
      assegnato: '',
      dipendenze: [],
    }])
    setNextId(n => n + 1)
  }

  // Inserisci task in una posizione specifica
  function insertTaskAt(index) {
    const newTask = {
      tempId: `new-${nextId}`,
      nome: '',
      fase: 'Sviluppo',
      ore: 40,
      profilo: 'Tecnico Senior',
      assegnato: '',
      dipendenze: [],
    }
    setPlanTasks(prev => {
      const copy = [...prev]
      copy.splice(index, 0, newTask)
      return copy
    })
    setNextId(n => n + 1)
  }

  // Sposta task su o giù
  function moveTask(tempId, direction) {
    setPlanTasks(prev => {
      const idx = prev.findIndex(t => t.tempId === tempId)
      if (idx < 0) return prev
      const newIdx = idx + direction
      if (newIdx < 0 || newIdx >= prev.length) return prev
      const copy = [...prev]
      const [moved] = copy.splice(idx, 1)
      copy.splice(newIdx, 0, moved)
      return copy
    })
  }

  // Rimuovi task
  function removeTask(tempId) {
    setPlanTasks(prev => {
      // Rimuovi anche le dipendenze verso questo task
      return prev
        .filter(t => t.tempId !== tempId)
        .map(t => ({
          ...t,
          dipendenze: t.dipendenze.filter(d => d.taskId !== tempId)
        }))
    })
  }

  // Aggiorna campo task
  function updateTask(tempId, field, value) {
    setPlanTasks(prev => prev.map(t => t.tempId === tempId ? { ...t, [field]: value } : t))
  }

  // Aggiungi dipendenza a un task
  function addDipendenza(tempId, predId, tipo = 'FS') {
    if (!predId || predId === tempId) return
    setPlanTasks(prev => prev.map(t => {
      if (t.tempId !== tempId) return t
      // Evita duplicati
      if (t.dipendenze.some(d => d.taskId === predId)) return t
      return { ...t, dipendenze: [...t.dipendenze, { taskId: predId, tipo }] }
    }))
  }

  // Rimuovi dipendenza
  function removeDipendenza(tempId, predId) {
    setPlanTasks(prev => prev.map(t => {
      if (t.tempId !== tempId) return t
      return { ...t, dipendenze: t.dipendenze.filter(d => d.taskId !== predId) }
    }))
  }

  // Cambia tipo dipendenza
  function changeDipTipo(tempId, predId, newTipo) {
    setPlanTasks(prev => prev.map(t => {
      if (t.tempId !== tempId) return t
      return { ...t, dipendenze: t.dipendenze.map(d => d.taskId === predId ? { ...d, tipo: newTipo } : d) }
    }))
  }

  // ── Verifica risorse (anteprima impatto) ──
  async function verificaRisorse() {
    const taskValidi = planTasks.filter(t => t.nome && t.ore > 0)
    if (taskValidi.length === 0) {
      alert('Compila almeno un task con nome e ore.')
      return
    }
    setImpattoLoading(true)
    try {
      const nuoviTask = taskValidi.map(t => {
        const g = ganttData.find(g => g.id === t.tempId)
        return {
          nome: t.nome,
          fase: t.fase,
          ore_stimate: t.ore,
          data_inizio: g?.start || progetto.data_inizio,
          data_fine: g?.end || progetto.data_fine,
          profilo_richiesto: t.profilo,
          dipendente_id: t.assegnato,
          stato: 'Da iniziare',
        }
      })
      const res = await anteprimaImpatto({
        modifiche: [],
        nuovi_task: nuoviTask,
        progetto_id: progetto.id,
      })
      setImpatto(res.impatto)
    } catch (err) {
      alert('Errore nella verifica risorse: ' + err.message)
    } finally {
      setImpattoLoading(false)
    }
  }

  // ── Conferma e avvia progetto ──
  async function confermaProgetto() {
    const taskValidi = planTasks.filter(t => t.nome && t.ore > 0)
    if (taskValidi.length === 0) {
      alert('Compila almeno un task con nome e ore.')
      return
    }
    if (!confirm(`Stai per avviare "${progetto.nome}" con ${taskValidi.length} task. I task verranno creati nel sistema e il progetto passerà a "In esecuzione". Procedere?`)) return

    try {
      const nuoviTask = taskValidi.map(t => {
        const g = ganttData.find(g => g.id === t.tempId)
        // Converti nome dipendente → id dipendente
        const dipMatch = dipendenti.find(d => d.nome === t.assegnato)
        return {
          nome: t.nome,
          fase: t.fase,
          ore_stimate: t.ore,
          data_inizio: g?.start || progetto.data_inizio,
          data_fine: g?.end || progetto.data_fine,
          profilo_richiesto: t.profilo,
          dipendente_id: dipMatch ? dipMatch.id : '',
          predecessore: '',
          stato: 'Da iniziare',
        }
      })
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
      alert('Errore nella conferma: ' + err.message)
    }
  }

  // ── Salva bozza ──
  async function salva() {
    try {
      await salvaBozza(progetto.id, { planTasks, nextId })
      setSalvataggioMsg('Bozza salvata!')
      setTimeout(() => setSalvataggioMsg(''), 3000)
    } catch (err) {
      setSalvataggioMsg('Errore nel salvataggio')
    }
  }

  // ── Carica bozza al mount ──
  useEffect(() => {
    caricaBozza(progetto.id).then(res => {
      if (res.dati_json && res.dati_json.planTasks) {
        setPlanTasks(res.dati_json.planTasks)
        if (res.dati_json.nextId) setNextId(res.dati_json.nextId)
      }
    }).catch(() => {})
  }, [progetto.id])

  // Calcola GANTT
  const ganttData = useMemo(() => {
    const data = calcolaGanttDaPlan(planTasks, progetto.data_inizio)
    return data.map(t => ({
      ...t,
      project: progetto.nome,
    }))
  }, [planTasks, progetto])

  // Riepilogo
  const totaleOre = planTasks.reduce((s, t) => s + (t.ore || 0), 0)
  const deltaOre = totaleOre - progetto.budget_ore
  const profiliUsati = [...new Set(planTasks.map(t => t.profilo))].length

  // Calcola ore pianificate per persona nella tabella corrente
  const orePianificatePerPersona = useMemo(() => {
    const map = {}
    planTasks.forEach(t => {
      if (t.assegnato) {
        map[t.assegnato] = (map[t.assegnato] || 0) + (t.ore || 0)
      }
    })
    return map
  }, [planTasks])

  // Candidati assegnazione per profilo con saturazione dinamica
  function getCandidati(profilo, currentTaskId) {
    return dipendenti
      .filter(d => d.profilo === profilo)
      .map(d => {
        // Ore pianificate per questa persona (escludendo il task corrente per non contare doppio)
        const orePianAltri = planTasks
          .filter(t => t.assegnato === d.nome && t.tempId !== currentTaskId)
          .reduce((sum, t) => sum + (t.ore || 0), 0)
        // Stima settimanale: ore pianificate / durata progetto in settimane
        const durataSettimane = Math.max(1, Math.round(
          (new Date(progetto.data_fine).getTime() - new Date(progetto.data_inizio).getTime()) / (7 * 86400000)
        ))
        const caricoExtraSett = orePianAltri / durataSettimane
        const saturazioneDinamica = Math.round(d.saturazione_pct + (caricoExtraSett / (d.ore_sett || 40)) * 100)
        return {
          ...d,
          orePianificate: orePianAltri,
          saturazioneDinamica,
        }
      })
      .sort((a, b) => a.saturazioneDinamica - b.saturazioneDinamica) // meno caricati prima
  }

  return (
    <div className="space-y-6">
      {/* Info progetto */}
      <div className="flex justify-between items-start">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h2 className="text-lg font-semibold">{progetto.nome}</h2>
            <span className={`text-xs px-2 py-1 rounded-full font-medium ${isBando ? 'bg-blue-900/30 text-blue-300' : 'bg-green-900/30 text-green-300'}`}>{isBando ? '📨 In bando' : '🎉 Vinto'}</span>
          </div>
          <p className="text-sm text-gray-400">{progetto.cliente}</p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-3">
          <p className="text-xs text-gray-400">Budget ore</p>
          <p className="text-lg font-bold">{progetto.budget_ore}h</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-3">
          <p className="text-xs text-gray-400">Ore pianificate</p>
          <p className={`text-lg font-bold ${deltaOre > 0 ? 'text-red-400' : 'text-green-400'}`}>{totaleOre}h</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-3">
          <p className="text-xs text-gray-400">Periodo</p>
          <p className="text-sm font-bold">{formatDateShort(progetto.data_inizio)} → {formatDateShort(progetto.data_fine)}</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-3">
          <p className="text-xs text-gray-400">Task / Profili</p>
          <p className="text-lg font-bold">{planTasks.length} task · {profiliUsati} profili</p>
        </div>
      </div>

      {deltaOre > 0 && (
        <div className="p-3 bg-red-900/20 border border-red-800 rounded-lg text-sm text-red-300">
          ⚠️ Le ore pianificate ({totaleOre}h) superano il budget ({progetto.budget_ore}h) di {deltaOre}h.
        </div>
      )}

      {/* ── Tabella task ─────────────────────────────────────────── */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        <div className="p-4 border-b border-gray-800 flex justify-between items-center">
          <h3 className="font-semibold">📝 Definizione task</h3>
          <div className="flex gap-2">
            <button onClick={addTask}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-xs font-medium">
              + Aggiungi task
            </button>
            <button onClick={() => setSuggerisciOpen(!suggerisciOpen)}
              disabled={suggerisciLoading}
              className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 disabled:bg-purple-800 rounded-lg text-xs font-medium">
              {suggerisciLoading ? '⏳ L\'agente sta pensando...' : '🧠 Suggerisci con IA'}
            </button>
          </div>
        </div>

        {/* Pannello suggerisci con IA */}
        {suggerisciOpen && (
          <div className="bg-purple-900/20 border border-purple-800 rounded-xl p-4 -mt-2">
            <p className="text-sm text-purple-300 mb-2">Descrivi il progetto in poche parole — l'agente proporrà una struttura di task.</p>
            <div className="flex gap-2">
              <textarea value={suggerisciDesc}
                onChange={e => setSuggerisciDesc(e.target.value)}
                placeholder={`Es: "Sistema per gestione ferie e presenze, con portale web per i dipendenti e dashboard per HR..."`}
                rows={2}
                className="flex-1 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm placeholder-gray-500 focus:border-purple-500 focus:outline-none resize-none" />
              <button onClick={async () => {
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
                    // Crea i task con tempId
                    const nuoviTask = res.task_suggeriti.map((t, i) => ({
                      tempId: `new-${nextId + i}`,
                      nome: t.nome,
                      fase: t.fase || 'Sviluppo',
                      ore: t.ore || 40,
                      profilo: (t.profilo || 'Tecnico Senior').split(',')[0].trim(),
                      assegnato: '',
                      dipendenze: [],
                      _predecessori: t.predecessori || [],           // array di indici 1-based
                      _dipSuggerite: t.dipendenze_suggerite || '',   // fallback vecchio formato
                    }))
 
                    // Collega le dipendenze usando gli indici numerici
                    nuoviTask.forEach((task, idx) => {
                      // Nuovo formato: array di indici numerici (1-based)
                      if (task._predecessori && task._predecessori.length > 0) {
                        for (const predIdx of task._predecessori) {
                          // predIdx è 1-based, l'array è 0-based
                          const pred = nuoviTask[predIdx - 1]
                          if (pred && pred.tempId !== task.tempId) {
                            if (!task.dipendenze.find(d => d.taskId === pred.tempId)) {
                              task.dipendenze.push({ taskId: pred.tempId, tipo: 'FS' })
                            }
                          }
                        }
                      }
                      // Fallback: vecchio formato testuale (per retrocompatibilità)
                      else if (task._dipSuggerite) {
                        const descDip = task._dipSuggerite.toLowerCase()
                        nuoviTask.forEach(pred => {
                          if (pred.tempId === task.tempId) return
                          const nomeLower = pred.nome.toLowerCase()
                          if (descDip.includes(nomeLower)) {
                            if (!task.dipendenze.find(d => d.taskId === pred.tempId)) {
                              task.dipendenze.push({ taskId: pred.tempId, tipo: 'FS' })
                            }
                          }
                        })
                      }
                      delete task._predecessori
                      delete task._dipSuggerite
                    })
 
                    setPlanTasks(nuoviTask)
                    setNextId(n => n + nuoviTask.length)
                    setSuggerisciOpen(false)
                    setSuggerisciDesc('')
                  } else if (res.parse_error) {
                    alert('L\'agente ha risposto ma non sono riuscito a interpretare la risposta. Riprova.')
                  }
                } catch (err) {
                  alert('Errore: ' + err.message)
                } finally {
                  setSuggerisciLoading(false)
                }
              }}
                disabled={suggerisciLoading || !suggerisciDesc.trim()}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-600 rounded-lg text-sm font-medium self-end">
                Genera
              </button>
            </div>
            {suggerisciDesc && (
              <p className="text-xs text-gray-500 mt-2">⚠️ I task attuali verranno sostituiti con quelli suggeriti. Salva la bozza prima se vuoi conservarli.</p>
            )}
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-800 text-gray-400">
              <tr>
                <th className="text-left px-3 py-2 w-8">#</th>
                <th className="text-left px-3 py-2 min-w-[200px]">Nome task</th>
                <th className="text-left px-3 py-2 w-32">Fase</th>
                <th className="text-right px-3 py-2 w-20">Ore</th>
                <th className="text-left px-3 py-2 w-44">Profilo</th>
                <th className="text-left px-3 py-2 w-44">Assegnato a</th>
                <th className="text-left px-3 py-2 min-w-[220px]">Dipendenze</th>
                <th className="text-center px-3 py-2 w-12"></th>
              </tr>
            </thead>
            <tbody>
              {planTasks.map((task, idx) => (
                <tr key={task.tempId} className="border-t border-gray-800 hover:bg-gray-800/30">
                  {/* # */}
                  <td className="px-3 py-2 text-gray-500 text-xs">{idx + 1}</td>

                  {/* Nome */}
                  <td className="px-3 py-2">
                    <input type="text" value={task.nome}
                      onChange={e => updateTask(task.tempId, 'nome', e.target.value)}
                      placeholder="Nome del task..."
                      className="w-full bg-transparent border-b border-gray-700 focus:border-blue-500 outline-none py-1 text-sm placeholder-gray-600" />
                  </td>

                  {/* Fase */}
                  <td className="px-3 py-2">
                    <select value={task.fase} onChange={e => updateTask(task.tempId, 'fase', e.target.value)}
                      className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs w-full">
                      <option>Analisi</option>
                      <option>Design</option>
                      <option>Sviluppo</option>
                      <option>Testing</option>
                      <option>Deploy</option>
                      <option>Gestione</option>
                      <option>Vendita</option>
                      <option>Amministrazione</option>
                    </select>
                  </td>

                  {/* Ore */}
                  <td className="px-3 py-2">
                    <input type="number" min="1" value={task.ore}
                      onChange={e => updateTask(task.tempId, 'ore', parseInt(e.target.value) || 0)}
                      className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-right" />
                  </td>

                  {/* Profilo */}
                  <td className="px-3 py-2">
                    <select value={task.profilo} onChange={e => updateTask(task.tempId, 'profilo', e.target.value)}
                      className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs w-full">
                      {PROFILI.map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </td>

                  {/* Assegnato a */}
                  <td className="px-3 py-2">
                    {(() => {
                      const candidati = getCandidati(task.profilo, task.tempId)
                      const currentCand = candidati.find(c => c.nome === task.assegnato)
                      const selectColor = currentCand && currentCand.saturazioneDinamica > 100
                        ? 'border-red-600 text-red-300' : 'border-gray-700'
                      return (
                        <select value={task.assegnato} onChange={e => updateTask(task.tempId, 'assegnato', e.target.value)}
                          className={`bg-gray-800 border rounded px-2 py-1 text-xs w-full ${selectColor}`}>
                          <option value="">— Seleziona —</option>
                          {candidati.map(d => (
                            <option key={d.id} value={d.nome}
                              style={{ color: d.saturazioneDinamica > 100 ? '#f87171' : d.saturazioneDinamica > 85 ? '#fbbf24' : '#86efac' }}>
                              {d.nome} ({d.saturazioneDinamica}%{d.orePianificate > 0 ? ` · +${d.orePianificate}h plan.` : ''})
                            </option>
                          ))}
                        </select>
                      )
                    })()}
                  </td>

                  {/* Dipendenze */}
                  <td className="px-3 py-2">
                    <div className="space-y-1">
                      {task.dipendenze.map(dep => {
                        const predTask = planTasks.find(t => t.tempId === dep.taskId)
                        return (
                          <div key={dep.taskId} className="flex items-center gap-1 text-xs bg-gray-800 rounded px-2 py-0.5">
                            <span className="text-gray-300 truncate max-w-[80px]">
                              {predTask?.nome || `#${planTasks.findIndex(t => t.tempId === dep.taskId) + 1}`}
                            </span>
                            <select value={dep.tipo} onChange={e => changeDipTipo(task.tempId, dep.taskId, e.target.value)}
                              className="bg-gray-700 rounded px-1 py-0.5 text-[10px] text-blue-300 border-none">
                              {DEP_TYPES.map(dt => <option key={dt} value={dt}>{dt}</option>)}
                            </select>
                            <button onClick={() => removeDipendenza(task.tempId, dep.taskId)}
                              className="text-gray-500 hover:text-red-400 ml-1">✕</button>
                          </div>
                        )
                      })}
                      {/* Aggiungi dipendenza */}
                      {planTasks.filter(t => t.tempId !== task.tempId && !task.dipendenze.some(d => d.taskId === t.tempId)).length > 0 && (
                        <select value="" onChange={e => { if (e.target.value) addDipendenza(task.tempId, e.target.value); e.target.value = '' }}
                          className="bg-gray-800 border border-dashed border-gray-600 rounded px-2 py-0.5 text-[10px] text-gray-500 w-full">
                          <option value="">+ dipendenza...</option>
                          {planTasks
                            .filter(t => t.tempId !== task.tempId && !task.dipendenze.some(d => d.taskId === t.tempId))
                            .map((t, i) => (
                              <option key={t.tempId} value={t.tempId}>
                                #{planTasks.indexOf(t) + 1} {t.nome || '(senza nome)'}
                              </option>
                            ))}
                        </select>
                      )}
                    </div>
                  </td>

                  {/* Azioni riga */}
                  <td className="px-3 py-2 text-center">
                    <div className="flex items-center gap-1 justify-center">
                      <button onClick={() => moveTask(task.tempId, -1)}
                        disabled={idx === 0}
                        className="text-gray-500 hover:text-white disabled:text-gray-700 text-xs" title="Sposta su">▲</button>
                      <button onClick={() => moveTask(task.tempId, 1)}
                        disabled={idx === planTasks.length - 1}
                        className="text-gray-500 hover:text-white disabled:text-gray-700 text-xs" title="Sposta giù">▼</button>
                      <button onClick={() => insertTaskAt(idx + 1)}
                        className="text-gray-500 hover:text-blue-400 text-xs" title="Inserisci dopo">➕</button>
                      {planTasks.length > 1 && (
                        <button onClick={() => removeTask(task.tempId)}
                          className="text-gray-500 hover:text-red-400 text-sm" title="Elimina">🗑️</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Legenda dipendenze ────────────────────────────────────── */}
      <div className="flex gap-6 text-xs text-gray-500">
        <span><strong className="text-gray-400">FS</strong> Fine → Inizio (B inizia dopo che A finisce)</span>
        <span><strong className="text-gray-400">SS</strong> Inizio → Inizio (B inizia quando inizia A)</span>
        <span><strong className="text-gray-400">FF</strong> Fine → Fine (B finisce quando finisce A)</span>
      </div>

      {/* ── Riepilogo saturazione risorse ────────────────────────── */}
      {Object.keys(orePianificatePerPersona).length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <h3 className="font-semibold text-sm mb-3">👥 Impatto sulle risorse con questo progetto</h3>
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(orePianificatePerPersona).map(([nome, orePlan]) => {
              const dip = dipendenti.find(d => d.nome === nome)
              if (!dip) return null
              const durataSettimane = Math.max(1, Math.round(
                (new Date(progetto.data_fine).getTime() - new Date(progetto.data_inizio).getTime()) / (7 * 86400000)
              ))
              const caricoExtraSett = orePlan / durataSettimane
              const satNuova = Math.round(dip.saturazione_pct + (caricoExtraSett / (dip.ore_sett || 40)) * 100)
              const isOver = satNuova > 100
              const isWarning = satNuova > 85 && satNuova <= 100
              return (
                <div key={nome} className={`p-3 rounded-lg border text-sm ${
                  isOver ? 'border-red-700 bg-red-900/20' : isWarning ? 'border-yellow-700 bg-yellow-900/20' : 'border-gray-700 bg-gray-800/50'
                }`}>
                  <div className="flex justify-between items-center">
                    <span className="font-medium">{nome}</span>
                    <span className={`text-xs font-bold ${isOver ? 'text-red-400' : isWarning ? 'text-yellow-400' : 'text-green-400'}`}>
                      {dip.saturazione_pct}% → {satNuova}%
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    {dip.profilo} · +{orePlan}h pianificate · {dip.n_task_attivi} task attuali
                    {isOver && ' · ⚠️ SOVRACCARICO'}
                  </p>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── GANTT generato ───────────────────────────────────────── */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
        <div className="flex justify-between items-center mb-3">
          <h3 className="font-semibold">📅 GANTT generato</h3>
          <div className="flex gap-2">
            <button onClick={salva}
              className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-xs">
              💾 Salva bozza
            </button>
            {salvataggioMsg && <span className="text-xs text-green-400 py-1.5">{salvataggioMsg}</span>}
            <button onClick={() => setShowGantt(!showGantt)}
              className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-xs">
              {showGantt ? 'Nascondi' : 'Mostra'} GANTT
            </button>
            {!isBando && (
              <button onClick={confermaProgetto} disabled={confermato}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium ${confermato ? 'bg-green-800 text-green-300' : 'bg-green-600 hover:bg-green-500'}`}>
                {confermato ? '✅ Progetto avviato!' : '✅ Conferma e avvia progetto'}
              </button>
            )}
            {isBando && (
              <button onClick={salva}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-500">
                💾 Salva pianificazione bando
              </button>
            )}
          </div>
        </div>

        {/* Riepilogo date calcolate */}
        {ganttData.length > 0 && (
          <div className="mb-3 text-xs text-gray-400">
            {ganttData.length} task pianificati ·
            dal {formatDateShort(ganttData.reduce((min, t) => t.start < min ? t.start : min, ganttData[0].start))} al {formatDateShort(ganttData.reduce((max, t) => t.end > max ? t.end : max, ganttData[0].end))}
          </div>
        )}

        {(showGantt || ganttData.length > 0) && (
          <GanttChart tasks={ganttData} compact />
        )}

        {ganttData.length === 0 && (
          <p className="text-gray-500 text-sm text-center py-4">Compila almeno un task con nome e ore per generare il GANTT.</p>
        )}
      </div>

      {/* ── IA: verifica ─────────────────────────────────────────── */}
      <div className="space-y-3">
        <div className="flex justify-end">
          <button onClick={async () => {
            const taskValidi = planTasks.filter(t => t.nome && t.ore > 0)
            if (taskValidi.length === 0) {
              alert('Compila almeno un task con nome e ore.')
              return
            }
            setVerificaLoading(true)
            setVerificaIA(null)
            try {
              const taskPerIA = taskValidi.map((t, idx) => {
                const g = ganttData.find(g => g.id === t.tempId)
                return {
                  nome: t.nome,
                  fase: t.fase,
                  ore: t.ore,
                  profilo: t.profilo,
                  assegnato: t.assegnato || 'Non assegnato',
                  dipendenze: t.dipendenze.map(d => {
                    const pred = planTasks.find(p => p.tempId === d.taskId)
                    return { predecessore: pred?.nome || '?', tipo: d.tipo }
                  }),
                  data_inizio: g?.start || '',
                  data_fine: g?.end || '',
                }
              })
              const res = await verificaPianificazione({
                progetto_nome: progetto.nome,
                progetto_cliente: progetto.cliente,
                budget_ore: progetto.budget_ore,
                data_inizio: progetto.data_inizio,
                data_fine: progetto.data_fine,
                task_pianificati: taskPerIA,
              })
              setVerificaIA(res)
            } catch (err) {
              alert('Errore nella verifica: ' + err.message)
            } finally {
              setVerificaLoading(false)
            }
          }}
            disabled={verificaLoading}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-purple-800 rounded-lg text-sm font-medium">
            {verificaLoading ? '⏳ L\'agente sta analizzando...' : '🧠 Chiedi all\'IA di verificare la pianificazione'}
          </button>
        </div>

        {/* Risultati verifica IA */}
        {verificaIA && !verificaIA.parse_error && (
          <div className={`rounded-xl border p-5 ${
            verificaIA.esito === 'ok' ? 'bg-green-900/20 border-green-800' :
            verificaIA.esito === 'problemi' ? 'bg-red-900/20 border-red-800' :
            'bg-yellow-900/20 border-yellow-800'
          }`}>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-lg">{verificaIA.esito === 'ok' ? '✅' : verificaIA.esito === 'problemi' ? '🔴' : '⚠️'}</span>
              <h4 className="font-semibold">{verificaIA.riepilogo}</h4>
            </div>

            {verificaIA.segnalazioni && verificaIA.segnalazioni.length > 0 && (
              <div className="space-y-2 mb-3">
                {verificaIA.segnalazioni.map((s, i) => (
                  <div key={i} className={`p-3 rounded-lg border text-sm ${
                    s.gravita === 'alta' ? 'bg-red-900/30 border-red-700' :
                    s.gravita === 'media' ? 'bg-yellow-900/30 border-yellow-700' :
                    'bg-gray-800 border-gray-700'
                  }`}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs font-bold uppercase px-2 py-0.5 rounded ${
                        s.gravita === 'alta' ? 'bg-red-700 text-white' :
                        s.gravita === 'media' ? 'bg-yellow-700 text-white' :
                        'bg-gray-600 text-gray-200'
                      }`}>{s.gravita}</span>
                      <span className="text-xs text-gray-400">{s.tipo?.replace(/_/g, ' ')}</span>
                      {s.task_coinvolto && <span className="text-xs text-gray-300 font-medium">· {s.task_coinvolto}</span>}
                    </div>
                    <p className="text-gray-200">{s.descrizione}</p>
                    {s.suggerimento && <p className="text-gray-400 text-xs mt-1">💡 {s.suggerimento}</p>}
                  </div>
                ))}
              </div>
            )}

            {verificaIA.nota_positiva && (
              <p className="text-green-300 text-sm">👍 {verificaIA.nota_positiva}</p>
            )}
          </div>
        )}

        {verificaIA && verificaIA.parse_error && (
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-4 text-sm text-gray-300">
            <p className="font-medium mb-2">Risposta dell'agente:</p>
            <p className="whitespace-pre-wrap">{verificaIA.raw_response}</p>
          </div>
        )}
      </div>
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════
//  PAGINA PIPELINE
// ═════════════════════════════════════════════════════════════════════

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
 
          {/* Se è attiva la pianificazione di un bando, mostra il componente */}
          {pianificazioneAttiva && pianificazioneAttiva._fromBando && (
            <>
              <button onClick={() => setPianificazioneAttiva(null)}
                className="text-sm text-gray-400 hover:text-white mb-2">
                ← Torna ai bandi
              </button>
              <PianificazioneProgetto progetto={pianificazioneAttiva} dipendenti={dipendenti} isBando={true} />
            </>
          )}
 
          {/* Lista bandi (nascosta quando si pianifica) */}
          {(!pianificazioneAttiva || !pianificazioneAttiva._fromBando) && bandi.map(p => {
            const tasks = getTasksProgetto(p.id)
            const persone = getPersoneProgetto(p.id)
            const scadenza = SCADENZE_BANDI[p.id]
            const oreStimate = tasks.reduce((s, t) => s + t.ore_stimate, 0)
            const taskComp = tasks.filter(t => t.stato === 'Completato').length
            return (
              <div key={p.id} className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                <div className="flex justify-between items-start mb-4">
                  <div><h2 className="text-lg font-semibold">{p.nome}</h2><p className="text-sm text-gray-400">{p.cliente}</p></div>
                  <div className="flex items-center gap-3">
                    {scadenza && <CountdownBadge scadenza={scadenza} />}
                    <span className="text-xs text-gray-500">Scadenza: {scadenza ? formatDate(scadenza) : 'N/D'}</span>
                  </div>
                </div>
                <div className="grid grid-cols-4 gap-4 mb-4">
                  <div className="bg-gray-800 rounded-lg p-3"><p className="text-xs text-gray-400">Valore stimato</p><p className="text-lg font-bold">€{(p.valore_contratto/1000).toFixed(0)}k</p></div>
                  <div className="bg-gray-800 rounded-lg p-3"><p className="text-xs text-gray-400">Ore preparazione</p><p className="text-lg font-bold">{oreStimate}h</p></div>
                  <div className="bg-gray-800 rounded-lg p-3"><p className="text-xs text-gray-400">Task</p><p className="text-lg font-bold">{taskComp}/{tasks.length}</p></div>
                  <div className="bg-gray-800 rounded-lg p-3"><p className="text-xs text-gray-400">Persone</p><p className="text-lg font-bold">{persone.length}</p></div>
                </div>
                <div className="mb-4"><p className="text-xs text-gray-400 uppercase tracking-wider mb-2">Team</p>
                  <div className="flex flex-wrap gap-2">
                    {persone.map(per => (
                      <span key={per.id} className={`text-xs px-3 py-1.5 rounded-lg border ${per.saturazione > 100 ? 'border-red-700 bg-red-900/20 text-red-300' : 'border-gray-700 bg-gray-800 text-gray-300'}`}>
                        {per.nome} · {per.profilo} · {per.ore}h {per.saturazione > 100 && <span className="text-red-400">⚠️ {per.saturazione}%</span>}
                      </span>
                    ))}
                  </div>
                </div>
 
                {/* Bottoni azione */}
                <div className="flex gap-3 mb-4">
                  <button onClick={() => setPianificazioneAttiva({ ...p, _fromBando: true })}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors">
                    📅 Pianifica GANTT bando
                  </button>
                </div>
 
                <details>
                  <summary className="cursor-pointer text-sm text-gray-400 hover:text-white">📋 Task preparazione ({tasks.length})</summary>
                  <div className="mt-2 space-y-1">
                    {tasks.map(t => (
                      <div key={t.id} className="flex items-center justify-between py-2 px-3 bg-gray-800/50 rounded-lg text-sm">
                        <div className="flex-1"><span className="font-medium">{t.nome}</span><span className="text-xs text-gray-500 ml-2">{t.dipendente_nome}</span></div>
                        <div className="flex items-center gap-3"><span className="text-xs text-gray-400">{t.ore_stimate}h</span>
                          <span className={`text-xs px-2 py-0.5 rounded ${t.stato === 'Completato' ? 'bg-green-900/30 text-green-300' : t.stato === 'In corso' ? 'bg-blue-900/30 text-blue-300' : 'bg-gray-700/30 text-gray-300'}`}>{t.stato}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </details>
              </div>
            )
          })}
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
                      <p className="text-sm text-gray-400">{p.cliente} · €{(p.valore_contratto/1000).toFixed(0)}k · {p.budget_ore}h budget</p>
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
              <button onClick={() => setPianificazioneAttiva(null)}
                className="text-sm text-gray-400 hover:text-white mb-2">
                ← Torna alla lista
              </button>
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
            const durata = Math.round((new Date(p.data_fine).getTime() - new Date(p.data_inizio).getTime()) / (86400000 * 30))
            const isSospeso = p.stato === 'Sospeso'
            return (
              <div key={p.id} className={`bg-gray-900 rounded-xl border p-6 ${isSospeso ? 'border-amber-800/50' : 'border-gray-800'}`}>
                <div className="flex items-center gap-3 mb-4">
                  <h2 className="text-lg font-semibold">{p.nome}</h2>
                  <span className={`text-xs px-2 py-1 rounded-full font-medium ${isSospeso ? 'bg-amber-900/30 text-amber-300' : 'bg-gray-700 text-gray-300'}`}>
                    {isSospeso ? '⏸️ Sospeso' : '✅ Completato'}
                  </span>
                  <span className="text-sm text-gray-400">{p.cliente}</span>
                </div>
                <div className="grid grid-cols-5 gap-4 mb-4">
                  <div className="bg-gray-800 rounded-lg p-3"><p className="text-xs text-gray-400">Durata</p><p className="text-lg font-bold">{durata} mesi</p></div>
                  <div className="bg-gray-800 rounded-lg p-3"><p className="text-xs text-gray-400">Valore</p><p className="text-lg font-bold">€{(p.valore_contratto/1000).toFixed(0)}k</p></div>
                  <div className="bg-gray-800 rounded-lg p-3"><p className="text-xs text-gray-400">Budget</p><p className="text-lg font-bold">{p.budget_ore}h</p></div>
                  <div className="bg-gray-800 rounded-lg p-3"><p className="text-xs text-gray-400">Consumate</p><p className={`text-lg font-bold ${oreConsumate > p.budget_ore ? 'text-red-400' : 'text-green-400'}`}>{oreConsumate}h</p></div>
                  <div className="bg-gray-800 rounded-lg p-3"><p className="text-xs text-gray-400">Task</p><p className="text-lg font-bold">{taskComp}/{tasks.length}</p></div>
                </div>
                <ProgressBar value={oreConsumate} max={p.budget_ore} label="Ore vs budget" color={oreConsumate > p.budget_ore ? 'bg-red-500' : 'bg-blue-500'} />
                <div className="mt-4 mb-3"><p className="text-xs text-gray-400 uppercase tracking-wider mb-2">Team</p>
                  <div className="flex flex-wrap gap-2">
                    {persone.map(per => <span key={per.id} className="text-xs px-3 py-1.5 rounded-lg border border-gray-700 bg-gray-800 text-gray-300">{per.nome} · {per.profilo} · {per.ore}h</span>)}
                  </div>
                </div>
                {isSospeso && <div className="p-3 bg-amber-900/20 border border-amber-800/40 rounded-lg text-sm text-amber-200 mt-3">⏸️ <strong>Motivo:</strong> {p.fase_corrente || 'Non specificato'}</div>}
                <details className="mt-3"><summary className="cursor-pointer text-sm text-gray-400 hover:text-white">📝 Note e lezioni apprese</summary>
                  <div className="mt-2 p-4 bg-gray-800/50 rounded-lg border border-dashed border-gray-600"><p className="text-sm text-gray-500 italic">Nessuna nota registrata.</p></div>
                </details>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}                   