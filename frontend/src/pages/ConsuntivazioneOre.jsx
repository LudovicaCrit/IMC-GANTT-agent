/**
 * ═════════════════════════════════════════════════════════════════════════
 * ConsuntivazioneOre.jsx — la settimana a ore, unità × giorni
 * ═════════════════════════════════════════════════════════════════════════
 *
 * LA pagina della Consuntivazione, su `/consuntivazione`. Dal passo 5.1
 * (23/09/2026) è l'unica: la pagina a cursore (ConsuntivazioneUser.jsx) non ha
 * più una rotta che ci porti, e sparisce col passo 5.2. Legge
 * `/api/consuntivi/me` e scrive su `/api/consuntivi/salva-blocchi`.
 *
 * Sta dentro `GuscioConsuntivazione` come ci stava la pagina a cursore: a un
 * manager o a un PM il guscio offre lo scambio fra «la mia settimana» — questa
 * griglia — e la vista del gruppo. Essere diventata la pagina unica non toglie
 * niente a chi supervisiona.
 *
 * Dalla griglia si dichiara TUTTO: le celle si SELEZIONANO (mezz'ore) e la
 * TESTA della riga — stato, resta, nota — si modifica (sotto-passi 2 e 3). La
 * presa visione («ancora fermo») non c'è più: un'unità ferma si dice con stato
 * e nota, lasciando vuote le celle dei giorni.
 *
 * LA MATRICE
 *   righe   = le unità di /me: un task, oppure — se scomposto — i suoi pezzi.
 *             Raggruppate per progetto, nell'ordine in cui /me le restituisce.
 *             Più le righe AGGIUNTE A MANO (sotto-passo 5): un task proprio che
 *             /me non propone — fuori finestra, sospeso, chiuso da poco — scelto
 *             da `AggiungiRiga`. Vivono solo nel browser finché non le si salva
 *             con delle ore: vedi `avvertenze` più sotto.
 *   colonne = lunedì-venerdì della settimana, ognuno in mattina/pomeriggio.
 *             Il weekend non c'è: il backend non accetta ore di sabato e
 *             domenica (N2).
 *
 * La struttura «giorni come colonne» è pensata per ospitare più avanti una
 * fascia separata (le presenze) sopra o sotto la matrice delle ore: i giorni
 * si calcolano una volta (`giorniSettimana`) e non sono cablati nella tabella.
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { fetchConsuntiviMe, salvaBlocchi } from '../api'
import GuscioConsuntivazione from '../components/consuntivazione/GuscioConsuntivazione'
import SelettoreSettimana from '../components/consuntivazione/SelettoreSettimana'
import PromemoriaNota from '../components/consuntivazione/PromemoriaNota'
import BarraSalvataggio from '../components/consuntivazione/BarraSalvataggio'
import AggiungiRiga from '../components/consuntivazione/AggiungiRiga'
import BannerScoperti from '../components/consuntivazione/BannerScoperti'
import { fmtOre, fmtGiorno } from '../components/consuntivazione/formato'
import {
  SOGLIE, GIORNI_LAVORATIVI, monteGiornaliero, livelloGiorno, livelloSettimana, giornoCoperto,
} from '../components/consuntivazione/soglie'

/* ── Come si mostra un livello di saturazione ─────────────────────────
 * Il segnale è sul NUMERO e le parole sono neutre: «oltre il monte» constata,
 * non valuta. Ambra e arancio per «oltre» e «è tanto», che non bloccano nulla;
 * il rosso solo oltre le 24 ore, l'unico caso che il backend rifiuta.
 */
const ASPETTO_LIVELLO = {
  normale: { cella: 'text-gray-300', etichetta: null },
  oltre:   { cella: 'text-amber-300', etichetta: 'oltre il monte' },
  alto:    { cella: 'bg-orange-950/50 text-orange-200', etichetta: 'è tanto' },
  tetto:   { cella: 'bg-red-950/60 text-red-200', etichetta: 'oltre 24h' },
}

/* ── Costanti ─────────────────────────────────────────────────────── */
const NOMI_GIORNO = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven']

// Lo stato come lo dichiara il dipendente (STATI_DICHIARABILI nel backend).
// «Completato» si legge «Concluso»: è la parola della griglia.
const STATO = {
  'In corso':   { etichetta: 'In corso', stile: 'bg-blue-900/50 text-blue-200 border-blue-800' },
  'Completato': { etichetta: 'Concluso', stile: 'bg-emerald-900/50 text-emerald-200 border-emerald-800' },
  'Bloccato':   { etichetta: 'Bloccato', stile: 'bg-red-900/50 text-red-200 border-red-800' },
}

/* ── Le scelte di una mezza giornata ──────────────────────────────────
 * A SELEZIONE, non a scrittura libera: si dice «2 ore», non «2h15». Passi da
 * mezz'ora fino a 6 ore; da 6,5 a 8 come «casi estremi», separati per non
 * invitarli. Il dato resta decimale (2,5 → 2.5 nel payload).
 * Un valore già salvato che cade fuori dai passi (0,25 da una giornata di 4,25)
 * si mostra come opzione in più, marcata «attuale», invece di sparire.
 */
const passi = (da, a) => Array.from({ length: Math.round((a - da) / 0.5) + 1 }, (_, i) => da + i * 0.5)
const SCELTE_NORMALI = passi(0.5, 6)
const SCELTE_ESTREME = passi(6.5, 8)
const IN_SCELTE = new Set([...SCELTE_NORMALI, ...SCELTE_ESTREME])

/* ── Date e numeri ────────────────────────────────────────────────── */
// Le date della settimana si calcolano sulla stringa ISO in UTC: con l'ora
// locale, un fuso o un cambio d'ora sposterebbero un giorno sull'altro.
const giornoIso = (lunediIso, offset) => {
  const [a, m, g] = lunediIso.split('-').map(Number)
  return new Date(Date.UTC(a, m - 1, g + offset)).toISOString().slice(0, 10)
}
export const giorniSettimana = (lunediIso) =>
  NOMI_GIORNO.map((nome, i) => {
    const iso = giornoIso(lunediIso, i)
    return { iso, nome, numero: Number(iso.slice(8, 10)) }
  })

const arrotonda2 = (x) => Math.round(x * 100) / 100
const oggiIso = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/**
 * Le ore di un giorno divise in mattina e pomeriggio — SOLO INTERFACCIA.
 *
 * Il dato salvato è l'ora-giorno ({giorno, ore}): mattina e pomeriggio non
 * esistono nel backend. Riaprendo una settimana la divisione si RICOSTRUISCE
 * con una regola fissa — prima la mattina, fino a metà del monte giornaliero;
 * il resto al pomeriggio. Chi aveva messo 0 + 3 ritrova 3 + 0: è voluto, la
 * divisione aiuta a comporre la giornata e non è un'informazione da conservare.
 */
export const dividiGiornata = (ore, metaMonteGiorno) => {
  const mattina = Math.min(ore, metaMonteGiorno)
  return { mattina: arrotonda2(mattina), pomeriggio: arrotonda2(ore - mattina) }
}

const orePerGiorno = (blocchi) =>
  Object.fromEntries((blocchi ?? []).map((b) => [b.giorno, Number(b.ore)]))

