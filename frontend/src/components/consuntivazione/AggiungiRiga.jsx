/**
 * AggiungiRiga.jsx — dichiarare ore su un'attività che la griglia non propone.
 *
 * Consuntivazione a ore, passo 4 sotto-passo 5. La griglia mostra le unità che
 * /me ritiene «di questa settimana»: il task con la finestra aperta, quello
 * scaduto ma ancora vivo, quello su cui ci sono già ore (N21). Il lavoro vero
 * esce da quella lista — si anticipa un task che parte il mese prossimo, si
 * chiude una coda su un task finito tre settimane fa, il PM ha spostato a voce
 * qualcosa che nel piano non è ancora scritto. Senza questo pulsante quelle ore
 * non hanno dove andare: il dipendente deve chiedere al PM di cambiare le date
 * prima di poter dire cosa ha fatto.
 *
 * DA DOVE VENGONO I TASK — GET /api/tasks, che per un utente normale ritorna
 * GIÀ i soli task suoi (Scenario B), tutti tranne gli Eliminati, con progetto e
 * date. Niente endpoint nuovo: il backend non si tocca.
 *
 * SI OFFRE SOLO CIÒ CHE IL SALVATAGGIO ACCETTEREBBE. È la stessa regola di
 * `_motivo_non_modificabile` nello strato dati, che serve insieme la
 * validazione e il flag `modificabile` di /me: «una riga offerta non può poi
 * essere rifiutata». Quindi si filtra via:
 *   - i task di ALTRI (N13). Per l'utente normale non arrivano nemmeno, ma un
 *     manager riceve da /api/tasks l'azienda intera, e /salva-blocchi è
 *     self-only senza deroghe: offrirglieli sarebbe offrire un 400;
 *   - gli Annullati (gli Eliminati li toglie già il backend);
 *   - i task GIÀ in griglia, che avrebbero una riga doppia.
 * Resta fuori portata il task SCOMPOSTO: /api/tasks non dice se lo è, e
 * GET /api/sottotask/{id} è solo-manager. Oggi in DB non ce n'è nessuno; se un
 * giorno ce ne sarà uno e verrà scelto qui, il salvataggio risponde «il task è
 * scomposto in sottotask, le ore vanno dichiarate sui singoli pezzi» e la
 * pagina lo mostra accanto alla riga, che si toglie con la ×. Sgradevole ma non
 * rotto — e tanto basta finché i pezzi non si potranno leggere da qui.
 *
 * ORIZZONTE: un mese attorno alla settimana. È COMODITÀ, non validità — il
 * salvataggio accetta qualunque task proprio, di qualunque data. Serve a tenere
 * la lista corta e sensata invece di srotolare tutto lo storico. I task SENZA
 * date ci sono sempre: come nei rami 1-2 del filtro di /me, di uno senza date
 * non si può dire che non intersechi la settimana.
 *
 * ORDINE: prima i progetti su cui la persona sta già lavorando questa settimana
 * (i progetto_id delle righe di /me), poi gli altri, ciascun blocco per nome.
 * È un ORDINAMENTO e non un filtro: il progetto nuovo resta raggiungibile, sta
 * solo più in basso.
 */
import React, { useState, useEffect, useMemo, useRef } from 'react'
import { fetchTasks } from '../../api'
import { fmtData } from './formato'

/** Lunedì−30 giorni … domenica+30: l'orizzonte della lista. */
export function orizzonteMese(lunediIso, giorni = 30) {
  const [a, m, g] = String(lunediIso).slice(0, 10).split('-').map(Number)
  const sposta = (offset) =>
    new Date(Date.UTC(a, m - 1, g + offset)).toISOString().slice(0, 10)
  return { da: sposta(-giorni), a: sposta(6 + giorni) }
}

/** Un task è nell'orizzonte se la sua finestra lo interseca, o se non ha date. */
export const nellOrizzonte = (t, da, a) => {
  const inizio = t.data_inizio ? String(t.data_inizio).slice(0, 10) : null
  const fine = t.data_fine ? String(t.data_fine).slice(0, 10) : null
  if (!inizio || !fine) return true
  return inizio <= a && fine >= da
}

