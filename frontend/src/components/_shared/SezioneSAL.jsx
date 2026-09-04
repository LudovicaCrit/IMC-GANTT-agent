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
 * `VistaSnapshot` riceve lo `stato` già caricato e decide come disegnarlo. La
 * scommessa ha pagato: la Fase 2 (mini-GANTT) ha toccato SOLO quel componente
 * — zero righe di backend, zero di caricamento, perché `data_inizio`,
 * `data_fine` e `stato` erano già tutti nel JSONB dal giugno 2026. È costato un
 * componente in più allora e ha risparmiato una riscrittura adesso.
 *
 * ── MANAGER-ONLY, ED È SOLO L'INTERFACCIA ────────────────────────────
 * Il pulsante compare se `ruolo_app === 'manager'`. Il BACKEND è più permissivo
 * — `_autorizza_progetto` ammette «manager OPPURE il PM di quel progetto», ed è
 * il design originale del SAL («consolidata su approvazione del PM»). Quindi un
 * pm che chiamasse l'API riuscirebbe: qui si nasconde il gesto finché la
 * matrice dei permessi-PM non è decisa, senza togliere al backend una capacità
 * che ha per progetto. La LISTA resta visibile a chiunque apra la pagina.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { consolidaSAL, listaStoricoSAL, apriSnapshotSAL } from '../../api'
import StatoBadge from './StatoBadge'
import TimelineBars from './TimelineBars'
import { diffSnapshot, descriviDiff } from './diffSnapshot'

const fmtDataOra = (iso) => {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('it-IT', { day: 'numeric', month: 'short', year: 'numeric' }) +
    ' · ' + d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })
}
const fmtH = (n) => (n == null ? '—' : `${Number(n).toLocaleString('it-IT')}h`)

/* ── Da snapshot a barre ───────────────────────────────────────────────
 * L'ADATTATORE, e sta qui apposta: `TimelineBars` non deve sapere che esiste
 * uno snapshot SAL, né che le fasi stanno alla radice, né che i task si
 * chiamano `task` al singolare (spelling dello snapshot — in
 * `/api/gantt/strutturato` sono `tasks`). Tutta questa conoscenza è del
 * chiamante; al componente arriva una lista piatta e basta.
 *
 * È la stessa scelta della scala: se il disegnatore conoscesse la forma della
 * sorgente, la seconda sorgente costerebbe una riscrittura invece di dieci
 * righe come queste.
 *
 * L'ORDINE è quello del JSONB — cioè l'ordine congelato: fasi per `ordine`,
 * task dentro la loro fase. Non si riordina per data: un mini-GANTT che
 * rimescolasse le righe non sarebbe più confrontabile con la tabella accanto.
 */
function barreDaSnapshot(stato, esito = null) {
  const barre = []
  const attivo = Boolean(esito?.confrontabile)

  // Attacca il verdetto del motore a una barra. Il componente riceve stringhe
  // già pronte (`diff`, `diffTesto`): non importa `diffSnapshot`, e resta
  // utilizzabile con un confronto che un giorno venisse da un'altra parte.
  const conDiff = (tipo, id, base) => {
    if (!attivo) return base
    const v = esito[tipo][id]
    if (!v) return base
    const slittata = v.dettagli.inizio || v.dettagli.fine
    return {
      ...base,
      diff: v.diff,
      diffTesto: descriviDiff(v.diff, v.dettagli),
      // L'ombra è la posizione PRECEDENTE. `?? base.…` perché può essere
      // slittato un solo capo: l'altro resta dov'è, e l'ombra deve comunque
      // avere due estremi per essere disegnata.
      ombra: slittata ? {
        data_inizio: v.dettagli.inizio?.da ?? base.data_inizio,
        data_fine: v.dettagli.fine?.da ?? base.data_fine,
      } : undefined,
    }
  }

  const barraFase = (f) => conDiff('fasi', f.id, {
    chiave: `f-${f.id}`, label: f.nome,
    data_inizio: f.data_inizio, data_fine: f.data_fine, stato: f.stato, livello: 0,
  })
  const barraTask = (t) => conDiff('task', t.id, {
    chiave: `t-${t.id}`, label: t.nome,
    data_inizio: t.data_inizio, data_fine: t.data_fine, stato: t.stato, livello: 1,
    sottotitolo: t.dipendente_nome || 'non assegnato',
  })

  // Le voci SPARITE non stanno in B — ma sono la cosa che si vuole vedere.
  // Si reinseriscono al loro posto: un task sparito sotto la fase da cui è
  // sparito, una fase sparita in coda. Metterle tutte in fondo le renderebbe
  // un elenco a parte, e si perderebbe il «da dove».
  const taskSpariti = new Map()
  const fasiSparite = []
  for (const s of esito?.spariti ?? []) {
    if (s.tipo === 'task') {
      if (!taskSpariti.has(s.faseId)) taskSpariti.set(s.faseId, [])
      taskSpariti.get(s.faseId).push(s.voce)
    } else {
      fasiSparite.push(s.voce)
    }
  }

  for (const f of stato?.fasi ?? []) {
    barre.push(barraFase(f))
    for (const t of f.task ?? []) barre.push(barraTask(t))
    for (const t of taskSpariti.get(f.id) ?? []) barre.push(barraTask(t))
  }
  // Una fase sparita si porta dietro i suoi task solo in teoria: il backend
  // rifiuta di cancellare una fase con task agganciati (409), quindi qui la
  // lista è quasi sempre vuota. Gestita lo stesso — «quasi sempre» non è
  // «sempre», e il motore non fa questa assunzione.
  for (const f of fasiSparite) {
    barre.push(barraFase(f))
    for (const t of f.task ?? []) barre.push(barraTask(t))
  }
  return barre
}