/* ── «Scomposto» vuol dire CHE HA PEZZI VIVI ──────────────────────────
 * `Annullato` è lo stato con cui il PM toglie un pezzo dal PIANO: il pezzo
 * resta in tabella — è la via che il Cantiere offre per cancellarlo
 * conservando le dichiarazioni già fatte — ma non è più lavoro da fare. Un
 * task i cui pezzi sono stati annullati tutti torna a essere un'unità di
 * lavoro: è M9, e il backend lo applica in due punti
 * (`tipo_unita_per_task` e `task_scomposti` in `task_settimana_dipendente`),
 * tutti e due con questo identico confronto.
 *
 * LA STRINGA È LA STESSA DEL BACKEND, di proposito e senza modo di condividerla
 * (il payload non porta un flag «scomposto»): se di là cambia, questa è la riga
 * da cambiare. Decidere qui con un criterio diverso — per esempio «ha pezzi
 * nella lista» — fa divergere la pagina dal salvataggio, ed è esattamente il
 * bug che questa costante chiude: la lista dei pezzi contiene anche gli
 * Annullati su cui ci sono ore (N21), quindi non è vuota, quindi il task veniva
 * disegnato come scomposto e non aveva nessuna riga su cui dichiarare — mentre
 * /salva-blocchi le ore le avrebbe accettate.
 */
const PEZZO_ANNULLATO = 'Annullato'
const haPezziVivi = (pezzi) => pezzi.some((p) => p.stato !== PEZZO_ANNULLATO)

/* ── Dalle righe di /me alle righe della matrice ──────────────────────
 * Una riga per UNITÀ: il task se non è scomposto, i pezzi se lo è. Un task
 * scomposto porta una riga-intestazione, e — se ha ore messe sul task prima
 * della scomposizione (M8) — una riga in sola lettura con quelle: stanno nei
 * totali, quindi devono stare anche nella matrice.
 * `modificabile` arriva da /me, che usa la stessa regola del salvataggio.
 *
 * Un task NON scomposto può comunque portarsi dietro dei pezzi: quelli
 * annullati su cui ci sono ore, che N21 tiene visibili. Allora si disegnano
 * tutt'e due — la riga del task, compilabile, e i pezzi accanto in sola
 * lettura: le loro ore stanno nei totali e devono stare anche nella matrice,
 * ma il posto dove dichiarare adesso è il task.
 *
 * `aggiunte` sono i task scelti a mano (sotto-passo 5). Entrano nel gruppo del
 * loro progetto se c'è già, altrimenti ne aprono uno — e allora `interna` resta
 * `null`, perché la tipologia del progetto la sa /me e /api/tasks non la porta:
 * meglio nessuna etichetta che una etichetta inventata. Sono righe piene a
 * tutti gli effetti (modificabili, celle vuote, testa editabile) tranne per
 * `aggiunta: true`, che serve alla × per toglierle e all'avvertenza.
 */
export function costruisciGruppi(taskSettimana, dipendenteId, aggiunte = []) {
  const gruppi = new Map()
  for (const t of taskSettimana ?? []) {
    if (!gruppi.has(t.progetto_id)) {
      gruppi.set(t.progetto_id, {
        progetto_id: t.progetto_id, progetto_nome: t.progetto_nome,
        interna: t.interna, righe: [],
      })
    }
    const righe = gruppi.get(t.progetto_id).righe
    const pezzi = t.sottotask ?? []

    const rigaPezzo = (p) => {
      const diUnAltro = p.assegnatario_id && p.assegnatario_id !== dipendenteId
      return {
        chiave: `sott:${p.id}`, tipo: 'sottotask', id: p.id, nome: p.nome,
        codice: `${t.task_id} · #${p.id}`, pezzo: true, modificabile: p.modificabile,
        motivoSolaLettura: diUnAltro ? 'di un collega'
          : p.stato === PEZZO_ANNULLATO ? 'annullato' : 'non più modificabile',
        stato: p.stato_dichiarato, nota: p.nota, residuo: p.ore_stimate_residue,
        presaVisione: p.presa_visione, notaEreditata: p.nota_ereditata,
        notaEreditataDa: p.nota_ereditata_da,
        blocchi: p.blocchi ?? [], storico: p.blocchi_storico ?? [],
      }
    }

    // NON scomposto: il task è l'unità di lavoro, con i pezzi annullati-con-ore
    // (se ce ne sono) accanto, in sola lettura.
    if (!haPezziVivi(pezzi)) {
      righe.push({
        chiave: `task:${t.task_id}`, tipo: 'task', id: t.task_id, nome: t.task_nome,
        codice: t.task_id, previste: t.ore_pianificate_settimana, inRitardo: t.in_ritardo,
        dataFine: t.data_fine, modificabile: t.modificabile,
        motivoSolaLettura: 'non più modificabile',
        stato: t.stato_dichiarato, nota: t.nota, residuo: t.ore_stimate_residue,
        presaVisione: t.presa_visione, notaEreditata: t.nota_ereditata,
        notaEreditataDa: t.nota_ereditata_da,
        blocchi: t.blocchi ?? [], storico: t.blocchi_storico ?? [],
      })
      righe.push(...pezzi.map(rigaPezzo))
      continue
    }

    righe.push({ chiave: `int:${t.task_id}`, tipo: 'intestazione', nome: t.task_nome, codice: t.task_id })
    if ((t.blocchi?.length ?? 0) + (t.blocchi_storico?.length ?? 0) > 0) {
      righe.push({
        chiave: `task-prima:${t.task_id}`, tipo: 'task', id: t.task_id,
        nome: 'ore sul task, prima della scomposizione', codice: t.task_id,
        modificabile: false, motivoSolaLettura: 'si compila sui pezzi',
        blocchi: t.blocchi ?? [], storico: t.blocchi_storico ?? [], secondaria: true,
      })
    }
    righe.push(...pezzi.map(rigaPezzo))
  }

  for (const t of aggiunte) {
    if (!gruppi.has(t.progetto_id)) {
      gruppi.set(t.progetto_id, {
        progetto_id: t.progetto_id, progetto_nome: t.progetto_nome || t.progetto_id,
        interna: null, righe: [],
      })
    }
    gruppi.get(t.progetto_id).righe.push({
      chiave: `task:${t.id}`, tipo: 'task', id: t.id, nome: t.nome, codice: t.id,
      modificabile: true, aggiunta: true,
      stato: null, nota: null, residuo: null, presaVisione: false,
      blocchi: [], storico: [],
    })
  }
  return [...gruppi.values()]
}

/**
 * Le ore del giorno di una riga, tenendo conto delle modifiche non salvate:
 * { [giornoIso]: {mattina, pomeriggio} } per i giorni toccati, altrimenti la
 * divisione dei blocchi di /me.
 */
const celleRiga = (riga, giorni, modificheRiga, metaMonteGiorno) => {
  const salvate = orePerGiorno(riga.blocchi)
  return Object.fromEntries(giorni.map((g) => [
    g.iso,
    modificheRiga?.[g.iso]
      ?? (salvate[g.iso] != null ? dividiGiornata(salvate[g.iso], metaMonteGiorno) : { mattina: 0, pomeriggio: 0 }),
  ]))
}

/** Le ore-giorno di una riga come le manderebbe il payload: solo giorni con ore. */
const blocchiDaCelle = (celle) =>
  Object.entries(celle)
    .map(([giorno, c]) => ({ giorno, ore: arrotonda2(c.mattina + c.pomeriggio) }))
    .filter((b) => b.ore > 0)

