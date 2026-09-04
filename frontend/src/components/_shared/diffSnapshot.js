/**
 * ═════════════════════════════════════════════════════════════════════════
 * diffSnapshot.js — Cosa è cambiato fra due stati di un progetto
 * ═════════════════════════════════════════════════════════════════════════
 *
 * Funzione PURA: due strutture `{progetto, fasi:[{task:[…]}]}` entrano, un
 * verdetto per id esce. Non sa da dove vengano — due SAL, un SAL e lo stato
 * attuale, un SAL e un preventivo. È deliberato: la prima interfaccia è «vs il
 * precedente», ma «due a scelta» e «vs stato attuale» sono la STESSA domanda
 * con A e B presi da posti diversi. Se il motore conoscesse gli snapshot,
 * quelle due estensioni sarebbero due motori.
 *
 * ── SI APPAIA PER ID, MAI PER POSIZIONE ──────────────────────────────
 * `Fase.id` e `Task.id` sono chiavi primarie del DB (INTEGER e VARCHAR): fra
 * due snapshot dello stesso progetto sono le stesse — verificato sul dato vero.
 * `ordine` invece cambia, e appaiare per posizione mostrerebbe uno slittamento
 * fantasma ogni volta che qualcuno riordina la lista senza toccare le date.
 *
 * I TASK SI APPAIANO GLOBALMENTE, non dentro la loro fase. Un task spostato di
 * fase è lo stesso task: appaiandolo per (fase, id) risulterebbe «sparito da 7»
 * più «nuovo in 8», cioè due bugie invece di un fatto. Lo spostamento si
 * registra come dettaglio.
 *
 * ── ⚠ «SPARITO» NON VUOL DIRE ASSENTE ────────────────────────────────
 * Un task cancellato NON esce dallo snapshot: il soft-delete scrive
 * `stato = "Eliminato"` e la riga resta, e il serializzatore SAL — a differenza
 * di `gantt_strutturato` — non la filtra. Un diff che guardasse solo gli id
 * direbbe «stato cambiato», in ambra, come un rinvio qualunque: la cosa più
 * grave che possa succedere fra due SAL sarebbe quella che si vede meno.
 * Quindi `stato → "Eliminato"` È una sparizione, e viene marcata come tale.
 *
 * Le FASI invece spariscono per davvero (`session.delete`), ma solo a zero
 * task: entrambe le forme di sparizione sono gestite.
 *
 * ── LE VOCI SPARITE VANNO RESTITUITE, NON SOLO CONTATE ───────────────
 * Ciò che c'era in A e non c'è in B non ha una barra in B — ma è esattamente la
 * cosa che si vuole vedere. Il motore restituisce anche le voci sparite con i
 * loro dati lato-A, così chi disegna può aggiungere quelle righe.
 */

/** I cinque verdetti. Ordinati per gravità: vince il più grave. */
export const DIFF = {
  NUOVO: 'nuovo',
  SPARITO: 'sparito',
  SLITTATO: 'slittato',
  MODIFICATO: 'modificato',
  INVARIATO: 'invariato',
}

// Priorità: se una voce è insieme slittata E cambiata di stato, il verdetto è
// «slittata». Non perché lo stato conti meno, ma perché lo slittamento è ciò
// che si legge SULLA BARRA — e la barra è il supporto del messaggio. Lo stato
// resta nei dettagli e nel tooltip, non si perde.
const GRAVITA = {
  [DIFF.NUOVO]: 4, [DIFF.SPARITO]: 4, [DIFF.SLITTATO]: 3,
  [DIFF.MODIFICATO]: 2, [DIFF.INVARIATO]: 1,
}

const GIORNO_MS = 86400000

/** Giorni fra due date ISO. `null` se una delle due manca: una data che
 *  compare o scompare è un cambiamento, ma non è uno slittamento misurabile. */
function giorniFra(da, a) {
  if (!da || !a) return null
  const d = (new Date(a).getTime() - new Date(da).getTime()) / GIORNO_MS
  return Math.round(d)
}

/**
 * Confronta una voce (fase o task) con la sua controparte.
 * @returns {{diff: string, dettagli: object}}
 */
function confrontaVoce(prima, dopo) {
  const dettagli = {}
  let verdetto = DIFF.INVARIATO

  const alza = (v) => { if (GRAVITA[v] > GRAVITA[verdetto]) verdetto = v }

  // ── Sparizione per soft-delete (vedi ⚠ in testa al file) ──────────
  if (dopo.stato === 'Eliminato' && prima.stato !== 'Eliminato') {
    return { diff: DIFF.SPARITO, dettagli: { eliminato: true, stato: { da: prima.stato, a: dopo.stato } } }
  }

  // ── Date ──────────────────────────────────────────────────────────
  if (prima.data_inizio !== dopo.data_inizio) {
    dettagli.inizio = { da: prima.data_inizio, a: dopo.data_inizio, giorni: giorniFra(prima.data_inizio, dopo.data_inizio) }
    alza(DIFF.SLITTATO)
  }
  if (prima.data_fine !== dopo.data_fine) {
    dettagli.fine = { da: prima.data_fine, a: dopo.data_fine, giorni: giorniFra(prima.data_fine, dopo.data_fine) }
    alza(DIFF.SLITTATO)
  }

  // ── Stato ─────────────────────────────────────────────────────────
  if (prima.stato !== dopo.stato) {
    dettagli.stato = { da: prima.stato, a: dopo.stato }
    alza(DIFF.MODIFICATO)
  }

  return { diff: verdetto, dettagli }
}

