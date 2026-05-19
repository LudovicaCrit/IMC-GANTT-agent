/**
 * ═════════════════════════════════════════════════════════════════════════
 * SezioneFasiTask.jsx — Drill-down editabile fasi/task del Cantiere
 * ═════════════════════════════════════════════════════════════════════════
 *
 * Estratto da CantiereDettaglio.jsx (Step 2.3-bis 4a, 18 mag 2026).
 *
 * IL COMPONENTE PIÙ COMPLESSO del Cantiere: orchestrazione fasi + task,
 * 3 modali (NuovaFase, Task, ConfermaCascata), cascata stato fase→task
 * (handoff v16 §14.1, implementata Step 2.4-bis B il 18 mag).
 *
 * Contiene anche, come componenti privati a questo modulo:
 *   - FaseEditabile: riga fase espandibile con tabella task
 *   - ModaleConfermaCascata: conferma cambio stato fase con anteprima task
 *   - ModaleNuovaFase: form creazione fase
 *   - ModaleTask: form creazione/modifica task con PannelloSaturazione
 *   - PannelloSaturazione: saturazione live del dipendente nelle settimane
 *     del task (Step 2.4-bis A)
 *   - ModaleWrapper: wrapper estetico modali (overlay + box centrato)
 *
 * Props del componente principale:
 *   - progetto: oggetto gerarchico con fasi[].tasks[]
 *   - dipendenti: lista dipendenti per il select Responsabile
 *   - onAggiornaFase(faseId, dati, cascade=false): PATCH fase
 *   - onEliminaFase(fase): DELETE fase (con vincolo task figli)
 *   - onAggiungiFase(dati): POST fase
 *   - onAggiungiTask(dati): POST task
 *   - onAggiornaTask(taskId, dati): PATCH task
 *   - onEliminaTask(task): soft delete task
 *   - readonly: default false. Se true, nasconde TUTTI i bottoni di edit
 *     (+ Aggiungi fase, + Aggiungi task, ✏, 🗑, select inline stato fase).
 *     Il drill-down ▶/▼ resta navigabile (è consultazione, non edit).
 *
 * Uso futuro readonly=true: GANTT accordion dinamica (4c), Archivio (2.6).
 */

import React, { useState, useEffect } from 'react'
import { STATI_FASE, STATI_TASK } from './_costanti'
import StatoBadge from '../_shared/StatoBadge'
import { FormInput, FormInputDate, FormSelect } from '../_shared/Form'
import { fetchSaturazionePeriodo } from '../../api'
import { giorniLavorativi} from '../../utils/festivita'

// ═════════════════════════════════════════════════════════════════════════
// Componente principale
// ═════════════════════════════════════════════════════════════════════════