/**
 * I candidati, filtrati e raggruppati per progetto. Funzione pura: è dove sta
 * tutta la decisione di «cosa si può offrire», e si prova senza montare nulla.
 */
export function candidatiPerProgetto(tasks, { dipendenteId, escludi, progettiAttivi, lunedi, cerca = '' }) {
  const { da, a } = orizzonteMese(lunedi)
  const ago = cerca.trim().toLowerCase()
  const ammessi = (tasks ?? []).filter((t) =>
    t.dipendente_id === dipendenteId &&
    !escludi.has(t.id) &&
    t.stato !== 'Annullato' &&
    nellOrizzonte(t, da, a) &&
    (ago === '' || `${t.nome} ${t.progetto_nome} ${t.id}`.toLowerCase().includes(ago)))

  const gruppi = new Map()
  for (const t of ammessi) {
    if (!gruppi.has(t.progetto_id)) {
      gruppi.set(t.progetto_id, {
        progetto_id: t.progetto_id,
        progetto_nome: t.progetto_nome || t.progetto_id,
        attivo: progettiAttivi.has(t.progetto_id),
        task: [],
      })
    }
    gruppi.get(t.progetto_id).task.push(t)
  }
  return [...gruppi.values()]
    .map((g) => ({ ...g, task: [...g.task].sort((x, y) => x.nome.localeCompare(y.nome, 'it')) }))
    .sort((x, y) => (y.attivo - x.attivo) || x.progetto_nome.localeCompare(y.progetto_nome, 'it'))
}

const STILE_STATO = {
  'Completato': 'text-emerald-300/80',
  'Bloccato': 'text-red-300/80',
  'Sospeso': 'text-amber-300/80',
}