const stessiBlocchi = (a, b) => {
  const ma = orePerGiorno(a), mb = orePerGiorno(b)
  const giorni = new Set([...Object.keys(ma), ...Object.keys(mb)])
  return [...giorni].every((g) => arrotonda2(ma[g] ?? 0) === arrotonda2(mb[g] ?? 0))
}

/* ── La testa della riga: stato, nota, resta ──────────────────────────
 * `modificheTesta[chiave]` tiene SOLO i campi toccati; un campo assente vale
 * «come da /me». La nota vuota o di soli spazi vale null (come nel backend).
 * «Resta» si scrive come testo — «2,5» con la virgola deve funzionare — e si
 * legge in numero: vuoto = null, non-numero o negativo = NaN (non valido).
 */
const normNota = (s) => (s ?? '').trim() || null
const leggiResiduo = (testo) => {
  const t = (testo ?? '').trim()
  if (t === '') return null
  const n = Number(t.replace(',', '.'))
  return Number.isFinite(n) && n >= 0 ? n : NaN
}
const testaCorrente = (r, m) => {
  const stato = m?.stato !== undefined ? m.stato : (r.stato ?? null)
  const notaTesto = m?.nota !== undefined ? m.nota : (r.nota ?? '')
  const residuoTesto = m?.residuo !== undefined
    ? m.residuo
    : (r.residuo != null ? fmtOre(r.residuo) : '')
  const residuo = leggiResiduo(residuoTesto)
  return {
    stato, notaTesto, residuoTesto, residuo,
    statoCambiato: stato !== (r.stato ?? null),
    notaCambiata: normNota(notaTesto) !== normNota(r.nota),
    residuoCambiato: Number.isNaN(residuo) || residuo !== (r.residuo ?? null),
  }
}

