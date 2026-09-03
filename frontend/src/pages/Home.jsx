/**
 * ═════════════════════════════════════════════════════════════════════════
 * Home.jsx — Lo stato delle cose, dal punto di vista di chi guarda
 * ═════════════════════════════════════════════════════════════════════════
 *
 * RISCRITTA il 03/09/2026. La versione precedente era rimasta indietro di un
 * modello dati e mezzo, e non era riparabile a toppe:
 *   - filtrava su `In bando` e `Vinto - Da pianificare`, stati ABOLITI dal
 *     vecchio modello bandi: due sezioni permanentemente vuote;
 *   - aveva `p.id !== 'P010'` cablato, cioè l'hack che il resto del codice ha
 *     già rimosso — e che oggi escluderebbe un progetto-cliente vero (P010 è
 *     stato riusato per «AIoT Smart City Maida»);
 *   - chiamava /progetti, /dipendenti e /tasks in un `Promise.all`. I primi due
 *     sono `require_manager`: per un DIPENDENTE il 403 faceva rigettare tutto e
 *     la pagina restava bianca. La Home non era mai stata usabile da chi non è
 *     manager.
 * Ora legge UN solo endpoint — `/api/home/dashboard`, `get_current_user` — che
 * applica il filtro-ruolo a monte e restituisce solo ciò che chi guarda può
 * vedere.
 *
 * IL PATTO: polso e attenzione INSIEME. Le cose che vanno bene sono visibili
 * quanto quelle che vanno male, e non è gentilezza: una pagina di sola sofferenza
 * si smette di aprire, e allora non avvisa più nemmeno quando servirebbe.
 *
 * ANTI-SCROLL — è un requisito, non un'estetica. All'apertura si devono vedere
 * il polso di TUTTI i rami e le prime voci di attenzione senza scrollare.
 * Le scelte che lo ottengono:
 *   - intestazione di UNA riga (la vecchia aveva h1 + sottotitolo + 4 KPI);
 *   - i rami AFFIANCATI (`sm:grid-cols-2`), non impilati: due card da ~200px
 *     accanto costano metà dell'altezza di due impilate;
 *   - team e interne in una STRISCIA sottile, non due card piene;
 *   - attenzione tagliata ai primi 5 per ramo, il resto dietro un toggle.
 *
 * ALTEZZA CHE SEGUE IL CONTENUTO: `items-start` sulla griglia. Senza, i figli
 * di un grid si stirano all'altezza del più alto (`stretch` è il default) e la
 * card di Innovation Plaza — 2 progetti — resterebbe alta come quella di
 * IMC-Improve, con un buco in mezzo. Se domani un ramo cresce, cresce la sua
 * card e nient'altro.
 */

import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchHomeDashboard } from '../api'
import PastigliaSemaforo from '../components/_shared/PastigliaSemaforo'

/* Quante voci di attenzione per ramo prima del taglio. Cinque è la scelta:
 * abbastanza per vedere un problema vero, poche perché resti sopra la piega
 * anche con due rami aperti. Il resto non si perde — sta dietro il toggle. */
const VOCI_VISIBILI = 5

/* I colori del semaforo, per i contatori del polso. Stessa palette della
 * PastigliaSemaforo (red/amber/gray/green-500 del design system): il polso e le
 * pastiglie devono dire lo stesso colore, o l'occhio non li collega. */
const STILE_COLORE = {
  rosso: 'text-red-400',
  giallo: 'text-amber-400',
  grigio: 'text-gray-400',
  verde: 'text-green-400',
}
const ORDINE_COLORI = ['rosso', 'giallo', 'grigio', 'verde']

/* I motivi, resi in italiano. Il backend manda `tipo` + i dati; la frase la
 * costruisce il frontend — è resa, non dato, e cambiarla non è una migration.
 * `tipo` è una stringa-enum estendibile: un tipo sconosciuto degrada a sé stesso
 * invece di far sparire la riga. */
function testoMotivo(m) {
  if (m.tipo === 'scaduto') {
    const g = m.giorni
    return g === 0 ? 'scade oggi' : `scaduto da ${g} ${g === 1 ? 'giorno' : 'giorni'}`
  }
  if (m.tipo === 'superamento_ore') return 'sforamento ore'
  if (m.tipo === 'semaforo_rosso') {
    const n = m.figli_rossi || 0
    if (m.origine === 'figli') return `${n} ${n === 1 ? 'fase' : 'fasi'} in ritardo`
    if (m.origine === 'entrambe') return `in ritardo, e ${n} ${n === 1 ? 'fase' : 'fasi'} dentro`
    return 'in ritardo'
  }
  return m.tipo
}