export default function AggiungiRiga({ lunedi, dipendenteId, escludi, progettiAttivi, onScegli, disabilitato }) {
  const [aperto, setAperto] = useState(false)
  const [tasks, setTasks] = useState(null)
  const [caricamento, setCaricamento] = useState(false)
  const [errore, setErrore] = useState(null)
  const [cerca, setCerca] = useState('')
  const pannello = useRef(null)
  const campoCerca = useRef(null)

  // Il pannello nasce in fondo alla pagina, sotto una tabella lunga e dietro la
  // barra di salvataggio, che è sticky: aperto e basta resterebbe fuori campo o
  // per metà coperto, e sembrerebbe che il pulsante non abbia fatto niente.
  //
  // Il fuoco si dà DOPO, e con `preventScroll`. Con `autoFocus` sull'input il
  // browser fa il suo scroll-into-view sul campo appena montato, che annulla
  // questo e lascia il pannello incollato sotto la barra di salvataggio: due
  // scroll che si contendono la stessa pagina, e vince quello che non vogliamo.
  //
  // E si rifà quando ARRIVANO i task, non solo all'apertura: appena aperto il
  // pannello è alto tre righe, e centrare quello non basta a far entrare la
  // lista che compare un istante dopo.
  useEffect(() => {
    if (!aperto) return
    pannello.current?.scrollIntoView({ block: 'center' })
    campoCerca.current?.focus({ preventScroll: true })
  }, [aperto, tasks])

  // Si carica alla PRIMA apertura e si tiene: la lista dei propri task non
  // cambia mentre si compila una settimana, e ricaricarla a ogni apertura
  // farebbe lampeggiare il pannello per niente.
  useEffect(() => {
    if (!aperto || tasks !== null || caricamento) return
    setCaricamento(true)
    setErrore(null)
    fetchTasks()
      .then(setTasks)
      .catch((e) => setErrore(e?.message || String(e)))
      .finally(() => setCaricamento(false))
  }, [aperto, tasks, caricamento])

  const gruppi = useMemo(
    () => (tasks ? candidatiPerProgetto(tasks, { dipendenteId, escludi, progettiAttivi, lunedi, cerca }) : []),
    [tasks, dipendenteId, escludi, progettiAttivi, lunedi, cerca])

  const quanti = gruppi.reduce((s, g) => s + g.task.length, 0)

  if (!aperto) {
    return (
      <button
        type="button"
        disabled={disabilitato}
        onClick={() => setAperto(true)}
        data-aggiungi-riga="apri"
        className="mt-3 px-3 py-2 rounded-lg text-sm border border-dashed border-gray-700 text-gray-400
                   hover:text-gray-200 hover:border-gray-500 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        + Ho lavorato su altro
      </button>
    )
  }

  return (
    <div ref={pannello} className="mt-3 bg-gray-900 rounded-xl border border-gray-800 p-4"
         data-aggiungi-riga="pannello">
      <div className="flex items-start justify-between gap-4 mb-3">
        <div>
          <p className="text-sm text-gray-200">Aggiungi un'attività alla settimana</p>
          <p className="text-[11px] text-gray-500 mt-0.5">
            I tuoi task, anche fuori dalle date di questa settimana. Scegline uno e compilalo come gli altri.
          </p>
        </div>
        <button type="button" onClick={() => { setAperto(false); setCerca('') }}
                className="text-gray-500 hover:text-gray-300 text-sm shrink-0">chiudi ✕</button>
      </div>

      <input
        ref={campoCerca}
        type="text"
        value={cerca}
        onChange={(e) => setCerca(e.target.value)}
        placeholder="Cerca per attività, progetto o codice…"
        aria-label="Cerca un'attività da aggiungere"
        data-aggiungi-cerca
        className="w-full rounded-md px-2.5 py-1.5 text-sm border border-gray-700 bg-gray-950 text-gray-200
                   placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-600 mb-3"
      />

      {caricamento && <p className="text-sm text-gray-500">Caricamento delle tue attività…</p>}
      {errore && <p className="text-sm text-red-400">Errore: {errore}</p>}

      {!caricamento && !errore && quanti === 0 && (
        <p className="text-sm text-gray-500" data-aggiungi-vuoto>
          {cerca.trim()
            ? 'Nessuna attività corrisponde alla ricerca.'
            : 'Nessun’altra attività da aggiungere: quelle del mese attorno a questa settimana sono già tutte in griglia.'}
        </p>
      )}

      <div className="max-h-80 overflow-y-auto divide-y divide-gray-800/70" data-aggiungi-lista>
        {gruppi.map((g) => (
          <div key={g.progetto_id} className="py-2">
            <p className="text-[11px] uppercase tracking-wider text-gray-500 mb-1 flex items-center gap-2">
              <span className="text-gray-300 normal-case tracking-normal text-xs font-medium">{g.progetto_nome}</span>
              {g.attivo && (
                <span className="px-1.5 rounded bg-blue-950/60 border border-blue-900 text-blue-300 text-[10px]">
                  ci stai già lavorando
                </span>
              )}
            </p>
            <ul>
              {g.task.map((t) => (
                <li key={t.id}>
                  <button
                    type="button"
                    onClick={() => { onScegli(t); setCerca('') }}
                    data-aggiungi-task={t.id}
                    className="w-full text-left px-2 py-1.5 rounded-md hover:bg-gray-800/70 focus:outline-none
                               focus:ring-2 focus:ring-blue-600"
                  >
                    <span className="text-sm text-gray-200">{t.nome}</span>
                    <span className="block text-[11px] text-gray-600 flex flex-wrap gap-x-2">
                      <span>{t.id}</span>
                      {t.stato && <span className={STILE_STATO[t.stato] ?? ''}>{t.stato}</span>}
                      {t.data_inizio && t.data_fine && (
                        <span>{fmtData(t.data_inizio)} – {fmtData(t.data_fine)}</span>
                      )}
                      {!t.data_inizio && !t.data_fine && <span>senza date</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}
