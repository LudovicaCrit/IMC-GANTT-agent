/**
 * ═════════════════════════════════════════════════════════════════════════
 * SezioneSAL.jsx — Le fotografie di un progetto (SAL)
 * ═════════════════════════════════════════════════════════════════════════
 *
 * Un SAL è uno stato del progetto CONGELATO in un istante: progetto, fasi,
 * task, ore, date e stati come erano quel giorno. Non è un backup e non si
 * ricalcola — è un atto, e per questo si consolida a mano.
 *
 * PRIMO CLIENTE DI UN BACKEND SCRITTO NEL GIUGNO 2026. I sei endpoint SAL
 * esistevano, funzionavano e non erano mai stati chiamati da nessuna parte:
 * `api.js` non aveva una sola funzione, nessuna pagina li consumava, e in
 * tabella c'erano zero snapshot. Non era un bug — era un pilastro eretto e mai
 * acceso. Questo componente è l'interruttore.
 *
 * ── TRE PARTI, IN QUEST'ORDINE ───────────────────────────────────────
 *   1. il gesto      — «Consolida SAL», con la nota del perché
 *   2. lo storico    — le fotografie fatte, la più recente in cima
 *   3. l'apertura    — una fotografia aperta, in sola lettura
 *
 * ── LA NOTA NON È UN OPTIONAL DECORATIVO ─────────────────────────────
 * Il campo è facoltativo lato API, ma qui si chiede sempre: senza, lo storico
 * diventa una fila di date indistinguibili, e fra sei mesi nessuno saprà perché
 * quel 4 settembre valeva una fotografia. «Fine fase analisi», «prima del
 * cambio di scope» — è quella riga a rendere lo storico leggibile.
 *
 * ── PERCHÉ LA RESA È SEPARATA DAL CARICAMENTO ────────────────────────
 * `VistaSnapshot` riceve lo `stato` già caricato e lo disegna come tabella. La
 * Fase 2 (mini-GANTT dallo snapshot) sostituirà SOLO quel componente: i dati
 * che servono a disegnare le barre — `data_inizio`, `data_fine` e `stato` su
 * ogni fase e ogni task — sono già tutti nel JSONB, quindi non ci sarà nulla da
 * cambiare nel backend né nel caricamento. Tenere le due cose separate adesso
 * costa un componente in più e risparmia una riscrittura dopo.
 *
 * ── MANAGER-ONLY, ED È SOLO L'INTERFACCIA ────────────────────────────
 * Il pulsante compare se `ruolo_app === 'manager'`. Il BACKEND è più permissivo
 * — `_autorizza_progetto` ammette «manager OPPURE il PM di quel progetto», ed è
 * il design originale del SAL («consolidata su approvazione del PM»). Quindi un
 * pm che chiamasse l'API riuscirebbe: qui si nasconde il gesto finché la
 * matrice dei permessi-PM non è decisa, senza togliere al backend una capacità
 * che ha per progetto. La LISTA resta visibile a chiunque apra la pagina.
 */

import React, { useState, useEffect, useCallback } from 'react'
import { consolidaSAL, listaStoricoSAL, apriSnapshotSAL } from '../../api'
import StatoBadge from './StatoBadge'

const fmtDataOra = (iso) => {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('it-IT', { day: 'numeric', month: 'short', year: 'numeric' }) +
    ' · ' + d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })
}
const fmtH = (n) => (n == null ? '—' : `${Number(n).toLocaleString('it-IT')}h`)

/* ── La fotografia aperta ──────────────────────────────────────────────
 * QUESTO è il componente che la Fase 2 sostituirà: riceve `stato` (il JSONB) e
 * decide come disegnarlo. Oggi tabella per fase, con i task dentro; domani un
 * mini-GANTT, leggendo gli stessi `data_inizio`/`data_fine`/`stato`.
 *
 * Tutto in SOLA LETTURA, e si vede: nessun input, nessun bottone d'azione.
 * Una fotografia non si modifica — se i numeri sono sbagliati si corregge il
 * progetto e si scatta una foto nuova, non si ritocca quella vecchia.
 */
