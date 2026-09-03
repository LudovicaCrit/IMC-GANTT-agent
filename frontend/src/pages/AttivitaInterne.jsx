/**
 * ═════════════════════════════════════════════════════════════════════════
 * AttivitaInterne.jsx — Chi passa quanto tempo su lavoro non-cliente
 * ═════════════════════════════════════════════════════════════════════════
 *
 * RISCRITTA il 03/09/2026, e non per stile: la versione precedente mostrava
 * dati SBAGLIATI e permetteva una scrittura pericolosa.
 *
 * IL BUG. Le attività interne erano modellate come task di un progetto-
 * contenitore, `P010`, e la pagina faceva `fetchTasks('P010')`. Ma P010 è stato
 * RIUSATO per un progetto-cliente vero — «AIoT Smart City Maida», Comune di
 * Maida — mentre le interne diventavano 27 progetti `tipologia='interna'`.
 * Quindi la pagina:
 *   - mostrava i 5 task del progetto Maida spacciandoli per attività interne;
 *   - NON mostrava nessuna delle 27 interne vere;
 *   - col form di creazione, scriveva task dentro un progetto FATTURABILE.
 *
 * COSA MOSTRA ORA — l'asse è la PERSONA, non il progetto. La domanda a cui
 * questa pagina risponde è «chi passa quanto tempo su cosa che non è cliente»,
 * e un elenco piatto dei 27 progetti la direbbe peggio: 19 su 27 sono mansioni
 * continuative con la stessa finestra annuale, e in fila sarebbero una lista
 * amorfa. Ogni riga porta comunque il progetto interno di appartenenza, così è
 * chiaro SU COSA.
 *
 * IL FORM DI CREAZIONE È STATO RIMOSSO, non riparato. Nel modello nuovo il
 * gesto è diventato ambiguo: «crea un'attività interna» significava «aggiungi
 * un task al contenitore», ma i contenitori ora sono 27. Le sue sette
 * `CATEGORIE` cablate non corrispondono ai progetti reali — a «Formazione»
 * corrispondono almeno tre progetti distinti (PC01, PI15, PI15b). Aggiungere un
 * task a un progetto interno si fa dal Cantiere, dove tutte e 27 sono già
 * visibili e modificabili.
 *
 * QUI SI GUARDA, NON SI DICHIARA. Le ore interne le dichiara il dipendente
 * dalla sua Consuntivazione: i task interni compaiono in `/me` come tutti gli
 * altri, con lo slider e le ore derivate (verificato — 15 dipendenti su 18 ne
 * hanno). Questa è una vista manageriale.
 *
 * ~h/sett è un'APPROSSIMAZIONE, e va letta come tale: il piano del task
 * spalmato sulle settimane di durata, la stessa formula (e lo stesso debito di
 * distribuzione uniforme) di `carico_settimanale_dipendente`. Le ore REALI
 * stanno nei consuntivi.
 */

import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchAttivitaInterne, eliminaAttivitaInterna } from '../api'

/* I colori delle tre famiglie. Servono a distinguere a colpo d'occhio un corso
 * da una mansione continuativa: sono cose diverse che convivono nella stessa
 * riga-persona. Palette del design system, tono basso — è una categoria, non
 * un allarme. */
const STILE_FAMIGLIA = {
  'Corsi': 'bg-sky-900/40 text-sky-300 border-sky-800/60',
  'Mansioni continuative': 'bg-surface-800 text-gray-400 border-border-default',
  'Sviluppo interno': 'bg-violet-900/30 text-violet-300 border-violet-800/60',
  'Altre': 'bg-surface-800 text-gray-500 border-border-subtle',
}

