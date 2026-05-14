import React, { useState, useEffect, useMemo } from 'react'
import { fetchDipendenti, fetchProgetti, fetchTasks, fetchSegnalazioni, interpretaScenario, simulaScenario, confermaScenario, applicaModifiche, salvaBozza, caricaBozza } from '../api'
import { GanttChart, StatusLegend } from './Gantt'

// ── Costanti ────────────────────────────────────────────────────────
const GRAVITA_STYLE = {
  alta:  'bg-red-900/30 border-red-700 text-red-300',
  media: 'bg-yellow-900/30 border-yellow-700 text-yellow-300',
  bassa: 'bg-gray-800/60 border-gray-700 text-gray-300',
}
const GRAVITA_BADGE = {
  alta:  'bg-red-600 text-white',
  media: 'bg-yellow-600 text-white',
  bassa: 'bg-gray-600 text-white',
}
const TIPO_ICON = {
  scadenza_bucata: '🚨', task_slittato: '📅', sovraccarico_persona: '👤',
}
const PROFILI = ['AD', 'Manager IT', 'Senior IT Consultant', 'IT Consultant', 'Senior Consultant', 'Consultant', 'PM', 'Manager HR', 'Responsabile amministrazione', 'Addetto amministrazione']
const FASI = ['Analisi', 'Design', 'Sviluppo', 'Testing', 'Deploy', 'Gestione', 'Vendita', 'Amministrazione']
const STATI_TASK = ['Da iniziare', 'In corso', 'Completato', 'Sospeso']


// ═════════════════════════════════════════════════════════════════════
//  COMPONENTE: Sidebar contesto
// ═════════════════════════════════════════════════════════════════════

