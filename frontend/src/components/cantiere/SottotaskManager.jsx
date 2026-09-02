/**
 * ═════════════════════════════════════════════════════════════════════════
 * SottotaskManager.jsx — Scomposizione di un task in sottotask (Cantiere)
 * ═════════════════════════════════════════════════════════════════════════
 *
 * Pannello in-riga che dà al PM l'interfaccia per SCOMPORRE un task nei pezzi
 * di lavoro su cui poi si dichiara. È il componente che fa NASCERE i sottotask:
 * il CRUD backend esiste dal 30/07/2026 ma non era mai stato chiamato, ed è la
 * ragione per cui in database non ne esisteva uno solo — e con essi restava
 * invisibile tutto il motore che ci gira sopra (avanzamento per pezzi, ore
 * derivate, semaforo di livello sottotask, presa-visione del fermo).
 *
 * AUTONOMO: si carica la propria lista all'apertura e la ricarica dopo ogni
 * modifica. Non riceve i pezzi dal payload del Cantiere e non li restituisce:
 * chi lo monta gli passa un `taskId` e nient'altro. Il GET porta anche il TASK
 * (nome, ore_pianificate, scostamento), quindi non serve duplicarli come prop —
 * e così i numeri mostrati sono sempre quelli che il backend ha appena
 * calcolato, non quelli dell'ultimo caricamento di pagina.
 *
 * COSA NON FA, in questo giro e per scelta:
 *   - l'OVERRIDE dell'assegnatario. Un pezzo eredita chi fa il task
 *     (`sottotask.dipendente_id or task.dipendente_id`), e il form non manda
 *     `dipendente_id`. Non è pigrizia: un pezzo assegnato a un'altra persona
 *     oggi non comparirebbe nella SUA Consuntivazione — `/me` parte dai task
 *     del dipendente, non dai pezzi — e nel form di chi ha il task apparirebbe
 *     in sola lettura. Nessuno dei due potrebbe dichiararlo. Prima si sistema
 *     `/me`, poi si espone l'override.
 *   - lo STATO alla creazione: un pezzo nasce sempre "Da iniziare", deciso dal
 *     backend. Poterlo creare già Annullato non vorrebbe dire niente.
 *
 * SEGNALA, NON IMPONE — è la disciplina che il backend ripete tre volte sulla
 * scomposizione, e vale anche qui: lo scostamento fra la somma dei pezzi e il
 * piano del task è un AVVISO. Niente blocco del salvataggio, niente
 * ribilanciamento automatico, nessun 422. Il PM vede i due numeri e decide.
 */

import React, { useState, useEffect, useCallback } from 'react'
import {
  listaSottotask,
  creaSottotask,
  modificaSottotask,
  riordinaSottotask,
  eliminaSottotask,
} from '../../api'
import { STATI_PIANIFICAZIONE_SOTTOTASK } from './_costanti'
import StatoBadge from '../_shared/StatoBadge'

const fmtH = (n) => (n == null ? '—' : `${n}h`)

/* ── Lo scostamento, reso secondo il suo segno ─────────────────────────
 * `differenza` = ore_pianificate_task − somma_stime_sottotask, la convenzione
 * di `ore_rimanenti` in routes/fasi.py: il positivo è il margine che resta, il
 * negativo lo sforo. Qui le due direzioni vogliono due letture diverse:
 *
 *   POSITIVA → piano non ancora coperto dai pezzi. È lo stato NORMALE mentre si
 *     scompone — si comincia da zero e si sale — e colorarlo di rosso
 *     insegnerebbe a ignorare l'avviso proprio mentre lo si sta usando. Neutro.
 *   NEGATIVA → i pezzi sforano il piano del task. Questa merita attenzione, ed
 *     è l'unica evidenziata.
 *   `null` → task mai scomposto o senza `ore_pianificate`: niente da dire, e la
 *     riga non compare affatto.
 */
function BandaScostamento({ scostamento }) {
  if (!scostamento) return null
  const { somma_stime_sottotask: somma, ore_pianificate_task: piano, differenza } = scostamento
  const sfora = differenza < 0

  return (
    <div
      className={`text-xs rounded-md px-3 py-2 border ${
        sfora
          ? 'bg-amber-900/25 border-amber-700/60 text-amber-200'
          : 'bg-gray-800/50 border-gray-700 text-gray-400'
      }`}
    >
      {sfora ? (
        <>
          <strong>{fmtH(somma)}</strong> assegnate ai pezzi, ma il task ne
          pianifica <strong>{fmtH(piano)}</strong>: sforano di{' '}
          <strong>{fmtH(Math.abs(differenza))}</strong>.
          <span className="text-amber-300/70"> Puoi salvare lo stesso — è una segnalazione, non un vincolo.</span>
        </>
      ) : (
        <>
          <strong>{fmtH(somma)}</strong> assegnate ai pezzi su{' '}
          <strong>{fmtH(piano)}</strong> pianificate dal task
          {differenza > 0 && <span className="text-gray-500"> · {fmtH(differenza)} non ancora coperte</span>}
        </>
      )}
    </div>
  )
}