/* ── La card di un ramo (una società) ──────────────────────────────────
 * Sereno per costruzione: il numero grande è quello dei progetti, non quello
 * dei problemi. I colori del semaforo stanno su una riga sola, e i completati
 * chiudono la card — l'ultima cosa che si legge è ciò che è andato a buon fine.
 */
function CardRamo({ ramo }) {
  const p = ramo.polso
  const stati = Object.entries(p.progetti_per_stato || {})
  const colori = ORDINE_COLORI.filter((c) => p.semaforo?.progetti?.[c])

  return (
    <div className="card p-5">
      <div className="flex items-baseline justify-between gap-3 mb-3">
        <h2 className="text-lg font-semibold text-gray-100 truncate">{ramo.azienda}</h2>
        <span className="text-sm text-gray-500 shrink-0">
          <span className="text-2xl font-semibold text-gray-100 font-data">{p.n_progetti}</span>
          {' '}progetti
        </span>
      </div>

      {/* Stati: chip in linea, vanno a capo se sono molti */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {stati.map(([stato, n]) => (
          <span key={stato} className="text-[11px] px-2 py-0.5 rounded bg-surface-800 text-gray-400 border border-border-subtle">
            {stato} <span className="text-gray-200 font-data">{n}</span>
          </span>
        ))}
      </div>

      {/* Semaforo: solo i colori PRESENTI. Mostrare «giallo 0» sarebbe rumore,
          e in strato 1 il giallo non viene mai emesso. */}
      <div className="flex items-center gap-4 text-sm mb-3">
        {colori.map((c) => (
          <span key={c} className={STILE_COLORE[c]}>
            <span className="font-data font-semibold">{p.semaforo.progetti[c]}</span>{' '}
            <span className="text-xs opacity-80">{c}</span>
          </span>
        ))}
        {colori.length === 0 && <span className="text-xs text-gray-600">nessun progetto</span>}
      </div>

      {/* La vittoria, in chiaro */}
      <div className="text-xs text-gray-500 pt-2 border-t border-border-subtle">
        <span className="text-green-400 font-data font-semibold">{p.task_completati}</span>
        {' '}task completati
      </div>
    </div>
  )
}

/* ── Una voce di attenzione ────────────────────────────────────────────
 * La pastiglia arriva da _shared: è la stessa che il Cantiere e l'Elenco usano,
 * quindi lo stesso colore significa la stessa cosa in tutta l'app.
 * `livello="progetto"` perché il tooltip dica «N fasi», non «N task»: i figli
 * diretti di un progetto sono le fasi.
 */
function VoceAttenzione({ voce, onClick }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left flex items-center gap-3 px-3 py-2 rounded-lg
                 hover:bg-white/[0.03] transition-colors"
      title={`Apri ${voce.nome}`}
    >
      <PastigliaSemaforo
        semaforo={voce.semaforo}
        stato={voce.stato}
        livello="progetto"
      />
      <span className="min-w-0 flex-1">
        <span className="block text-sm text-gray-200 truncate">{voce.nome}</span>
        <span className="block text-[11px] text-gray-500 truncate">
          {voce.cliente && <span className="text-gray-600">{voce.cliente} · </span>}
          {voce.motivi.map(testoMotivo).join(' · ')}
        </span>
      </span>
      <span className="text-[10px] text-gray-600 shrink-0 hidden sm:inline">{voce.urgenza}</span>
    </button>
  )
}

/* ── L'attenzione di un ramo, tagliata ─────────────────────────────────
 * Le voci arrivano GIÀ ORDINATE dall'endpoint (gravità, poi urgenza, poi id):
 * qui non si riordina nulla. Riordinare lato client aprirebbe la porta a due
 * ordini diversi per gli stessi dati.
 */
function BloccoAttenzione({ ramo, onApri }) {
  const [tutte, setTutte] = useState(false)
  const voci = ramo.attenzione
  const mostrate = tutte ? voci : voci.slice(0, VOCI_VISIBILI)
  const nascoste = voci.length - mostrate.length

  return (
    <div className="card p-4">
      <div className="flex items-baseline justify-between mb-2">
        <h3 className="text-sm font-semibold text-gray-300">{ramo.azienda}</h3>
        <span className="text-xs text-gray-500">
          {voci.length === 0
            ? 'niente da segnalare'
            : `${voci.length} da guardare`}
        </span>
      </div>

      {voci.length === 0 ? (
        <p className="text-xs text-gray-600 italic px-3 py-2">
          Tutti i progetti procedono nei tempi.
        </p>
      ) : (
        <>
          <div className="-mx-1">
            {mostrate.map((v) => (
              <VoceAttenzione key={v.progetto_id} voce={v} onClick={() => onApri(v.progetto_id)} />
            ))}
          </div>
          {(nascoste > 0 || tutte) && (
            <button
              onClick={() => setTutte(!tutte)}
              className="text-xs text-accent-300 hover:text-accent-400 mt-1 px-3"
            >
              {tutte ? '← mostra solo le prime' : `vedi tutte (${nascoste} in più) →`}
            </button>
          )}
        </>
      )}
    </div>
  )
}