function SidebarContesto({ dipendenti, progetti, segnalazioni }) {
  const progettiAttivi = progetti.filter(p => p.stato === 'In esecuzione')

  return (
    <div className="space-y-4">
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">👥 Carico persone</h4>
        <div className="space-y-2">
          {dipendenti
            .sort((a, b) => b.saturazione_pct - a.saturazione_pct)
            .slice(0, 8)
            .map(d => (
              <div key={d.id} className="flex items-center justify-between text-sm">
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{d.nome}</p>
                  <p className="text-[10px] text-gray-500">{d.profilo} · {d.n_task_attivi ?? '?'} task</p>
                </div>
                <div className="flex items-center gap-2 ml-2">
                  <div className="w-16 bg-gray-700 rounded-full h-1.5">
                    <div className={`h-1.5 rounded-full ${
                      d.saturazione_pct > 100 ? 'bg-red-500' : d.saturazione_pct > 85 ? 'bg-yellow-500' : 'bg-green-500'
                    }`} style={{ width: `${Math.min(100, d.saturazione_pct)}%` }} />
                  </div>
                  <span className={`text-xs font-mono w-10 text-right ${
                    d.saturazione_pct > 100 ? 'text-red-400' : d.saturazione_pct > 85 ? 'text-yellow-400' : 'text-gray-400'
                  }`}>{d.saturazione_pct}%</span>
                </div>
              </div>
            ))}
        </div>
      </div>

      {segnalazioni.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
            📥 Segnalazioni ({segnalazioni.length})
          </h4>
          <div className="space-y-2 max-h-[200px] overflow-y-auto">
            {segnalazioni.slice(0, 5).map(s => (
              <div key={s.id} className="p-2 bg-gray-800/50 rounded-lg text-xs">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium ${GRAVITA_BADGE[s.priorita]}`}>{s.priorita}</span>
                  <span className="text-gray-400">{s.dipendente || ''}</span>
                </div>
                <p className="text-gray-300 line-clamp-2">{s.dettaglio}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
          📁 Progetti attivi ({progettiAttivi.length})
        </h4>
        <div className="space-y-1.5">
          {progettiAttivi.map(p => (
            <div key={p.id} className="flex items-center justify-between text-xs">
              <span className="text-gray-300 truncate flex-1">{p.nome}</span>
              <span className="text-gray-500 ml-2">{p.cliente}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════
//  COMPONENTE: Visualizzazione GANTT prima/dopo + conseguenze
// ═════════════════════════════════════════════════════════════════════

function RisultatoSimulazione({ risultato }) {
  const [progettoAperto, setProgettoAperto] = useState(null)
  const [showSaturazioni, setShowSaturazioni] = useState(false)

  if (!risultato) return null

  const { gantt_prima, gantt_dopo, conseguenze, saturazioni, n_task_modificati, progetti_impattati, scadenze_bucate } = risultato
  const progettiIds = Object.keys(gantt_dopo || {})
  const progettoVisualizzato = progettoAperto || progettiIds[0]

  return (
    <div className="space-y-4">
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <span className="text-lg">📊</span>
            <h3 className="font-semibold">Anteprima impatto a cascata</h3>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-gray-400">{n_task_modificati} task impattati</span>
            <span className="text-gray-400">{progetti_impattati?.length || 0} progetti</span>
          </div>
        </div>

        {scadenze_bucate && scadenze_bucate.length > 0 && (
          <div className="mb-4 space-y-2">
            {scadenze_bucate.map((sb, i) => (
              <div key={i} className="p-3 bg-red-900/30 border border-red-700 rounded-lg flex items-center gap-3">
                <span className="text-xl">🚨</span>
                <div>
                  <p className="text-sm font-medium text-red-200">{sb.progetto} ({sb.cliente}): sfora di {sb.giorni_sforo} giorni</p>
                  <p className="text-xs text-red-300/70">Scadenza: {new Date(sb.scadenza).toLocaleDateString('it-IT')} → Fine: {new Date(sb.ultimo_task_fine).toLocaleDateString('it-IT')}</p>
                </div>
              </div>
            ))}
          </div>
        )}

        {progettiIds.length > 1 && (
          <div className="flex gap-2 mb-4 flex-wrap">
            {progettiIds.map(pid => {
              const info = gantt_dopo[pid]
              const haScadenza = scadenze_bucate?.some(sb => sb.progetto_id === pid)
              return (
                <button key={pid} onClick={() => setProgettoAperto(pid)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    progettoVisualizzato === pid ? 'bg-blue-600 text-white'
                      : haScadenza ? 'bg-red-900/30 text-red-300 border border-red-700'
                      : 'bg-gray-800 text-gray-400 hover:text-white'
                  }`}>
                  {haScadenza && '⚠️ '}{info?.progetto || pid}
                </button>
              )
            })}
          </div>
        )}

        {progettoVisualizzato && gantt_prima[progettoVisualizzato] && (
          <div className="space-y-3">
            <div className="flex justify-end"><StatusLegend /></div>
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 bg-gray-800 px-2 py-1 rounded">Prima</span>
              <div className="mt-2"><GanttChart tasks={gantt_prima[progettoVisualizzato]?.tasks || []} compact /></div>
            </div>
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-amber-300 bg-amber-900/30 px-2 py-1 rounded">Dopo</span>
              <div className="mt-2"><GanttChart tasks={gantt_dopo[progettoVisualizzato]?.tasks || []} compact /></div>
            </div>
          </div>
        )}
      </div>

      {conseguenze && conseguenze.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h3 className="font-semibold mb-3">📋 Conseguenze ({conseguenze.length})</h3>
          <div className="space-y-2 max-h-[300px] overflow-y-auto">
            {conseguenze.map((c, i) => (
              <div key={i} className={`p-3 rounded-lg border text-sm ${GRAVITA_STYLE[c.gravita]}`}>
                <div className="flex items-center gap-2 mb-1">
                  <span>{TIPO_ICON[c.tipo] || '📌'}</span>
                  <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${GRAVITA_BADGE[c.gravita]}`}>{c.gravita}</span>
                </div>
                <p className="text-gray-200 leading-relaxed">{c.testo}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {saturazioni && Object.keys(saturazioni).length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <button onClick={() => setShowSaturazioni(!showSaturazioni)} className="w-full flex items-center justify-between">
            <h3 className="font-semibold">👥 Saturazioni ({Object.keys(saturazioni).length})</h3>
            <span className="text-gray-400 text-sm">{showSaturazioni ? '▼' : '▶'}</span>
          </button>
          {showSaturazioni && (
            <div className="mt-4 space-y-4">
              {Object.entries(saturazioni).map(([did, data]) => (
                <div key={did} className="bg-gray-800/50 rounded-lg p-4">
                  <div className="flex items-center gap-3 mb-3">
                    <span className="font-medium">{data.nome}</span>
                    <span className="text-xs text-gray-400">{data.profilo} · {data.ore_sett}h/sett</span>
                  </div>
                  <div className="grid grid-cols-6 gap-1 text-[10px]">
                    {data.settimane?.slice(0, 6).map((s, i) => {
                      const lun = new Date(s.lunedi)
                      const over = s.carico_dopo > data.ore_sett
                      const pegg = s.carico_dopo > s.carico_prima
                      return (
                        <div key={i} className={`p-2 rounded text-center ${
                          over && pegg ? 'bg-red-900/40 border border-red-700' : over ? 'bg-yellow-900/30 border border-yellow-800' : 'bg-gray-700/30'
                        }`}>
                          <p className="text-gray-500 mb-1">{lun.toLocaleDateString('it-IT', { day: 'numeric', month: 'short' })}</p>
                          <p className="text-gray-400">{s.carico_prima}h</p>
                          <p className="text-gray-600">↓</p>
                          <p className={`font-bold ${over ? 'text-red-400' : 'text-green-400'}`}>{s.carico_dopo}h</p>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════
//  COMPONENTE: Pannello suggerimenti bilanciamento
// ═════════════════════════════════════════════════════════════════════

function BilanciamentoPanel() {
  const [dati, setDati] = useState(null)
  const [loading, setLoading] = useState(false)
  const [aperto, setAperto] = useState(false)

  async function carica() {
    if (dati) { setAperto(!aperto); return }
    setLoading(true)
    try {
      const res = await fetch('/api/risorse/suggerisci-bilanciamento')
      const data = await res.json()
      setDati(data)
      setAperto(true)
    } catch (err) {
      alert('Errore nel caricamento: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800">
      <button onClick={carica} className="w-full p-4 flex items-center justify-between hover:bg-gray-800/50 rounded-xl transition-colors">
        <div className="flex items-center gap-2">
          <span className="text-lg">⚖️</span>
          <span className="font-semibold text-sm">Suggerimenti bilanciamento carichi</span>
          {dati && <span className="text-xs text-gray-500 ml-2">{dati.n_sovraccarichi} sovraccarichi · {dati.proposte.length} proposte</span>}
        </div>
        <span className="text-gray-400 text-sm">{loading ? '⏳' : aperto ? '▼' : '▶'}</span>
      </button>

      {aperto && dati && (
        <div className="px-4 pb-4 space-y-3">
          {dati.proposte.length === 0 && (
            <p className="text-sm text-green-400">✅ Nessun sovraccarico rilevato — i carichi sono bilanciati.</p>
          )}

          {dati.proposte.map((p, i) => (
            <div key={i} className={`rounded-lg border p-4 ${
              p.priorita === 'alta' ? 'bg-red-900/20 border-red-800' : 'bg-yellow-900/15 border-yellow-800/50'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${
                  p.priorita === 'alta' ? 'bg-red-600 text-white' : 'bg-yellow-600 text-white'
                }`}>{p.priorita}</span>
                <span className="text-sm font-medium">{p.task_nome}</span>
                <span className="text-xs text-gray-500">({p.progetto})</span>
              </div>

              <div className="flex items-center gap-3 text-sm mb-2">
                <div className="flex items-center gap-1">
                  <span className="text-red-400 font-medium">{p.da_persona}</span>
                  <span className="text-gray-500">({p.da_saturazione}%</span>
                  <span className="text-gray-600">→</span>
                  <span className="text-green-400">{p.da_saturazione_dopo}%)</span>
                </div>
                <span className="text-gray-600">➜</span>
                <div className="flex items-center gap-1">
                  <span className="text-blue-400 font-medium">{p.candidato_migliore.candidato_nome}</span>
                  <span className="text-gray-500">({p.candidato_migliore.candidato_saturazione_attuale}%</span>
                  <span className="text-gray-600">→</span>
                  <span className={`${p.candidato_migliore.candidato_saturazione_dopo > 100 ? 'text-yellow-400' : 'text-green-400'}`}>
                    {p.candidato_migliore.candidato_saturazione_dopo}%)
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">
                  {p.ore_sett_task}h/sett · profilo: {p.profilo_richiesto}
                  {p.altri_candidati.length > 0 && ` · ${p.altri_candidati.length} alternative`}
                </span>
              </div>

              {p.altri_candidati.length > 0 && (
                <div className="mt-2 flex gap-2">
                  {p.altri_candidati.map((alt, j) => (
                    <span key={j} className="text-[10px] bg-gray-800 rounded px-2 py-1 text-gray-400">
                      anche: {alt.candidato_nome} ({alt.candidato_saturazione_attuale}% → {alt.candidato_saturazione_dopo}%)
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════
//  COMPONENTE: Editor GANTT unificato (manuale + IA integrata)
// ═════════════════════════════════════════════════════════════════════

function EditorGanttUnificato({ progetti, dipendenti, allTasks, segnalazioni, onTasksChanged }) {
  const [progettoSelezionato, setProgettoSelezionato] = useState('')
  const [planTasks, setPlanTasks] = useState([])
  const [nextId, setNextId] = useState(1)
  const [salvataggioMsg, setSalvataggioMsg] = useState('')

  // IA
  const [iaOpen, setIaOpen] = useState(false)
  const [iaTesto, setIaTesto] = useState('')
  const [iaLoading, setIaLoading] = useState(false)
  const [iaRisultato, setIaRisultato] = useState(null)
  const [iaModifiche, setIaModifiche] = useState([])

  // Simulazione / conferma
  const [simulazioneResult, setSimulazioneResult] = useState(null)
  const [simulaLoading, setSimulaLoading] = useState(false)
  const [confermato, setConfermato] = useState(false)
  const [confermaLoading, setConfermaLoading] = useState(false)
  const [storico, setStorico] = useState([])

  const progettiAttivi = progetti.filter(p => p.stato === 'In esecuzione' && p.id !== 'P010')
  const progetto = progettiAttivi.find(p => p.id === progettoSelezionato)

  // ── Carica task ──
  // ⚠️ DEPRECATO Step 2.0 (13 mag 2026): caricaBozza disabilitata, le bozze
  // sono ora progetti con stato='Bozza'. AnalisiInterventi verrà eliminata a Step 2.7.
  // Fino ad allora, carichiamo sempre i task reali (skip della bozza).
  useEffect(() => {
    if (!progettoSelezionato) { setPlanTasks([]); return }
    caricaTaskReali()
    setSimulazioneResult(null); setConfermato(false); setIaRisultato(null); setIaModifiche([])
  }, [progettoSelezionato])

  function caricaTaskReali() {
    const tasksProg = allTasks
      .filter(t => t.progetto_id === progettoSelezionato && t.stato !== 'Eliminato')
      .map(t => ({
        tempId: `existing-${t.id}`, realId: t.id, nome: t.nome,
        fase: t.fase || 'Sviluppo', ore: t.ore_stimate,
        profilo: t.profilo_richiesto || 'Tecnico Senior',
        assegnato: t.dipendente_nome || '', stato: t.stato,
        data_inizio: t.data_inizio, data_fine: t.data_fine,
        dipendenze: t.predecessore ? [{ taskId: `existing-${t.predecessore}`, tipo: 'FS' }] : [],
        isExisting: true, iaSuggested: false,
      }))
    setPlanTasks(tasksProg); setNextId(1)
  }

  // ── Editing ──
  function addTask() {
    setPlanTasks(prev => [...prev, {
      tempId: `new-${nextId}`, nome: '', fase: 'Sviluppo', ore: 40,
      profilo: 'Tecnico Senior', assegnato: '', stato: 'Da iniziare',
      data_inizio: '', data_fine: '', dipendenze: [], isExisting: false, iaSuggested: false,
    }]); setNextId(n => n + 1)
  }
  function insertTaskAt(index) {
    const t = { tempId: `new-${nextId}`, nome: '', fase: 'Sviluppo', ore: 40, profilo: 'Tecnico Senior', assegnato: '', stato: 'Da iniziare', data_inizio: '', data_fine: '', dipendenze: [], isExisting: false, iaSuggested: false }
    setPlanTasks(prev => { const c = [...prev]; c.splice(index, 0, t); return c }); setNextId(n => n + 1)
  }
  function moveTask(tempId, dir) {
    setPlanTasks(prev => { const idx = prev.findIndex(t => t.tempId === tempId); if (idx < 0) return prev; const ni = idx + dir; if (ni < 0 || ni >= prev.length) return prev; const c = [...prev]; const [m] = c.splice(idx, 1); c.splice(ni, 0, m); return c })
  }
  function removeTask(tempId) {
    setPlanTasks(prev => prev.filter(t => t.tempId !== tempId).map(t => ({ ...t, dipendenze: t.dipendenze.filter(d => d.taskId !== tempId) })))
  }
  function updateTask(tempId, field, value) {
    setPlanTasks(prev => prev.map(t => t.tempId === tempId ? { ...t, [field]: value, iaSuggested: false } : t))
  }
  function getCandidati(profilo) {
    return dipendenti
      .filter(d => d.profilo === profilo || (d.competenze && d.competenze.includes(profilo)))
      .sort((a, b) => a.saturazione_pct - b.saturazione_pct)
  }

  // ── Salva bozza ──
  // ⚠️ DEPRECATO Step 2.0 (13 mag 2026): disabilitata fino a Step 2.7 (Cantiere).
  async function salva() {
    setSalvataggioMsg('⏳ Salva bozza in migrazione — disponibile in Cantiere a breve')
    setTimeout(() => setSalvataggioMsg(''), 4000)
  }

  // ── IA: interpreta e applica alla tabella ──
  async function handleIA() {
    if (!iaTesto.trim() || iaLoading) return
    setIaLoading(true); setIaRisultato(null)
    try {
      const result = await interpretaScenario(iaTesto, '')
      setIaRisultato(result)
      if (result.modifiche && result.modifiche.length > 0 && !result.domande) {
        applicaModificheIAallaTabella(result.modifiche)
      }
    } catch (err) { alert('Errore agente IA: ' + err.message) }
    finally { setIaLoading(false) }
  }

  function applicaModificheIAallaTabella(modifiche) {
    setPlanTasks(prev => {
      let updated = [...prev]
      for (const mod of modifiche) {
        if (mod.tipo === 'sposta_task' && mod.task_id) {
          const idx = updated.findIndex(t => t.realId === mod.task_id || t.tempId === `existing-${mod.task_id}`)
          if (idx >= 0) {
            const t = { ...updated[idx], iaSuggested: true }
            if (mod.nuova_fine) t.data_fine = mod.nuova_fine
            if (mod.nuovo_inizio) t.data_inizio = mod.nuovo_inizio
            if (mod.nuove_ore) t.ore = mod.nuove_ore
            updated[idx] = t
          }
        }
      }
      return updated
    })
    setIaModifiche(modifiche)
    setSalvataggioMsg('🧠 Suggerimenti IA applicati — ritocca e poi verifica l\'impatto')
    setTimeout(() => setSalvataggioMsg(''), 5000)
  }

  // ── Verifica impatto (simulazione GANTT prima/dopo) ──
  async function verificaImpatto() {
    if (!progettoSelezionato) return
    setSimulaLoading(true); setSimulazioneResult(null)
    try {
      const modifiche = []
      for (const t of planTasks) {
        if (t.isExisting && t.realId) {
          const orig = allTasks.find(ot => ot.id === t.realId)
          if (!orig) continue
          if ((t.data_fine && t.data_fine !== orig.data_fine) || (t.data_inizio && t.data_inizio !== orig.data_inizio) || t.ore !== orig.ore_stimate) {
            modifiche.push({
              tipo: 'sposta_task', task_id: t.realId,
              nuova_fine: t.data_fine !== orig.data_fine ? t.data_fine : '',
              nuovo_inizio: t.data_inizio !== orig.data_inizio ? t.data_inizio : '',
              nuove_ore: t.ore !== orig.ore_stimate ? t.ore : 0,
            })
          }
        }
      }
      for (const mod of iaModifiche) { if (!modifiche.find(m => m.task_id === mod.task_id)) modifiche.push(mod) }

      if (modifiche.length === 0) { alert('Nessuna modifica alle date/ore rilevata. Modifica un task e riprova.'); setSimulaLoading(false); return }

      const result = await simulaScenario(modifiche)
      setSimulazioneResult(result)
    } catch (err) { alert('Errore simulazione: ' + err.message) }
    finally { setSimulaLoading(false) }
  }

  // ── Applica tutto ──
  async function applicaTutto() {
    if (!progettoSelezionato) return
    if (!confirm('Confermi di applicare le modifiche al GANTT? Saranno permanenti.')) return
    setConfermaLoading(true)
    try {
      const modificheScenario = []; const modificheDirette = []; const nuoviTask = []

      for (const t of planTasks) {
        if (t.isExisting && t.realId) {
          const orig = allTasks.find(ot => ot.id === t.realId)
          if (!orig) continue
          if (t.ore !== orig.ore_stimate) modificheDirette.push({ task_id: t.realId, campo: 'ore_stimate', nuovo_valore: String(t.ore) })
          const dipMatch = dipendenti.find(d => d.nome === t.assegnato)
          if (dipMatch && dipMatch.id !== orig.dipendente_id) modificheDirette.push({ task_id: t.realId, campo: 'dipendente_id', nuovo_valore: dipMatch.id })
          if (t.stato !== orig.stato) modificheDirette.push({ task_id: t.realId, campo: 'stato', nuovo_valore: t.stato })
          if ((t.data_fine && t.data_fine !== orig.data_fine) || (t.data_inizio && t.data_inizio !== orig.data_inizio)) {
            modificheScenario.push({ tipo: 'sposta_task', task_id: t.realId, nuova_fine: t.data_fine !== orig.data_fine ? t.data_fine : '', nuovo_inizio: t.data_inizio !== orig.data_inizio ? t.data_inizio : '', nuove_ore: 0 })
          }
        } else if (!t.isExisting && t.nome && t.ore > 0) {
          const dipMatch = dipendenti.find(d => d.nome === t.assegnato)
          nuoviTask.push({ nome: t.nome, fase: t.fase, ore_stimate: t.ore, data_inizio: t.data_inizio || progetto.data_inizio, data_fine: t.data_fine || progetto.data_fine, profilo_richiesto: t.profilo, dipendente_id: dipMatch ? dipMatch.id : '', stato: t.stato || 'Da iniziare' })
        }
      }
      for (const mod of iaModifiche) { if (!modificheScenario.find(m => m.task_id === mod.task_id)) modificheScenario.push(mod) }

      if (modificheScenario.length > 0) { const res = await confermaScenario(modificheScenario); if (!res.successo) alert('Errore scenario: ' + JSON.stringify(res.errori)) }
      if (modificheDirette.length > 0 || nuoviTask.length > 0) { await applicaModifiche({ modifiche: modificheDirette, nuovi_task: nuoviTask, progetto_id: progettoSelezionato }) }

      setConfermato(true)
      setStorico(prev => [...prev, { timestamp: new Date().toLocaleString('it-IT'), progetto: progetto?.nome || '', n_modifiche: modificheScenario.length + modificheDirette.length + nuoviTask.length }])
      if (onTasksChanged) onTasksChanged()
    } catch (err) { alert('Errore: ' + err.message) }
    finally { setConfermaLoading(false) }
  }

  function handleReset() {
    setSimulazioneResult(null); setConfermato(false); setIaRisultato(null); setIaModifiche([]); setIaTesto(''); caricaTaskReali()
  }

  const totaleOre = planTasks.reduce((s, t) => s + (t.ore || 0), 0)
  const budgetOre = progetto?.budget_ore || 0
  const deltaOre = totaleOre - budgetOre
  const taskIA = planTasks.filter(t => t.iaSuggested).length

  // ═══ RENDER: Selezione progetto ═══
  if (!progettoSelezionato) {
    return (
      <div className="space-y-4">
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-lg">📁</span>
            <h3 className="font-semibold">Seleziona il progetto da modificare</h3>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {progettiAttivi.map(p => (
              <button key={p.id} onClick={() => setProgettoSelezionato(p.id)}
                className="text-left bg-gray-800 hover:bg-gray-700 rounded-lg p-4 transition-colors border border-gray-700 hover:border-blue-600">
                <p className="font-medium">{p.nome}</p>
                <p className="text-xs text-gray-400 mt-1">{p.cliente} · {p.budget_ore}h · {p.task_totali} task</p>
              </button>
            ))}
          </div>
        </div>
        {/* Suggerimenti bilanciamento */}
        <BilanciamentoPanel />
        {storico.length > 0 && (
          <div className="bg-gray-900/50 rounded-xl border border-gray-800 p-4">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">📜 Modifiche applicate in questa sessione</h4>
            <div className="space-y-1">
              {storico.map((s, i) => (
                <div key={i} className="flex items-center justify-between text-xs text-gray-400">
                  <span>{s.timestamp} — {s.progetto}</span>
                  <span>{s.n_modifiche} modifiche</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  // ═══ RENDER: Editor progetto ═══
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <div className="flex justify-between items-start mb-3">
          <div>
            <div className="flex items-center gap-3">
              <button onClick={() => { setProgettoSelezionato(''); handleReset() }} className="text-gray-400 hover:text-white text-sm">← Indietro</button>
              <h3 className="font-semibold text-lg">{progetto?.nome}</h3>
              <span className="text-xs text-gray-500">{progetto?.cliente}</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {salvataggioMsg && <span className="text-xs text-green-400">{salvataggioMsg}</span>}
            <button onClick={salva} title="Funzionalità in migrazione — disponibile in Cantiere a breve" className="px-3 py-1.5 bg-gray-800 text-gray-500 rounded-lg text-xs cursor-not-allowed">💾 Salva bozza (in migrazione)</button>
          </div>
        </div>
        <div className="grid grid-cols-4 gap-4 text-sm">
          <div className="bg-gray-800 rounded-lg p-3"><p className="text-xs text-gray-400">Budget ore</p><p className="text-lg font-bold">{budgetOre}h</p></div>
          <div className="bg-gray-800 rounded-lg p-3"><p className="text-xs text-gray-400">Ore pianificate</p><p className={`text-lg font-bold ${deltaOre > 0 ? 'text-red-400' : 'text-green-400'}`}>{totaleOre}h {deltaOre !== 0 && <span className="text-xs">({deltaOre > 0 ? '+' : ''}{deltaOre}h)</span>}</p></div>
          <div className="bg-gray-800 rounded-lg p-3"><p className="text-xs text-gray-400">Task</p><p className="text-lg font-bold">{planTasks.length}</p></div>
          <div className="bg-gray-800 rounded-lg p-3"><p className="text-xs text-gray-400">Suggeriti IA</p><p className="text-lg font-bold text-purple-400">{taskIA}</p></div>
        </div>
      </div>

      {/* IA inline */}
      <div className="bg-purple-900/10 rounded-xl border border-purple-800/40 p-4">
        <button onClick={() => setIaOpen(!iaOpen)} className="flex items-center gap-2 w-full text-left">
          <span>🧠</span>
          <span className="font-medium text-sm">Suggerisci con IA</span>
          <span className="text-xs text-gray-500 ml-2">Descrivi un cambiamento → l'IA modifica la tabella → tu ritocchi → applichi</span>
          <span className="ml-auto text-gray-400 text-sm">{iaOpen ? '▼' : '▶'}</span>
        </button>
        {iaOpen && (
          <div className="mt-3">
            <div className="flex gap-3">
              <textarea value={iaTesto} onChange={e => setIaTesto(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleIA() } }}
                placeholder="Es: 'Sparkasse ha anticipato la scadenza DORA di 20 giorni' oppure 'Servono 40 ore in più per il testing'..."
                rows={2} disabled={iaLoading}
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-sm placeholder-gray-500 focus:border-purple-500 focus:outline-none resize-none disabled:opacity-50" />
              <button onClick={handleIA} disabled={!iaTesto.trim() || iaLoading}
                className="self-end px-5 py-3 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg text-sm font-medium transition-colors whitespace-nowrap">
                {iaLoading ? '⏳ Interpreto...' : '→ Suggerisci'}
              </button>
            </div>
            {iaRisultato && (
              <div className="mt-3 bg-gray-800/50 rounded-lg p-3">
                {iaRisultato.interpretazione && <p className="text-sm text-gray-200 mb-2">{iaRisultato.interpretazione}</p>}
                {iaRisultato.domande && <p className="text-sm text-yellow-300">❓ {iaRisultato.domande}</p>}
                {iaRisultato.modifiche && iaRisultato.modifiche.length > 0 && !iaRisultato.domande && (
                  <p className="text-xs text-purple-300 mt-1">✅ {iaRisultato.modifiche.length} modifiche applicate alla tabella — puoi ritoccarle prima di confermare</p>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Tabella task */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-800 text-gray-400">
            <tr>
              <th className="text-left px-3 py-2 w-8">#</th>
              <th className="text-left px-3 py-2 min-w-[180px]">Nome task</th>
              <th className="text-left px-3 py-2 w-28">Fase</th>
              <th className="text-right px-3 py-2 w-20">Ore</th>
              <th className="text-left px-3 py-2 w-36">Profilo</th>
              <th className="text-left px-3 py-2 w-40">Assegnato a</th>
              <th className="text-left px-3 py-2 w-28">Stato</th>
              <th className="text-center px-3 py-2 w-20"></th>
            </tr>
          </thead>
          <tbody>
            {planTasks.map((task, idx) => (
              <tr key={task.tempId} className={`border-t border-gray-800 hover:bg-gray-800/30 ${
                task.iaSuggested ? 'bg-purple-900/15 border-l-2 border-l-purple-500' : !task.isExisting ? 'bg-blue-900/10' : ''
              }`}>
                <td className="px-3 py-2 text-gray-500 text-xs">
                  {idx + 1}
                  {task.iaSuggested && <span className="text-purple-400 ml-1" title="Modificato dall'IA">🧠</span>}
                  {!task.isExisting && !task.iaSuggested && <span className="text-blue-400 ml-1" title="Nuovo">●</span>}
                </td>
                <td className="px-3 py-2">
                  <input type="text" value={task.nome} onChange={e => updateTask(task.tempId, 'nome', e.target.value)}
                    placeholder="Nome del task..." className="w-full bg-transparent border-b border-gray-700 focus:border-blue-500 outline-none py-1 text-sm placeholder-gray-600" />
                </td>
                <td className="px-3 py-2">
                  <select value={task.fase} onChange={e => updateTask(task.tempId, 'fase', e.target.value)}
                    className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs w-full">
                    {FASI.map(f => <option key={f} value={f}>{f}</option>)}
                  </select>
                </td>
                <td className="px-3 py-2">
                  <input type="number" min="1" value={task.ore} onChange={e => updateTask(task.tempId, 'ore', parseInt(e.target.value) || 0)}
                    className={`w-full bg-gray-800 border rounded px-2 py-1 text-sm text-right ${task.iaSuggested ? 'border-purple-600' : 'border-gray-700'}`} />
                </td>
                <td className="px-3 py-2">
                  <select value={task.profilo} onChange={e => updateTask(task.tempId, 'profilo', e.target.value)}
                    className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs w-full">
                    {PROFILI.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                </td>
                <td className="px-3 py-2">
                  {(() => {
                    const candidati = getCandidati(task.profilo)
                    return (
                      <select value={task.assegnato} onChange={e => updateTask(task.tempId, 'assegnato', e.target.value)}
                        className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs w-full">
                        <option value="">— Seleziona —</option>
                        {candidati.map(d => (
                          <option key={d.id} value={d.nome}
                            style={{ color: d.saturazione_pct > 100 ? '#f87171' : d.saturazione_pct > 85 ? '#fbbf24' : '#86efac' }}>
                            {d.profiloMatch ? '' : '⚠️ '}{d.nome} ({d.saturazione_pct}%)
                          </option>
                        ))}
                      </select>
                    )
                  })()}
                </td>
                <td className="px-3 py-2">
                  <select value={task.stato || 'Da iniziare'} onChange={e => updateTask(task.tempId, 'stato', e.target.value)}
                    className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs w-full">
                    {STATI_TASK.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </td>
                <td className="px-3 py-2 text-center">
                  <div className="flex items-center gap-1 justify-center">
                    <button onClick={() => moveTask(task.tempId, -1)} disabled={idx === 0} className="text-gray-500 hover:text-white disabled:text-gray-700 text-xs">▲</button>
                    <button onClick={() => moveTask(task.tempId, 1)} disabled={idx === planTasks.length - 1} className="text-gray-500 hover:text-white disabled:text-gray-700 text-xs">▼</button>
                    <button onClick={() => insertTaskAt(idx + 1)} className="text-gray-500 hover:text-blue-400 text-xs">➕</button>
                    <button onClick={() => removeTask(task.tempId)} className="text-gray-500 hover:text-red-400 text-sm">🗑️</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Azioni */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <button onClick={addTask} className="px-4 py-2 bg-gray-800 hover:bg-gray-700 border border-dashed border-gray-600 rounded-lg text-sm text-gray-400 hover:text-white transition-colors">+ Aggiungi task</button>
          {confermato && <button onClick={handleReset} className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm text-gray-400 hover:text-white transition-colors">🔄 Ricomincia</button>}
        </div>
        <div className="flex gap-3">
          <button onClick={verificaImpatto} disabled={simulaLoading}
            className="px-4 py-2 bg-blue-700 hover:bg-blue-600 disabled:bg-gray-700 rounded-lg text-sm font-medium transition-colors">
            {simulaLoading ? '⏳ Calcolo...' : '📊 Verifica impatto'}
          </button>
          <button onClick={applicaTutto} disabled={confermaLoading || confermato}
            className="px-4 py-2 bg-green-600 hover:bg-green-500 disabled:bg-gray-700 rounded-lg text-sm font-medium transition-colors">
            {confermato ? '✅ Applicato!' : confermaLoading ? '⏳ Applico...' : '✅ Applica modifiche'}
          </button>
        </div>
      </div>

      {/* Risultato simulazione GANTT */}
      {simulazioneResult && <RisultatoSimulazione risultato={simulazioneResult} />}
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════
//  PAGINA PRINCIPALE — TAVOLO DI LAVORO
// ═════════════════════════════════════════════════════════════════════

export default function AnalisiInterventi() {
  const [dipendenti, setDipendenti] = useState([])
  const [progetti, setProgetti] = useState([])
  const [allTasks, setAllTasks] = useState([])
  const [segnalazioni, setSegnalazioni] = useState([])
  const [loadingData, setLoadingData] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    Promise.all([fetchDipendenti(), fetchProgetti(), fetchTasks()])
      .then(([d, p, t]) => { setDipendenti(d); setProgetti(p); setAllTasks(t) })
      .finally(() => setLoadingData(false))
    fetchSegnalazioni().then(s => { if (s && s.length > 0) setSegnalazioni(s) }).catch(() => {})
  }, [])

  if (loadingData) return <p className="text-gray-400 p-8">Caricamento...</p>

  function reloadData() {
    Promise.all([fetchTasks(), fetchDipendenti(), fetchSegnalazioni()])
      .then(([t, d, s]) => { setAllTasks(t); setDipendenti(d); if (s && s.length > 0) setSegnalazioni(s) })
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold mb-2">🔬 Tavolo di Lavoro</h1>
          <p className="text-sm text-gray-400">
            Seleziona un progetto, modifica i task manualmente o con l'aiuto dell'IA, verifica l'impatto a cascata e applica.
          </p>
        </div>
        <button onClick={() => setSidebarOpen(!sidebarOpen)}
          className={`px-3 py-2 rounded-lg text-sm transition-colors ${
            sidebarOpen ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
          }`}>
          {sidebarOpen ? '✕ Chiudi contesto' : '👥 Contesto'}
        </button>
      </div>

      <div className="flex gap-6">
        <div className="flex-1 min-w-0">
          <EditorGanttUnificato progetti={progetti} dipendenti={dipendenti} allTasks={allTasks} segnalazioni={segnalazioni} onTasksChanged={reloadData} />
        </div>
        {sidebarOpen && (
          <div className="w-72 flex-shrink-0 animate-in slide-in-from-right">
            <SidebarContesto dipendenti={dipendenti} progetti={progetti} segnalazioni={segnalazioni} />
          </div>
        )}
      </div>
    </div>
  )
}