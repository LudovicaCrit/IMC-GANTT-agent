/**
 * ═════════════════════════════════════════════════════════════════════════
 * ConsuntivazioneOre.jsx — la settimana a ore, unità × giorni
 * ═════════════════════════════════════════════════════════════════════════
 *
 * Consuntivazione a ore, passo 4. AFFIANCATA a ConsuntivazioneUser.jsx (la
 * pagina a cursore), che resta viva fino al passo 5. Legge `/api/consuntivi/me`
 * e scrive su `/api/consuntivi/salva-blocchi`.
 *
 * Dalla griglia si dichiara TUTTO: le celle si SELEZIONANO (mezz'ore) e la
 * TESTA della riga — stato, resta, nota — si modifica (sotto-passi 2 e 3). La
 * presa visione («ancora fermo») non c'è più: un'unità ferma si dice con stato
 * e nota, lasciando vuote le celle dei giorni.
 *
 * LA MATRICE
 *   righe   = le unità di /me: un task, oppure — se scomposto — i suoi pezzi.
 *             Raggruppate per progetto, nell'ordine in cui /me le restituisce.
 *   colonne = lunedì-venerdì della settimana, ognuno in mattina/pomeriggio.
 *             Il weekend non c'è: il backend non accetta ore di sabato e
 *             domenica (N2).
 *
 * La struttura «giorni come colonne» è pensata per ospitare più avanti una
 * fascia separata (le presenze) sopra o sotto la matrice delle ore: i giorni
 * si calcolano una volta (`giorniSettimana`) e non sono cablati nella tabella.
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { fetchConsuntiviMe, salvaBlocchi } from '../api'
import GuscioConsuntivazione from '../components/consuntivazione/GuscioConsuntivazione'
import SelettoreSettimana from '../components/consuntivazione/SelettoreSettimana'
import PromemoriaNota from '../components/consuntivazione/PromemoriaNota'
import BarraSalvataggio from '../components/consuntivazione/BarraSalvataggio'
import { fmtOre } from '../components/consuntivazione/formato'

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

/* ── Dalle righe di /me alle righe della matrice ──────────────────────
 * Una riga per UNITÀ: il task se non è scomposto, i pezzi se lo è. Un task
 * scomposto porta una riga-intestazione, e — se ha ore messe sul task prima
 * della scomposizione (M8) — una riga in sola lettura con quelle: stanno nei
 * totali, quindi devono stare anche nella matrice.
 * `modificabile` arriva da /me, che usa la stessa regola del salvataggio.
 */
