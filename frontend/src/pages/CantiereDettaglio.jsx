// ═════════════════════════════════════════════════════════════════════════
// CantiereDettaglio.jsx — Scheda del singolo progetto (Step 2.4 Blocco 2)
//
// Raggiunta via /cantiere/{progettoId}.
// Struttura (handoff v15 §2.4):
//   - Header anagrafica + breadcrumb
//   - Banner stato (Bozza / Attivo / Sospeso / Completato / Annullato)
//   - Tab "Design" (default): KPI sintetici + Anagrafica + Persone +
//     Fasi/Task con drill-down editabile
//   - Tab "Scenari": snapshot deterministico criticità + placeholder
//     ChatbotEstraibile (IA propositiva, R2)
//
// Backend consumati:
//   GET /api/gantt/strutturato?progetto_id={id}  → gerarchia + aggregati
//   PATCH /api/progetti/{id}                     → anagrafica + stato
//   DELETE /api/progetti/{id}                    → solo bozze
//   POST/PATCH/DELETE /api/fasi[/...]            → CRUD fasi
//   POST/PATCH /api/tasks[/...]                  → CRUD task
//   PATCH /api/tasks/{id}/elimina                → soft delete task
//
// Note di design:
// - Stesso file React, due tab in cima → si naviga rapidamente senza perdere
//   il contesto progetto (handoff: "stessa lente, due zoom").
// - Tab Scenari NON parte da pagina vuota (handoff §3.5 punto 14): mostra
//   subito uno snapshot deterministico utile, IA è opzionale.
// ═════════════════════════════════════════════════════════════════════════

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  fetchGanttStrutturato,
  fetchDipendenti,
  fetchSaturazionePeriodo,
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

const STATI_FASE = ['Da iniziare', 'In corso', 'Completata', 'Sospesa', 'Annullata']
const STATI_TASK = ['Da iniziare', 'In corso', 'Completato', 'Bloccato']

const COLORI_STATO = {
  // Fase
  'Da iniziare': 'bg-gray-700 text-gray-300',
  'In corso': 'bg-blue-700 text-blue-100',
  'Completata': 'bg-green-700 text-green-100',
  'Sospesa': 'bg-yellow-700 text-yellow-100',
  'Annullata': 'bg-red-900 text-red-200',
  // Task
  'Completato': 'bg-green-700 text-green-100',
  'Da fare': 'bg-gray-700 text-gray-300',
  'Bloccato': 'bg-red-700 text-red-100',
  'Eliminato': 'bg-red-950 text-red-300',
  // Progetto
  'Bozza': 'bg-amber-800 text-amber-100',
  'In esecuzione': 'bg-blue-700 text-blue-100',
  'Sospeso': 'bg-yellow-700 text-yellow-100',
  'Annullato': 'bg-red-900 text-red-200',
}


// ─── Componenti utility ───────────────────────────────────────────────────

function StatoBadge({ stato }) {
  const cls = COLORI_STATO[stato] || 'bg-gray-700 text-gray-300'
  return <span className={`text-xs px-2 py-0.5 rounded ${cls}`}>{stato}</span>
}

function FormRow({ label, children }) {
  return (
    <div>
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</div>
      <div className="text-gray-200">{children}</div>
    </div>
  )
}

function FormInput({ label, value, onChange, type = 'text', required = false, placeholder = '' }) {
  return (
    <div>
      <label className="text-xs text-gray-500 uppercase tracking-wide block mb-1">
        {label}{required && <span className="text-red-400 ml-1">*</span>}
      </label>
      <input
        type={type}
        value={value ?? ''}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm focus:border-blue-500 outline-none"
      />
    </div>
  )
}

/** Input date con limiti min/max e tooltip esplicativo (Step 2.4-bis §14.2). */
function FormInputDate({ label, value, onChange, required = false, minDate = null, maxDate = null, hint = '' }) {
  const fuoriRange = value && ((minDate && value < minDate) || (maxDate && value > maxDate))
  return (
    <div>
      <label className="text-xs text-gray-500 uppercase tracking-wide block mb-1">
        {label}{required && <span className="text-red-400 ml-1">*</span>}
      </label>
      <input
        type="date"
        value={value ?? ''}
        onChange={e => onChange(e.target.value)}
        min={minDate || undefined}
        max={maxDate || undefined}
        className={`w-full border rounded px-3 py-2 text-sm focus:outline-none ${
          fuoriRange
            ? 'bg-red-950 border-red-700 focus:border-red-500'
            : 'bg-gray-800 border-gray-700 focus:border-blue-500'
        }`}
      />
      {hint && <div className="text-xs text-gray-500 mt-1">{hint}</div>}
      {fuoriRange && (
        <div className="text-xs text-red-400 mt-1">⚠ Data fuori dal range consentito</div>
      )}
    </div>
  )
}