/* ── Pagina ───────────────────────────────────────────────────────── */
export default function ConsuntivazioneOre() {
  const [dati, setDati] = useState(null)
  const [loading, setLoading] = useState(true)
  const [errore, setErrore] = useState(null)
  // Modifiche non salvate alle celle: { [chiaveRiga]: { [giornoIso]: {mattina, pomeriggio} } }
  const [modifiche, setModifiche] = useState({})
  // …e alla testa della riga: { [chiaveRiga]: { stato?, nota?, residuo? } }
  const [modificheTesta, setModificheTesta] = useState({})
  // I task aggiunti a mano (sotto-passo 5), nell'ordine in cui li si sceglie.
  // Non sono uno stato del server: esistono solo finché non si ricarica /me —
  // e dopo un salvataggio con ore tornano da soli, per N21.
  const [aggiunte, setAggiunte] = useState([])
  const [salvataggio, setSalvataggio] = useState(null)   // null | 'invio' | 'ok' | messaggio
  const [erroriSalvataggio, setErroriSalvataggio] = useState([])
  const [avvisi, setAvvisi] = useState([])

  const carica = useCallback((settimana, dopoSalvataggio = null) => {
    setLoading(true)
    setErrore(null)
    fetchConsuntiviMe(settimana)
      .then((d) => {
        setDati(d)
        setModifiche({})
        setModificheTesta({})
        setAggiunte([])
        setSalvataggio(dopoSalvataggio ? 'ok' : null)
        setErroriSalvataggio([])
        setAvvisi(dopoSalvataggio?.avvisi ?? [])
      })
      .catch((e) => setErrore(e?.message || String(e)))
      .finally(() => setLoading(false))
  }, [])
  useEffect(() => { carica(null) }, [carica])

  const vista = useMemo(() => {
    if (!dati) return null
    const giorni = giorniSettimana(dati.settimana)
    const gruppi = costruisciGruppi(dati.task_settimana, dati.dipendente_id, aggiunte)
    const righe = gruppi.flatMap((g) => g.righe).filter((r) => r.tipo !== 'intestazione')
    const monteSettimana = Number(dati.ore_contrattuali) || 0
    // Il monte GIORNALIERO non esiste nel modello: si ricava dal settimanale su
    // 5 giorni (40 → 8, 20 → 4). Serve solo a dividere mattina e pomeriggio.
    const metaMonteGiorno = monteSettimana / 5 / 2
    // Le unità già in griglia: non si offrono una seconda volta nella
    // selezione, che darebbe due righe sullo stesso task.
    const taskInGriglia = new Set([
      ...(dati.task_settimana ?? []).map((t) => t.task_id),
      ...aggiunte.map((t) => t.id),
    ])
    // I progetti su cui la persona sta già lavorando: servono all'ordinamento
    // della selezione, non a filtrarla.
    const progettiAttivi = new Set((dati.task_settimana ?? []).map((t) => t.progetto_id))
    return { giorni, gruppi, righe, monteSettimana, metaMonteGiorno, taskInGriglia, progettiAttivi }
  }, [dati, aggiunte])

  // Le celle e la testa correnti di ogni riga, e le righe DAVVERO modificate:
  // una riga toccata e riportata ai valori di partenza non conta come modifica.
  //
  // I PROBLEMI si calcolano sulle righe modificate, dal vivo, e fermano il
  // salvataggio prima che parta — meglio chiedere lo stato accanto alla riga
  // che incassare un 400:
  //   N5  ore senza stato: il backend le rifiuta, e «ore» vuol dire lavoro
  //       dichiarato senza dire a che punto è;
  //   D4  Bloccato senza nota: un fermo va spiegato;
  //   «resta» non numerico o negativo.
  //
  // Le AVVERTENZE invece non fermano niente: constatano una conseguenza che
  // l'utente non può dedurre. Oggi ce n'è una sola — una riga aggiunta a mano
  // senza ore. /me ripropone un task fuori finestra solo se ci sono BLOCCHI su
  // quella settimana (N21): uno stato o una nota da soli non bastano, e alla
  // prossima apertura la riga non ci sarebbe più. Il dato salvato resta in DB,
  // ma sparirebbe dalla vista senza che nessuno l'abbia detto.
  //
  // `senzaSpiegazione` (sotto-passo 6) non è né l'una né l'altra cosa: è un
  // PROMEMORIA. Le righe che non hanno ore e non hanno stato — su cui cioè non
  // si è detto proprio niente — finiscono nel banner in fondo, che invita a
  // dire come stanno e non impedisce nulla.
  //   · si chiama così e NON «scoperte» di proposito: «scoperto» in questa
  //     pagina vuol già dire un'altra cosa — il GIORNO sotto il monte, nella
  //     sintesi dei giorni coperti. Sono due domande diverse (le ore di una
  //     giornata, la spiegazione di un'attività) e devono restare due parole
  //     diverse, o fra un mese nessuno saprà più quale delle due si sta
  //     leggendo;
  //   · le righe in SOLA LETTURA non ci entrano (il `continue` qui sotto le ha
  //     già tolte): un pezzo di un collega o un task chiuso non è roba di cui
  //     questo dipendente debba rendere conto;
  //   · nemmeno quelle AGGIUNTE a mano, che senza ore hanno già la loro
  //     avvertenza accanto alla riga. Due messaggi sulla stessa riga per due
  //     ragioni diverse si annullano a vicenda;
  //   · lo stato è la risposta alla domanda «come sta». Una nota da sola non
  //     toglie la riga dall'elenco: dice qualcosa, ma non dice a che punto è.
  const stato = useMemo(() => {
    if (!vista) return null
    const celle = {}
    const teste = {}
    const cambi = {}
    const problemi = {}
    const avvertenze = {}
    const senzaSpiegazione = []
    const modificate = []
    for (const r of vista.righe) {
      celle[r.chiave] = celleRiga(r, vista.giorni, modifiche[r.chiave], vista.metaMonteGiorno)
      if (!r.modificabile) continue
      const testa = testaCorrente(r, modificheTesta[r.chiave])
      teste[r.chiave] = testa
      const blocchi = blocchiDaCelle(celle[r.chiave])
      if (r.aggiunta && blocchi.length === 0) {
        avvertenze[r.chiave] = 'senza ore questa riga non tornerà: alla prossima apertura questo task non è fra quelli della settimana'
      }
      // Ore della riga = celle + storico, come il totale che la riga mostra.
      const senzaOre = blocchi.length === 0 && r.storico.length === 0
      if (!r.aggiunta && senzaOre && !testa.stato) {
        senzaSpiegazione.push({ chiave: r.chiave, nome: r.nome })
      }
      const celleCambiate = Boolean(modifiche[r.chiave]) && !stessiBlocchi(r.blocchi, blocchi)
      if (!(celleCambiate || testa.statoCambiato || testa.notaCambiata || testa.residuoCambiato)) continue
      modificate.push(r)
      cambi[r.chiave] = { celleCambiate, blocchi }
      const p = {}
      if (blocchi.length > 0 && !testa.stato) p.stato = 'hai messo delle ore: scegli lo stato'
      if (testa.stato === 'Bloccato' && !normNota(testa.notaTesto)) p.nota = 'bloccato: scrivi il motivo nella nota'
      if (Number.isNaN(testa.residuo)) p.residuo = '«resta» dev\'essere un numero di ore, 0 o più'
      if (Object.keys(p).length) problemi[r.chiave] = p
    }
    const totaleGiorno = Object.fromEntries(vista.giorni.map((g) => [g.iso, 0]))
    let totaleSettimana = 0
    for (const r of vista.righe) {
      for (const g of vista.giorni) {
        const ore = celle[r.chiave][g.iso].mattina + celle[r.chiave][g.iso].pomeriggio
        totaleGiorno[g.iso] += ore
        totaleSettimana += ore
      }
      for (const b of r.storico) {
        if (b.giorno in totaleGiorno) totaleGiorno[b.giorno] += Number(b.ore)
        totaleSettimana += Number(b.ore)
      }
    }
    for (const g of vista.giorni) totaleGiorno[g.iso] = arrotonda2(totaleGiorno[g.iso])

    // ── Saturazione e giorni coperti: letti dai totali, contro il monte ──
    // Tutte le ore contano, anche storico e righe in sola lettura: sono le
    // stesse che il backend somma per il tetto delle 24h (N14). Un task fermo
    // non aggiunge ore, quindi non sposta nulla.
    const monteGiorno = monteGiornaliero(vista.monteSettimana)
    const livelloPerGiorno = Object.fromEntries(
      vista.giorni.map((g) => [g.iso, livelloGiorno(totaleGiorno[g.iso], monteGiorno)]))
    const giorniCoperti = vista.giorni.filter((g) => giornoCoperto(totaleGiorno[g.iso], monteGiorno)).length
    const giorniOltreTetto = vista.giorni.filter((g) => livelloPerGiorno[g.iso] === 'tetto')

    return {
      celle, teste, cambi, problemi, avvertenze, senzaSpiegazione, modificate, totaleGiorno,
      totaleSettimana: arrotonda2(totaleSettimana),
      monteGiorno, livelloPerGiorno, giorniCoperti, giorniOltreTetto,
      livelloSettimana: livelloSettimana(totaleSettimana, vista.monteSettimana),
    }
  }, [vista, modifiche, modificheTesta])

  const haPendenti = (stato?.modificate.length ?? 0) > 0

  useEffect(() => {
    if (!haPendenti) return
    const avvisa = (e) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', avvisa)
    return () => window.removeEventListener('beforeunload', avvisa)
  }, [haPendenti])

  const cambiaCella = (riga, giorno, meta, valore) => {
    setModifiche((prev) => {
      const correnti = celleRiga(riga, vista.giorni, prev[riga.chiave], vista.metaMonteGiorno)
      return {
        ...prev,
        [riga.chiave]: { ...(prev[riga.chiave] ?? {}), [giorno]: { ...correnti[giorno], [meta]: valore } },
      }
    })
    setSalvataggio(null)
    setErroriSalvataggio([])
  }

  /* Una riga aggiunta a mano si toglie con la ×: è un ripensamento, non una
   * modifica al DB. Si portano via anche le sue modifiche pendenti — altrimenti
   * resterebbero appese a una chiave che non ha più riga, e tornerebbero a
   * galla se si riaggiungesse lo stesso task. */
  const togliAggiunta = (riga) => {
    setAggiunte((prev) => prev.filter((t) => t.id !== riga.id))
    const scarta = (prev) => {
      const { [riga.chiave]: _via, ...resto } = prev
      return resto
    }
    setModifiche(scarta)
    setModificheTesta(scarta)
    setSalvataggio(null)
    setErroriSalvataggio([])
  }

  /* Dal banner alla riga. Il fuoco va sulla tendina dello stato, che è la
   * domanda che il banner ha appena fatto: portarci e basta lascerebbe
   * all'utente di ritrovare il punto con gli occhi in una tabella lunga.
   * `preventScroll` perché lo scorrimento l'ha già fatto la riga. */
  const vaiAllaRiga = (chiave) => {
    const riga = document.querySelector(`[data-riga="${chiave}"]`)
    if (!riga) return
    riga.scrollIntoView({ block: 'center', behavior: 'smooth' })
    riga.querySelector('select[aria-label^="Stato"]')?.focus({ preventScroll: true })
  }

  const cambiaTesta = (riga, campo, valore) => {
    setModificheTesta((prev) => ({ ...prev, [riga.chiave]: { ...(prev[riga.chiave] ?? {}), [campo]: valore } }))
    setSalvataggio(null)
    setErroriSalvataggio([])
  }

  /* ── Salvataggio ────────────────────────────────────────────────────
   * SOLO LE RIGHE MODIFICATE vanno nel payload: un'unità omessa resta intatta
   * nel DB (N7), quindi una riga non toccata non può essere cambiata per
   * sbaglio. Le righe in sola lettura (N21, pezzo di un collega) non ci entrano
   * mai: non possono essere fra le modificate.
   *
   * SI MANDA SOLO CIÒ CHE È CAMBIATO, per campo — il backend legge «assente»
   * come «non toccare» e null come «cancella»:
   *   blocchi  se le celle sono cambiate: mattina + pomeriggio → ore del giorno,
   *            solo i giorni con ore (`[]` azzera la riga);
   *   stato    se è cambiato, OPPURE se partono ore: il backend vuole lo stato
   *            nel payload quando ci sono ore (N5), non gli basta quello in DB;
   *   nota     se è cambiata, OPPURE se parte lo stato Bloccato: anche la nota
   *            del blocco dev'essere nel payload (D4);
   *   resta    se è cambiato (vuoto = null = cancellato).
   * PRESA VISIONE: la griglia non la gestisce più — un'unità ferma si dice con
   * stato e nota, celle vuote. Resta un solo gesto, senza interfaccia: se in DB
   * c'era la conferma di un fermo e ora partono ore, la si ritira (`false`),
   * perché «fermo» e ore nella stessa settimana si contraddicono (N22).
   */
  const salva = async () => {
    if (!haPendenti) return
    const problemi = Object.entries(stato.problemi).flatMap(([chiave, p]) => {
      const nome = vista.righe.find((r) => r.chiave === chiave)?.nome ?? chiave
      return Object.values(p).map((m) => `«${nome}»: ${m}`)
    })
    // Il tetto delle 24h in un giorno: il backend lo rifiuterebbe (N14), quindi
    // lo si dice PRIMA, con il giorno scritto come lo legge l'utente.
    for (const g of stato.giorniOltreTetto) {
      problemi.push(`${fmtGiorno(g.iso)}: ${fmtOre(stato.totaleGiorno[g.iso])}h in un giorno, oltre il massimo di ${SOGLIE.giornoTettoOre}h — togli qualche ora`)
    }
    if (problemi.length) {
      setErroriSalvataggio(problemi)
      setSalvataggio(problemi[0])
      return
    }
    // Righe aggiunte a mano che si salvano SENZA ore: il dato va in DB ma la
    // riga non tornerà (N21 richiede i blocchi). L'avvertenza è già accanto
    // alla riga; qui si chiede conferma, perché dopo il salvataggio la riga
    // sparisce dalla griglia e non c'è modo di accorgersene.
    //
    // LE ATTIVITÀ SENZA SPIEGAZIONE NON HANNO UNA FINESTRA, ed è una scelta.
    // Sarebbero il caso più frequente di tutti — quasi ogni settimana lascia
    // indietro qualcosa — e una finestra che compare quasi sempre si impara a
    // chiudere senza leggerla, portandosi via anche l'attenzione per quella
    // sopra, che invece dice una cosa che non si può dedurre. Il promemoria lo
    // fa il banner PRIMA (in fondo alla griglia) e la riga d'avviso DOPO (nella
    // barra di salvataggio, che è sticky e si vede anche da chi salva senza
    // essere mai sceso in fondo). Nessuno dei due ferma niente.
    const senzaOre = stato.modificate.filter((r) => stato.avvertenze[r.chiave])
    if (senzaOre.length) {
      const elenco = senzaOre.map((r) => `· ${r.nome}`).join('\n')
      const quante = senzaOre.length === 1 ? 'Questa attività aggiunta a mano non ha ore' : 'Queste attività aggiunte a mano non hanno ore'
      if (!window.confirm(
        `${quante}:\n${elenco}\n\nStato e nota si salvano, ma senza ore la riga non tornerà alla prossima apertura della settimana. Salvare lo stesso?`
      )) return
    }
    // Lo si calcola PRIMA di salvare, ma descrive il dopo: `senzaSpiegazione`
    // tiene già conto delle modifiche in corso, che fra un istante saranno in DB.
    const mute = stato.senzaSpiegazione
    const unita = stato.modificate.map((r) => {
      const testa = stato.teste[r.chiave]
      const { celleCambiate, blocchi } = stato.cambi[r.chiave]
      const voce = { tipo: r.tipo, id: r.id }
      const mandaStato = testa.statoCambiato || (celleCambiate && blocchi.length > 0)
      if (celleCambiate) voce.blocchi = blocchi
      if (mandaStato) voce.stato_dichiarato = testa.stato
      if (testa.notaCambiata || (mandaStato && testa.stato === 'Bloccato')) voce.nota = normNota(testa.notaTesto)
      if (testa.residuoCambiato) voce.ore_stimate_residue = testa.residuo
      if (r.presaVisione && celleCambiate && blocchi.length > 0) voce.presa_visione = false
      return voce
    })
    setSalvataggio('invio')
    setErroriSalvataggio([])
    try {
      const esito = await salvaBlocchi({ settimana: dati.settimana, unita })
      // L'avviso delle attività mute viaggia insieme a quelli del backend, nella
      // stessa lista: per chi legge sono tutt'e due «cose da sapere sul
      // salvataggio appena fatto», e distinguerle vorrebbe dire spiegare al
      // lettore da quale strato vengono, che non gli serve.
      const nota = mute.length
        ? [`${mute.length === 1 ? 'Un\u2019attività resta' : `${mute.length} attività restano`} senza ore e senza stato`
           + ` (${mute.slice(0, 3).map((s) => s.nome).join(', ')}${mute.length > 3 ? `, e altre ${mute.length - 3}` : ''}).`
           + ' Nessuno saprà perché sono ferme: basta lo stato, anche senza ore.']
        : []
      carica(dati.settimana, { ...esito, avvisi: [...nota, ...esito.avvisi] })
    } catch (e) {
      const errori = leggiErrori(e?.message || String(e), vista.righe)
      setErroriSalvataggio(errori)
      setSalvataggio(errori[0] ?? 'Salvataggio non riuscito')
    }
  }

  if (loading && !dati) return <GuscioConsuntivazione><p className="text-gray-400">Caricamento…</p></GuscioConsuntivazione>
  if (errore) return <GuscioConsuntivazione><p className="text-red-400">Errore: {errore}</p></GuscioConsuntivazione>
  if (!dati || !vista || !stato) return <GuscioConsuntivazione />

  const settimanaInfo = dati.settimane_disponibili?.find((s) => s.lunedi === dati.settimana)
  const soloLettura = settimanaInfo ? !settimanaInfo.compilabile : false
  const oggi = oggiIso()
  const nome = dati.nome?.split(' ')[0] ?? ''

  return (
    <GuscioConsuntivazione>
      {/* Il pulsante «← Consuntivazione a cursore» stava qui e se n'è andato
          col passo 5.1: non c'è più un altro posto dove andare. Resta la
          guardia sulla chiusura della scheda e sul cambio settimana, che sono
          gli altri due modi di perdere delle modifiche. */}
      <div className="mb-6">
        <p className="text-gray-400">Ciao {nome} — la tua settimana, a ore.</p>
        <p className="text-xs text-gray-600 mt-1">
          Per ogni attività: lo stato, le ore di ogni mezza giornata, quante ne restano. Un'attività ferma si dichiara con stato e nota, senza ore.
        </p>
      </div>

      <SelettoreSettimana
        settimane={dati.settimane_disponibili}
        attiva={dati.settimana}
        soloLettura={soloLettura}
        onScegli={(lunedi) => {
          if (haPendenti && !window.confirm('Hai modifiche non salvate. Cambiare settimana le perderà. Continuare?')) return
          carica(lunedi)
        }}
      />

      {/* ═══ Sintesi: giorni coperti + settimana contro il monte ═══
          Il completamento si misura per GIORNO, non per attività: «ho reso
          conto delle mie giornate». Un giorno è coperto quando le sue ore
          arrivano circa al monte giornaliero, da qualunque attività vengano. */}
      <div className="flex flex-wrap items-stretch gap-4 mb-4" data-sintesi>
        <div className="bg-gray-800 rounded-xl px-5 py-3 border border-gray-700">
          <p className="text-xs text-gray-400">Giorni coperti</p>
          <p className="text-2xl font-bold mt-0.5" data-giorni-coperti={stato.giorniCoperti}>
            {stato.giorniCoperti}<span className="text-gray-500 text-lg">/{GIORNI_LAVORATIVI}</span>
          </p>
          <div className="flex gap-1 mt-1.5">
            {vista.giorni.map((g) => {
              const coperto = giornoCoperto(stato.totaleGiorno[g.iso], stato.monteGiorno)
              return (
                <span key={g.iso}
                      title={`${fmtGiorno(g.iso)}: ${fmtOre(stato.totaleGiorno[g.iso])}h su ${fmtOre(stato.monteGiorno)}h`}
                      className={`text-[10px] px-1.5 py-0.5 rounded border ${
                        coperto ? 'bg-emerald-900/40 border-emerald-800 text-emerald-200' : 'border-gray-700 text-gray-500'}`}>
                  {g.nome.toLowerCase()}
                </span>
              )
            })}
          </div>
          <p className="text-[10px] text-gray-500 mt-1">
            coperto da {fmtOre(stato.monteGiorno * SOGLIE.giornoCopertoQuota)}h (monte {fmtOre(stato.monteGiorno)}h al giorno)
          </p>
        </div>
        <div className={`rounded-xl px-5 py-3 border ${
          stato.livelloSettimana === 'normale' ? 'bg-gray-800 border-gray-700'
            : stato.livelloSettimana === 'oltre' ? 'bg-amber-950/30 border-amber-800/60'
            : 'bg-orange-950/40 border-orange-800/70'}`}
             data-livello-settimana={stato.livelloSettimana}>
          <p className="text-xs text-gray-400">Ore della settimana</p>
          <p className={`text-2xl font-bold mt-0.5 ${ASPETTO_LIVELLO[stato.livelloSettimana].cella}`}>
            {fmtOre(stato.totaleSettimana)}<span className="text-gray-500 text-lg">/{fmtOre(vista.monteSettimana)}h</span>
          </p>
          <p className="text-[11px] mt-1 text-gray-400">
            {ASPETTO_LIVELLO[stato.livelloSettimana].etichetta ?? 'entro il monte settimanale'}
          </p>
        </div>
      </div>

      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-x-auto"
           data-totale-settimana={stato.totaleSettimana} data-totale-me={dati.totale_ore}>
        <table className="w-full text-sm border-collapse">
          <thead className="bg-gray-800 text-gray-400">
            <tr>
              <th rowSpan={2} className="px-3 py-2 text-left font-medium min-w-[14rem]">Attività</th>
              <th rowSpan={2} className="px-3 py-2 text-left font-medium min-w-[12rem]">Stato · nota · resta</th>
              {vista.giorni.map((g) => (
                <th key={g.iso} colSpan={2}
                    className={`px-1 pt-2 pb-0.5 text-center font-medium border-l border-gray-700 ${g.iso > oggi ? 'text-gray-600' : ''}`}
                    title={g.iso > oggi ? 'Giorno futuro: non si dichiarano ore' : undefined}>
                  {g.nome} {g.numero}
                </th>
              ))}
              <th rowSpan={2} className="px-3 py-2 text-right font-medium border-l border-gray-700">Totale</th>
            </tr>
            <tr className="text-[10px] uppercase tracking-wider text-gray-500">
              {vista.giorni.map((g) => (
                <React.Fragment key={g.iso}>
                  <th className="px-1 pb-1.5 font-normal border-l border-gray-700">matt.</th>
                  <th className="px-1 pb-1.5 font-normal">pom.</th>
                </React.Fragment>
              ))}
            </tr>
          </thead>

          <tbody>
            {vista.gruppi.map((gruppo) => (
              <React.Fragment key={gruppo.progetto_id}>
                <tr className="bg-gray-800/40 border-t border-gray-800">
                  <td colSpan={3 + vista.giorni.length * 2} className="px-3 py-1.5">
                    {/* La tipologia la sa /me. Un gruppo nato da una riga
                        aggiunta a mano ha `interna: null` (vedi
                        costruisciGruppi): nessuna etichetta, invece di
                        dichiarare «Progetto» senza saperlo. */}
                    {gruppo.interna != null && (
                      <span className={`px-2 py-0.5 rounded text-[10px] uppercase tracking-wider font-medium mr-2 ${
                        gruppo.interna ? 'bg-gray-700 text-gray-300' : 'bg-blue-900/50 text-blue-300 border border-blue-800'
                      }`}>
                        {gruppo.interna ? 'Interna' : 'Progetto'}
                      </span>
                    )}
                    <span className="font-medium text-gray-200">{gruppo.progetto_nome}</span>
                  </td>
                </tr>
                {gruppo.righe.map((r) => r.tipo === 'intestazione'
                  ? <RigaIntestazione key={r.chiave} riga={r} colonne={vista.giorni.length * 2 + 2} />
                  : <RigaUnita key={r.chiave} riga={r} giorni={vista.giorni} celle={stato.celle[r.chiave]}
                               testa={stato.teste[r.chiave]} problemi={stato.problemi[r.chiave]}
                               avvertenza={stato.avvertenze[r.chiave]}
                               onRimuovi={r.aggiunta ? () => togliAggiunta(r) : null}
                               onCambiaTesta={(campo, valore) => cambiaTesta(r, campo, valore)}
                               modificata={stato.modificate.includes(r)}
                               bloccata={soloLettura || salvataggio === 'invio'} oggi={oggi}
                               onCambia={(giorno, meta, valore) => cambiaCella(r, giorno, meta, valore)} />
                )}
              </React.Fragment>
            ))}
          </tbody>

          <tfoot>
            <tr className="border-t-2 border-gray-700 bg-gray-800/60 text-gray-300">
              <td colSpan={2} className="px-3 py-2 text-right text-xs uppercase tracking-wider text-gray-500">
                Totale giorno
              </td>
              {vista.giorni.map((g) => {
                const livello = stato.livelloPerGiorno[g.iso]
                const aspetto = ASPETTO_LIVELLO[livello]
                return (
                  <td key={g.iso} colSpan={2}
                      className={`px-1 py-2 text-center font-mono border-l border-gray-700 ${aspetto.cella}`}
                      data-totale-giorno={g.iso} data-livello={livello}
                      title={`${fmtGiorno(g.iso)}: ${fmtOre(stato.totaleGiorno[g.iso])}h su ${fmtOre(stato.monteGiorno)}h di monte`}>
                    {stato.totaleGiorno[g.iso] ? fmtOre(stato.totaleGiorno[g.iso]) : <span className="text-gray-600">·</span>}
                    {aspetto.etichetta && (
                      <span className="block text-[10px] font-sans leading-tight">{aspetto.etichetta}</span>
                    )}
                  </td>
                )
              })}
              <td className={`px-3 py-2 text-right font-mono font-semibold border-l border-gray-700 ${
                ASPETTO_LIVELLO[stato.livelloSettimana].cella}`}>
                {fmtOre(stato.totaleSettimana)}
                <span className="block text-[10px] font-normal text-gray-500">su {fmtOre(vista.monteSettimana)} di monte</span>
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      <p className="text-[11px] text-gray-600 mt-3">
        Mattina e pomeriggio sono solo un aiuto per comporre la giornata: si salvano le ore del giorno.
        Le ore <span className="text-amber-300/80">storiche</span> vengono dai consuntivi settimanali precedenti e non si modificano.
      </p>

      {/* «Di queste non hai detto niente»: l'invito a spiegare le attività
          rimaste senza ore e senza stato. Non è la copertura — quella sta in
          cima e guarda i giorni — e non ferma il salvataggio.

          QUANDO COMPARE: solo se nella settimana c'è già qualcosa — ore
          salvate, o modifiche in corso. Su una settimana ancora vergine ogni
          riga è senza ore e senza stato, e aprire la pagina per trovarsi
          «13 attività non hanno né ore né stato» non è un promemoria, è un
          rimprovero per essersi presentati. Il promemoria ha senso quando si è
          cominciato: allora quelle rimaste indietro si vedono per quello che
          sono. */}
      {!soloLettura && (haPendenti || stato.totaleSettimana > 0) && (
        <BannerScoperti scoperti={stato.senzaSpiegazione} onVai={vaiAllaRiga} />
      )}

      {/* Fuori programma: un task proprio che la settimana non propone. La
          selezione riceve già decise le due liste che la riguardano — cosa
          escludere e cosa mettere in cima — perché sono fatti di QUESTA
          settimana, e la pagina è l'unica che li ha. */}
      {!soloLettura && (
        <AggiungiRiga
          lunedi={dati.settimana}
          dipendenteId={dati.dipendente_id}
          escludi={vista.taskInGriglia}
          progettiAttivi={vista.progettiAttivi}
          disabilitato={salvataggio === 'invio'}
          onScegli={(task) => {
            setAggiunte((prev) => prev.some((t) => t.id === task.id) ? prev : [...prev, task])
            setSalvataggio(null)
          }}
        />
      )}

      {!soloLettura && (
        <BarraSalvataggio
          stato={salvataggio}
          haPendenti={haPendenti}
          nModifiche={stato.modificate.length}
          onSalva={salva}
          errori={erroriSalvataggio}
          avvisi={avvisi}
        />
      )}
    </GuscioConsuntivazione>
  )
}

