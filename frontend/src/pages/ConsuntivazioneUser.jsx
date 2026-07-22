import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { apiFetch } from '../api'

/* ── Costanti ─────────────────────────────────────────────────────── */
const STATI = ['In corso', 'Completato', 'Bloccato']

const STATO_STYLE = {
  'In corso':   { on: 'bg-blue-600 text-white border-blue-500',      off: 'text-blue-300/60 border-gray-700 hover:border-blue-800' },
  'Completato': { on: 'bg-emerald-600 text-white border-emerald-500', off: 'text-emerald-300/60 border-gray-700 hover:border-emerald-800' },
  'Bloccato':   { on: 'bg-red-600 text-white border-red-500',        off: 'text-red-300/60 border-gray-700 hover:border-red-800' },
}

const TOOLTIP = {
  previste: 'Le ore programmate per te su questo task in questa settimana.',
  ore: 'Quante ore ci hai messo, se te lo ricordi. Campo facoltativo.',
}

/* ── Helpers ──────────────────────────────────────────────────────── */
const fmtH = (n) => `${(n ?? 0).toFixed(1).replace(/\.0$/, '')}h`

const fmtData = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('it-IT', { day: 'numeric', month: 'short' })
}

/* ── Pagina ───────────────────────────────────────────────────────── */
export default function ConsuntivazioneUser() {
  const [dati, setDati] = useState(null)
  const [loading, setLoading] = useState(true)
  const [errore, setErrore] = useState(null)
  const [salvataggio, setSalvataggio] = useState(null) // null | 'invio' | 'ok' | messaggio errore

  const [settimanaSel, setSettimanaSel] = useState(null)

  // Modifiche pendenti: { [task_id]: { stato?, ore?, nota? } }
  const [modifiche, setModifiche] = useState({})
  const [noteAperte, setNoteAperte] = useState({})

  /* ── Caricamento ── */
  const carica = useCallback((settimana) => {
    setLoading(true)
    const url = settimana
      ? `/api/consuntivi/me?settimana=${settimana}`
      : '/api/consuntivi/me'
    apiFetch(url)
      .then((d) => {
        setDati(d)
        setSettimanaSel(d.settimana)
        setModifiche({})
        setNoteAperte({})
        setSalvataggio(null)
      })
      .catch((e) => setErrore(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { carica(null) }, [carica])

  /* ── Avviso se si esce con modifiche pendenti ── */
  const haPendenti = Object.keys(modifiche).length > 0
  useEffect(() => {
    if (!haPendenti) return
    const handler = (e) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [haPendenti])

  /* ── Stato/valori correnti di un task (modifica pendente o valore dal server) ── */
  const valore = (t, campo) => {
    const m = modifiche[t.task_id]
    if (m && m[campo] !== undefined) return m[campo]
    if (campo === 'stato') return STATI.includes(t.stato_dichiarato) ? t.stato_dichiarato : null
    if (campo === 'ore') return t.ore_consumate || ''
    if (campo === 'nota') return t.nota ?? ''
    return undefined
  }

  const modifica = (task_id, campo, val) => {
    setModifiche((prev) => ({
      ...prev,
      [task_id]: { ...(prev[task_id] ?? {}), [campo]: val },
    }))
    setSalvataggio(null)
  }

  /* ── Raggruppamento per progetto ── */
  const gruppi = useMemo(() => {
    const map = new Map()
    for (const t of dati?.task_settimana ?? []) {
      if (!map.has(t.progetto_id)) {
        map.set(t.progetto_id, {
          progetto_id: t.progetto_id,
          progetto_nome: t.progetto_nome,
          interna: t.interna,
          task: [],
        })
      }
      map.get(t.progetto_id).task.push(t)
    }
    return [...map.values()]
  }, [dati])

  /* ── Totali ── */
  const totali = useMemo(() => {
    const task = dati?.task_settimana ?? []
    const previste = task.reduce((s, t) => s + (t.ore_pianificate_settimana ?? 0), 0)
    const dichiarate = task.reduce((s, t) => s + (parseFloat(valore(t, 'ore')) || 0), 0)
    const dichiarati = task.filter((t) => {
      const m = modifiche[t.task_id]
      if (m && m.stato !== undefined) return m.stato !== null
      return t.stato_dichiarato != null
    }).length
    return { previste, dichiarate, dichiarati, totale: task.length }
  }, [dati, modifiche])

  /* ── Settimana corrente selezionabile? ── */
  const settimanaInfo = dati?.settimane_disponibili?.find((s) => s.lunedi === dati?.settimana)
  const soloLettura = settimanaInfo ? !settimanaInfo.compilabile : false

  /* ── Salvataggio ── */
  const salva = async () => {
    if (!haPendenti || soloLettura) return

    // Validazione: Bloccato richiede nota
    for (const t of dati.task_settimana) {
      const stato = valore(t, 'stato')
      const nota = (valore(t, 'nota') ?? '').trim()
      if (stato === 'Bloccato' && !nota) {
        setSalvataggio(`"${t.task_nome}" è bloccato: scrivi perché nella nota.`)
        setNoteAperte((p) => ({ ...p, [t.task_id]: true }))
        return
      }
    }

    setSalvataggio('invio')

    const ore_per_task = {}
    const stati_per_task = {}
    const note_per_task = {}

    for (const [task_id, m] of Object.entries(modifiche)) {
      if (m.ore !== undefined) ore_per_task[task_id] = parseFloat(m.ore) || 0
      if (m.stato !== undefined && m.stato !== null) stati_per_task[task_id] = m.stato
      if (m.nota !== undefined) note_per_task[task_id] = m.nota
    }

    try {
      await apiFetch('/api/consuntivi/salva', {
        method: 'POST',
        body: {
          dipendente_id: dati.dipendente_id,
          settimana: dati.settimana,
          ore_per_task,
          stati_per_task,
          note_per_task,
        },
      })
      setSalvataggio('ok')
      carica(dati.settimana)
    } catch (e) {
      const msg =
        typeof e === 'string' ? e
        : e?.detail ? (typeof e.detail === 'string' ? e.detail : JSON.stringify(e.detail))
        : e?.message ? e.message
        : JSON.stringify(e)
      setSalvataggio(msg)
      console.error('Salvataggio fallito:', e)
    }
  }

  /* ── Render ── */
  if (loading) return <p className="text-gray-400">Caricamento…</p>
  if (errore) return <p className="text-red-400">Errore: {errore}</p>
  if (!dati) return null

  const nome = dati.nome?.split(' ')[0] ?? ''

  return (
    <div className="max-w-6xl pb-24">
      <h1 className="text-3xl font-bold mb-1">⏱️ Consuntivazione</h1>

      <div className="flex items-start justify-between mb-6">
        <p className="text-gray-400">
          Ciao {nome} — ecco cosa era in programma per te.
        </p>

        {/* Agganci IA — segnaposto, non ancora collegati */}
        <div className="flex gap-2 shrink-0">
          <button disabled
            title="In arrivo: detta cosa hai fatto, l'assistente compila per te"
            className="px-3 py-2 rounded-lg text-sm font-medium bg-gray-800 text-gray-500 border border-gray-700 cursor-not-allowed">
            🎙️ Modalità vocale
          </button>
          <button disabled
            title="In arrivo: assistente che aiuta a ricostruire la settimana"
            className="px-3 py-2 rounded-lg text-sm font-medium bg-gray-800 text-gray-500 border border-gray-700 cursor-not-allowed">
            💬 Apri assistente
          </button>
        </div>
      </div>

      {/* ═══ Selettore settimana ═══ */}
      <div className="flex items-center gap-2 mb-6">
        {dati.settimane_disponibili?.map((s) => {
          const attiva = s.lunedi === dati.settimana
          return (
            <button
              key={s.lunedi}
              onClick={() => {
                if (haPendenti && !confirm('Hai modifiche non salvate. Cambiare settimana le perderà. Continuare?')) return
                carica(s.lunedi)
              }}
              className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                attiva
                  ? 'bg-gray-700 text-white border-gray-600'
                  : 'bg-gray-900 text-gray-400 border-gray-800 hover:text-gray-200'
              }`}
            >
              {s.etichetta}
              {!s.compilabile && <span className="ml-2 text-[10px] text-gray-500">già chiusa</span>}
            </button>
          )
        })}
      </div>

      {soloLettura && (
        <div className="bg-gray-800/60 border border-gray-700 rounded-lg px-4 py-3 mb-6">
          <p className="text-sm text-gray-300">
            Questa settimana è già stata compilata: puoi consultarla, ma non modificarla.
          </p>
        </div>
      )}

      {/* ═══ Riquadri di sintesi ═══ */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Dichiarati ora</p>
          <p className="text-2xl font-bold mt-1">
            {totali.dichiarati}<span className="text-gray-500 text-lg"> / {totali.totale}</span>
          </p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Ore previste</p>
          <p className="text-2xl font-bold mt-1 text-blue-300">{fmtH(totali.previste)}</p>
          <p className="text-xs text-gray-500 mt-0.5">su {dati.ore_contrattuali}h contrattuali</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Ore dichiarate</p>
          <p className="text-2xl font-bold mt-1 text-green-400">{fmtH(totali.dichiarate)}</p>
          <p className="text-xs text-gray-500 mt-0.5">facoltative</p>
        </div>
      </div>

      {/* ═══ Tabella ═══ */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-800 text-gray-400">
            <tr>
              <th className="px-4 py-3 text-left font-medium">Task</th>
              <th className="px-4 py-3 text-right font-medium">
                <span title={TOOLTIP.previste} className="cursor-help">Previste</span>
              </th>
              <th className="px-4 py-3 text-center font-medium">A che punto sei?</th>
              <th className="px-4 py-3 text-center font-medium">
                <span title={TOOLTIP.ore} className="cursor-help">Ore</span>
              </th>
              <th className="px-3 py-3 text-center font-medium w-12">Nota</th>
            </tr>
          </thead>
          <tbody>
            {gruppi.map((g) => (
              <React.Fragment key={g.progetto_id}>
                {/* Intestazione progetto */}
                <tr className="bg-gray-800/40 border-t border-gray-800">
                  <td colSpan={5} className="px-4 py-2">
                    <span className="inline-flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-[10px] uppercase tracking-wider font-medium ${
                        g.interna
                          ? 'bg-gray-700 text-gray-300'
                          : 'bg-blue-900/50 text-blue-300 border border-blue-800'
                      }`}>
                        {g.interna ? 'Interna' : 'Progetto'}
                      </span>
                      <span className="font-medium text-gray-200">{g.progetto_nome}</span>
                    </span>
                  </td>
                </tr>

                {/* Righe task */}
                {g.task.map((t) => {
                  const statoSel = valore(t, 'stato')
                  const nota = valore(t, 'nota') ?? ''
                  const haNota = nota.trim().length > 0
                  const aperta = noteAperte[t.task_id]
                  const statoNonDichiarabile = !STATI.includes(t.stato)

                  return (
                    <React.Fragment key={t.task_id}>
                      <tr className={`border-t border-gray-800/60 ${
                        modifiche[t.task_id] ? 'bg-amber-950/20' : ''
                      }`}>
                        {/* Task */}
                        <td className="px-4 py-3">
                          <p className="text-gray-200">{t.task_nome}</p>
                          <p className="text-xs text-gray-600 flex items-center gap-2">
                            <span>{t.task_id}</span>
                            <span className="text-gray-500">· attualmente {t.stato}</span>
                            {t.in_ritardo && (
                              <span className="text-amber-500/80">· ⚠ oltre la data prevista</span>
                            )}
                          </p>
                        </td>

                        {/* Previste */}
                        <td className="px-4 py-3 text-right">
                          {t.ore_pianificate_settimana === null ? (
                            <span className="text-gray-600">—</span>
                          ) : (
                            <>
                              <span className="text-blue-300 font-medium">
                                {t.ore_pianificate_settimana < 0.5 && t.ore_pianificate_settimana > 0
                                  ? '<1h'
                                  : fmtH(t.ore_pianificate_settimana)}
                              </span>
                              <p className="text-[11px] text-gray-600">
                                su {fmtH(t.ore_pianificate)} totali
                              </p>
                            </>
                          )}
                        </td>

                        {/* Stato — azione principale */}
                        <td className="px-4 py-3">
                          <div className="flex gap-1 justify-center">
                            {STATI.map((s) => {
                              const sel = statoSel === s
                              const st = STATO_STYLE[s]
                              return (
                                <button
                                  key={s}
                                  disabled={soloLettura}
                                  onClick={() => {
                                    modifica(t.task_id, 'stato', sel ? null : s)
                                    if (s === 'Bloccato' && !sel) {
                                      setNoteAperte((p) => ({ ...p, [t.task_id]: true }))
                                    }
                                  }}
                                  className={`px-2.5 py-1.5 rounded-md text-xs font-medium border transition-colors
                                              ${sel ? st.on : st.off} ${soloLettura ? 'opacity-50 cursor-not-allowed' : ''}`}
                                >
                                  {s === 'Completato' ? 'Fatto' : s}
                                </button>
                              )
                            })}
                          </div>
                        </td>

                        {/* Ore — facoltative */}
                        <td className="px-4 py-3 text-center">
                          <input
                            type="number" min="0" step="0.5"
                            disabled={soloLettura}
                            value={valore(t, 'ore')}
                            onChange={(e) => modifica(t.task_id, 'ore', e.target.value)}
                            placeholder="—"
                            className="w-16 bg-gray-950 text-gray-200 rounded-md px-2 py-1.5 text-center
                                       border border-gray-700 focus:outline-none focus:ring-2
                                       focus:ring-blue-600 focus:border-blue-600
                                       disabled:opacity-50 placeholder:text-gray-700"
                          />
                        </td>

                        {/* Icona nota */}
                        <td className="px-3 py-3 text-center">
                          <button
                            onClick={() => setNoteAperte((p) => ({ ...p, [t.task_id]: !aperta }))}
                            title={haNota ? 'Nota presente' : 'Aggiungi una nota'}
                            className={`w-7 h-7 rounded-md border transition-colors ${
                              haNota
                                ? 'bg-amber-900/30 border-amber-700/60 text-amber-300'
                                : 'border-gray-700 text-gray-600 hover:text-gray-400'
                            }`}
                          >
                            {haNota ? '✎' : '+'}
                          </button>
                        </td>
                      </tr>

                      {/* Riga nota espansa */}
                      {aperta && (
                        <tr className="border-t border-gray-800/30">
                          <td colSpan={5} className="px-4 pb-3 pt-0 bg-gray-800/20">
                            <textarea
                              rows={2}
                              disabled={soloLettura}
                              value={nota}
                              onChange={(e) => modifica(t.task_id, 'nota', e.target.value)}
                              placeholder={
                                statoSel === 'Bloccato'
                                  ? 'Perché è bloccato? (obbligatorio)'
                                  : 'A che punto sei? Cosa hai fatto?'
                              }
                              className={`w-full bg-gray-950 text-gray-200 rounded-md px-3 py-2 text-sm
                                          border focus:outline-none focus:ring-2 focus:ring-blue-600
                                          placeholder:text-gray-600 disabled:opacity-50 ${
                                            statoSel === 'Bloccato' && !nota.trim()
                                              ? 'border-red-800'
                                              : 'border-gray-700'
                                          }`}
                            />
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  )
                })}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* ═══ Barra di salvataggio fissa ═══ */}
      {!soloLettura && (
        <div className="fixed bottom-0 left-0 right-0 border-t backdrop-blur"
             style={{ backgroundColor: 'rgba(17,24,39,0.92)', borderColor: 'var(--color-border-subtle, #1f2937)' }}>
          <div className="max-w-6xl mx-auto px-8 py-3 flex items-center justify-between">
            <div className="text-sm">
              {salvataggio === 'ok' && <span className="text-green-400">✓ Salvato</span>}
              {salvataggio === 'invio' && <span className="text-gray-400">Salvataggio…</span>}
              {salvataggio && !['ok', 'invio'].includes(salvataggio) && (
                <span className="text-red-400">{salvataggio}</span>
              )}
              {!salvataggio && haPendenti && (
                <span className="text-amber-300">
                  {Object.keys(modifiche).length} {Object.keys(modifiche).length === 1 ? 'modifica' : 'modifiche'} da salvare
                </span>
              )}
              {!salvataggio && !haPendenti && (
                <span className="text-gray-600">Nessuna modifica</span>
              )}
            </div>

            <button
              onClick={salva}
              disabled={!haPendenti || salvataggio === 'invio'}
              className="px-5 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white
                         hover:bg-blue-500 disabled:bg-gray-800 disabled:text-gray-600
                         disabled:cursor-not-allowed transition-colors"
            >
              Salva
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
