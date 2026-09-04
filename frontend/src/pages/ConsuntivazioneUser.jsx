import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { apiFetch } from '../api'
import { unitaDichiarata, unitaCompilabili } from '../components/_shared/unitaLavoro'

/* ── Costanti ─────────────────────────────────────────────────────── */
const STATI = ['In corso', 'Completato', 'Bloccato']

const STATO_STYLE = {
  'In corso':   { on: 'bg-blue-600 text-white border-blue-500',      off: 'text-blue-300/60 border-gray-700 hover:border-blue-800' },
  'Completato': { on: 'bg-emerald-600 text-white border-emerald-500', off: 'text-emerald-300/60 border-gray-700 hover:border-emerald-800' },
  'Bloccato':   { on: 'bg-red-600 text-white border-red-500',        off: 'text-red-300/60 border-gray-700 hover:border-red-800' },
}

const TOOLTIP = {
  previste: 'Le ore programmate per te su questo task in questa settimana.',
  ore: 'Quante ore ci hai messo, se te lo ricordi. Campo facoltativo.',
  oreEffettive: 'Ore reali su questo pezzo, se l\'avanzamento non le racconta ' +
                '(fermo, o costato più della stima). Vuoto = si calcolano dal cursore.',
  oreEffettiveTask: 'Ore reali su questo task, se l\'avanzamento non le racconta ' +
                    '(fermo, o costato più del previsto). Vuoto = si calcolano dal cursore.',
  // Le ore non si scrivono più a mano da nessuna parte: si calcolano
  // dall'avanzamento — dei pezzi se il task è scomposto, del task stesso se
  // non lo è. Il tooltip lo dice in entrambi i casi.
  oreDerivate: 'Calcolate dall\'avanzamento: quanto è avanzato per la sua ' +
               'stima, oppure le ore reali dove le hai scritte a mano.',
}

/* ── Helpers ──────────────────────────────────────────────────────── */
const fmtH = (n) => `${(n ?? 0).toFixed(1).replace(/\.0$/, '')}h`

const fmtData = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('it-IT', { day: 'numeric', month: 'short' })
}

/* ── Il promemoria della nota ereditata ────────────────────────────────
 * Nodo F-2 (b). Mostra il perché di un fermo scritto in una settimana
 * PRECEDENTE, così chi compila non deve ridigitare «aspetto le credenziali»
 * ogni lunedì.
 *
 * SOLA LETTURA, E FUORI DAL CAMPO-NOTA. È la regola più importante di questo
 * componente, e non è una scelta di stile. Se il testo ereditato finisse
 * PRECOMPILATO nel `<textarea>` della nota, al salvataggio partirebbe in
 * `note_per_task` / `note_sottotask` come nota PROPRIA di questa settimana, e
 * il backend non ha modo di distinguerla: la barriera costruita nel data layer
 * è sul canale della presa-visione (`viste_*` porta solo id), NON sul campo
 * nota. Il risultato sarebbe che il dipendente firma parole scritte da un
 * collega — o da sé stesso settimane fa — senza averle riscritte.
 * Quindi: un <p>, non un input. Nessun `value`, nessun `onChange`.
 *
 * QUANDO SI MOSTRA — le due condizioni arrivano dal docstring di
 * `task_settimana_dipendente`, che le ha decise e non le applica di proposito
 * («qui non si filtra, si espone il fatto»):
 *   - l'unità è FERMA: chi ha mosso il cursore ha già detto la sua, e un
 *     promemoria di un vecchio fermo sarebbe fuori tempo;
 *   - non ha già una nota PROPRIA questa settimana: se l'utente ha scritto,
 *     il promemoria ha finito il suo lavoro e sparisce.
 */
function PromemoriaNota({ testo, da, mostra }) {
  if (!mostra || !testo) return null
  return (
    <p className="text-[11px] text-gray-500 italic mt-1 flex items-start gap-1.5">
      <span className="text-gray-600 not-italic shrink-0" aria-hidden="true">↺</span>
      <span className="min-w-0">
        <span className="text-gray-600 not-italic">
          {da ? `Settimana del ${fmtData(da)}: ` : 'In precedenza: '}
        </span>
        «{testo}»
      </span>
    </p>
  )
}