function FormSelect({ label, value, onChange, options, required = false }) {
  return (
    <div>
      <label className="text-xs text-gray-500 uppercase tracking-wide block mb-1">
        {label}{required && <span className="text-red-400 ml-1">*</span>}
      </label>
      <select
        value={value ?? ''}
        onChange={e => onChange(e.target.value)}
        className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm focus:border-blue-500 outline-none"
      >
        {options.map(o => typeof o === 'string'
          ? <option key={o} value={o}>{o}</option>
          : <option key={o.value} value={o.value}>{o.label}</option>
        )}
      </select>
    </div>
  )
}


// ─── Banner di stato ─────────────────────────────────────────────────────

function BannerStato({ progetto, onAvvia, onCambiaStato }) {
  if (progetto.stato === 'Bozza') {
    const puoAvviare = progetto.n_fasi > 0
    return (
      <div className="bg-amber-900/40 border border-amber-700 rounded-lg p-4 mb-6 flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="text-amber-200 font-semibold">📝 Progetto in BOZZA</div>
          <div className="text-sm text-amber-300/80 mt-1">
            {puoAvviare
              ? 'Pronto per essere avviato. Verifica fasi e task, poi clicca "Avvia progetto".'
              : 'Per avviare il progetto, aggiungi almeno una fase nella sezione Design.'}
          </div>
        </div>
        <button
          onClick={onAvvia}
          disabled={!puoAvviare}
          className={`px-5 py-2 rounded-lg font-semibold text-sm transition-colors ${
            puoAvviare
              ? 'bg-green-600 hover:bg-green-500 text-white'
              : 'bg-gray-700 text-gray-500 cursor-not-allowed'
          }`}
        >
          ▶ Avvia progetto
        </button>
      </div>
    )
  }

  const cambiabile = ['In esecuzione', 'Sospeso'].includes(progetto.stato)
  const divergenza = progetto.stato !== progetto.stato_derivato

  return (
    <div className="bg-gray-800/60 border border-gray-700 rounded-lg p-4 mb-6">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm text-gray-400">Stato:</span>
        <StatoBadge stato={progetto.stato} />
        {divergenza && (
          <span className="text-xs text-yellow-400" title="Stato calcolato dalle fasi">
            ⚠ derivato: <strong>{progetto.stato_derivato}</strong>
          </span>
        )}
        {cambiabile && (
          <div className="ml-auto flex gap-2 items-center flex-wrap">
            <span className="text-xs text-gray-500">Cambia in:</span>
            {progetto.stato === 'In esecuzione' && (
              <button onClick={() => onCambiaStato('Sospeso')}
                className="px-3 py-1 text-xs bg-yellow-700/60 hover:bg-yellow-700 rounded">Sospeso</button>
            )}
            {progetto.stato === 'Sospeso' && (
              <button onClick={() => onCambiaStato('In esecuzione')}
                className="px-3 py-1 text-xs bg-blue-700/60 hover:bg-blue-700 rounded">In esecuzione</button>
            )}
            <button onClick={() => onCambiaStato('Completato')}
              className="px-3 py-1 text-xs bg-green-700/60 hover:bg-green-700 rounded">Completato</button>
            <button onClick={() => onCambiaStato('Annullato')}
              className="px-3 py-1 text-xs bg-red-800/60 hover:bg-red-800 rounded">Annullato</button>
          </div>
        )}
      </div>
    </div>
  )
}


// ─── KPI sintetici (header tab Design) ───────────────────────────────────

function KpiSintetici({ progetto }) {
  const budgetOre = progetto.budget_ore || 0
  const oreCons = progetto.ore_consumate_totali || 0
  const oreVen = progetto.ore_vendute_totali || 0
  const pct = oreVen > 0 ? Math.round((oreCons / oreVen) * 100) : 0
  const sforamento = oreVen > 0 && oreCons > oreVen

  // Conteggio task per stato (per "completamento" semplice)
  let taskTot = 0, taskComp = 0
  progetto.fasi?.forEach(f => {
    f.tasks.forEach(t => {
      taskTot++
      if (t.stato === 'Completato') taskComp++
    })
  })
  const pctTask = taskTot > 0 ? Math.round((taskComp / taskTot) * 100) : 0

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      <KpiCard label="Budget ore" valore={`${budgetOre}h`} />
      <KpiCard
        label="Ore consumate"
        valore={`${oreCons}h / ${oreVen}h`}
        rosso={sforamento}
      />
      <KpiCard label="Avanzamento" valore={`${pct}%`} />
      <KpiCard label="Task completati" valore={`${taskComp} / ${taskTot} (${pctTask}%)`} />
    </div>
  )
}

