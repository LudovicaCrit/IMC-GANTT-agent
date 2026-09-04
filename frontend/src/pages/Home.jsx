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
import { fetchHomeDashboard, fetchConsuntiviMe } from '../api'
import PastigliaSemaforo from '../components/_shared/PastigliaSemaforo'
import { unitaDichiarata, unitaCompilabili } from '../components/_shared/unitaLavoro'
import { useAuth } from '../contexts/AuthContext'

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

/* ── LE MIE COSE — comune a PM e dipendente ────────────────────────────
 * Legge `/api/consuntivi/me`, LO STESSO endpoint della Consuntivazione. Non un
 * riassunto dedicato: due endpoint per «cosa devo fare questa settimana»
 * sarebbero due verità che divergono al primo ritocco.
 *
 * Tre domande, in quest'ordine — ed è l'ordine dell'urgenza, non della comodità:
 *   1. cosa mi manca da compilare  (contatore F-1)
 *   2. cosa è fermo e perché       (le note ereditate, F-2)
 *   3. cosa scade a breve          (`data_fine`, aggiunta a /me per questo)
 *
 * IL CONTATORE usa `unitaCompilabili`/`unitaDichiarata` da _shared: le stesse
 * funzioni della Consuntivazione, spostate lì apposta. Se contassero in due modi
 * diversi, la stessa persona vedrebbe «3/8» qui e «4/8» là senza sapere a chi
 * credere. Le mappe di modifiche pendenti sono vuote: in Home non si compila,
 * si guarda ciò che è già salvato.
 *
 * LE INTERNE SONO SEPARATE, col flag `interna` che /me porta già: un corso e un
 * task-cliente non chiedono la stessa attenzione, e mescolarli allunga la lista
 * senza aggiungere informazione.
 */
const GIORNI_IMMINENTE = 7