/**
 * Il messaggio di un 400 in una lista leggibile. Il backend manda «Consuntivo
 * non salvato: a; b; c» con gli id delle unità («task T063: …»): qui si
 * dividono le violazioni e si mette accanto all'id il NOME dell'attività, che
 * è ciò che l'utente vede in griglia. Le date ISO diventano «lun 7 set» e le ore
 * «29.0h» diventano «29h»: il messaggio va letto da chi compila, non dal backend.
 */
export function leggiErrori(messaggio, righe) {
  const nomi = new Map(righe.map((r) => [`${r.tipo} ${r.id}`, r.nome]))
  return messaggio
    .replace(/^Consuntivo non salvato:\s*/, '')
    .split('; ')
    .map((m) => m
      .replace(/^(task \S+|sottotask \d+)(:|,)/, (tutto, chiave, seg) =>
        nomi.has(chiave) ? `«${nomi.get(chiave)}» (${chiave})${seg}` : tutto)
      .replace(/\b(\d{4}-\d{2}-\d{2})\b/g, (iso) => fmtGiorno(iso))
      .replace(/\b(\d+(?:\.\d+)?)h\b/g, (_, n) => `${fmtOre(Number(n))}h`))
    .filter(Boolean)
}

/* ── Riga-intestazione di un task scomposto ───────────────────────── */
function RigaIntestazione({ riga, colonne }) {
  return (
    <tr className="border-t border-gray-800/60">
      <td colSpan={colonne + 1} className="px-3 pt-2 pb-1">
        <span className="text-gray-300">{riga.nome}</span>
        <span className="text-xs text-gray-600 ml-2">{riga.codice} · scomposto in pezzi</span>
      </td>
    </tr>
  )
}