export function costruisciGruppi(taskSettimana, dipendenteId) {
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
    const scomposto = pezzi.some((p) => p.stato !== 'Annullato')

    if (!scomposto && pezzi.length === 0) {
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
    for (const p of pezzi) {
      const diUnAltro = p.assegnatario_id && p.assegnatario_id !== dipendenteId
      righe.push({
        chiave: `sott:${p.id}`, tipo: 'sottotask', id: p.id, nome: p.nome,
        codice: `${t.task_id} · #${p.id}`, pezzo: true, modificabile: p.modificabile,
        motivoSolaLettura: diUnAltro ? 'di un collega' : p.stato === 'Annullato' ? 'annullato' : 'non più modificabile',
        stato: p.stato_dichiarato, nota: p.nota, residuo: p.ore_stimate_residue,
        presaVisione: p.presa_visione, notaEreditata: p.nota_ereditata,
        notaEreditataDa: p.nota_ereditata_da,
        blocchi: p.blocchi ?? [], storico: p.blocchi_storico ?? [],
      })
    }
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
    const gruppi = costruisciGruppi(dati.task_settimana, dati.dipendente_id)
    const righe = gruppi.flatMap((g) => g.righe).filter((r) => r.tipo !== 'intestazione')
    const monteSettimana = Number(dati.ore_contrattuali) || 0
    // Il monte GIORNALIERO non esiste nel modello: si ricava dal settimanale su
    // 5 giorni (40 → 8, 20 → 4). Serve solo a dividere mattina e pomeriggio.
    const metaMonteGiorno = monteSettimana / 5 / 2
    return { giorni, gruppi, righe, monteSettimana, metaMonteGiorno }
  }, [dati])

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
  const stato = useMemo(() => {
    if (!vista) return null
    const celle = {}
    const teste = {}
    const cambi = {}
    const problemi = {}
    const modificate = []
    for (const r of vista.righe) {
      celle[r.chiave] = celleRiga(r, vista.giorni, modifiche[r.chiave], vista.metaMonteGiorno)
      if (!r.modificabile) continue
      const testa = testaCorrente(r, modificheTesta[r.chiave])
      teste[r.chiave] = testa
      const blocchi = blocchiDaCelle(celle[r.chiave])
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
    return { celle, teste, cambi, problemi, modificate, totaleGiorno, totaleSettimana: arrotonda2(totaleSettimana) }
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
    if (problemi.length) {
      setErroriSalvataggio(problemi)
      setSalvataggio(problemi[0])
      return
    }
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
      carica(dati.settimana, esito)
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
      <div className="flex items-start justify-between mb-6 gap-4">
        <div>
          <p className="text-gray-400">Ciao {nome} — la tua settimana, a ore.</p>
          <p className="text-xs text-gray-600 mt-1">
            Per ogni attività: lo stato, le ore di ogni mezza giornata, quante ne restano. Un'attività ferma si dichiara con stato e nota, senza ore.
          </p>
        </div>
        <Link to="/consuntivazione"
          className="px-3 py-2 rounded-lg text-sm font-medium bg-gray-800 text-gray-300 border border-gray-700 hover:text-white shrink-0">
          ← Consuntivazione a cursore
        </Link>
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
                    <span className={`px-2 py-0.5 rounded text-[10px] uppercase tracking-wider font-medium mr-2 ${
                      gruppo.interna ? 'bg-gray-700 text-gray-300' : 'bg-blue-900/50 text-blue-300 border border-blue-800'
                    }`}>
                      {gruppo.interna ? 'Interna' : 'Progetto'}
                    </span>
                    <span className="font-medium text-gray-200">{gruppo.progetto_nome}</span>
                  </td>
                </tr>
                {gruppo.righe.map((r) => r.tipo === 'intestazione'
                  ? <RigaIntestazione key={r.chiave} riga={r} colonne={vista.giorni.length * 2 + 2} />
                  : <RigaUnita key={r.chiave} riga={r} giorni={vista.giorni} celle={stato.celle[r.chiave]}
                               testa={stato.teste[r.chiave]} problemi={stato.problemi[r.chiave]}
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
              {vista.giorni.map((g) => (
                <td key={g.iso} colSpan={2} className="px-1 py-2 text-center font-mono border-l border-gray-700"
                    data-totale-giorno={g.iso}>
                  {stato.totaleGiorno[g.iso] ? fmtOre(stato.totaleGiorno[g.iso]) : <span className="text-gray-600">·</span>}
                </td>
              ))}
              <td className="px-3 py-2 text-right font-mono font-semibold border-l border-gray-700">
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
 * è ciò che l'utente vede in griglia.
 */
function leggiErrori(messaggio, righe) {
  const nomi = new Map(righe.map((r) => [`${r.tipo} ${r.id}`, r.nome]))
  return messaggio
    .replace(/^Consuntivo non salvato:\s*/, '')
    .split('; ')
    .map((m) => m.replace(/^(task \S+|sottotask \d+)(:|,)/, (tutto, chiave, seg) =>
      nomi.has(chiave) ? `«${nomi.get(chiave)}» (${chiave})${seg}` : tutto))
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
function RigaUnita({ riga: r, giorni, celle, testa, problemi, modificata, bloccata, oggi, onCambia, onCambiaTesta }) {
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
        <p className="text-[11px] text-gray-600 flex flex-wrap gap-x-2">
          <span>{r.codice}</span>
          {r.previste != null && <span>previste {fmtOre(r.previste)}h</span>}
          {r.inRitardo && <span className="text-amber-500/90">⚠ scaduto</span>}
          {!r.modificabile && (
            <span className="px-1.5 rounded bg-gray-800 text-gray-400 border border-gray-700">
              sola lettura · {r.motivoSolaLettura}
            </span>
          )}
        </p>
      </td>

      {/* Testa: stato · resta · nota.
          Modificabile sulle righe dell'utente; in sola lettura (N21, pezzo di un
          collega) resta com'è. Niente «ancora fermo»: un'unità ferma si dice con
          lo stato e la nota, lasciando vuote le celle dei giorni. */}
      <td className="px-3 py-2" data-testa={r.chiave}>
        {r.secondaria ? null : modificabileTesta ? (
          <TestaModificabile riga={r} testa={testa} problemi={problemi} disabilitata={bloccata}
                             ferma={ferma} onCambia={onCambiaTesta} />
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