function LeMieCose({ me, onVaiACompilare }) {
  const task = me?.task_settimana ?? []
  const unita = unitaCompilabili(task, me?.dipendente_id, {}, {})
  const fatte = unita.filter((u) => unitaDichiarata(u.riga, u.pendenti)).length
  const totali = unita.length

  const oggi = new Date(); oggi.setHours(0, 0, 0, 0)
  const giorniA = (iso) => (iso ? Math.round((new Date(iso) - oggi) / 86400000) : null)

  // Fermi CON UNA RAGIONE: la nota ereditata è il «perché» scritto in una
  // settimana precedente. Un task fermo senza spiegazione non entra qui — non
  // c'è niente da ricordare.
  const fermi = task.filter((t) => t.nota_ereditata)
  // Imminenti: scadono entro una settimana o sono già scadute, e non sono
  // chiuse. `in_ritardo` lo dice il backend, la soglia dei 7 giorni è resa.
  const imminenti = task
    .filter((t) => {
      const g = giorniA(t.data_fine)
      return t.in_ritardo || (g !== null && g >= 0 && g <= GIORNI_IMMINENTE)
    })
    .sort((a, b) => (giorniA(a.data_fine) ?? 999) - (giorniA(b.data_fine) ?? 999))

  const clienti = task.filter((t) => !t.interna)
  const interne = task.filter((t) => t.interna)

  const testoScadenza = (t) => {
    const g = giorniA(t.data_fine)
    if (g === null) return null
    if (g < 0) return `scaduto da ${-g} ${g === -1 ? 'giorno' : 'giorni'}`
    if (g === 0) return 'scade oggi'
    if (g === 1) return 'scade domani'
    return `scade fra ${g} giorni`
  }

  return (
    <div className="card p-5 mb-4">
      <div className="flex items-baseline justify-between gap-3 mb-3 flex-wrap">
        <h2 className="text-lg font-semibold text-gray-100">Le mie cose</h2>
        <button
          onClick={onVaiACompilare}
          className="text-sm text-accent-300 hover:text-accent-400"
        >
          {totali > 0 && fatte < totali
            ? `${totali - fatte} da compilare →`
            : 'Apri la consuntivazione →'}
        </button>
      </div>

      {/* Il contatore: la barra dice a colpo d'occhio quanto manca. */}
      <div className="flex items-center gap-3 mb-4">
        <span className="text-sm text-gray-400">
          <span className="font-data text-gray-100 text-lg">{fatte}</span>
          <span className="text-gray-600">/{totali}</span> compilate
        </span>
        <div className="flex-1 h-1.5 bg-surface-800 rounded-full overflow-hidden">
          <div
            className={`h-full progress-bar ${fatte === totali && totali > 0 ? 'bg-green-500' : 'bg-accent-400'}`}
            style={{ width: totali ? `${(fatte / totali) * 100}%` : '0%' }}
          />
        </div>
      </div>

      {task.length === 0 && (
        <p className="text-sm text-gray-500 italic">
          Nessun task assegnato in questa settimana.
        </p>
      )}

      {/* Fermi — con il perché, dalla nota ereditata */}
      {fermi.length > 0 && (
        <div className="mb-3">
          <h3 className="text-[11px] uppercase tracking-wider text-amber-500/80 mb-1">
            Fermi ({fermi.length})
          </h3>
          {fermi.map((t) => (
            <div key={t.task_id} className="text-sm py-1 flex items-baseline gap-2">
              <span className="text-amber-500 shrink-0" aria-hidden="true">▪</span>
              <span className="min-w-0">
                <span className="text-gray-200">{t.task_nome}</span>
                <span className="block text-[11px] text-gray-500 italic truncate">
                  «{t.nota_ereditata}»
                </span>
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Scadenze — solo quelle che stringono */}
      {imminenti.length > 0 && (
        <div className="mb-3">
          <h3 className="text-[11px] uppercase tracking-wider text-gray-500 mb-1">
            In scadenza ({imminenti.length})
          </h3>
          {imminenti.slice(0, 4).map((t) => (
            <div key={t.task_id} className="text-sm py-0.5 flex items-baseline justify-between gap-3">
              <span className="text-gray-200 truncate">{t.task_nome}</span>
              <span className={`text-[11px] shrink-0 ${t.in_ritardo ? 'text-red-400' : 'text-gray-500'}`}>
                {testoScadenza(t)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Il riepilogo per tipo: due numeri, non due liste */}
      <div className="text-xs text-gray-500 pt-2 border-t border-border-subtle">
        <span className="font-data text-gray-300">{clienti.length}</span> su progetti
        {interne.length > 0 && (
          <>
            {' · '}
            <span className="font-data text-gray-300">{interne.length}</span> attività interne
          </>
        )}
      </div>
    </div>
  )
}

/* ── IL CENNO — solo per il dipendente ─────────────────────────────────
 * Il dipendente SA come stanno i suoi progetti, ma non riceve gli strumenti per
 * intervenirci: non li dirige. Concretamente — pastiglia + nome, niente elenco
 * dei motivi, niente conteggio di fasi rosse.
 *
 * La differenza col PM non è di dato ma di RESA: l'endpoint restituisce a
 * entrambi lo stesso payload (`progetti_attivi_visibili` include per tutti i
 * progetti dove si ha un task). Filtrarlo lato server avrebbe voluto dire
 * distinguere «diretti» da «operati», che è una semantica nuova — decisione
 * separata, non un dettaglio di questa pagina.
 */
function CennoProgetti({ rami, onApri }) {
  const voci = rami.flatMap((r) =>
    r.attenzione.map((v) => ({ ...v, azienda: r.azienda }))
  )
  const nProgetti = rami.reduce((s, r) => s + r.polso.n_progetti, 0)

  return (
    <div className="card p-4">
      <div className="flex items-baseline justify-between gap-3 mb-2">
        <h2 className="text-sm font-semibold text-gray-300">I miei progetti</h2>
        <span className="text-xs text-gray-500">
          <span className="font-data text-gray-300">{nProgetti}</span> in corso
        </span>
      </div>

      {voci.length === 0 ? (
        <p className="text-xs text-gray-600 italic">
          Nessuno dei progetti su cui lavori è in difficoltà.
        </p>
      ) : (
        <>
          <p className="text-[11px] text-gray-500 mb-2">
            {voci.length} {voci.length === 1 ? 'progetto' : 'progetti'} da tenere d'occhio:
          </p>
          <div className="flex flex-wrap gap-2">
            {voci.map((v) => (
              <button
                key={v.progetto_id}
                onClick={() => onApri(v.progetto_id)}
                className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-surface-800/60
                           border border-border-subtle hover:border-border-default transition-colors"
                title={`${v.nome} — apri`}
              >
                <PastigliaSemaforo semaforo={v.semaforo} stato={v.stato} livello="progetto" />
                <span className="text-xs text-gray-300 truncate max-w-[190px]">{v.nome}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

/* ── Pagina ────────────────────────────────────────────────────────────── */
export default function Home() {
  const { user } = useAuth()
  const [dati, setDati] = useState(null)      // /home/dashboard
  const [me, setMe] = useState(null)          // /consuntivi/me — solo pm e user
  const [errore, setErrore] = useState(null)
  const [loading, setLoading] = useState(true)
  const [polsoAperto, setPolsoAperto] = useState(false)
  const navigate = useNavigate()

  const ruolo = user?.ruolo_app ?? 'user'
  const isManager = ruolo === 'manager'

  useEffect(() => {
    // Un manager NON chiede /me: la sua Home è il quadro d'insieme, e una
    // chiamata in più per dati che non rende sarebbe latenza regalata.
    // `allSettled` e non `all`: se /me fallisse, il quadro dei progetti deve
    // comparire lo stesso — è l'errore che rompeva la vecchia Home, dove un
    // 403 su una delle tre fetch lasciava la pagina bianca.
    const chiamate = isManager
      ? [fetchHomeDashboard()]
      : [fetchHomeDashboard(), fetchConsuntiviMe()]

    Promise.allSettled(chiamate)
      .then(([d, m]) => {
        if (d.status === 'fulfilled') setDati(d.value)
        else setErrore(d.reason?.message || 'Errore di caricamento')
        if (m?.status === 'fulfilled') setMe(m.value)
      })
      .finally(() => setLoading(false))
  }, [isManager])

  if (loading) return <p className="text-gray-400">Caricamento…</p>
  if (errore && !dati) {
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
  const apriProgetto = (pid) => navigate(`/elenco/${pid}`)

  /* ══ RAGGIO 1 — MANAGER ══════════════════════════════════════════════
   * Invariato dalla tappa 1: il quadro d'insieme, segmentato per società.
   * Nessuna «mie cose»: un manager guarda l'azienda, e i suoi task li compila
   * dalla Consuntivazione come tutti. */
  if (isManager) {
    if (rami.length === 0) return <VuotoSereno />
    return (
      <div className="max-w-6xl">
        <Intestazione daGuardare={daGuardare} />
        <div className={`grid gap-4 items-start mb-3 ${rami.length > 1 ? 'sm:grid-cols-2' : ''}`}>
          {rami.map((r) => <CardRamo key={r.azienda_id} ramo={r} />)}
        </div>
        <StrisciaTeam team={team} interne={interne} navigate={navigate} />
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-2">
          Da guardare
        </h2>
        <div className={`grid gap-4 items-start ${rami.length > 1 ? 'sm:grid-cols-2' : ''}`}>
          {rami.map((r) => (
            <BloccoAttenzione key={r.azienda_id} ramo={r} onApri={apriProgetto} />
          ))}
        </div>
      </div>
    )
  }

  /* ══ RAGGI 2 e 3 — PM e DIPENDENTE ═══════════════════════════════════
   * Condividono «le mie cose» IN CIMA: per chi opera, la prima domanda è
   * sempre «cosa devo fare io», non «come va l'azienda».
   * Sotto, la differenza:
   *   PM   → il polso e l'attenzione COMPLETI dei suoi progetti, ma COLLASSATI
   *          all'apertura. È lui che valuta i ritardi, quindi gli strumenti ci
   *          sono tutti — ma sotto la piega, perché «le mie cose» viene prima.
   *   USER → il CENNO: pastiglie e nomi. Sa che un progetto è rosso; non
   *          riceve l'elenco dei motivi, che è materiale per chi decide. */
  const isPm = ruolo === 'pm'

  return (
    <div className="max-w-4xl">
      <div className="flex items-baseline justify-between gap-4 mb-4">
        <h1 className="text-xl font-semibold">Home</h1>
        <p className="text-xs text-gray-500">{me?.nome ?? ''}</p>
      </div>

      <LeMieCose me={me} onVaiACompilare={() => navigate('/consuntivazione-new')} />

      {rami.length === 0 ? (
        <p className="text-xs text-gray-600 italic px-1">
          Non risultano progetti attivi che ti riguardano.
        </p>
      ) : isPm ? (
        <div className="card p-4">
          {/* Collassato di default: «le mie cose» deve restare sopra la piega.
              Il conteggio nell'intestazione dice se vale la pena aprire, così
              la scelta è informata anche da chiuso. */}
          <button
            onClick={() => setPolsoAperto(!polsoAperto)}
            className="w-full flex items-baseline justify-between gap-3 text-left"
          >
            <h2 className="text-sm font-semibold text-gray-300">
              I progetti che seguo
            </h2>
            <span className="text-xs text-gray-500">
              {daGuardare > 0
                ? <span className="text-amber-400">{daGuardare} da guardare</span>
                : 'tutto in ordine'}
              <span className="ml-2 text-gray-600">{polsoAperto ? '▲' : '▼'}</span>
            </span>
          </button>

          {polsoAperto && (
            <div className="mt-3 space-y-3">
              <div className={`grid gap-3 items-start ${rami.length > 1 ? 'sm:grid-cols-2' : ''}`}>
                {rami.map((r) => <CardRamo key={r.azienda_id} ramo={r} />)}
              </div>
              {rami.map((r) => (
                <BloccoAttenzione key={r.azienda_id} ramo={r} onApri={apriProgetto} />
              ))}
            </div>
          )}
        </div>
      ) : (
        <CennoProgetti rami={rami} onApri={apriProgetto} />
      )}
    </div>
  )
}

/* ── Pezzi condivisi fra i raggi ───────────────────────────────────────── */

function Intestazione({ daGuardare }) {
  return (
    <div className="flex items-baseline justify-between gap-4 mb-4">
      <h1 className="text-xl font-semibold">Home</h1>
      <p className="text-xs text-gray-500">
        {daGuardare === 0
          ? 'Niente che richieda attenzione'
          : `${daGuardare} ${daGuardare === 1 ? 'progetto' : 'progetti'} da guardare`}
      </p>
    </div>
  )
}

function VuotoSereno() {
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

function StrisciaTeam({ team, interne, navigate }) {
  return (
    <div className="card px-4 py-2.5 mb-6 flex items-center justify-between gap-4 flex-wrap text-sm">
      <span className="text-gray-400">
        <span className="font-data text-gray-100">{team.n_persone}</span> persone
        {team.sovraccarichi > 0 ? (
          <>
            {' · '}
            <button onClick={() => navigate('/risorse')}
              className="text-amber-400 hover:text-amber-300"
              title="Apri Risorse per vedere il carico">
              <span className="font-data">{team.sovraccarichi}</span> sovraccariche →
            </button>
          </>
        ) : (
          <span className="text-gray-600"> · nessun sovraccarico</span>
        )}
      </span>
      <button onClick={() => navigate('/attivita-interne')}
        className="text-gray-400 hover:text-gray-200" title="Apri Attività Interne">
        <span className="font-data text-gray-100">{interne.n_totali}</span> attività interne
        {interne.n_in_attenzione > 0 && (
          <span className="text-amber-400">
            {' · '}<span className="font-data">{interne.n_in_attenzione}</span> in attenzione
          </span>
        )}
        {' →'}
      </button>
    </div>
  )
}