function ChipFamiglia({ famiglia }) {
  const cls = STILE_FAMIGLIA[famiglia] || STILE_FAMIGLIA['Altre']
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${cls} shrink-0`}>
      {famiglia}
    </span>
  )
}

const fmtMese = (iso) =>
  iso ? new Date(iso).toLocaleDateString('it-IT', { month: 'short', year: '2-digit' }) : '?'

export default function AttivitaInterne() {
  const [dati, setDati] = useState(null)
  const [loading, setLoading] = useState(true)
  const [errore, setErrore] = useState(null)
  const [filtro, setFiltro] = useState(null)   // null = tutte le famiglie
  const navigate = useNavigate()

  const carica = () => {
    setLoading(true)
    fetchAttivitaInterne()
      .then(setDati)
      .catch((e) => setErrore(e.message || 'Errore di caricamento'))
      .finally(() => setLoading(false))
  }

  useEffect(carica, [])

  const elimina = async (a) => {
    if (!confirm(`Eliminare «${a.nome}»?\n\nIl task viene archiviato (soft delete), le ore già dichiarate restano.`)) return
    try {
      await eliminaAttivitaInterna(a.task_id)
      carica()
    } catch (e) {
      // Il backend manda messaggi scritti per essere letti — per esempio se il
      // task non è di un progetto interno. Non si sostituiscono con un generico.
      setErrore(e.message)
    }
  }

  if (loading) return <p className="text-gray-400">Caricamento…</p>

  const tot = dati?.totali ?? { n_progetti: 0, n_task: 0, n_persone: 0, per_famiglia: {} }
  const famiglie = Object.entries(tot.per_famiglia || {})

  // Il filtro agisce sulle ATTIVITÀ, non sulle persone: una persona resta
  // visibile finché le resta almeno un'attività della famiglia scelta.
  const persone = (dati?.per_persona ?? [])
    .map((g) => ({ ...g, attivita: filtro ? g.attivita.filter((a) => a.famiglia === filtro) : g.attivita }))
    .filter((g) => g.attivita.length > 0)

  return (
    <div className="max-w-5xl">
      <div className="flex items-baseline justify-between gap-4 mb-1">
        <h1 className="text-xl font-semibold">Attività interne</h1>
        <p className="text-xs text-gray-500">
          {tot.n_progetti} progetti · {tot.n_task} attività · {tot.n_persone} persone
        </p>
      </div>
      <p className="text-xs text-gray-500 mb-4">
        Lavoro senza cliente: formazione, mansioni continuative, sviluppo interno.
        Le ore si dichiarano dalla{' '}
        <button onClick={() => navigate('/consuntivazione-new')}
          className="text-accent-300 hover:text-accent-400">Consuntivazione</button>
        ; per aggiungere un'attività, aprila dal{' '}
        <button onClick={() => navigate('/cantiere')}
          className="text-accent-300 hover:text-accent-400">Cantiere</button>
        {' '}sul progetto interno relativo.
      </p>

      {errore && (
        <div className="text-xs bg-red-900/30 border border-red-800 text-red-200 rounded-md px-3 py-2 mb-4">
          {errore}
        </div>
      )}

      {/* Filtro per famiglia — chip cliccabili, non una tendina: sono tre. */}
      <div className="flex flex-wrap gap-2 mb-4">
        <button
          onClick={() => setFiltro(null)}
          className={`text-xs px-3 py-1 rounded-lg border transition-colors ${
            filtro === null
              ? 'bg-accent-600 text-white border-accent-500'
              : 'border-border-default text-gray-400 hover:text-gray-200'
          }`}
        >
          Tutte <span className="font-data">{tot.n_progetti}</span>
        </button>
        {famiglie.map(([f, n]) => (
          <button
            key={f}
            onClick={() => setFiltro(filtro === f ? null : f)}
            className={`text-xs px-3 py-1 rounded-lg border transition-colors ${
              filtro === f
                ? 'bg-accent-600 text-white border-accent-500'
                : 'border-border-default text-gray-400 hover:text-gray-200'
            }`}
          >
            {f} <span className="font-data">{n}</span>
          </button>
        ))}
      </div>

      {persone.length === 0 ? (
        <div className="card p-8 text-center">
          <p className="text-gray-300 mb-1">Nessuna attività interna</p>
          <p className="text-sm text-gray-500">
            {filtro ? `Nessuna attività della famiglia «${filtro}».` : 'Non ci sono attività interne assegnate.'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {persone.map((g) => (
            <div key={g.dipendente_id} className="card p-4">
              <div className="flex items-baseline justify-between gap-3 mb-2">
                <div className="min-w-0">
                  <span className="font-semibold text-gray-100">{g.nome}</span>
                  <span className="text-xs text-gray-500 ml-2">
                    {g.profilo}{g.ore_sett ? ` · ${g.ore_sett}h/sett` : ''}
                  </span>
                </div>
                <span className="text-sm text-accent-300 font-data shrink-0">
                  ~{g.ore_settimana_interne}h/sett
                </span>
              </div>

              <div className="space-y-1">
                {g.attivita.map((a) => (
                  <div key={a.task_id}
                    className="flex items-center gap-3 px-2.5 py-1.5 rounded-lg bg-surface-800/50 text-sm">
                    <ChipFamiglia famiglia={a.famiglia} />
                    <span className="min-w-0 flex-1">
                      <span className="block text-gray-200 truncate">{a.nome}</span>
                      <span className="block text-[11px] text-gray-500 truncate">
                        <span className="font-mono text-gray-600">{a.progetto_id}</span>
                        {' '}{a.progetto_nome}
                      </span>
                    </span>
                    <span className="text-[11px] text-gray-500 shrink-0 hidden sm:inline">
                      {fmtMese(a.data_inizio)} → {fmtMese(a.data_fine)}
                    </span>
                    <span className="text-xs font-data text-gray-400 w-16 text-right shrink-0">
                      {a.ore_settimana != null ? `~${a.ore_settimana}h/sett` : '—'}
                    </span>
                    <button
                      onClick={() => elimina(a)}
                      title="Archivia questa attività (soft delete)"
                      className="text-xs text-red-500 hover:text-red-400 px-1 shrink-0"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Le attività senza assegnatario: se ce ne fossero, non devono sparire —
          sono lavoro pianificato che nessuno sta facendo. */}
      {(dati?.senza_assegnatario?.length ?? 0) > 0 && (
        <div className="card p-4 mt-3 border-amber-900/40">
          <h3 className="text-sm font-semibold text-amber-300 mb-2">
            Senza assegnatario ({dati.senza_assegnatario.length})
          </h3>
          {dati.senza_assegnatario.map((a) => (
            <div key={a.task_id} className="text-sm text-gray-300 py-1">
              {a.nome} <span className="text-xs text-gray-500">· {a.progetto_nome}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