/* ── Pagina ────────────────────────────────────────────────────────────── */
export default function Home() {
  const [dati, setDati] = useState(null)
  const [errore, setErrore] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    fetchHomeDashboard()
      .then(setDati)
      .catch((e) => setErrore(e.message || 'Errore di caricamento'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-gray-400">Caricamento…</p>
  if (errore) {
    return (
      <div className="card p-6 max-w-lg">
        <p className="text-red-300 font-medium mb-1">Non riesco a caricare la Home</p>
        <p className="text-sm text-gray-400">{errore}</p>
      </div>
    )
  }

  const rami = dati?.rami ?? []
  const interne = dati?.interne ?? { n_totali: 0, n_in_attenzione: 0 }
  const team = dati?.team ?? { n_persone: 0, sovraccarichi: 0 }
  const daGuardare = rami.reduce((s, r) => s + r.attenzione.length, 0)

  // STATO VUOTO — un dipendente senza incarichi, o un PM di progetti tutti
  // chiusi. L'endpoint risponde 200 con `rami: []`, non un errore: qui si rende
  // sereno, perché «non hai progetti» è una risposta legittima e non un guasto.
  if (rami.length === 0) {
    return (
      <div>
        <h1 className="text-xl font-semibold mb-4">Home</h1>
        <div className="card p-8 text-center">
          <p className="text-gray-300 mb-1">Nessun progetto da mostrare</p>
          <p className="text-sm text-gray-500">
            Non ci sono progetti attivi che ti riguardano. Se pensi che sia un
            errore, parlane col tuo PM.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl">
      {/* Intestazione di UNA riga: ogni riga qui è altezza rubata al polso. */}
      <div className="flex items-baseline justify-between gap-4 mb-4">
        <h1 className="text-xl font-semibold">Home</h1>
        <p className="text-xs text-gray-500">
          {daGuardare === 0
            ? 'Niente che richieda attenzione'
            : `${daGuardare} ${daGuardare === 1 ? 'progetto' : 'progetti'} da guardare`}
        </p>
      </div>

      {/* ═══ POLSO — i rami affiancati ═══
          `items-start`: l'altezza segue il contenuto, niente stiramento.
          `sm:grid-cols-2` solo se i rami sono due: con uno solo la card
          prende tutta la larghezza invece di lasciare metà schermo vuota. */}
      <div className={`grid gap-4 items-start mb-3 ${rami.length > 1 ? 'sm:grid-cols-2' : ''}`}>
        {rami.map((r) => <CardRamo key={r.azienda_id} ramo={r} />)}
      </div>

      {/* ═══ Striscia: team + interne ═══
          Una riga sola, non due card piene: è contesto, non protagonista. */}
      <div className="card px-4 py-2.5 mb-6 flex items-center justify-between gap-4 flex-wrap text-sm">
        <span className="text-gray-400">
          <span className="font-data text-gray-100">{team.n_persone}</span> persone
          {team.sovraccarichi > 0 ? (
            <>
              {' · '}
              <button
                onClick={() => navigate('/risorse')}
                className="text-amber-400 hover:text-amber-300"
                title="Apri Risorse per vedere il carico"
              >
                <span className="font-data">{team.sovraccarichi}</span> sovraccariche →
              </button>
            </>
          ) : (
            <span className="text-gray-600"> · nessun sovraccarico</span>
          )}
        </span>

        {/* Le interne: due numeri e un link. NON il dettaglio — il loro
            «sforamento ore» è di natura diversa da quello di un progetto-cliente
            (un corso non ha un cliente che paga la differenza), e mescolarli
            insegnerebbe a ignorare la lista. */}
        <button
          onClick={() => navigate('/attivita-interne')}
          className="text-gray-400 hover:text-gray-200"
          title="Apri Attività Interne"
        >
          <span className="font-data text-gray-100">{interne.n_totali}</span> attività interne
          {interne.n_in_attenzione > 0 && (
            <span className="text-amber-400">
              {' · '}<span className="font-data">{interne.n_in_attenzione}</span> in attenzione
            </span>
          )}
          {' →'}
        </button>
      </div>

      {/* ═══ ATTENZIONE — per ramo, corta ═══ */}
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-2">
        Da guardare
      </h2>
      <div className={`grid gap-4 items-start ${rami.length > 1 ? 'sm:grid-cols-2' : ''}`}>
        {rami.map((r) => (
          <BloccoAttenzione
            key={r.azienda_id}
            ramo={r}
            onApri={(pid) => navigate(`/elenco/${pid}`)}
          />
        ))}
      </div>
    </div>
  )
}