/* ── Una mezza giornata ───────────────────────────────────────────── */
function SceltaOre({ valore, onScegli, disabilitata, etichetta }) {
  const fuoriPasso = valore > 0 && !IN_SCELTE.has(valore)
  return (
    <select
      value={valore > 0 ? String(valore) : ''}
      disabled={disabilitata}
      onChange={(e) => onScegli(e.target.value === '' ? 0 : Number(e.target.value))}
      aria-label={etichetta}
      className={`w-full min-w-[3.25rem] appearance-none text-center font-mono rounded-md py-1 px-0.5 text-sm border
                  focus:outline-none focus:ring-2 focus:ring-blue-600 disabled:cursor-not-allowed ${
        valore > 0
          ? 'bg-blue-950/50 border-blue-800/70 text-blue-100'
          : 'bg-transparent border-gray-800 text-gray-600 hover:border-gray-600'
      } ${disabilitata ? 'opacity-40' : ''}`}
    >
      <option value="">·</option>
      {fuoriPasso && <option value={String(valore)}>{fmtOre(valore)} (attuale)</option>}
      {SCELTE_NORMALI.map((v) => <option key={v} value={String(v)}>{fmtOre(v)}</option>)}
      <optgroup label="casi estremi">
        {SCELTE_ESTREME.map((v) => <option key={v} value={String(v)}>{fmtOre(v)}</option>)}
      </optgroup>
    </select>
  )
}