export default function SezioneFasiTask({
  progetto,
  dipendenti,
  onAggiornaFase,
  onEliminaFase,
  onAggiungiFase,
  onAggiungiTask,
  onAggiornaTask,
  onEliminaTask,
  readonly = false,
}) {
  const [modaleNuovaFase, setModaleNuovaFase] = useState(false)
  const [modaleNuovoTask, setModaleNuovoTask] = useState(null) // { faseId, faseNome, ... }
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
        {!readonly && (
          <button onClick={() => setModaleNuovaFase(true)}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded text-sm font-semibold">
            + Aggiungi fase
          </button>
        )}
      </div>

      {progetto.fasi.length === 0 ? (
        <p className="text-sm text-gray-500 italic">
          {readonly ? 'Nessuna fase pianificata.' : 'Nessuna fase. Aggiungi la prima fase per iniziare la pianificazione.'}
        </p>
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
            readonly={readonly}
          />
        ))
      )}

      {!readonly && modaleNuovaFase && (
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
      {!readonly && modaleNuovoTask && (
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
      {!readonly && modaleEditTask && (
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

// ═════════════════════════════════════════════════════════════════════════
// FaseEditabile — riga fase espandibile con tabella task
// ═════════════════════════════════════════════════════════════════════════

function FaseEditabile({ fase, dipendenti, tutteLeTaskDelProgetto, espansa, onToggle, onAggiorna, onElimina, onAggiungiTask, onEditTask, onEliminaTask, readonly = false }) {
  const [editingStato, setEditingStato] = useState(false)
  const [statoLocal, setStatoLocal] = useState(fase.stato)
  const [modaleCascata, setModaleCascata] = useState(null) // statoNuovo da confermare
  const sforamento = fase.ore_vendute > 0 && fase.ore_consumate > fase.ore_vendute

  // Stati che richiedono modale di conferma con cascata (handoff v16 §14.1)
  const STATI_CON_CASCATA = ['Sospesa', 'Annullata', 'Completata', 'Da iniziare']

  const salvaStato = async () => {
    if (statoLocal === fase.stato) {
      setEditingStato(false)
      return
    }
    if (STATI_CON_CASCATA.includes(statoLocal) && fase.tasks.length > 0) {
      setModaleCascata(statoLocal)
      setEditingStato(false)
      return
    }
    await onAggiorna(fase.id, { stato: statoLocal })
    setEditingStato(false)
  }

  const annullaModaleCascata = () => {
    setModaleCascata(null)
    setStatoLocal(fase.stato)
  }

  const confermaCascata = async (conCascata) => {
    try {
      await onAggiorna(fase.id, { stato: modaleCascata }, conCascata)
    } finally {
      setModaleCascata(null)
    }
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

        {!readonly && editingStato ? (
          <select value={statoLocal} onChange={e => setStatoLocal(e.target.value)}
            onBlur={salvaStato} autoFocus
            className="bg-gray-800 border border-gray-600 rounded px-2 py-0.5 text-xs">
            {STATI_FASE.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        ) : readonly ? (
          <StatoBadge stato={fase.stato} />
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
          {!readonly && (
            <button onClick={onElimina} title="Elimina fase (solo senza task)"
              className="text-red-400 hover:text-red-300 ml-2">🗑</button>
          )}
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
                  {!readonly && <th className="text-right py-1">Azioni</th>}
                </tr>
              </thead>
              <tbody>
                {fase.tasks.map(t => {
                  const sfora = t.ore_stimate > 0 && t.ore_consumate > t.ore_stimate
                  return (
                    <tr key={t.id} className="border-t border-gray-800/40 hover:bg-gray-800/30">
                      <td className="py-1.5 pr-2">
                        <div>{t.nome}</div>
                        {t.predecessore && (
                          <div className="text-[10px] text-gray-500 mt-0.5">
                            ↳ dopo <span className="font-mono">{t.predecessore}</span>
                            <span className="text-gray-600" title="Tipo dipendenza Finish-to-Start (default, R2 estenderà a SS/FF/SF)"> · FS</span>
                          </div>
                        )}
                      </td>
                      <td className="py-1.5 pr-2 text-xs text-gray-400">{t.dipendente_nome || '—'}</td>
                      <td className="py-1.5 pr-2 text-right text-xs">
                        <span className={sfora ? 'text-red-400 font-medium' : 'text-gray-300'}>{t.ore_consumate}h</span>
                        <span className="text-gray-600"> / {t.ore_stimate}h</span>
                      </td>
                      <td className="py-1.5 pr-2 text-xs text-gray-500">{t.data_inizio || '?'} → {t.data_fine || '?'}</td>
                      <td className="py-1.5 pr-2"><StatoBadge stato={t.stato} /></td>
                      {!readonly && (
                        <td className="py-1.5 text-right">
                          <button onClick={() => onEditTask(t)} title="Modifica task"
                            className="text-xs text-blue-400 hover:text-blue-300 mr-2">✏</button>
                          <button onClick={() => onEliminaTask(t)} title="Elimina task"
                            className="text-xs text-red-400 hover:text-red-300">🗑</button>
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
          {!readonly && (
            <button onClick={onAggiungiTask}
              className="text-xs text-blue-400 hover:text-blue-300 mt-1">
              + Aggiungi task a questa fase
            </button>
          )}
        </div>
      )}

      {modaleCascata && (
        <ModaleConfermaCascata
          fase={fase}
          statoNuovo={modaleCascata}
          onClose={annullaModaleCascata}
          onConferma={confermaCascata}
        />
      )}
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════
// ModaleConfermaCascata — conferma cambio stato fase con anteprima task
// (Step 2.4-bis B, handoff v16 §14.1)
// ═════════════════════════════════════════════════════════════════════════

function ModaleConfermaCascata({ fase, statoNuovo, onClose, onConferma }) {
  // Caso speciale "Da iniziare": verifica ore consumate (bloccante)
  let bloccante = false
  let taskConConsumate = []
  if (statoNuovo === 'Da iniziare') {
    taskConConsumate = fase.tasks.filter(t => (t.ore_consumate || 0) > 0)
    if (taskConConsumate.length > 0) bloccante = true
  }

  const regolaCascata = {
    'Sospesa': { from: ['In corso'], to: 'Sospeso' },
    'Annullata': { from: ['Da iniziare', 'In corso', 'Sospeso'], to: 'Annullato' },
    'Completata': { from: ['Da iniziare', 'In corso', 'Sospeso'], to: 'Completato' },
    'Da iniziare': { from: ['In corso'], to: 'Da iniziare' },
  }[statoNuovo]

  const taskImpattati = regolaCascata
    ? fase.tasks.filter(t => regolaCascata.from.includes(t.stato))
    : []

  const titolo = bloccante
    ? `⛔ Operazione non consentita`
    : `Confermi cambio stato fase a "${statoNuovo}"?`

  return (
    <ModaleWrapper titolo={titolo} onClose={onClose} salvando={false}>
      {bloccante ? (
        <div className="space-y-3">
          <p className="text-sm text-red-300">
            Non posso riportare la fase <strong>"{fase.nome}"</strong> a "Da iniziare":
            ha <strong>{taskConConsumate.length}</strong> task con ore consumate.
            Una fase con lavoro già consuntivato non può fingere di non essere mai iniziata.
          </p>
          <p className="text-xs text-gray-400">Task con ore consumate:</p>
          <ul className="text-xs bg-gray-800/60 rounded p-2 max-h-40 overflow-y-auto">
            {taskConConsumate.map(t => (
              <li key={t.id} className="py-0.5">
                <span className="font-mono text-gray-400">{t.id}</span>{' '}
                {t.nome}{' '}
                <span className="text-red-300">({t.ore_consumate}h consumate)</span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-gray-500 italic">
            Per procedere, azzera prima la consuntivazione di questi task.
          </p>
          <div className="flex justify-end pt-2">
            <button onClick={onClose}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm">Chiudi</button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-gray-300">
            Stai cambiando lo stato della fase <strong>"{fase.nome}"</strong> a <strong>{statoNuovo}</strong>.
          </p>
          {taskImpattati.length > 0 ? (
            <>
              <p className="text-sm text-gray-300">
                Ci sono <strong>{taskImpattati.length}</strong> task in stato attivo. Cosa fare con loro?
              </p>
              <ul className="text-xs bg-gray-800/60 rounded p-2 max-h-40 overflow-y-auto">
                {taskImpattati.map(t => (
                  <li key={t.id} className="py-0.5">
                    <span className="font-mono text-gray-400">{t.id}</span>{' '}
                    {t.nome}{' '}
                    <StatoBadge stato={t.stato} />
                    {' → '}
                    <span className="text-blue-300">{regolaCascata.to}</span>
                  </li>
                ))}
              </ul>
              <div className="flex gap-2 pt-2 justify-end flex-wrap">
                <button onClick={onClose}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm">Annulla</button>
                <button onClick={() => onConferma(false)}
                  className="px-4 py-2 bg-yellow-700 hover:bg-yellow-600 rounded text-sm">
                  Solo la fase
                </button>
                <button onClick={() => onConferma(true)}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm font-semibold">
                  Anche i task ({taskImpattati.length})
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="text-sm text-gray-400 italic">Nessun task attivo da aggiornare.</p>
              <div className="flex gap-2 pt-2 justify-end">
                <button onClick={onClose}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm">Annulla</button>
                <button onClick={() => onConferma(false)}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm font-semibold">
                  Conferma
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </ModaleWrapper>
  )
}

// ═════════════════════════════════════════════════════════════════════════
// IndicatoreCapacita — verifica ore_stimate vs durata task (handoff v16 §14.3)
// ═════════════════════════════════════════════════════════════════════════

/**
 * Mostra sotto al campo "Ore stimate" un messaggio dinamico che valuta
 * se le ore stimate sono coerenti con la durata del task (esprimendolo
 * come saturazione % della capacità giornaliera).
 *
 * Formula:
 *   capacita = giorni_lavorativi × ore_giornaliere
 *   saturazione_pct = ore_stimate / capacita × 100
 *
 *   ore_giornaliere = dipendente.ore_sett / 5  (se selezionato)
 *                   = 8                          (default = 40h/sett)
 *
 *   giorni_lavorativi: esclude weekend e festività italiane
 *
 * Soglie (3 livelli, semplici per singolo task):
 *   <100%   verde   "ragionevole"
 *   100-125% arancio "carico pieno, considera straordinario"
 *   >125%   rosso   "irrealistico"
 *
 * Casi speciali:
 *   - Date mancanti o incoerenti: niente messaggio
 *   - Ore 0: niente messaggio
 *   - 0 giorni lavorativi (solo weekend/festivi): messaggio dedicato
 *
 * NON è bloccante: il modale Task gestirà la conferma esplicita
 * quando saturazione > 125% (vedi handleSalva di ModaleTask).
 *
 * Esporta anche helper `calcolaSaturazioneTask` per riuso in altri punti.
 */

export function calcolaSaturazioneTask({ oreStimate, dataInizio, dataFine, dipendente }) {
  if (!oreStimate || !dataInizio || !dataFine) return null
  if (dataFine < dataInizio) return null
  const gg = giorniLavorativi(dataInizio, dataFine)
  if (gg === 0) {
    return { tipo: 'no_giorni_lavorativi', giorni: 0 }
  }
  const oreGior = dipendente ? (dipendente.ore_sett / 5) : 8
  const capacita = gg * oreGior
  const saturazione = (Number(oreStimate) / capacita) * 100
  return {
    tipo: 'normale',
    giorni: gg,
    oreGiornaliere: oreGior,
    capacita,
    saturazionePct: Math.round(saturazione),
  }
}

function IndicatoreCapacita({ oreStimate, dataInizio, dataFine, dipendente }) {
  const r = calcolaSaturazioneTask({ oreStimate, dataInizio, dataFine, dipendente })
  if (!r) return null

  if (r.tipo === 'no_giorni_lavorativi') {
    return (
      <div className="mt-1 text-xs text-amber-300 italic">
        ⚠ Periodo senza giorni lavorativi (solo weekend e/o festività)
      </div>
    )
  }

  const { giorni, capacita, saturazionePct, oreGiornaliere } = r
  let livello, icona, msg
  if (saturazionePct <= 100) {
    livello = 'text-green-300'
    icona = '✓'
    msg = `${oreStimate}h in ${giorni} ${giorni === 1 ? 'giorno' : 'giorni'} lavorativ${giorni === 1 ? 'o' : 'i'} (capacità ${capacita}h) — saturazione ${saturazionePct}%`
  } else if (saturazionePct <= 125) {
    livello = 'text-orange-300'
    icona = '⚠'
    msg = `${oreStimate}h in ${giorni} ${giorni === 1 ? 'giorno' : 'giorni'} (capacità ${capacita}h) — saturazione ${saturazionePct}%, oltre il 100% — considera straordinario`
  } else {
    livello = 'text-red-400'
    icona = '⛔'
    msg = `${oreStimate}h in ${giorni} ${giorni === 1 ? 'giorno' : 'giorni'} (capacità ${capacita}h) — saturazione ${saturazionePct}%, irrealistico (${oreGiornaliere}h/giorno disponibili)`
  }
  return (
    <div className={`mt-1 text-xs ${livello}`}>
      {icona} {msg}
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════
// PannelloSaturazione — saturazione live del dipendente (Step 2.4-bis A)
// ═════════════════════════════════════════════════════════════════════════

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
  if (stato.loading) return <div className="mt-2 text-xs text-gray-500 italic">Calcolo saturazione…</div>
  if (stato.errore) return <div className="mt-2 text-xs text-red-400">Errore saturazione: {stato.errore}</div>
  if (!stato.dati) return null

  const d = stato.dati
  const sat = d.saturazione_media_pct

  // Soglie allineate alla heatmap SatCell di Risorse.jsx (handoff v16 §14.4)
  let livello, cls
  if (sat < 90) { livello = 'ok'; cls = 'bg-green-900/30 border-green-700 text-green-200' }
  else if (sat < 100) { livello = 'attenzione'; cls = 'bg-yellow-900/30 border-yellow-700 text-yellow-200' }
  else if (sat <= 125) { livello = 'sovraccarico'; cls = 'bg-orange-900/40 border-orange-700 text-orange-200' }
  else if (sat <= 150) { livello = 'critico'; cls = 'bg-red-900/40 border-red-700 text-red-200' }
  else { livello = 'critico-grave'; cls = 'bg-red-800/60 border-red-600 text-red-100 font-semibold' }

  const icona = livello === 'ok' ? '✓' : livello === 'attenzione' ? '⚠' : livello === 'sovraccarico' ? '⚠' : '⛔'

  const piccoOltreCap = d.saturazione_max_pct > 125 && sat <= 125

  return (
    <div className={`mt-2 border rounded-md px-3 py-2 text-xs ${cls}`}>
      <div className="flex items-center justify-between mb-1">
        <span className="font-semibold">{icona} {d.nome} · {d.ore_sett}h/sett</span>
        <span className="font-mono">media {sat}%  ·  picco {d.saturazione_max_pct}%</span>
      </div>
      <div className="opacity-80">
        Saturazione nelle {d.settimane_coperte} settimane del task
        {sat > 150 && <strong> — ⚠ critico (oltre 150%)</strong>}
        {sat > 125 && sat <= 150 && <strong> — oltre il soft cap (125%), considera redistribuzione</strong>}
        {piccoOltreCap && <span className="italic"> — picco oltre soft cap in almeno una settimana</span>}
      </div>
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════
// ModaleNuovaFase
// ═════════════════════════════════════════════════════════════════════════

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

// ═════════════════════════════════════════════════════════════════════════
// ModaleTask — creazione/modifica task con PannelloSaturazione integrato
// ═════════════════════════════════════════════════════════════════════════

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

    // Verifica capacità: se saturazione > 125%, chiedi conferma esplicita
    // prima di salvare (handoff v16 §14.3, non bloccante con attrito).
    const dipendente = dipendenti.find(d => d.id === form.dipendente_id)
    const stima = calcolaSaturazioneTask({
      oreStimate: form.ore_stimate,
      dataInizio: form.data_inizio,
      dataFine: form.data_fine,
      dipendente,
    })
    if (stima && stima.tipo === 'normale' && stima.saturazionePct > 125) {
      const oreGiornoRichieste = Math.round(Number(form.ore_stimate) / stima.giorni)
      const ok = window.confirm(
        `Attenzione: questo task ha saturazione del ${stima.saturazionePct}% rispetto alla capacità.\n\n` +
        `${form.ore_stimate}h in ${stima.giorni} ${stima.giorni === 1 ? 'giorno lavorativo' : 'giorni lavorativi'} ` +
        `richiederebbero ${oreGiornoRichieste}h/giorno, oltre il limite di ${stima.oreGiornaliere}h/giorno disponibili.\n\n` +
        `Salvo comunque? Verrà segnalato in Consuntivazione per riconciliazione a valle.`
      )
      if (!ok) return
    }
    
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
          <div>
            <FormInput label="Ore stimate" type="number" value={form.ore_stimate} onChange={v => setForm({...form, ore_stimate: v})} />
            <IndicatoreCapacita
              oreStimate={form.ore_stimate}
              dataInizio={form.data_inizio}
              dataFine={form.data_fine}
              dipendente={dipendenti.find(d => d.id === form.dipendente_id)}
            />
          </div>
          <FormSelect label="Stato" value={form.stato} onChange={v => setForm({...form, stato: v})} options={STATI_TASK} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <FormInputDate
            label="Data inizio"
            value={form.data_inizio}
            onChange={v => setForm({...form, data_inizio: v})}
            minDate={mode === 'nuovo'
              ? (faseDataInizio && faseDataInizio > new Date().toISOString().slice(0,10)
                 ? faseDataInizio
                 : new Date().toISOString().slice(0,10))
              : faseDataInizio}
            maxDate={faseDataFine}
            hint={mode === 'nuovo'
              ? `Fase: ${faseDataInizio || '?'} → ${faseDataFine || '?'} · Non puoi pianificare nel passato`
              : (faseDataInizio ? `Fase: ${faseDataInizio} → ${faseDataFine || '?'}` : '')}
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

// ═════════════════════════════════════════════════════════════════════════
// ModaleWrapper — overlay generico per le modali
// ═════════════════════════════════════════════════════════════════════════

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