function KpiCard({ label, valore, rosso = false }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</div>
      <div className={`text-xl font-semibold ${rosso ? 'text-red-400' : 'text-gray-100'}`}>
        {valore}
      </div>
    </div>
  )
}


// ─── Sezione Anagrafica ──────────────────────────────────────────────────

function SezioneAnagrafica({ progetto, onSalva, onEliminaBozza }) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({
    nome: progetto.nome || '',
    cliente: progetto.cliente || '',
    data_inizio: progetto.data_inizio || '',
    data_fine: progetto.data_fine || '',
    budget_ore: progetto.budget_ore || 0,
  })
  const [salvando, setSalvando] = useState(false)
  const [errore, setErrore] = useState(null)

  const handleSalva = async () => {
    setSalvando(true); setErrore(null)
    try {
      await onSalva({
        nome: form.nome,
        cliente: form.cliente,
        data_inizio: form.data_inizio || null,
        data_fine: form.data_fine || null,
        budget_ore: Number(form.budget_ore) || 0,
      })
      setEditing(false)
    } catch (e) {
      setErrore(e.message || 'Errore nel salvataggio')
    } finally { setSalvando(false) }
  }

  const handleAnnulla = () => {
    setForm({
      nome: progetto.nome || '',
      cliente: progetto.cliente || '',
      data_inizio: progetto.data_inizio || '',
      data_fine: progetto.data_fine || '',
      budget_ore: progetto.budget_ore || 0,
    })
    setEditing(false); setErrore(null)
  }

  return (
    <section className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">📋 Anagrafica</h2>
        <div className="flex gap-2">
          {!editing && (
            <button onClick={() => setEditing(true)}
              className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-sm">
              ✏ Modifica
            </button>
          )}
          {progetto.stato === 'Bozza' && !editing && (
            <button onClick={onEliminaBozza}
              className="px-3 py-1.5 bg-red-900/60 hover:bg-red-900 rounded text-sm">
              🗑 Elimina bozza
            </button>
          )}
        </div>
      </div>

      {!editing ? (
        <div className="grid grid-cols-2 gap-x-8 gap-y-3 text-sm">
          <FormRow label="ID">{progetto.id}</FormRow>
          <FormRow label="Tipologia">{progetto.tipologia}</FormRow>
          <FormRow label="Nome">{progetto.nome}</FormRow>
          <FormRow label="Cliente">{progetto.cliente || <span className="text-gray-600 italic">—</span>}</FormRow>
          <FormRow label="Data inizio">{progetto.data_inizio || <span className="text-gray-600 italic">—</span>}</FormRow>
          <FormRow label="Data fine">{progetto.data_fine || <span className="text-gray-600 italic">—</span>}</FormRow>
          <FormRow label="Budget ore">{progetto.budget_ore || 0}h</FormRow>
          <FormRow label="PM">{progetto.pm_id || <span className="text-gray-600 italic">—</span>}</FormRow>
        </div>
      ) : (
        <div className="space-y-3">
          <FormInput label="Nome" value={form.nome} onChange={v => setForm({...form, nome: v})} required />
          <FormInput label="Cliente" value={form.cliente} onChange={v => setForm({...form, cliente: v})} />
          <div className="grid grid-cols-2 gap-4">
            <FormInput label="Data inizio" type="date" value={form.data_inizio} onChange={v => setForm({...form, data_inizio: v})} />
            <FormInput label="Data fine" type="date" value={form.data_fine} onChange={v => setForm({...form, data_fine: v})} />
          </div>
          <FormInput label="Budget ore" type="number" value={form.budget_ore} onChange={v => setForm({...form, budget_ore: v})} />
          {errore && <p className="text-sm text-red-400">{errore}</p>}
          <div className="flex gap-2 pt-2">
            <button onClick={handleSalva} disabled={salvando}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm font-semibold disabled:bg-gray-700">
              {salvando ? 'Salvataggio…' : '💾 Salva'}
            </button>
            <button onClick={handleAnnulla} disabled={salvando}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm">
              Annulla
            </button>
          </div>
        </div>
      )}
    </section>
  )
}