export default function SottotaskManager({ taskId }) {
  const [dati, setDati] = useState(null)
  const [caricamento, setCaricamento] = useState(true)
  const [errore, setErrore] = useState(null)
  const [occupato, setOccupato] = useState(false)

  // Form "aggiungi": vive qui e non in un componente a sé — sono due campi.
  const [nuovoNome, setNuovoNome] = useState('')
  const [nuovoOre, setNuovoOre] = useState('')

  // Modifica in linea: l'id del pezzo aperto, più i due campi in corso.
  const [inModifica, setInModifica] = useState(null)
  const [bozza, setBozza] = useState({ nome: '', ore_stimate: '' })

  const ricarica = useCallback(async () => {
    try {
      setDati(await listaSottotask(taskId))
      setErrore(null)
    } catch (e) {
      setErrore(e.message || 'Errore di caricamento')
    } finally {
      setCaricamento(false)
    }
  }, [taskId])

  useEffect(() => { ricarica() }, [ricarica])

  /* Ogni scrittura passa da qui: un solo posto dove si azzera l'errore
   * precedente, si blocca l'interfaccia e si ricarica. Gli errori NON si
   * ingoiano e non finiscono in un alert: il backend manda messaggi scritti per
   * essere letti — il 409 dice quante dichiarazioni ci sono e cosa fare invece,
   * il 400 sullo stato rimanda alla Consuntivazione — e un «Errore» generico
   * butterebbe via proprio la parte utile. */
  const esegui = async (azione) => {
    setOccupato(true)
    setErrore(null)
    try {
      await azione()
      await ricarica()
    } catch (e) {
      setErrore(e.message || 'Operazione non riuscita')
    } finally {
      setOccupato(false)
    }
  }

  const aggiungi = () => {
    const nome = nuovoNome.trim()
    if (!nome) { setErrore('Il nome del sottotask è obbligatorio'); return }
    return esegui(async () => {
      await creaSottotask({
        task_id: taskId,
        nome,
        // Campo vuoto = pezzo non stimato, che è un caso legittimo: il PM può
        // scomporre prima e stimare poi. `null` e non 0 — «non stimato» e
        // «stimato zero» sono due cose diverse per il motore ore-derivate, che
        // sul primo segnala e sul secondo deriva zero ore.
        ore_stimate: nuovoOre === '' ? null : Number(nuovoOre),
      })
      setNuovoNome('')
      setNuovoOre('')
    })
  }

  const salvaModifica = (pezzo) => {
    const nome = bozza.nome.trim()
    if (!nome) { setErrore('Il nome non può essere vuoto'); return }
    return esegui(async () => {
      await modificaSottotask(pezzo.id, {
        nome,
        ore_stimate: bozza.ore_stimate === '' ? null : Number(bozza.ore_stimate),
      })
      setInModifica(null)
    })
  }

  /* Riordino con le frecce. Si mandano SOLO le due righe che si scambiano:
   * il PUT è batch e "replace" — si dichiara lo stato finale, e i pezzi non
   * citati restano dove sono. Uno scambio è quindi una sola chiamata. */
  const sposta = (indice, direzione) => {
    const lista = dati.sottotask
    const altro = lista[indice + direzione]
    if (!altro) return
    const questo = lista[indice]
    return esegui(() => riordinaSottotask(taskId, [
      { sottotask_id: questo.id, ordine: altro.ordine },
      { sottotask_id: altro.id, ordine: questo.ordine },
    ]))
  }

  if (caricamento) return <p className="text-xs text-gray-500 italic py-2">Carico i sottotask…</p>

  const pezzi = dati?.sottotask ?? []
  const disabilita = occupato

  return (
    <div className="py-2 space-y-2">
      <BandaScostamento scostamento={dati?.task?.scostamento} />

      {errore && (
        <div className="text-xs bg-red-900/30 border border-red-800 text-red-200 rounded-md px-3 py-2">
          {errore}
        </div>
      )}

      {pezzi.length === 0 ? (
        <p className="text-xs text-gray-500 italic">
          Nessun sottotask — questo task si compila come uno solo.
        </p>
      ) : (
        <ul className="space-y-1">
          {pezzi.map((p, i) => (
            <li key={p.id} className="flex items-center gap-2 text-sm py-1 border-b border-gray-800/40">
              {/* Frecce: la prima non sale, l'ultima non scende. */}
              <span className="flex flex-col leading-none shrink-0">
                <button
                  onClick={() => sposta(i, -1)}
                  disabled={disabilita || i === 0}
                  title="Sposta su"
                  className="text-[10px] text-gray-500 hover:text-gray-300 disabled:opacity-20 disabled:cursor-not-allowed"
                >▲</button>
                <button
                  onClick={() => sposta(i, +1)}
                  disabled={disabilita || i === pezzi.length - 1}
                  title="Sposta giù"
                  className="text-[10px] text-gray-500 hover:text-gray-300 disabled:opacity-20 disabled:cursor-not-allowed"
                >▼</button>
              </span>
              <span className="text-xs text-gray-600 font-mono w-4 shrink-0">{p.ordine}</span>

              {inModifica === p.id ? (
                <>
                  <input
                    value={bozza.nome}
                    onChange={(e) => setBozza({ ...bozza, nome: e.target.value })}
                    className="flex-1 min-w-0 bg-gray-950 text-gray-200 rounded px-2 py-1 text-sm border border-gray-700
                               focus:outline-none focus:ring-2 focus:ring-blue-600"
                  />
                  <input
                    type="number" min="0" step="1"
                    value={bozza.ore_stimate}
                    onChange={(e) => setBozza({ ...bozza, ore_stimate: e.target.value })}
                    placeholder="ore"
                    className="w-16 bg-gray-950 text-gray-200 rounded px-2 py-1 text-sm text-center border border-gray-700
                               focus:outline-none focus:ring-2 focus:ring-blue-600 placeholder:text-gray-700"
                  />
                  <button onClick={() => salvaModifica(p)} disabled={disabilita}
                    className="text-xs text-emerald-400 hover:text-emerald-300 disabled:opacity-40">✓</button>
                  <button onClick={() => setInModifica(null)} disabled={disabilita}
                    className="text-xs text-gray-500 hover:text-gray-300 disabled:opacity-40">✗</button>
                </>
              ) : (
                <>
                  <span className="flex-1 min-w-0 truncate text-gray-300">{p.nome}</span>
                  <span className="text-xs text-gray-500 w-12 text-right shrink-0">
                    {p.ore_stimate == null
                      ? <span className="text-gray-600 italic">n.s.</span>
                      : fmtH(p.ore_stimate)}
                  </span>

                  {/* Solo i tre di PIANIFICAZIONE: i dichiarabili sono del
                      dipendente e il backend li rifiuta con 400. Offrire solo
                      questi vuol dire non far mai incontrare quell'errore. */}
                  <select
                    value={p.stato}
                    disabled={disabilita}
                    onChange={(e) => esegui(() => modificaSottotask(p.id, { stato: e.target.value }))}
                    className="bg-gray-800 border border-gray-600 rounded px-1.5 py-0.5 text-xs
                               disabled:opacity-40 shrink-0"
                  >
                    {STATI_PIANIFICAZIONE_SOTTOTASK.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>

                  <button
                    onClick={() => { setInModifica(p.id); setBozza({ nome: p.nome, ore_stimate: p.ore_stimate ?? '' }) }}
                    disabled={disabilita}
                    title="Modifica nome e ore"
                    className="text-xs text-blue-400 hover:text-blue-300 disabled:opacity-40 shrink-0"
                  >✏</button>

                  {/* `n_dichiarazioni` arriva dal GET apposta per questo: si
                      sa in anticipo che il DELETE fallirebbe con 409, e si
                      disabilita il cestino spiegando cosa fare invece —
                      invece di far provare e incassare l'errore. */}
                  <button
                    onClick={() => esegui(() => eliminaSottotask(p.id))}
                    disabled={disabilita || p.n_dichiarazioni > 0}
                    title={p.n_dichiarazioni > 0
                      ? `Ha ${p.n_dichiarazioni} dichiarazioni di lavoro: non si elimina. Portalo ad "Annullato" per toglierlo dal piano conservando lo storico.`
                      : 'Elimina il sottotask'}
                    className="text-xs text-red-400 hover:text-red-300 disabled:opacity-25 disabled:cursor-not-allowed shrink-0"
                  >🗑</button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* Aggiungi — in fondo, come "+ Aggiungi task a questa fase" */}
      <div className="flex items-center gap-2 pt-1">
        <input
          value={nuovoNome}
          onChange={(e) => setNuovoNome(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') aggiungi() }}
          placeholder="Nome del sottotask"
          disabled={disabilita}
          className="flex-1 min-w-0 bg-gray-950 text-gray-200 rounded px-2 py-1 text-sm border border-gray-700
                     focus:outline-none focus:ring-2 focus:ring-blue-600 placeholder:text-gray-600 disabled:opacity-40"
        />
        <input
          type="number" min="0" step="1"
          value={nuovoOre}
          onChange={(e) => setNuovoOre(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') aggiungi() }}
          placeholder="ore"
          disabled={disabilita}
          title="Stima in ore. Vuoto = pezzo non ancora stimato."
          className="w-16 bg-gray-950 text-gray-200 rounded px-2 py-1 text-sm text-center border border-gray-700
                     focus:outline-none focus:ring-2 focus:ring-blue-600 placeholder:text-gray-700 disabled:opacity-40"
        />
        <button
          onClick={aggiungi}
          disabled={disabilita || !nuovoNome.trim()}
          className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-medium
                     disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
        >
          + Aggiungi
        </button>
      </div>
    </div>
  )
}