/* ── La testa modificabile: stato, resta, nota ────────────────────────
 * STATO prima di tutto: è la domanda della riga («a che punto è?») ed è
 * sempre visibile. RESTA accanto, a portata di mano: le ore che mancano sono il
 * perno dell'avanzamento, e un campo nascosto non lo compila nessuno. NOTA
 * sotto, a tutta larghezza.
 * I problemi (ore senza stato, Bloccato senza nota, resta non valido) si
 * mostrano ACCANTO al campo, dal vivo: il salvataggio non parte finché ci sono.
 */
function TestaModificabile({ riga: r, testa, problemi, disabilitata, ferma, onCambia }) {
  const bordo = (errore) => errore ? 'border-red-700 ring-1 ring-red-800' : 'border-gray-700'
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1.5">
        <select
          value={testa.stato ?? ''}
          disabled={disabilitata}
          onChange={(e) => onCambia('stato', e.target.value || null)}
          aria-label={`Stato di ${r.nome}`}
          className={`flex-1 min-w-0 rounded-md px-1.5 py-1 text-xs border bg-gray-950 focus:outline-none focus:ring-2 focus:ring-blue-600 ${
            testa.stato ? STATO[testa.stato].stile : 'text-gray-400'} ${bordo(problemi?.stato)}`}
        >
          <option value="">stato ▾</option>
          <option value="In corso">In corso</option>
          <option value="Completato">Concluso</option>
          <option value="Bloccato">Bloccato</option>
        </select>
        <label className={`flex items-center gap-1 rounded-md px-1.5 py-1 text-xs border bg-gray-950 ${bordo(problemi?.residuo)}`}
               title="Quante ore mancano ancora per finire, secondo te. Vuoto = non stimato; 0 = finito.">
          <span className="text-amber-300/80">resta</span>
          <input
            type="text" inputMode="decimal"
            value={testa.residuoTesto}
            disabled={disabilitata}
            onChange={(e) => onCambia('residuo', e.target.value)}
            placeholder="—"
            aria-label={`Ore che restano su ${r.nome}`}
            className="w-10 bg-transparent text-right font-mono text-amber-100 focus:outline-none placeholder:text-gray-600"
          />
          <span className="text-gray-500">h</span>
        </label>
      </div>
      <input
        type="text"
        value={testa.notaTesto}
        disabled={disabilitata}
        onChange={(e) => onCambia('nota', e.target.value)}
        placeholder={testa.stato === 'Bloccato' ? 'Perché è bloccato? (obbligatoria)' : 'Nota (facoltativa)'}
        aria-label={`Nota su ${r.nome}`}
        className={`w-full rounded-md px-2 py-1 text-xs border bg-gray-950 text-gray-200 placeholder:text-gray-600
                    focus:outline-none focus:ring-2 focus:ring-blue-600 ${bordo(problemi?.nota)}`}
      />
      {problemi && (
        <ul className="text-[11px] text-red-400 space-y-0.5" data-problemi={r.chiave}>
          {Object.values(problemi).map((m) => <li key={m}>⚠ {m}</li>)}
        </ul>
      )}
      <PromemoriaNota testo={r.notaEreditata} da={r.notaEreditataDa} mostra={ferma && !normNota(testa.notaTesto)} />
    </div>
  )
}