// ─── Sezione Persone coinvolte ───────────────────────────────────────────

function SezionePersone({ progetto, dipendenti }) {
  // Derivo lista persone uniche dai task
  const personeIds = useMemo(() => {
    const s = new Set()
    progetto.fasi?.forEach(f => f.tasks.forEach(t => { if (t.dipendente_id) s.add(t.dipendente_id) }))
    return [...s]
  }, [progetto])

  if (personeIds.length === 0) {
    return (
      <section className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <h2 className="text-xl font-semibold mb-2">👥 Persone coinvolte</h2>
        <p className="text-sm text-gray-500 italic">Nessuna persona assegnata ai task di questo progetto.</p>
      </section>
    )
  }

  const persone = personeIds.map(id => dipendenti.find(d => d.id === id)).filter(Boolean)

  return (
    <section className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
      <h2 className="text-xl font-semibold mb-3">👥 Persone coinvolte ({persone.length})</h2>
      <div className="flex flex-wrap gap-2">
        {persone.map(d => (
          <div key={d.id} className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm">
            <div className="font-medium">{d.nome}</div>
            <div className="text-xs text-gray-500">{d.profilo || ''}</div>
          </div>
        ))}
      </div>
    </section>
  )
}


// ─── Sezione Fasi & Task (drill-down editabile) ──────────────────────────

function SezioneFasiTask({ progetto, dipendenti, onAggiornaFase, onEliminaFase, onAggiungiFase, onAggiungiTask, onAggiornaTask, onEliminaTask }) {
  const [modaleNuovaFase, setModaleNuovaFase] = useState(false)
  const [modaleNuovoTask, setModaleNuovoTask] = useState(null) // { faseId, faseNome }
  const [modaleEditTask, setModaleEditTask] = useState(null)   // task object
  const [faseEspansa, setFaseEspansa] = useState(() => {
    // Default: fasi "In corso" aperte
    const s = new Set()
    progetto.fasi?.forEach(f => { if (f.stato === 'In corso') s.add(f.id) })
    return s
  })

  const toggleFase = (faseId) => {
    setFaseEspansa(prev => {
      const n = new Set(prev)
      if (n.has(faseId)) n.delete(faseId); else n.add(faseId)
      return n
    })
  }

  return (
    <section className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">🧩 Fasi e task ({progetto.n_fasi} {progetto.n_fasi === 1 ? 'fase' : 'fasi'})</h2>
        <button onClick={() => setModaleNuovaFase(true)}
          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded text-sm font-semibold">
          + Aggiungi fase
        </button>
      </div>

      {progetto.fasi.length === 0 ? (
        <p className="text-sm text-gray-500 italic">Nessuna fase. Aggiungi la prima fase per iniziare la pianificazione.</p>
      ) : (
        progetto.fasi.map(fase => (
          <FaseEditabile
            key={fase.id}
            fase={fase}
            dipendenti={dipendenti}
            tutteLeTaskDelProgetto={progetto.fasi.flatMap(f => f.tasks)}
            espansa={faseEspansa.has(fase.id)}
            onToggle={() => toggleFase(fase.id)}
            onAggiorna={onAggiornaFase}
            onElimina={() => onEliminaFase(fase)}
            onAggiungiTask={() => setModaleNuovoTask({
              faseId: fase.id,
              faseNome: fase.nome,
              faseDataInizio: fase.data_inizio,
              faseDataFine: fase.data_fine,
            })}
            onEditTask={(task) => setModaleEditTask({
              ...task,
              fase_id: fase.id,
              _faseDataInizio: fase.data_inizio,
              _faseDataFine: fase.data_fine,
            })}
            onEliminaTask={onEliminaTask}
          />
        ))
      )}

      {modaleNuovaFase && (
        <ModaleNuovaFase
          progettoId={progetto.id}
          ordineSuggerito={progetto.fasi.length + 1}
          onClose={() => setModaleNuovaFase(false)}
          onSalva={async (dati) => {
            await onAggiungiFase(dati)
            setModaleNuovaFase(false)
          }}
        />
      )}
      {modaleNuovoTask && (
        <ModaleTask
          mode="nuovo"
          progettoId={progetto.id}
          faseId={modaleNuovoTask.faseId}
          faseNome={modaleNuovoTask.faseNome}
          faseDataInizio={modaleNuovoTask.faseDataInizio}
          faseDataFine={modaleNuovoTask.faseDataFine}
          dipendenti={dipendenti}
          tutteLeTaskDelProgetto={progetto.fasi.flatMap(f => f.tasks)}
          onClose={() => setModaleNuovoTask(null)}
          onSalva={async (dati) => {
            await onAggiungiTask(dati)
            setModaleNuovoTask(null)
          }}
        />
      )}
      {modaleEditTask && (
        <ModaleTask
          mode="modifica"
          task={modaleEditTask}
          progettoId={progetto.id}
          faseId={modaleEditTask.fase_id}
          faseDataInizio={modaleEditTask._faseDataInizio}
          faseDataFine={modaleEditTask._faseDataFine}
          dipendenti={dipendenti}
          tutteLeTaskDelProgetto={progetto.fasi.flatMap(f => f.tasks)}
          onClose={() => setModaleEditTask(null)}
          onSalva={async (dati) => {
            await onAggiornaTask(modaleEditTask.id, dati)
            setModaleEditTask(null)
          }}
        />
      )}
    </section>
  )
}