/* ── Pagina ───────────────────────────────────────────────────────── */
export default function ConsuntivazioneUser() {
  const [dati, setDati] = useState(null)
  const [loading, setLoading] = useState(true)
  const [errore, setErrore] = useState(null)
  const [salvataggio, setSalvataggio] = useState(null) // null | 'invio' | 'ok' | messaggio errore

  const [settimanaSel, setSettimanaSel] = useState(null)

  // Modifiche pendenti: { [task_id]: { stato?, ore?, nota? } }
  const [modifiche, setModifiche] = useState({})
  const [noteAperte, setNoteAperte] = useState({})

  // Modifiche pendenti sui PEZZI: { [sottotask_id]: { percentuale?, ore_effettive?, bloccato?, nota? } }
  // Mappa separata e non annidata dentro `modifiche`: la grana è diversa (il
  // sottotask ha un id suo, non è un campo del task) e il submit ne costruisce
  // quattro dizionari distinti. Tenerle separate evita di dover distinguere a
  // ogni lettura se una chiave è un task o un pezzo.
  const [modificheSottotask, setModificheSottotask] = useState({})
  const [noteSottotaskAperte, setNoteSottotaskAperte] = useState({})

  /* ── Caricamento ── */
  const carica = useCallback((settimana) => {
    setLoading(true)
    const url = settimana
      ? `/api/consuntivi/me?settimana=${settimana}`
      : '/api/consuntivi/me'
    apiFetch(url)
      .then((d) => {
        setDati(d)
        setSettimanaSel(d.settimana)
        setModifiche({})
        setNoteAperte({})
        setModificheSottotask({})
        setNoteSottotaskAperte({})
        setSalvataggio(null)
      })
      .catch((e) => setErrore(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { carica(null) }, [carica])

  /* ── Avviso se si esce con modifiche pendenti ── */
  const nModifiche =
    Object.keys(modifiche).length + Object.keys(modificheSottotask).length
  const haPendenti = nModifiche > 0
  useEffect(() => {
    if (!haPendenti) return
    const handler = (e) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [haPendenti])

  /* ── Stato/valori correnti di un task (modifica pendente o valore dal server) ── */
  const valore = (t, campo) => {
    const m = modifiche[t.task_id]
    if (m && m[campo] !== undefined) return m[campo]
    if (campo === 'stato') return STATI.includes(t.stato_dichiarato) ? t.stato_dichiarato : null
    if (campo === 'ore') return t.ore_consumate || ''
    if (campo === 'nota') return t.nota ?? ''
    // ── Il task come UNITÀ DI LAVORO ────────────────────────────────────
    // Stessi quattro campi di un pezzo, risolti allo stesso modo. Vivono in
    // `modifiche[task_id]`, la mappa che c'era già: sono campi DEL task, non
    // di un'altra entità, e una terza mappa avrebbe solo aggiunto un posto
    // dove cercarli.
    // Il cursore parte da dove il task è ARRIVATO: la dichiarazione di questa
    // settimana se c'è, altrimenti la baseline. Mai da zero — ripartire da
    // zero su un task al 40% suggerirebbe di aver disfatto il lavoro.
    // `?? 0` sulla baseline: per il task /me la manda `null` quando non c'è
    // storia (a differenza dei pezzi, dove è 0), e uno slider ha bisogno di un
    // numero.
    if (campo === 'percentuale') return t.percentuale ?? t.baseline_pct ?? 0
    if (campo === 'ore_effettive') return t.ore_effettive ?? ''
    if (campo === 'bloccato') return t.stato_dichiarato === 'Bloccato'
    // Nodo F-2. `=== true` e non truthy: /me manda sempre il campo, false
    // incluso, e la domanda ha una risposta anche quando la riga non esiste.
    if (campo === 'presaVisione') return t.presa_visione === true
    return undefined
  }

  const modifica = (task_id, campo, val) => {
    setModifiche((prev) => ({
      ...prev,
      [task_id]: { ...(prev[task_id] ?? {}), [campo]: val },
    }))
    setSalvataggio(null)
  }

  /* ── Stesso meccanismo, un livello più giù: i pezzi ── */
  const valoreSottotask = (p, campo) => {
    const m = modificheSottotask[p.id]
    if (m && m[campo] !== undefined) return m[campo]
    // Il cursore parte da dove il pezzo è ARRIVATO: la dichiarazione di questa
    // settimana se c'è, altrimenti la baseline (l'ultima percentuale
    // dichiarata prima d'ora). Mai da zero: ripartire da zero su un pezzo al
    // 40% suggerirebbe di aver disfatto il lavoro.
    if (campo === 'percentuale') return p.percentuale ?? p.baseline_pct
    if (campo === 'ore_effettive') return p.ore_effettive ?? ''
    if (campo === 'bloccato') return p.stato_dichiarato === 'Bloccato'
    if (campo === 'nota') return p.nota ?? ''
    if (campo === 'presaVisione') return p.presa_visione === true
    return undefined
  }

  const modificaSottotask = (sottotask_id, campo, val) => {
    setModificheSottotask((prev) => ({
      ...prev,
      [sottotask_id]: { ...(prev[sottotask_id] ?? {}), [campo]: val },
    }))
    setSalvataggio(null)
  }

  /* ── Raggruppamento per progetto ── */
  const gruppi = useMemo(() => {
    const map = new Map()
    for (const t of dati?.task_settimana ?? []) {
      if (!map.has(t.progetto_id)) {
        map.set(t.progetto_id, {
          progetto_id: t.progetto_id,
          progetto_nome: t.progetto_nome,
          interna: t.interna,
          task: [],
        })
      }
      map.get(t.progetto_id).task.push(t)
    }
    return [...map.values()]
  }, [dati])

  /* ── Totali ── */
  const totali = useMemo(() => {
    const task = dati?.task_settimana ?? []
    // Le due somme di ore restano sul TASK: sono grandezze del task, e la
    // riga del task le mostra aggregate anche quando è scomposto.
    const previste = task.reduce((s, t) => s + (t.ore_pianificate_settimana ?? 0), 0)
    const dichiarate = task.reduce((s, t) => s + (parseFloat(valore(t, 'ore')) || 0), 0)

    // Il contatore invece conta UNITÀ DI LAVORO, non righe di task (nodo F-1).
    // Prima contava `stato_dichiarato` sul task e `task.length`: dopo
    // l'avanzamento uniforme quel criterio è morto due volte — su un task
    // scomposto lo stato del task resta vuoto (vive sui pezzi), e sul task
    // atomico i tre pulsanti di stato non esistono più (5c). Un task con 3
    // sottotask tutti compilati usciva 0/1.
    const unita = unitaCompilabili(task, dati?.dipendente_id, modifiche, modificheSottotask)
    const dichiarati = unita.filter((u) => unitaDichiarata(u.riga, u.pendenti)).length

    return { previste, dichiarate, dichiarati, totale: unita.length }
  }, [dati, modifiche, modificheSottotask])

  /* ── Settimana corrente selezionabile? ── */
  const settimanaInfo = dati?.settimane_disponibili?.find((s) => s.lunedi === dati?.settimana)
  const soloLettura = settimanaInfo ? !settimanaInfo.compilabile : false

  /* ── Salvataggio ── */
  const salva = async () => {
    if (!haPendenti || soloLettura) return

    // Validazione: Bloccato richiede nota. Si legge `bloccato` e non più
    // `stato`: dal 5c il blocco del task è un flag come sul pezzo, e `stato`
    // ricadrebbe sul valore del server ignorando uno sblocco appena fatto.
    // E si controllano solo i task TOCCATI, come per i pezzi: un task già
    // bloccato senza nota, che non ho aperto, non deve impedirmi di salvare.
    for (const t of dati.task_settimana) {
      if (!modifiche[t.task_id]) continue
      if (!valore(t, 'bloccato')) continue
      if ((valore(t, 'nota') ?? '').trim()) continue
      setSalvataggio(`"${t.task_nome}" è bloccato: scrivi perché nella nota.`)
      setNoteAperte((p) => ({ ...p, [t.task_id]: true }))
      return
    }

    // Stessa regola sui PEZZI. Si controllano solo quelli TOCCATI: un pezzo
    // altrui già bloccato senza nota non è affar mio e non deve impedirmi di
    // salvare. Rifiutare qui evita al dipendente il 400 del backend, che dice
    // la stessa cosa ma dopo aver premuto Salva.
    const pezzi = (dati.task_settimana ?? []).flatMap((t) => t.sottotask ?? [])
    for (const p of pezzi) {
      if (!modificheSottotask[p.id]) continue
      if (!valoreSottotask(p, 'bloccato')) continue
      if ((valoreSottotask(p, 'nota') ?? '').trim()) continue
      setSalvataggio(`"${p.nome}" è bloccato: scrivi perché nella nota.`)
      setNoteSottotaskAperte((prev) => ({ ...prev, [p.id]: true }))
      return
    }

    setSalvataggio('invio')

    const ore_per_task = {}
    const stati_per_task = {}
    const note_per_task = {}

    for (const [task_id, m] of Object.entries(modifiche)) {
      if (m.ore !== undefined) ore_per_task[task_id] = parseFloat(m.ore) || 0
      if (m.stato !== undefined && m.stato !== null) stati_per_task[task_id] = m.stato
      if (m.nota !== undefined) note_per_task[task_id] = m.nota
    }

    /* ── I quattro dizionari dei pezzi ──────────────────────────────────
     * Chiavi come stringhe (JSON non ne conosce altre): il DTO le dichiara
     * `dict[int, …]` e pydantic converte. `bloccati` è un array, che pydantic
     * riceve in un `set[int]`.
     *
     * QUANDO SI MANDA LA PERCENTUALE — non solo quando il cursore si è mosso.
     * Il backend ricalcola `stato_dichiarato` se il pezzo compare fra gli
     * avanzamenti O fra i bloccati; se lo si toglie da «bloccato» senza
     * mandare nulla, non ricade in nessuno dei due e resterebbe Bloccato per
     * sempre. Quindi lo sblocco manda anche la percentuale, che è ciò da cui
     * lo stato va riderivato.
     * Simmetricamente NON si manda la percentuale quando si ritocca solo la
     * nota di un pezzo fermo: la manderemmo identica, ma basterebbe a far
     * ricalcolare lo stato e a sbloccarlo in silenzio.
     */
    const avanzamenti_sottotask = {}
    const ore_effettive_sottotask = {}
    const bloccati_sottotask = []
    const note_sottotask = {}
    // Nodo F-2: le unità confermate «ancora ferme». Due liste di SOLI ID — è il
    // canale dedicato del backend, e porta solo appartenenza: nessuna
    // percentuale (su un pezzo la sbloccherebbe) e nessuna nota (la
    // `nota_ereditata` non deve poter tornare indietro come nota propria).
    const viste_task = []
    const viste_sottotask = []

    for (const p of pezzi) {
      const m = modificheSottotask[p.id]
      if (!m) continue
      const id = String(p.id)
      const bloccato = valoreSottotask(p, 'bloccato')

      if (m.percentuale !== undefined || m.bloccato === false) {
        avanzamenti_sottotask[id] = Number(valoreSottotask(p, 'percentuale'))
      }
      // Campo svuotato = nessun valore da mandare: la chiave assente lascia in
      // pace le ore già salvate. Azzerarle davvero non è esprimibile — 0.0 per
      // il backend significa «zero ore effettive, e lo dico io», che spegne la
      // derivazione invece di riattivarla.
      if (m.ore_effettive !== undefined && String(m.ore_effettive).trim() !== '') {
        ore_effettive_sottotask[id] = parseFloat(m.ore_effettive)
      }
      if (bloccato) bloccati_sottotask.push(p.id)
      if (valoreSottotask(p, 'presaVisione')) viste_sottotask.push(p.id)
      if (m.nota !== undefined) note_sottotask[id] = m.nota
    }

    /* ── I due dizionari del TASK come unità di lavoro ──────────────────
     * Stessa logica dei pezzi qui sopra, applicata al task: la condizione su
     * QUANDO mandare la percentuale è identica, e non è una scelta di stile —
     * il backend ricalcola `stato_dichiarato` solo se il task compare fra i
     * `percentuale_per_task` (che è ciò che lo mette fra le «unità» del
     * salvataggio). Sbloccare senza mandare la percentuale lascerebbe il task
     * Bloccato per sempre; mandarla mentre si ritocca solo la nota di un task
     * fermo lo sbloccherebbe in silenzio.
     *
     * Il BLOCCO del task non ha un dizionario suo: il backend lo legge da
     * `stati_per_task[task_id] === 'Bloccato'`, che è dove il task ha sempre
     * dichiarato il proprio stato. Dopo il 5c è l'unico valore che quel
     * dizionario porta ancora — gli altri due stati li deriva il cursore.
     *
     * SOLO i task NON scomposti: su un task con pezzi la percentuale vive sui
     * pezzi, e mandargliene una sarebbe la doppia verità che il backend già
     * scarta con un avviso. Meglio non mandargliela affatto.
     */
    const percentuale_per_task = {}
    const ore_effettive_per_task = {}

    for (const t of dati.task_settimana ?? []) {
      const m = modifiche[t.task_id]
      if (!m) continue
      if ((t.sottotask ?? []).length > 0) continue   // scomposto: sta ai pezzi

      if (m.percentuale !== undefined || m.bloccato === false) {
        percentuale_per_task[t.task_id] = Number(valore(t, 'percentuale'))
      }
      // Campo svuotato = niente da mandare: la chiave assente lascia in pace
      // le ore già salvate. Azzerarle davvero non è esprimibile — 0.0 per il
      // backend significa «zero ore effettive, e lo dico io», che spegne la
      // derivazione invece di riattivarla.
      if (m.ore_effettive !== undefined && String(m.ore_effettive).trim() !== '') {
        ore_effettive_per_task[t.task_id] = parseFloat(m.ore_effettive)
      }
      if (valore(t, 'bloccato')) stati_per_task[t.task_id] = 'Bloccato'
      // Il gesto vale solo se ACCESO: toglierlo non manda nulla, e il backend
      // scrive `presa_visione = True` senza mai riportarlo a False — una
      // conferma data non si ritira da sola a metà settimana.
      if (valore(t, 'presaVisione')) viste_task.push(t.task_id)
    }

    try {
      await apiFetch('/api/consuntivi/salva', {
        method: 'POST',
        body: {
          dipendente_id: dati.dipendente_id,
          settimana: dati.settimana,
          ore_per_task,
          stati_per_task,
          note_per_task,
          percentuale_per_task,
          ore_effettive_per_task,
          avanzamenti_sottotask,
          ore_effettive_sottotask,
          bloccati_sottotask,
          note_sottotask,
          viste_task,
          viste_sottotask,
        },
      })
      setSalvataggio('ok')
      carica(dati.settimana)
    } catch (e) {
      const msg =
        typeof e === 'string' ? e
        : e?.detail ? (typeof e.detail === 'string' ? e.detail : JSON.stringify(e.detail))
        : e?.message ? e.message
        : JSON.stringify(e)
      setSalvataggio(msg)
      console.error('Salvataggio fallito:', e)
    }
  }

  /* ── Render ── */
  if (loading) return <p className="text-gray-400">Caricamento…</p>
  if (errore) return <p className="text-red-400">Errore: {errore}</p>
  if (!dati) return null

  const nome = dati.nome?.split(' ')[0] ?? ''

  return (
    <div className="max-w-6xl pb-24">
      <h1 className="text-3xl font-bold mb-1">⏱️ Consuntivazione</h1>

      <div className="flex items-start justify-between mb-6">
        <p className="text-gray-400">
          Ciao {nome} — ecco cosa era in programma per te.
        </p>

        {/* Agganci IA — segnaposto, non ancora collegati */}
        <div className="flex gap-2 shrink-0">
          <button disabled
            title="In arrivo: detta cosa hai fatto, l'assistente compila per te"
            className="px-3 py-2 rounded-lg text-sm font-medium bg-gray-800 text-gray-500 border border-gray-700 cursor-not-allowed">
            🎙️ Modalità vocale
          </button>
          <button disabled
            title="In arrivo: assistente che aiuta a ricostruire la settimana"
            className="px-3 py-2 rounded-lg text-sm font-medium bg-gray-800 text-gray-500 border border-gray-700 cursor-not-allowed">
            💬 Apri assistente
          </button>
        </div>
      </div>

      {/* ═══ Selettore settimana ═══ */}
      <div className="flex items-center gap-2 mb-6">
        {dati.settimane_disponibili?.map((s) => {
          const attiva = s.lunedi === dati.settimana
          return (
            <button
              key={s.lunedi}
              onClick={() => {
                if (haPendenti && !confirm('Hai modifiche non salvate. Cambiare settimana le perderà. Continuare?')) return
                carica(s.lunedi)
              }}
              className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                attiva
                  ? 'bg-gray-700 text-white border-gray-600'
                  : 'bg-gray-900 text-gray-400 border-gray-800 hover:text-gray-200'
              }`}
            >
              {s.etichetta}
              {!s.compilabile && <span className="ml-2 text-[10px] text-gray-500">già chiusa</span>}
            </button>
          )
        })}
      </div>

      {soloLettura && (
        <div className="bg-gray-800/60 border border-gray-700 rounded-lg px-4 py-3 mb-6">
          <p className="text-sm text-gray-300">
            Questa settimana è già stata compilata: puoi consultarla, ma non modificarla.
          </p>
        </div>
      )}

      {/* ═══ Riquadri di sintesi ═══ */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Dichiarati ora</p>
          <p className="text-2xl font-bold mt-1">
            {totali.dichiarati}<span className="text-gray-500 text-lg"> / {totali.totale}</span>
          </p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Ore previste</p>
          <p className="text-2xl font-bold mt-1 text-blue-300">{fmtH(totali.previste)}</p>
          <p className="text-xs text-gray-500 mt-0.5">su {dati.ore_contrattuali}h contrattuali</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Ore dichiarate</p>
          <p className="text-2xl font-bold mt-1 text-green-400">{fmtH(totali.dichiarate)}</p>
          <p className="text-xs text-gray-500 mt-0.5">facoltative</p>
        </div>
      </div>

      {/* ═══ Tabella ═══ */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-800 text-gray-400">
            <tr>
              <th className="px-4 py-3 text-left font-medium">Task</th>
              <th className="px-4 py-3 text-right font-medium">
                <span title={TOOLTIP.previste} className="cursor-help">Previste</span>
              </th>
              <th className="px-4 py-3 text-center font-medium">A che punto sei?</th>
              <th className="px-4 py-3 text-center font-medium">
                <span title={TOOLTIP.ore} className="cursor-help">Ore</span>
              </th>
              <th className="px-3 py-3 text-center font-medium w-12">Nota</th>
            </tr>
          </thead>
          <tbody>
            {gruppi.map((g) => (
              <React.Fragment key={g.progetto_id}>
                {/* Intestazione progetto */}
                <tr className="bg-gray-800/40 border-t border-gray-800">
                  <td colSpan={5} className="px-4 py-2">
                    <span className="inline-flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-[10px] uppercase tracking-wider font-medium ${
                        g.interna
                          ? 'bg-gray-700 text-gray-300'
                          : 'bg-blue-900/50 text-blue-300 border border-blue-800'
                      }`}>
                        {g.interna ? 'Interna' : 'Progetto'}
                      </span>
                      <span className="font-medium text-gray-200">{g.progetto_nome}</span>
                    </span>
                  </td>
                </tr>

                {/* Righe task */}
                {g.task.map((t) => (
                  <RigaTask
                    key={t.task_id}
                    task={t}
                    statoSel={valore(t, 'stato')}
                    ore={valore(t, 'ore')}
                    nota={valore(t, 'nota') ?? ''}
                    pct={valore(t, 'percentuale')}
                    oreEffettive={valore(t, 'ore_effettive')}
                    bloccato={valore(t, 'bloccato')}
                    modificata={Boolean(modifiche[t.task_id])}
                    notaAperta={Boolean(noteAperte[t.task_id])}
                    soloLettura={soloLettura}
                    onModifica={(campo, val) => modifica(t.task_id, campo, val)}
                    onNotaAperta={(v) =>
                      setNoteAperte((p) => ({ ...p, [t.task_id]: v }))
                    }
                    dipendenteId={dati.dipendente_id}
                    valoreSottotask={valoreSottotask}
                    noteSottotaskAperte={noteSottotaskAperte}
                    onModificaSottotask={modificaSottotask}
                    onNotaSottotaskAperta={(id, v) =>
                      setNoteSottotaskAperte((prev) => ({ ...prev, [id]: v }))
                    }
                  />
                ))}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* ═══ Barra di salvataggio fissa ═══ */}
      {!soloLettura && (
        <div className="fixed bottom-0 left-0 right-0 border-t backdrop-blur"
             style={{ backgroundColor: 'rgba(17,24,39,0.92)', borderColor: 'var(--color-border-subtle, #1f2937)' }}>
          <div className="max-w-6xl mx-auto px-8 py-3 flex items-center justify-between">
            <div className="text-sm">
              {salvataggio === 'ok' && <span className="text-green-400">✓ Salvato</span>}
              {salvataggio === 'invio' && <span className="text-gray-400">Salvataggio…</span>}
              {salvataggio && !['ok', 'invio'].includes(salvataggio) && (
                <span className="text-red-400">{salvataggio}</span>
              )}
              {!salvataggio && haPendenti && (
                <span className="text-amber-300">
                  {nModifiche} {nModifiche === 1 ? 'modifica' : 'modifiche'} da salvare
                </span>
              )}
              {!salvataggio && !haPendenti && (
                <span className="text-gray-600">Nessuna modifica</span>
              )}
            </div>

            <button
              onClick={salva}
              disabled={!haPendenti || salvataggio === 'invio'}
              className="px-5 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white
                         hover:bg-blue-500 disabled:bg-gray-800 disabled:text-gray-600
                         disabled:cursor-not-allowed transition-colors"
            >
              Salva
            </button>
          </div>
        </div>
      )}
    </div>
  )
}


/* ── Riga di un task ──────────────────────────────────────────────────
 * Il task e ciò che il dipendente dichiara su di esso: stato, ore, nota.
 *
 * COMPONENTE CONTROLLATO — non possiede stato proprio del form. Riceve i
 * valori già risolti dal padre (che sa se viene dalla modifica pendente o dal
 * server, vedi `valore`) e comunica ogni cambiamento all'insù. Lo stato resta
 * uno solo, `modifiche`, e il submit continua a costruirci sopra il body di
 * /salva senza sapere niente di questo componente.
 *
 * `onModifica(campo, valore)` — il padre chiude sul task_id, così qui non
 * serve conoscerlo per scrivere.
 * `onNotaAperta(bool)` — apre/chiude il riquadro nota. Un solo callback e non
 * due (toggle + apri) perché sono la stessa azione con un valore diverso:
 * l'icona passa `!notaAperta`, il pulsante "Bloccato" passa `true`.
 *
 * Restituisce un Fragment con DUE <tr>: la riga e la nota espansa. È anche il
 * punto in cui, più avanti, si innesterà il blocco sottotask — un terzo <tr>
 * dentro lo stesso Fragment, senza toccare la struttura della tabella.
 */
function RigaTask({
  task: t,
  statoSel,
  ore,
  nota,
  pct,
  oreEffettive,
  bloccato,
  presaVisione,
  modificata,
  notaAperta,
  soloLettura,
  onModifica,
  onNotaAperta,
  dipendenteId,
  valoreSottotask,
  noteSottotaskAperte,
  onModificaSottotask,
  onNotaSottotaskAperta,
}) {
  const haNota = nota.trim().length > 0
  // La chiave `sottotask` arriva da /me SOLO sui task scomposti: la sua
  // presenza è il criterio, non un flag a parte che potrebbe disallinearsi
  // dalla lista che descrive.
  const pezzi = t.sottotask ?? []
  const scomposto = pezzi.length > 0

  return (
    <React.Fragment>
      <tr className={`border-t border-gray-800/60 ${
        modificata ? 'bg-amber-950/20' : ''
      }`}>
        {/* Task */}
        <td className="px-4 py-3">
          <p className="text-gray-200">{t.task_nome}</p>
          <p className="text-xs text-gray-600 flex items-center gap-2">
            <span>{t.task_id}</span>
            <span className="text-gray-500">· attualmente {t.stato}</span>
            {t.in_ritardo && (
              <span className="text-amber-500/80">· ⚠ oltre la data prevista</span>
            )}
          </p>
        </td>

        {/* Previste */}
        <td className="px-4 py-3 text-right">
          {t.ore_pianificate_settimana === null ? (
            <span className="text-gray-600">—</span>
          ) : (
            <>
              <span className="text-blue-300 font-medium">
                {t.ore_pianificate_settimana < 0.5 && t.ore_pianificate_settimana > 0
                  ? '<1h'
                  : fmtH(t.ore_pianificate_settimana)}
              </span>
              <p className="text-[11px] text-gray-600">
                su {fmtH(t.ore_pianificate)} totali
              </p>
            </>
          )}
        </td>

        {/* A che punto sei? — il cursore, non più tre pulsanti.
            I tre stati non si chiedono più a NESSUN task: «In corso» e
            «Completato» sono riflessi dell'avanzamento (del task o dei suoi
            pezzi), e chiederli a parte significava raccogliere due risposte
            alla stessa domanda, che possono contraddirsi. Resta «Bloccato»,
            dentro i controlli, perché è l'unica cosa che una percentuale non
            può dire. */}
        <td className="px-4 py-3">
          {scomposto ? (
            // Task scomposto: la risposta sta nei pezzi, qui sotto.
            <p className="text-[11px] text-gray-600 text-center">nei pezzi ↓</p>
          ) : (
            <div className="flex items-center gap-3">
              <ControlliAvanzamento
                pct={pct}
                baseline={t.baseline_pct ?? 0}
                oreEffettive={oreEffettive}
                bloccato={bloccato}
                presaVisione={presaVisione}
                disabilitato={soloLettura}
                titoloBloccato="Il task è fermo: dovrai scrivere perché"
                titoloOreEffettive={TOOLTIP.oreEffettiveTask}
                onModifica={onModifica}
                onNotaAperta={onNotaAperta}
              />
            </div>
          )}
        </td>

        {/* Ore — DERIVATE, sempre. Niente input a mano da nessuna parte: le
            calcola il backend dall'avanzamento (Δ × stima, o le ore reali dove
            dichiarate), e le derivate VINCONO su un eventuale valore scritto a
            mano. Un campo editabile qui accetterebbe un numero per poi
            sostituirlo in silenzio al salvataggio: meglio non offrirlo. */}
        <td className="px-4 py-3 text-center">
          <span className="text-gray-300 font-medium" title={TOOLTIP.oreDerivate}>
            {fmtH(t.ore_consumate)}
          </span>
          <p className="text-[11px] text-gray-600">
            {scomposto ? 'dai pezzi' : "dall'avanzamento"}
          </p>
        </td>

        {/* Icona nota */}
        <td className="px-3 py-3 text-center">
          <button
            onClick={() => onNotaAperta(!notaAperta)}
            title={haNota ? 'Nota presente' : 'Aggiungi una nota'}
            className={`w-7 h-7 rounded-md border transition-colors ${
              haNota
                ? 'bg-amber-900/30 border-amber-700/60 text-amber-300'
                : 'border-gray-700 text-gray-600 hover:text-gray-400'
            }`}
          >
            {haNota ? '✎' : '+'}
          </button>
          <PromemoriaNota
            testo={t.nota_ereditata}
            da={t.nota_ereditata_da}
            mostra={!scomposto && Number(pct) === Number(t.baseline_pct ?? 0) && !haNota}
          />
        </td>
      </tr>

      {/* Riga nota espansa */}
      {notaAperta && (
        <tr className="border-t border-gray-800/30">
          <td colSpan={5} className="px-4 pb-3 pt-0 bg-gray-800/20">
            <textarea
              rows={2}
              disabled={soloLettura}
              value={nota}
              onChange={(e) => onModifica('nota', e.target.value)}
              placeholder={
                statoSel === 'Bloccato'
                  ? 'Perché è bloccato? (obbligatorio)'
                  : 'A che punto sei? Cosa hai fatto?'
              }
              className={`w-full bg-gray-950 text-gray-200 rounded-md px-3 py-2 text-sm
                          border focus:outline-none focus:ring-2 focus:ring-blue-600
                          placeholder:text-gray-600 disabled:opacity-50 ${
                            statoSel === 'Bloccato' && !nota.trim()
                              ? 'border-red-800'
                              : 'border-gray-700'
                          }`}
            />
          </td>
        </tr>
      )}

      {/* Pezzi in cui il task è scomposto */}
      {scomposto && (
        <tr className="border-t border-gray-800/30">
          <td colSpan={5} className="px-4 pb-4 pt-1 bg-gray-950/40">
            <div className="pl-4 border-l-2 border-gray-800 space-y-2">
              {pezzi.map((p) => (
                <PezzoSottotask
                  key={p.id}
                  pezzo={p}
                  // Un pezzo affidato a un altro si vede ma non si compila:
                  // l'avanzamento lo dichiara chi ci lavora. `assegnatario_id`
                  // arriva già RISOLTO da /me (override o eredità dal task).
                  mio={p.assegnatario_id === dipendenteId}
                  soloLettura={soloLettura}
                  pct={valoreSottotask(p, 'percentuale')}
                  oreEffettive={valoreSottotask(p, 'ore_effettive')}
                  bloccato={valoreSottotask(p, 'bloccato')}
                  presaVisione={valoreSottotask(p, 'presaVisione')}
                  nota={valoreSottotask(p, 'nota')}
                  notaAperta={Boolean(noteSottotaskAperte[p.id])}
                  onModifica={(campo, val) => onModificaSottotask(p.id, campo, val)}
                  onNotaAperta={(v) => onNotaSottotaskAperta(p.id, v)}
                />
              ))}
            </div>
          </td>
        </tr>
      )}
    </React.Fragment>
  )
}


/* ── Un pezzo (sottotask) dentro la riga del task ──────────────────────
 * Mostra a che punto è il pezzo e — quando è di chi sta compilando — lascia
 * dichiararne l'avanzamento. Controllato come RigaTask: nessuno stato proprio.
 */
function PezzoSottotask({
  pezzo: p,
  mio,
  pct,
  oreEffettive,
  bloccato,
  presaVisione,
  nota,
  notaAperta,
  soloLettura,
  onModifica,
  onNotaAperta,
}) {
  // Non compilabile: settimana chiusa, oppure pezzo affidato a un altro.
  const bloccatoInput = soloLettura || !mio
  const haNota = (nota ?? '').trim().length > 0
  return (
    <>
      <div className="flex items-center gap-3 py-1.5">
        {/* Nome + stima */}
        <div className="min-w-0 w-56">
          <p className={`text-sm truncate ${mio ? 'text-gray-300' : 'text-gray-500'}`}>
            {p.nome}
            {p.stato === 'Sospeso' && (
              <span className="ml-2 text-[10px] uppercase tracking-wider text-amber-500/70">sospeso</span>
            )}
          </p>
          <p className="text-[11px] text-gray-600">
            {p.ore_stimate == null ? 'non stimato' : `stima ${fmtH(p.ore_stimate)}`}
            {!mio && <span className="text-gray-500"> · di un altro</span>}
          </p>
        </div>

        <ControlliAvanzamento
          pct={pct}
          baseline={p.baseline_pct}
          oreEffettive={oreEffettive}
          bloccato={bloccato}
          presaVisione={presaVisione}
          disabilitato={bloccatoInput}
          titoloBloccato="Il pezzo è fermo: dovrai scrivere perché"
          titoloOreEffettive={TOOLTIP.oreEffettive}
          onModifica={onModifica}
          onNotaAperta={onNotaAperta}
        />

        {/* Nota */}
        <button
          onClick={() => onNotaAperta(!notaAperta)}
          title={haNota ? 'Nota presente' : 'Aggiungi una nota'}
          className={`w-6 h-6 rounded-md border text-xs transition-colors shrink-0 ${
            haNota
              ? 'bg-amber-900/30 border-amber-700/60 text-amber-300'
              : 'border-gray-700 text-gray-600 hover:text-gray-400'
          }`}
        >
          {haNota ? '✎' : '+'}
        </button>
      </div>

      {/* Il perché di un fermo, scritto in una settimana precedente. Sotto la
          riga e FUORI dal textarea: vedi PromemoriaNota per cosa succederebbe
          se finisse dentro il campo. */}
      <PromemoriaNota
        testo={p.nota_ereditata}
        da={p.nota_ereditata_da}
        mostra={Number(pct) === Number(p.baseline_pct) && !haNota}
      />

      {notaAperta && (
        <div className="pb-2 pr-1">
          <textarea
            rows={2}
            disabled={bloccatoInput}
            value={nota}
            onChange={(e) => onModifica('nota', e.target.value)}
            placeholder={bloccato ? 'Perché è fermo? (obbligatorio)' : 'Cosa hai fatto su questo pezzo?'}
            className={`w-full bg-gray-950 text-gray-200 rounded-md px-3 py-2 text-sm
                        border focus:outline-none focus:ring-2 focus:ring-blue-600
                        placeholder:text-gray-600 disabled:opacity-40 ${
                          bloccato && !haNota ? 'border-red-800' : 'border-gray-700'
                        }`}
          />
        </div>
      )}
    </>
  )
}


/* ── I controlli dell'avanzamento ──────────────────────────────────────
 * Cursore + casella numerica sulla stessa percentuale, ore effettive, toggle
 * Bloccato, e lo stato derivato mostrato in sola lettura.
 *
 * Condivisi fra il PEZZO e il TASK non scomposto, perché sono la stessa
 * domanda posta sulla stessa cosa: un'unità di lavoro. Il backend li tratta
 * già così (`ore_derivate_unita`, `_baseline_percentuali` col tipo), e due
 * copie di questi controlli finirebbero per divergere — un cursore a passi di
 * 5 e uno a passi di 1, un minimo rispettato e uno no — facendo comportare la
 * stessa dichiarazione in due modi a seconda di dove la si scrive.
 *
 * COSA NON È QUI, e non per dimenticanza: l'involucro (il pezzo vive in un
 * <div> dentro un colSpan, il task renderà <td> dentro un <tr>), il nome e la
 * stima, e la nota — che entrambi hanno ma resa in forme diverse. Restano di
 * chi lo usa.
 *
 * `onNotaAperta` invece serve: «Bloccato» apre la nota, e non è un dettaglio
 * di layout ma parte di cosa significa bloccare — la nota diventa obbligatoria
 * nello stesso istante. Il componente non la rende, ma la apre.
 *
 * Controllato come i suoi due chiamanti: nessuno stato proprio.
 */
function ControlliAvanzamento({
  pct,
  baseline,
  oreEffettive,
  bloccato,
  presaVisione,
  disabilitato,
  titoloBloccato,
  titoloOreEffettive,
  onModifica,
  onNotaAperta,
}) {
  // Lo stato non si chiede: si legge dallo slider. Solo "Bloccato" è un flag a
  // parte, perché è l'unica cosa che una percentuale non può dire — un lavoro
  // fermo al 40% è indistinguibile da uno che avanza piano.
  const statoMostrato = bloccato
    ? 'Bloccato'
    : pct >= 100 ? 'Completato'
    : pct > 0 ? 'In corso'
    : null

  // FERMA = il cursore non si è mosso rispetto a dove il lavoro era arrivato.
  // `pct` arriva già risolto dagli accessor, che cadono sulla baseline quando
  // la dichiarazione di questa settimana manca: quindi questo confronto copre
  // insieme «non pervenuta» e «dichiarata uguale a prima», che sono i due casi
  // in cui la presa-visione ha senso. Chi ha mosso il cursore ha già
  // dichiarato, e il gesto sparisce — offrirglielo sarebbe chiedere due volte
  // la stessa cosa.
  const ferma = Number(pct) === Number(baseline)

  return (
    <>
      {/* Avanzamento: cursore + casella. Due controlli sullo stesso valore
          perché servono a due gesti diversi — il cursore per la stima a
          occhio, la casella per scrivere «65» senza inseguire il pixel. */}
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <input
          type="range"
          min={baseline} max={100} step={5}
          disabled={disabilitato}
          value={pct}
          onChange={(e) => onModifica('percentuale', Number(e.target.value))}
          title={baseline > 0 ? `Non sotto il ${baseline}% già dichiarato` : undefined}
          className="flex-1 min-w-0 accent-blue-500 disabled:opacity-40 disabled:cursor-not-allowed"
        />
        <input
          type="number"
          min={baseline} max={100} step={5}
          disabled={disabilitato}
          value={pct}
          onChange={(e) => onModifica('percentuale', Number(e.target.value))}
          className="w-14 bg-gray-950 text-gray-200 rounded-md px-1.5 py-1 text-center text-sm
                     border border-gray-700 focus:outline-none focus:ring-2
                     focus:ring-blue-600 focus:border-blue-600 disabled:opacity-40"
        />
        <span className="text-[11px] text-gray-600 w-14 shrink-0">
          {baseline > 0 ? `da ${baseline}%` : ''}
        </span>
      </div>

      {/* Ore reali, quando l'avanzamento non le cattura */}
      <input
        type="number" min="0" step="0.5"
        disabled={disabilitato}
        value={oreEffettive}
        onChange={(e) => onModifica('ore_effettive', e.target.value)}
        placeholder="—"
        title={titoloOreEffettive}
        className="w-16 bg-gray-950 text-gray-200 rounded-md px-2 py-1 text-center text-sm
                   border border-gray-700 focus:outline-none focus:ring-2
                   focus:ring-blue-600 focus:border-blue-600
                   disabled:opacity-40 placeholder:text-gray-700"
      />

      {/* Bloccato */}
      <button
        disabled={disabilitato}
        onClick={() => {
          onModifica('bloccato', !bloccato)
          if (!bloccato) onNotaAperta(true)   // la nota diventa obbligatoria
        }}
        title={titoloBloccato}
        className={`px-2 py-1 rounded-md text-xs font-medium border transition-colors shrink-0 ${
          bloccato ? STATO_STYLE['Bloccato'].on : STATO_STYLE['Bloccato'].off
        } ${disabilitato ? 'opacity-40 cursor-not-allowed' : ''}`}
      >
        Bloccato
      </button>

      {/* Presa in visione — solo sulle unità FERME (nodo F-2).
          «Confermo, ancora fermo»: una traccia senza avanzamento, che fa
          risultare l'unità dichiarata senza costringere a inventare un
          progresso. Manda SOLO l'id (viste_task / viste_sottotask): non
          tocca la percentuale, e su un pezzo Bloccato è la differenza fra
          confermare il fermo e sbloccarlo in silenzio.
          Convive con «Bloccato»: un pezzo bloccato è fermo per definizione,
          ed è proprio quello su cui la conferma settimanale serve di più. */}
      {ferma && (
        <button
          disabled={disabilitato}
          onClick={() => onModifica('presaVisione', !presaVisione)}
          title={presaVisione
            ? 'Hai confermato che è ancora fermo. Clicca per annullare.'
            : 'Confermo di averlo guardato: è ancora fermo, non è avanzato'}
          className={`px-2 py-1 rounded-md text-xs font-medium border transition-colors shrink-0 ${
            presaVisione
              ? 'bg-slate-600 text-white border-slate-500'
              : 'text-slate-300/60 border-gray-700 hover:border-slate-600'
          } ${disabilitato ? 'opacity-40 cursor-not-allowed' : ''}`}
        >
          {presaVisione ? '✓ Fermo' : 'Ancora fermo'}
        </button>
      )}

      {/* Stato derivato, in sola lettura: è il riflesso dello slider */}
      <div className="w-20 text-center shrink-0">
        {statoMostrato && (
          <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${STATO_STYLE[statoMostrato].on}`}>
            {statoMostrato === 'Completato' ? 'Fatto' : statoMostrato}
          </span>
        )}
      </div>
    </>
  )
}