/* ── La fotografia aperta ──────────────────────────────────────────────
 * DUE LETTURE DELLO STESSO DATO, e nessuna delle due basta da sola:
 *   ▦ Barre   — i TEMPI: quando, quanto, quanto si sovrappone. Un mini-GANTT
 *               sulla stessa scala del GANTT vero, così le proporzioni
 *               corrispondono a quello che si è visto in /gantt.
 *   ☰ Tabella — le ORE: consuntivato/venduto per fase e per task, e il nome
 *               di chi. Le barre non mostrano le ore e non devono: una barra
 *               larga non è una barra costosa.
 *
 * Default Barre perché la domanda che si fa aprendo un SAL è quasi sempre
 * «com'era messo il progetto allora», ed è una domanda di tempi. Le ore si
 * cercano quando si sa già cosa si cerca — un click più in là.
 *
 * Tutto in SOLA LETTURA, e si vede: nessun input, nessun bottone d'azione.
 * Una fotografia non si modifica — se i numeri sono sbagliati si corregge il
 * progetto e si scatta una foto nuova, non si ritocca quella vecchia.
 */
function VistaSnapshot({ snapshot, precedente, confronto, idPrecedente, onToggleConfronto, caricandoConfronto }) {
  const [vista, setVista] = useState('barre')
  const stato = snapshot?.stato
  // `useMemo` PRIMA dei return anticipati: gli hook non possono stare dopo un
  // ramo condizionale. I calcoli reggono il caso nullo da sé.
  const esito = useMemo(
    () => (confronto && precedente ? diffSnapshot(precedente.stato, stato) : null),
    [confronto, precedente, stato],
  )
  const barre = useMemo(() => barreDaSnapshot(stato, esito), [stato, esito])
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
      <div className="flex items-baseline justify-between gap-3 flex-wrap mb-3">
        <p className="text-[11px] text-gray-500">
          {p.cliente && <>{p.cliente} · </>}
          stato <span className="text-gray-300">{p.stato}</span>
          {p.urgenza && <> · urgenza <span className="text-gray-300">{p.urgenza}</span></>}
          {p.pm_nome && <> · PM {p.pm_nome}</>}
          {' · '}{fasi.length} fasi · {nTask} task
          <span className="text-gray-600"> · schema v{stato.schema_version}</span>
        </p>

        {/* Il commutatore: due bottoni, non un menu — le viste sono due e si
            alternano, non si scelgono da un elenco. */}
        <div className="flex rounded-md overflow-hidden border border-border-subtle shrink-0">
          {[['barre', '▦ Barre'], ['tabella', '☰ Tabella']].map(([k, etichetta]) => (
            <button
              key={k}
              onClick={() => setVista(k)}
              className={`px-2.5 py-1 text-[11px] transition-colors ${
                vista === k
                  ? 'bg-surface-800 text-gray-200 font-medium'
                  : 'text-gray-500 hover:text-gray-300 hover:bg-white/[0.03]'
              }`}
            >
              {etichetta}
            </button>
          ))}
        </div>
      </div>

      {/* ── Il confronto ────────────────────────────────────────────
          Vive solo nella vista Barre: la tabella mostra le ore, che questo
          primo giro di diff non confronta. Accenderlo lì prometterebbe una
          cosa che non fa. */}
      {vista === 'barre' && (
        <div className="flex items-center gap-2 flex-wrap mb-2">
          <button
            onClick={onToggleConfronto}
            disabled={!idPrecedente || caricandoConfronto}
            title={idPrecedente
              ? `Confronta con lo snapshot #${idPrecedente}`
              : 'È la prima fotografia di questo progetto: non c\'è un precedente con cui confrontarla'}
            className={`px-2.5 py-1 rounded-md text-[11px] border transition-colors
                        disabled:opacity-40 disabled:cursor-not-allowed ${
                          confronto
                            ? 'bg-amber-600/20 border-amber-600/60 text-amber-200'
                            : 'border-border-subtle text-gray-400 hover:text-gray-200 hover:bg-white/[0.03]'
                        }`}
          >
            {caricandoConfronto ? '…' : '⇄'} confronta col precedente
            {idPrecedente ? <span className="text-gray-500 font-data"> #{idPrecedente}</span> : null}
          </button>

          {/* Il perché del pulsante spento, scritto — un bottone grigio senza
              spiegazione si legge come un guasto. */}
          {!idPrecedente && (
            <span className="text-[10px] text-gray-500 italic">
              prima fotografia del progetto: non c'è un «prima»
            </span>
          )}

          {confronto && esito?.confrontabile && (
            <span className="text-[10px] text-gray-400 flex items-center gap-2 flex-wrap">
              <span className="text-gray-600">rispetto a #{idPrecedente}:</span>
              {esito.riepilogo.slittato > 0 && <span className="text-amber-300">{esito.riepilogo.slittato} slittate</span>}
              {esito.riepilogo.nuovo > 0 && <span className="text-green-300">{esito.riepilogo.nuovo} nuove</span>}
              {esito.riepilogo.sparito > 0 && <span className="text-red-300">{esito.riepilogo.sparito} sparite</span>}
              {esito.riepilogo.modificato > 0 && <span className="text-purple-300">{esito.riepilogo.modificato} modificate</span>}
              {/* «Niente» è una risposta, e va detta: senza, un GANTT tutto
                  attenuato sembra un confronto non riuscito. */}
              {esito.riepilogo.slittato + esito.riepilogo.nuovo + esito.riepilogo.sparito + esito.riepilogo.modificato === 0 && (
                <span className="italic">nessuna differenza — i due SAL fotografano lo stesso GANTT</span>
              )}
            </span>
          )}
        </div>
      )}

      {vista === 'barre' ? (
        <TimelineBars
          barre={barre}
          // Tetto più basso del GANTT a pagina intera (80): qui il riquadro è
          // una card dentro una pagina, non lo schermo. Cambia la densità, non
          // le proporzioni.
          weekPxMax={28}
          labelW={190}
          dataScatto={snapshot.data_snapshot}
          maxHeight={420}
          messaggioVuoto="Questa fotografia non ha fasi con date: niente da disegnare."
        />
      ) : (
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
      )}
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
  // Il confronto: acceso/spento, e lo snapshot del PRIMA una volta caricato.
  // Si tiene qui e non in `VistaSnapshot` perché serve `storico` per sapere
  // qual è il precedente — e perché il caricamento va spento quando si cambia
  // fotografia (vedi `apri`).
  const [confronto, setConfronto] = useState(false)
  const [precedente, setPrecedente] = useState(null)
  const [caricandoConfronto, setCaricandoConfronto] = useState(false)

  // Il «precedente» è il vicino più vecchio nello storico, che arriva già
  // ordinato per data desc dal backend: l'elemento DOPO quello aperto.
  // `undefined` se l'aperto è l'ultimo della lista — cioè il primo scattato.
  const idPrecedente = (() => {
    if (!aperto) return null
    const i = storico.findIndex(s => s.id === aperto.id)
    return i >= 0 ? storico[i + 1]?.id ?? null : null
  })()

  const toggleConfronto = async () => {
    if (confronto) { setConfronto(false); return }
    if (!idPrecedente) return
    // Si carica una volta sola: riaccendere il confronto sulla stessa
    // fotografia non ri-chiama l'API.
    if (precedente?.id !== idPrecedente) {
      setCaricandoConfronto(true)
      try {
        setPrecedente(await apriSnapshotSAL(idPrecedente))
      } catch (e) {
        // Il confronto NON si accende: meglio nessun diff di un diff su un
        // «prima» che non è arrivato.
        setErrore(e.message || 'Non riesco a caricare la fotografia precedente')
        return
      } finally {
        setCaricandoConfronto(false)
      }
    }
    setConfronto(true)
  }

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
    // Cambiando fotografia il confronto si spegne: lasciarlo acceso
    // mostrerebbe per un istante il diff della PRECEDENTE coppia sulla nuova
    // fotografia — un confronto fra due cose che non sono quelle sullo schermo.
    setConfronto(false)
    setPrecedente(null)
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
                {attivo && (
                  <VistaSnapshot
                    snapshot={aperto}
                    precedente={precedente}
                    confronto={confronto}
                    idPrecedente={idPrecedente}
                    onToggleConfronto={toggleConfronto}
                    caricandoConfronto={caricandoConfronto}
                  />
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