function FaseEditabile({ fase, dipendenti, tutteLeTaskDelProgetto, espansa, onToggle, onAggiorna, onElimina, onAggiungiTask, onEditTask, onEliminaTask }) {
  const [editingStato, setEditingStato] = useState(false)
  const [statoLocal, setStatoLocal] = useState(fase.stato)
  const sforamento = fase.ore_vendute > 0 && fase.ore_consumate > fase.ore_vendute

  const salvaStato = async () => {
    if (statoLocal !== fase.stato) {
      await onAggiorna(fase.id, { stato: statoLocal })
    }
    setEditingStato(false)
  }

  return (
    <div className="border-t border-gray-800">
      <div className="flex items-center gap-3 py-3 flex-wrap">
        <button onClick={onToggle} className="text-gray-500 text-xs hover:text-gray-300 w-5">
          {espansa ? '▼' : '▶'}
        </button>
        <span className="text-xs text-gray-600 font-mono">{fase.ordine}</span>
        <span className="font-medium">{fase.nome}</span>
        <span className="text-xs text-gray-600">({fase.n_task} {fase.n_task === 1 ? 'task' : 'task'})</span>

        {editingStato ? (
          <select value={statoLocal} onChange={e => setStatoLocal(e.target.value)}
            onBlur={salvaStato} autoFocus
            className="bg-gray-800 border border-gray-600 rounded px-2 py-0.5 text-xs">
            {STATI_FASE.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        ) : (
          <button onClick={() => setEditingStato(true)} title="Click per cambiare stato">
            <StatoBadge stato={fase.stato} />
          </button>
        )}

        <div className="ml-auto flex items-center gap-3 text-xs">
          <span>
            <span className={sforamento ? 'text-red-400 font-medium' : 'text-gray-300'}>
              {fase.ore_consumate}h
            </span>
            <span className="text-gray-600"> / {fase.ore_vendute}h</span>
          </span>
          <span className="text-gray-500">{fase.data_inizio || '?'} → {fase.data_fine || '?'}</span>
          <button onClick={onElimina} title="Elimina fase (solo senza task)"
            className="text-red-400 hover:text-red-300 ml-2">🗑</button>
        </div>
      </div>

      {espansa && (
        <div className="pl-8 pb-3 bg-gray-900/40">
          {fase.tasks.length === 0 ? (
            <p className="text-xs text-gray-500 italic py-2">Nessun task in questa fase.</p>
          ) : (
            <table className="w-full text-sm mb-2">
              <thead>
                <tr className="text-xs text-gray-500 uppercase tracking-wide">
                  <th className="text-left py-1 pr-2">Nome</th>
                  <th className="text-left py-1 pr-2">Responsabile</th>
                  <th className="text-right py-1 pr-2">Ore (cons./stim.)</th>
                  <th className="text-left py-1 pr-2">Periodo</th>
                  <th className="text-left py-1 pr-2">Stato</th>
                  <th className="text-right py-1">Azioni</th>
                </tr>
              </thead>
              <tbody>
                {fase.tasks.map(t => {
                  const sfora = t.ore_stimate > 0 && t.ore_consumate > t.ore_stimate
                  return (
                    <tr key={t.id} className="border-t border-gray-800/40 hover:bg-gray-800/30">
                      <td className="py-1.5 pr-2">{t.nome}</td>
                      <td className="py-1.5 pr-2 text-xs text-gray-400">{t.dipendente_nome || '—'}</td>
                      <td className="py-1.5 pr-2 text-right text-xs">
                        <span className={sfora ? 'text-red-400 font-medium' : 'text-gray-300'}>{t.ore_consumate}h</span>
                        <span className="text-gray-600"> / {t.ore_stimate}h</span>
                      </td>
                      <td className="py-1.5 pr-2 text-xs text-gray-500">{t.data_inizio || '?'} → {t.data_fine || '?'}</td>
                      <td className="py-1.5 pr-2"><StatoBadge stato={t.stato} /></td>
                      <td className="py-1.5 text-right">
                        <button onClick={() => onEditTask(t)} title="Modifica task"
                          className="text-xs text-blue-400 hover:text-blue-300 mr-2">✏</button>
                        <button onClick={() => onEliminaTask(t)} title="Elimina task"
                          className="text-xs text-red-400 hover:text-red-300">🗑</button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
          <button onClick={onAggiungiTask}
            className="text-xs text-blue-400 hover:text-blue-300 mt-1">
            + Aggiungi task a questa fase
          </button>
        </div>
      )}
    </div>
  )
}


// ─── Modali ─────────────────────────────────────────────────────────────

// ─── Pannello saturazione dipendente (Step 2.4-bis §14.4) ───────────────

/**
 * Mostra la saturazione del dipendente selezionato nel periodo del task.
 * Si aggiorna automaticamente quando cambia dipendente, data_inizio, data_fine.
 * Colori secondo soglie:
 *   verde   <80%   ok
 *   giallo  80-100 quasi pieno
 *   arancio 100-125 sovraccarico tollerabile (soft cap)
 *   rosso   >125   sovraccarico critico
 */
function PannelloSaturazione({ dipendenteId, dataInizio, dataFine, escludiTaskId }) {
  const [stato, setStato] = useState({ loading: false, dati: null, errore: null })

  useEffect(() => {
    if (!dipendenteId || !dataInizio || !dataFine) {
      setStato({ loading: false, dati: null, errore: null })
      return
    }
    if (dataFine < dataInizio) {
      setStato({ loading: false, dati: null, errore: null })
      return
    }
    let annullato = false
    setStato(s => ({ ...s, loading: true, errore: null }))
    fetchSaturazionePeriodo({ dipendenteId, dataInizio, dataFine, escludiTaskId })
      .then(d => { if (!annullato) setStato({ loading: false, dati: d, errore: null }) })
      .catch(e => { if (!annullato) setStato({ loading: false, dati: null, errore: e.message }) })
    return () => { annullato = true }
  }, [dipendenteId, dataInizio, dataFine, escludiTaskId])

  if (!dipendenteId) return null
  if (stato.loading) {
    return <div className="mt-2 text-xs text-gray-500 italic">Calcolo saturazione…</div>
  }
  if (stato.errore) {
    return <div className="mt-2 text-xs text-red-400">Errore saturazione: {stato.errore}</div>
  }
  if (!stato.dati) return null

  const d = stato.dati
  const sat = d.saturazione_media_pct

  let livello, cls
  if (sat < 80) { livello = 'ok'; cls = 'bg-green-900/30 border-green-700 text-green-200' }
  else if (sat < 100) { livello = 'attenzione'; cls = 'bg-yellow-900/30 border-yellow-700 text-yellow-200' }
  else if (sat <= 125) { livello = 'sovraccarico'; cls = 'bg-orange-900/40 border-orange-700 text-orange-200' }
  else { livello = 'critico'; cls = 'bg-red-900/40 border-red-700 text-red-200' }

  const icona = livello === 'ok' ? '✓' : livello === 'attenzione' ? '⚠' : '⛔'

  return (
    <div className={`mt-2 border rounded-md px-3 py-2 text-xs ${cls}`}>
      <div className="flex items-center justify-between mb-1">
        <span className="font-semibold">{icona} {d.nome} · {d.ore_sett}h/sett</span>
        <span className="font-mono">
          media {sat}%  ·  picco {d.saturazione_max_pct}%
        </span>
      </div>
      <div className="opacity-80">
        Saturazione media nelle {d.settimane_coperte} settimane del task
        {sat > 125 && <strong> — oltre il soft cap (125%)</strong>}
      </div>
    </div>
  )
}


function ModaleNuovaFase({ progettoId, ordineSuggerito, onClose, onSalva }) {
  const [form, setForm] = useState({
    nome: '', ordine: ordineSuggerito,
    data_inizio: '', data_fine: '', ore_vendute: 0,
  })
  const [salvando, setSalvando] = useState(false)
  const [errore, setErrore] = useState(null)

  const handleSalva = async () => {
    if (!form.nome.trim()) { setErrore('Il nome è obbligatorio'); return }
    setSalvando(true); setErrore(null)
    try {
      await onSalva({
        progetto_id: progettoId,
        nome: form.nome.trim(),
        ordine: Number(form.ordine),
        data_inizio: form.data_inizio || null,
        data_fine: form.data_fine || null,
        ore_vendute: Number(form.ore_vendute) || 0,
        ore_pianificate: 0,
        note: '',
      })
    } catch (e) { setErrore(e.message || 'Errore') }
    finally { setSalvando(false) }
  }

  return (
    <ModaleWrapper titolo="Nuova fase" onClose={onClose} salvando={salvando}>
      <div className="space-y-3">
        <FormInput label="Nome fase" value={form.nome} onChange={v => setForm({...form, nome: v})} required />
        <FormInput label="Ordine" type="number" value={form.ordine} onChange={v => setForm({...form, ordine: v})} />
        <div className="grid grid-cols-2 gap-3">
          <FormInput label="Data inizio" type="date" value={form.data_inizio} onChange={v => setForm({...form, data_inizio: v})} />
          <FormInput label="Data fine" type="date" value={form.data_fine} onChange={v => setForm({...form, data_fine: v})} />
        </div>
        <FormInput label="Ore vendute" type="number" value={form.ore_vendute} onChange={v => setForm({...form, ore_vendute: v})} />
        {errore && <p className="text-sm text-red-400">{errore}</p>}
      </div>
      <div className="flex gap-2 mt-5 justify-end">
        <button onClick={onClose} disabled={salvando}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm">Annulla</button>
        <button onClick={handleSalva} disabled={salvando}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm font-semibold disabled:bg-gray-700">
          {salvando ? 'Salvataggio…' : '💾 Crea fase'}
        </button>
      </div>
    </ModaleWrapper>
  )
}

function ModaleTask({ mode, task, progettoId, faseId, faseNome, faseDataInizio, faseDataFine, dipendenti, tutteLeTaskDelProgetto, onClose, onSalva }) {
  const [form, setForm] = useState(() => mode === 'modifica' ? {
    nome: task.nome || '',
    ore_stimate: task.ore_stimate || 0,
    data_inizio: task.data_inizio || '',
    data_fine: task.data_fine || '',
    profilo_richiesto: task.profilo_richiesto || '',
    dipendente_id: task.dipendente_id || '',
    predecessore: task.predecessore || '',
    stato: task.stato || 'Da iniziare',
  } : {
    nome: '', ore_stimate: 0,
    data_inizio: '', data_fine: '',
    profilo_richiesto: '', dipendente_id: '',
    predecessore: '', stato: 'Da iniziare',
  })
  const [salvando, setSalvando] = useState(false)
  const [errore, setErrore] = useState(null)

  const handleSalva = async () => {
    if (!form.nome.trim()) { setErrore('Il nome è obbligatorio'); return }
    setSalvando(true); setErrore(null)
    try {
      if (mode === 'nuovo') {
        await onSalva({
          progetto_id: progettoId,
          fase_id: faseId,
          nome: form.nome.trim(),
          ore_stimate: Number(form.ore_stimate) || 0,
          data_inizio: form.data_inizio || null,
          data_fine: form.data_fine || null,
          profilo_richiesto: form.profilo_richiesto || '',
          dipendente_id: form.dipendente_id || '',
          predecessore: form.predecessore || '',
          stato: form.stato,
        })
      } else {
        await onSalva({
          nome: form.nome.trim(),
          ore_stimate: Number(form.ore_stimate) || 0,
          data_inizio: form.data_inizio || null,
          data_fine: form.data_fine || null,
          profilo_richiesto: form.profilo_richiesto || '',
          dipendente_id: form.dipendente_id || '',
          predecessore: form.predecessore || '',
          stato: form.stato,
        })
      }
    } catch (e) { setErrore(e.message || 'Errore') }
    finally { setSalvando(false) }
  }

  const dipOptions = [{ value: '', label: '— Nessuno —' }, ...dipendenti.map(d => ({ value: d.id, label: d.nome }))]
  const taskAltri = tutteLeTaskDelProgetto.filter(t => mode === 'nuovo' || t.id !== task?.id)
  const predOptions = [{ value: '', label: '— Nessuno —' }, ...taskAltri.map(t => ({ value: t.id, label: `${t.id} — ${t.nome}` }))]

  return (
    <ModaleWrapper titolo={mode === 'nuovo' ? `Nuovo task in fase "${faseNome}"` : `Modifica task ${task.id}`} onClose={onClose} salvando={salvando}>
      <div className="space-y-3">
        <FormInput label="Nome task" value={form.nome} onChange={v => setForm({...form, nome: v})} required />
        <div className="grid grid-cols-2 gap-3">
          <FormInput label="Ore stimate" type="number" value={form.ore_stimate} onChange={v => setForm({...form, ore_stimate: v})} />
          <FormSelect label="Stato" value={form.stato} onChange={v => setForm({...form, stato: v})} options={STATI_TASK} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <FormInputDate
            label="Data inizio"
            value={form.data_inizio}
            onChange={v => setForm({...form, data_inizio: v})}
            minDate={faseDataInizio}
            maxDate={faseDataFine}
            hint={faseDataInizio ? `Fase: ${faseDataInizio} → ${faseDataFine || '?'}` : ''}
          />
          <FormInputDate
            label="Data fine"
            value={form.data_fine}
            onChange={v => setForm({...form, data_fine: v})}
            minDate={form.data_inizio || faseDataInizio}
            maxDate={faseDataFine}
          />
        </div>
        <FormSelect label="Responsabile" value={form.dipendente_id} onChange={v => setForm({...form, dipendente_id: v})} options={dipOptions} />
        <PannelloSaturazione
          dipendenteId={form.dipendente_id}
          dataInizio={form.data_inizio}
          dataFine={form.data_fine}
          escludiTaskId={mode === 'modifica' ? task?.id : null}
        />
        <FormInput label="Profilo richiesto" value={form.profilo_richiesto} onChange={v => setForm({...form, profilo_richiesto: v})} placeholder="es. Tecnico Senior" />
        <FormSelect label="Predecessore (task)" value={form.predecessore} onChange={v => setForm({...form, predecessore: v})} options={predOptions} />
        {errore && <p className="text-sm text-red-400">{errore}</p>}
      </div>
      <div className="flex gap-2 mt-5 justify-end">
        <button onClick={onClose} disabled={salvando}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm">Annulla</button>
        <button onClick={handleSalva} disabled={salvando}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm font-semibold disabled:bg-gray-700">
          {salvando ? 'Salvataggio…' : mode === 'nuovo' ? '💾 Crea task' : '💾 Salva'}
        </button>
      </div>
    </ModaleWrapper>
  )
}

function ModaleWrapper({ titolo, onClose, salvando, children }) {
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 max-w-lg w-full max-h-[90vh] overflow-y-auto">
        <h3 className="text-lg font-semibold mb-4">{titolo}</h3>
        {children}
      </div>
    </div>
  )
}


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
  const [loading, setLoading] = useState(true)
  const [errore, setErrore] = useState(null)
  const [tab, setTab] = useState('design')

  const ricarica = useCallback(async () => {
    try {
      const [data, dips] = await Promise.all([
        fetchGanttStrutturato({ progettoId }),
        fetchDipendenti(),
      ])
      if (!data || data.length === 0) {
        setErrore('Progetto non trovato')
        setProgetto(null)
      } else {
        setProgetto(data[0])
        setDipendenti(dips || [])
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

  const aggiornaFase = async (faseId, dati) => {
    try { await updateFase(faseId, dati); await ricarica() }
    catch (e) { alert('Errore: ' + e.message) }
  }

  const eliminaFase = async (fase) => {
    if (!confirm(`Eliminare la fase "${fase.nome}"? Non sarà possibile se ha task agganciati.`)) return
    try { await deleteFase(fase.id); await ricarica() }
    catch (e) { alert(e.message || 'Errore') }
  }

  const aggiungiFase = async (dati) => { await createFase(dati); await ricarica() }

  // ── Azioni task ────────────────────────────────────────────────────────

  const aggiungiTask = async (dati) => { await createTask(dati); await ricarica() }

  const aggiornaTask = async (taskId, dati) => { await updateTask(taskId, dati); await ricarica() }

  const eliminaTask = async (task) => {
    if (!confirm(`Eliminare il task "${task.nome}"? Verrà marcato come Eliminato (soft delete).`)) return
    try { await deleteTask(task.id); await ricarica() }
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
      {/* Breadcrumb */}
      <div className="mb-4">
        <Link to="/gantt" className="text-sm text-blue-400 hover:text-blue-300">← Torna a GANTT</Link>
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