/** Indicizza i task di uno snapshot per id, ricordando in quale fase stavano. */
function indicizzaTask(stato) {
  const indice = new Map()
  for (const f of stato?.fasi ?? []) {
    for (const t of f.task ?? []) {
      indice.set(t.id, { voce: t, faseId: f.id, faseNome: f.nome })
    }
  }
  return indice
}

/**
 * @param {object} prima  struttura-snapshot "A" (il PRIMA)
 * @param {object} dopo   struttura-snapshot "B" (il DOPO — quello che si disegna)
 * @returns {{
 *   fasi: Object<id, {diff, dettagli}>,
 *   task: Object<id, {diff, dettagli}>,
 *   spariti: Array<{tipo, voce, faseId, faseNome, dettagli}>,
 *   riepilogo: Object<diff, number>,
 *   confrontabile: boolean
 * }}
 */
export function diffSnapshot(prima, dopo) {
  const vuoto = {
    fasi: {}, task: {}, spariti: [],
    riepilogo: { nuovo: 0, sparito: 0, slittato: 0, modificato: 0, invariato: 0 },
    confrontabile: false,
  }
  // Senza uno dei due termini non c'è confronto — e va detto con un flag, non
  // con un risultato vuoto che sembra «nessuna differenza». Sono due cose
  // opposte: «non ho confrontato» ≠ «ho confrontato e non è cambiato niente».
  if (!prima?.fasi || !dopo?.fasi) return vuoto

  const esito = { ...vuoto, fasi: {}, task: {}, spariti: [], riepilogo: { ...vuoto.riepilogo }, confrontabile: true }
  const conta = (v) => { esito.riepilogo[v] = (esito.riepilogo[v] ?? 0) + 1 }

  /* ── FASI ─────────────────────────────────────────────────────────── */
  const fasiPrima = new Map((prima.fasi ?? []).map(f => [f.id, f]))
  for (const f of dopo.fasi ?? []) {
    const p = fasiPrima.get(f.id)
    if (!p) {
      esito.fasi[f.id] = { diff: DIFF.NUOVO, dettagli: {} }
      conta(DIFF.NUOVO)
      continue
    }
    const r = confrontaVoce(p, f)
    esito.fasi[f.id] = r
    conta(r.diff)
  }
  for (const [id, f] of fasiPrima) {
    if (!(dopo.fasi ?? []).some(x => x.id === id)) {
      esito.fasi[id] = { diff: DIFF.SPARITO, dettagli: {} }
      esito.spariti.push({ tipo: 'fase', voce: f, faseId: f.id, faseNome: f.nome, dettagli: {} })
      conta(DIFF.SPARITO)
    }
  }

  /* ── TASK (appaiati globalmente, vedi testa del file) ──────────────── */
  const taskPrima = indicizzaTask(prima)
  const taskDopo = indicizzaTask(dopo)

  for (const [id, { voce, faseId }] of taskDopo) {
    const p = taskPrima.get(id)
    if (!p) {
      esito.task[id] = { diff: DIFF.NUOVO, dettagli: {} }
      conta(DIFF.NUOVO)
      continue
    }
    const r = confrontaVoce(p.voce, voce)
    // Lo spostamento di fase è un dettaglio, non un verdetto a sé: la barra
    // resta una sola e il fatto si legge nel tooltip. Se non è cambiato
    // nient'altro, basta però ad alzare la voce da «invariato».
    if (p.faseId !== faseId) {
      r.dettagli.fase = { da: p.faseNome, a: taskDopo.get(id).faseNome }
      if (r.diff === DIFF.INVARIATO) r.diff = DIFF.MODIFICATO
    }
    esito.task[id] = r
    conta(r.diff)
  }
  for (const [id, { voce, faseId, faseNome }] of taskPrima) {
    if (!taskDopo.has(id)) {
      esito.task[id] = { diff: DIFF.SPARITO, dettagli: {} }
      esito.spariti.push({ tipo: 'task', voce, faseId, faseNome, dettagli: {} })
      conta(DIFF.SPARITO)
    }
  }

  return esito
}

/** Frase leggibile di un verdetto — per i tooltip. Sta qui e non nel
 *  componente perché è il motore a sapere cosa significano i dettagli. */
export function descriviDiff(diff, dettagli = {}) {
  const pezzi = []
  const seg = (n) => (n > 0 ? `+${n}g` : `${n}g`)
  if (diff === DIFF.NUOVO) return 'NUOVO — non c\'era nello snapshot precedente'
  if (diff === DIFF.SPARITO) {
    return dettagli.eliminato
      ? 'SPARITO — eliminato dopo lo snapshot precedente'
      : 'SPARITO — c\'era nello snapshot precedente, ora no'
  }
  if (dettagli.inizio) pezzi.push(`inizio ${dettagli.inizio.da} → ${dettagli.inizio.a} (${seg(dettagli.inizio.giorni)})`)
  if (dettagli.fine) pezzi.push(`fine ${dettagli.fine.da} → ${dettagli.fine.a} (${seg(dettagli.fine.giorni)})`)
  if (dettagli.stato) pezzi.push(`stato ${dettagli.stato.da} → ${dettagli.stato.a}`)
  if (dettagli.fase) pezzi.push(`spostato da «${dettagli.fase.da}» a «${dettagli.fase.a}»`)
  if (pezzi.length === 0) return 'invariato'
  return (diff === DIFF.SLITTATO ? 'SLITTATO — ' : 'MODIFICATO — ') + pezzi.join(' · ')
}