/* ── Riga di un'unità ─────────────────────────────────────────────── */
function RigaUnita({ riga: r, giorni, celle, testa, problemi, avvertenza, modificata, bloccata, oggi,
                     onCambia, onCambiaTesta, onRimuovi }) {
  const storico = orePerGiorno(r.storico)
  const totale = arrotonda2(
    Object.values(celle).reduce((s, c) => s + c.mattina + c.pomeriggio, 0)
    + r.storico.reduce((s, b) => s + Number(b.ore), 0))
  const ferma = totale === 0
  const statoRiga = STATO[r.stato]
  const modificabileTesta = r.modificabile && !r.secondaria && testa

  return (
    <tr className={`border-t border-gray-800/60 align-top ${
      !r.modificabile ? 'bg-gray-950/40' : modificata ? 'bg-amber-950/20' : ''}`}
        data-riga={r.chiave}>
      {/* Attività */}
      <td className={`px-3 py-2 ${r.pezzo || r.secondaria ? 'pl-7' : ''}`}>
        <p className={r.modificabile ? 'text-gray-200' : 'text-gray-500'}>
          {r.pezzo && <span className="text-gray-600 mr-1">↳</span>}
          {r.nome}
        </p>
        <p className="text-[11px] text-gray-600 flex flex-wrap gap-x-2 items-center">
          <span>{r.codice}</span>
          {r.previste != null && <span>previste {fmtOre(r.previste)}h</span>}
          {r.inRitardo && <span className="text-amber-500/90">⚠ scaduto</span>}
          {r.aggiunta && (
            <span className="px-1.5 rounded bg-blue-950/60 text-blue-300 border border-blue-900">
              aggiunta da te
            </span>
          )}
          {!r.modificabile && (
            <span className="px-1.5 rounded bg-gray-800 text-gray-400 border border-gray-700">
              sola lettura · {r.motivoSolaLettura}
            </span>
          )}
          {onRimuovi && (
            <button type="button" onClick={onRimuovi} disabled={bloccata}
                    data-togli-riga={r.chiave}
                    title="Togli questa riga dalla settimana"
                    aria-label={`Togli ${r.nome} dalla settimana`}
                    className="text-gray-600 hover:text-red-400 disabled:opacity-40">✕</button>
          )}
        </p>
      </td>

      {/* Testa: stato · resta · nota.
          Modificabile sulle righe dell'utente; in sola lettura (N21, pezzo di un
          collega) resta com'è. Niente «ancora fermo»: un'unità ferma si dice con
          lo stato e la nota, lasciando vuote le celle dei giorni. */}
      <td className="px-3 py-2" data-testa={r.chiave}>
        {r.secondaria ? null : modificabileTesta ? (
          <>
            <TestaModificabile riga={r} testa={testa} problemi={problemi} disabilitata={bloccata}
                               ferma={ferma} onCambia={onCambiaTesta} />
            {/* Non è un errore e non ferma il salvataggio: è una conseguenza
                che dal form non si vede (vedi `avvertenze`). */}
            {avvertenza && (
              <p className="text-[11px] text-amber-400/90 mt-1" data-avvertenza={r.chiave}>
                ⓘ {avvertenza}
              </p>
            )}
          </>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-1.5">
              {statoRiga
                ? <span className={`px-1.5 py-0.5 rounded text-[11px] border ${statoRiga.stile}`}>{statoRiga.etichetta}</span>
                : <span className="text-[11px] text-gray-600">stato —</span>}
              <span className={`px-1.5 py-0.5 rounded text-[11px] border ${
                r.residuo != null ? 'border-amber-800/60 text-amber-200/90' : 'border-gray-800 text-gray-600'
              }`}>
                resta {r.residuo != null ? `${fmtOre(r.residuo)}h` : '—'}
              </span>
            </div>
            {r.nota && <p className="text-xs text-gray-400 italic mt-1">«{r.nota}»</p>}
          </>
        )}
      </td>

      {/* Giorni: mattina | pomeriggio. Lo storico occupa il giorno intero. */}
      {giorni.map((g) => {
        if (storico[g.iso] != null) {
          return (
            <td key={g.iso} colSpan={2} className="px-1 py-2 text-center border-l border-gray-800">
              <span className="inline-block px-1.5 py-0.5 rounded text-xs font-mono bg-amber-950/40 text-amber-300/80 border border-amber-900/60"
                    title="Ore storiche (consuntivo settimanale precedente): sola lettura">
                {fmtOre(storico[g.iso])} storico
              </span>
            </td>
          )
        }
        const c = celle[g.iso]
        // Sola lettura: righe non modificabili (N21, pezzo di un collega).
        // Celle bloccate: settimana chiusa, salvataggio in corso, giorno futuro.
        if (!r.modificabile) {
          return (
            <React.Fragment key={g.iso}>
              {[c.mattina, c.pomeriggio].map((v, i) => (
                <td key={i} className={`px-1 py-2 text-center font-mono text-gray-500 ${i === 0 ? 'border-l border-gray-800' : ''}`}>
                  {v ? fmtOre(v) : <span className="text-gray-700">·</span>}
                </td>
              ))}
            </React.Fragment>
          )
        }
        const disabilitata = bloccata || g.iso > oggi
        return (
          <React.Fragment key={g.iso}>
            <td className="px-0.5 py-1.5 border-l border-gray-800" data-cella={`${g.iso}:mattina`}>
              <SceltaOre valore={c.mattina} disabilitata={disabilitata}
                         etichetta={`${r.nome}, ${g.nome} ${g.numero}, mattina`}
                         onScegli={(v) => onCambia(g.iso, 'mattina', v)} />
            </td>
            <td className="px-0.5 py-1.5" data-cella={`${g.iso}:pomeriggio`}>
              <SceltaOre valore={c.pomeriggio} disabilitata={disabilitata}
                         etichetta={`${r.nome}, ${g.nome} ${g.numero}, pomeriggio`}
                         onScegli={(v) => onCambia(g.iso, 'pomeriggio', v)} />
            </td>
          </React.Fragment>
        )
      })}

      {/* Totale riga */}
      <td className={`px-3 py-2 text-right font-mono border-l border-gray-800 ${totale ? 'text-gray-100' : 'text-gray-600'}`}
          data-totale-riga={r.chiave}>
        {totale ? fmtOre(totale) : '·'}
      </td>
    </tr>
  )
}