function VistaSnapshot({ snapshot }) {
  const stato = snapshot?.stato
  if (!stato) return null
  const p = stato.progetto ?? {}
  const fasi = stato.fasi ?? []
  const nTask = fasi.reduce((s, f) => s + (f.task?.length ?? 0), 0)

  return (
    <div className="mt-3 border-t border-border-default pt-3">
      {/* Intestazione: di CHE COSA è la fotografia e di QUANDO */}
      <div className="flex items-baseline justify-between gap-3 flex-wrap mb-1">
        <h4 className="text-sm font-semibold text-gray-100">{p.nome}</h4>
        <span className="text-[11px] text-gray-500">
          fotografia del {fmtDataOra(snapshot.data_snapshot)}
        </span>
      </div>
      <p className="text-[11px] text-gray-500 mb-3">
        {p.cliente && <>{p.cliente} · </>}
        stato <span className="text-gray-300">{p.stato}</span>
        {p.urgenza && <> · urgenza <span className="text-gray-300">{p.urgenza}</span></>}
        {p.pm_nome && <> · PM {p.pm_nome}</>}
        {' · '}{fasi.length} fasi · {nTask} task
        <span className="text-gray-600"> · schema v{stato.schema_version}</span>
      </p>

      <div className="space-y-2">
        {fasi.map((f) => (
          <div key={f.id} className="bg-surface-800/40 rounded-lg p-3">
            <div className="flex items-baseline justify-between gap-3 flex-wrap mb-1">
              <span className="text-sm text-gray-200">
                <span className="text-gray-600 font-data mr-1.5">{f.ordine}</span>
                {f.nome}
              </span>
              <span className="text-[11px] text-gray-500 flex items-center gap-2">
                <StatoBadge stato={f.stato} />
                <span className="font-data">
                  {fmtH(f.ore_consumate)}<span className="text-gray-600">/{fmtH(f.ore_vendute)}</span>
                </span>
                <span>{f.data_inizio || '?'} → {f.data_fine || '?'}</span>
              </span>
            </div>

            {(f.task ?? []).length > 0 && (
              <table className="w-full text-xs mt-1">
                <tbody>
                  {f.task.map((t) => (
                    <tr key={t.id} className="border-t border-border-subtle/60">
                      <td className="py-1 pr-2 text-gray-300">{t.nome}</td>
                      <td className="py-1 pr-2 text-gray-500 w-32 truncate">{t.dipendente_nome || '—'}</td>
                      <td className="py-1 pr-2 text-right font-data text-gray-400 w-24">
                        {fmtH(t.ore_consumate)}<span className="text-gray-600">/{fmtH(t.ore_pianificate)}</span>
                      </td>
                      <td className="py-1 pr-2 text-gray-500 w-40 hidden sm:table-cell">
                        {t.data_inizio || '?'} → {t.data_fine || '?'}
                      </td>
                      <td className="py-1 w-24"><StatoBadge stato={t.stato} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function SezioneSAL({ progettoId, isManager }) {
  const [storico, setStorico] = useState([])
  const [aperto, setAperto] = useState(null)      // lo snapshot caricato
  const [caricando, setCaricando] = useState(true)
  const [occupato, setOccupato] = useState(false)
  const [errore, setErrore] = useState(null)
  const [nota, setNota] = useState('')
  const [formAperto, setFormAperto] = useState(false)

  const ricarica = useCallback(async () => {
    try {
      setStorico(await listaStoricoSAL(progettoId))
      setErrore(null)
    } catch (e) {
      setErrore(e.message || 'Errore nel caricamento dello storico')
    } finally {
      setCaricando(false)
    }
  }, [progettoId])

  useEffect(() => { ricarica() }, [ricarica])

  const consolida = async () => {
    setOccupato(true)
    setErrore(null)
    try {
      const nuovo = await consolidaSAL(progettoId, nota.trim() || null)
      setNota('')
      setFormAperto(false)
      await ricarica()
      // Si apre subito la fotografia appena scattata: è ciò che si vuole
      // vedere dopo aver premuto, e risparmia un click per verificare che
      // sia venuta bene.
      apri(nuovo.id)
    } catch (e) {
      setErrore(e.message || 'Consolidamento non riuscito')
    } finally {
      setOccupato(false)
    }
  }

  const apri = async (id) => {
    if (aperto?.id === id) { setAperto(null); return }   // ri-click = chiudi
    setOccupato(true)
    try {
      setAperto(await apriSnapshotSAL(id))
    } catch (e) {
      setErrore(e.message || 'Non riesco ad aprire la fotografia')
    } finally {
      setOccupato(false)
    }
  }

  if (caricando) return <p className="text-sm text-gray-500">Carico lo storico…</p>

  return (
    <div className="card p-5">
      <div className="flex items-baseline justify-between gap-3 flex-wrap mb-1">
        <h2 className="text-lg font-semibold text-gray-100">SAL — le fotografie</h2>
        {isManager && !formAperto && (
          <button
            onClick={() => setFormAperto(true)}
            disabled={occupato}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg
                       text-sm font-medium disabled:opacity-40"
          >
            📸 Consolida SAL
          </button>
        )}
      </div>
      <p className="text-xs text-gray-500 mb-3">
        Uno stato del progetto congelato a una data. Si scatta quando serve —
        fine fase, cambio di scope — anche a progetto in corso.
      </p>

      {errore && (
        <div className="text-xs bg-red-900/30 border border-red-800 text-red-200 rounded-md px-3 py-2 mb-3">
          {errore}
        </div>
      )}

      {/* Il form: la nota si chiede PRIMA di consolidare, non dopo. */}
      {formAperto && (
        <div className="bg-surface-800/60 rounded-lg p-3 mb-3">
          <label className="block text-xs text-gray-400 mb-1">
            Perché consolidi adesso? <span className="text-gray-600">(es. «fine fase analisi»)</span>
          </label>
          <div className="flex gap-2">
            <input
              value={nota}
              onChange={(e) => setNota(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') consolida() }}
              placeholder="Motivo della fotografia"
              autoFocus
              className="flex-1 min-w-0 bg-gray-950 text-gray-200 rounded px-2 py-1.5 text-sm
                         border border-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-600
                         placeholder:text-gray-600"
            />
            <button onClick={consolida} disabled={occupato}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm
                         font-medium disabled:opacity-40 shrink-0">
              {occupato ? '…' : 'Consolida'}
            </button>
            <button onClick={() => { setFormAperto(false); setNota('') }} disabled={occupato}
              className="px-2 text-sm text-gray-500 hover:text-gray-300 shrink-0">✗</button>
          </div>
        </div>
      )}

      {/* Lo storico */}
      {storico.length === 0 ? (
        <p className="text-sm text-gray-500 italic">
          Nessuna fotografia ancora
          {isManager ? ' — premi «Consolida SAL» per la prima.' : '.'}
        </p>
      ) : (
        <ul className="space-y-1">
          {storico.map((s) => {
            const attivo = aperto?.id === s.id
            return (
              <li key={s.id}>
                <button
                  onClick={() => apri(s.id)}
                  disabled={occupato}
                  className={`w-full text-left flex items-baseline gap-3 px-3 py-2 rounded-lg
                              transition-colors disabled:opacity-50 ${
                                attivo ? 'bg-surface-800' : 'hover:bg-white/[0.03]'
                              }`}
                >
                  <span className="text-gray-600 text-xs shrink-0">{attivo ? '▼' : '▶'}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm text-gray-200">
                      {fmtDataOra(s.data_snapshot)}
                    </span>
                    <span className="block text-[11px] text-gray-500 truncate">
                      {s.consolidato_da_nome || s.consolidato_da || '—'}
                      {s.nota ? <> · <span className="italic">«{s.nota}»</span></> : null}
                    </span>
                  </span>
                  <span className="text-[10px] text-gray-600 font-data shrink-0">#{s.id}</span>
                </button>
                {attivo && <VistaSnapshot snapshot={aperto} />}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
