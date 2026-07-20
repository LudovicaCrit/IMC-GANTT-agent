import React, { useState, useEffect, useMemo } from 'react'
import { apiFetch } from '../api'

/* ── Helpers ──────────────────────────────────────────────────────── */
const fmtH = (n) => `${(n ?? 0).toFixed(1).replace('.0', '')}h`

/* ── Tooltip campi (frasi congelate nel design A') ─────────────────── */
const TOOLTIP = {
  iniziale: 'Le ore stimate per questo task all\'inizio del progetto. Riferimento storico, non cambia.',
  pianificate: 'Le ore programmate per te su questo task in questa settimana.',
  consumate: 'Le ore che hai effettivamente lavorato su questo task in questa settimana.',
  rimanenti: 'Quante ore mancano per completare il task. Si calcola da sé, ma puoi modificarla se la stima iniziale era sbagliata.',
}

function Th({ children, tip, align = 'right' }) {
  return (
    <th className={`px-4 py-3 text-${align} font-medium`}>
      <span className="inline-flex items-center gap-1">
        {children}
        {tip && (
          <span
            title={tip}
            className="text-gray-600 cursor-help text-[10px] border border-gray-600 rounded-full w-3.5 h-3.5 inline-flex items-center justify-center"
          >
            ?
          </span>
        )}
      </span>
    </th>
  )
}

/* ── Pagina ───────────────────────────────────────────────────────── */
export default function ConsuntivazioneUser() {
  const [dati, setDati] = useState(null)
  const [loading, setLoading] = useState(true)
  const [errore, setErrore] = useState(null)
  const [ore, setOre] = useState({}) // { task_id: valore }

  useEffect(() => {
    apiFetch('/api/consuntivi/me')
      .then((d) => {
        setDati(d)
        const iniziali = {}
        for (const t of d.task_settimana ?? []) {
          iniziali[t.task_id] = t.ore_consumate || ''
        }
        setOre(iniziali)
      })
      .catch((e) => setErrore(e.message))
      .finally(() => setLoading(false))
  }, [])

  // Raggruppa i task per progetto, mantenendo l'ordine di arrivo
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

  const totali = useMemo(() => {
    const task = dati?.task_settimana ?? []
    const pianificate = task.reduce((s, t) => s + (t.ore_pianificate_settimana ?? 0), 0)
    const consumate = Object.values(ore).reduce((s, v) => s + (parseFloat(v) || 0), 0)
    return { pianificate, consumate, restanti: Math.max(0, pianificate - consumate) }
  }, [dati, ore])

  if (loading) return <p className="text-gray-400">Caricamento…</p>
  if (errore) return <p className="text-red-400">Errore: {errore}</p>
  if (!dati) return null

  const nome = dati.nome?.split(' ')[0] ?? ''

  return (
    <div className="max-w-6xl">
      <h1 className="text-3xl font-bold mb-1">⏱️ Consuntivazione</h1>

      <div className="flex items-start justify-between mb-6">
        <p className="text-gray-400">
          Ciao {nome} — ecco cosa era previsto per te questa settimana.
        </p>

        {/* ═══ Agganci IA — segnaposto, non ancora collegati ═══
            Il form resta lo strumento primario: l'IA è uno strato di
            supporto (compila su dettatura, spiega i campi, aiuta a
            ricordare), non un canale parallelo. */}
        <div className="flex gap-2 shrink-0">
          <button
            disabled
            title="In arrivo: detta cosa hai fatto, l'assistente compila i campi per te"
            className="px-3 py-2 rounded-lg text-sm font-medium bg-gray-800 text-gray-500
                       border border-gray-700 cursor-not-allowed inline-flex items-center gap-2"
          >
            🎙️ Modalità vocale
          </button>
          <button
            disabled
            title="In arrivo: assistente che spiega i campi e aiuta a ricostruire la settimana"
            className="px-3 py-2 rounded-lg text-sm font-medium bg-gray-800 text-gray-500
                       border border-gray-700 cursor-not-allowed inline-flex items-center gap-2"
          >
            💬 Apri assistente
          </button>
        </div>
      </div>

      {/* ═══ Riquadri di sintesi ═══ */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Pianificate</p>
          <p className="text-2xl font-bold mt-1 text-blue-300">{fmtH(totali.pianificate)}</p>
          <p className="text-xs text-gray-500 mt-0.5">su {dati.ore_contrattuali}h contrattuali</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Consumate finora</p>
          <p className="text-2xl font-bold mt-1 text-green-400">{fmtH(totali.consumate)}</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Da compilare</p>
          <p className="text-2xl font-bold mt-1 text-amber-300">{fmtH(totali.restanti)}</p>
          <p className="text-xs text-gray-500 mt-0.5">rispetto al pianificato</p>
        </div>
      </div>

      {/* ═══ Tabella ═══ */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-800 text-gray-400">
            <tr>
              <th className="px-4 py-3 text-left font-medium">Task</th>
              <Th tip={TOOLTIP.iniziale}>Iniziale</Th>
              <Th tip={TOOLTIP.pianificate}>Pianificate</Th>
              <Th tip={TOOLTIP.consumate} align="center">Consumate</Th>
              <Th tip={TOOLTIP.rimanenti}>Rimanenti</Th>
            </tr>
          </thead>
          <tbody>
            {gruppi.map((g) => (
              <React.Fragment key={g.progetto_id}>
                {/* Intestazione progetto */}
                <tr className="bg-gray-800/40 border-t border-gray-800">
                  <td colSpan={5} className="px-4 py-2">
                    <span className="inline-flex items-center gap-2">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] uppercase tracking-wider font-medium ${
                          g.interna
                            ? 'bg-gray-700 text-gray-300'
                            : 'bg-blue-900/50 text-blue-300 border border-blue-800'
                        }`}
                      >
                        {g.interna ? 'Interna' : 'Progetto'}
                      </span>
                      <span className="font-medium text-gray-200">{g.progetto_nome}</span>
                    </span>
                  </td>
                </tr>

                {/* Righe task */}
                {g.task.map((t) => {
                  const quota = t.ore_pianificate_settimana
                  const sforato = (t.ore_rimanenti ?? 0) < 0
                  return (
                    <tr key={t.task_id} className="border-t border-gray-800/60 hover:bg-gray-800/30">
                      <td className="px-4 py-3">
                        <p className="text-gray-200">{t.task_nome}</p>
                        <p className="text-xs text-gray-600">
                          {t.task_id} · {t.stato}
                        </p>
                      </td>

                      {/* Iniziale */}
                      <td className="px-4 py-3 text-right text-gray-500">{fmtH(t.ore_iniziale)}</td>

                      {/* Pianificate: quota settimana in evidenza, totale sotto */}
                      <td className="px-4 py-3 text-right">
                        {quota === null || quota === undefined ? (
                          <span className="text-gray-600">—</span>
                        ) : (
                          <>
                            <span className="inline-block px-2 py-0.5 rounded-md bg-blue-900/40 text-blue-300 font-semibold">
                              {quota < 0.5 && quota > 0 ? '<1h' : fmtH(quota)}
                            </span>
                            <p className="text-[11px] text-gray-600 mt-1">
                              su {fmtH(t.ore_pianificate)} totali
                            </p>
                          </>
                        )}
                      </td>

                      {/* Consumate: unico campo editabile */}
                      <td className="px-4 py-3 text-center">
                        <input
                          type="number"
                          min="0"
                          step="0.5"
                          value={ore[t.task_id] ?? ''}
                          onChange={(e) =>
                            setOre((prev) => ({ ...prev, [t.task_id]: e.target.value }))
                          }
                          placeholder="0"
                          className="w-20 bg-white text-gray-900 rounded-md px-2 py-1.5 text-center
                                     font-medium border border-gray-300
                                     focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </td>

                      {/* Rimanenti */}
                      <td
                        className={`px-4 py-3 text-right ${
                          sforato ? 'text-red-400 font-medium' : 'text-gray-500'
                        }`}
                      >
                        {sforato ? `−${fmtH(Math.abs(t.ore_rimanenti))}` : fmtH(t.ore_rimanenti)}
                        {sforato && <p className="text-[11px] text-red-500/70">oltre il previsto</p>}
                      </td>
                    </tr>
                  )
                })}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-gray-600 mt-4">
        Il salvataggio non è ancora collegato — questa è una vista di anteprima del layout.
      </p>
    </div>
  )
}
