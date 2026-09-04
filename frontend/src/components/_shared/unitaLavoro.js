/**
 * ═════════════════════════════════════════════════════════════════════════
 * unitaLavoro.js — «Che cos'è un'unità di lavoro, e quando è dichiarata»
 * ═════════════════════════════════════════════════════════════════════════
 *
 * ESTRATTO da ConsuntivazioneUser.jsx il 04/09/2026, quando la Home ha avuto
 * bisogno dello stesso conteggio per «le mie cose». Non è una copia: è uno
 * SPOSTAMENTO, e la ragione è che due copie avrebbero risposto in modo diverso
 * alla stessa domanda. Il contatore della Consuntivazione e quello della Home
 * devono dire lo stesso numero — se divergessero, l'utente vedrebbe «3/8» in
 * una pagina e «4/8» nell'altra sugli stessi dati, senza modo di capire quale
 * creda.
 *
 * Entrambe le funzioni sono PURE: nessuna fetch, nessuno stato. Si testano
 * senza montare una pagina, ed è così che sono state verificate.
 */

/* ── «Questa unità è stata dichiarata?» ────────────────────────────────
 * Nodo F-1. La domanda è UNA e la risposta sta in UN posto, perché la fanno
 * in due: un TASK ATOMICO e un SOTTOTASK. Il payload di /me li rende
 * simmetrici apposta — «i tre campi che il frontend serve per rendere lo
 * slider del task, gemelli di quelli che ogni pezzo porta già» — quindi lo
 * stesso criterio attraversa entrambi senza un `if` sul tipo.
 *
 * `riga`     : la riga COME ARRIVA DAL SERVER (t o p), non filtrata da accessor.
 * `pendenti` : la modifica locale non ancora salvata — `modifiche[task_id]` per
 *              un task, `modificheSottotask[id]` per un pezzo. Le due mappe
 *              hanno grana diversa e restano separate: qui si passa quella
 *              giusta, la funzione non deve saperlo.
 *
 * SI LEGGE IL CAMPO GREZZO, MAI `valore()`/`valoreSottotask()`. Quegli
 * accessor cadono sulla baseline quando la dichiarazione manca
 * (`p.percentuale ?? p.baseline_pct`) — è giusto per uno slider, che non deve
 * mai ripartire da zero, ed è fatale qui: `percentuale` non sarebbe MAI null e
 * ogni unità risulterebbe dichiarata. Il contatore direbbe sempre M/M.
 *
 * F-2 aggiungerà qui la PRESA VISIONE del fermo — un quinto termine in questo
 * `||`, e nient'altro da toccare: è la ragione per cui questa funzione esiste
 * separata invece di stare inline nel `useMemo`.
 */
export const unitaDichiarata = (riga, pendenti) => {
  // 1. Modifiche pendenti: contano SUBITO, prima del salvataggio. Chi muove
  //    lo slider deve vedere il contatore salire, altrimenti sembra rotto.
  //    Solo i campi che sono una dichiarazione: `ore_effettive` non c'è
  //    (decisione presa) e `ore` è ormai derivata, non scritta a mano.
  if (pendenti && (pendenti.percentuale !== undefined ||
                   pendenti.bloccato !== undefined ||
                   pendenti.nota !== undefined ||
                   // Nodo F-2: il gesto appena fatto, non ancora salvato.
                   pendenti.presaVisione !== undefined)) return true

  // 2. Quello che il server ha già registrato per QUESTA settimana.
  //    `percentuale` è `d.percentuale if d else None`: null = non pervenuta.
  if (riga.percentuale != null) return true
  if (riga.stato_dichiarato != null) return true
  if ((riga.nota ?? '').trim() !== '') return true
  // Nodo F-2: «l'ho guardata, è ancora ferma» è una dichiarazione a tutti gli
  // effetti — è il motivo per cui questo nodo esiste. NON si legge
  // `nota_ereditata`: è il promemoria di una settimana precedente, non una
  // traccia di questa, e contarla direbbe «dichiarato» di chi non ha aperto
  // la pagina.
  if (riga.presa_visione === true) return true

  return false
}

/* ── Le unità COMPILABILI della settimana ──────────────────────────────
 * Nodo F-1. L'unità di conteggio non è il task: è il pezzo di lavoro su cui
 * si dichiara. Un task scomposto NON conta per sé — «lo stato vive sui pezzi»
 * — contano i suoi sottotask, uno per uno. Un task con 3 pezzi vale 3.
 *
 * COMPILABILI, non «mostrate». Un pezzo affidato a un collega compare in /me
 * ma è in sola lettura (`bloccatoInput = soloLettura || !mio` in
 * PezzoSottotask): contarlo renderebbe il denominatore IRRAGGIUNGIBILE — 2/5
 * per sempre, con tre unità che chi guarda non può toccare in nessun modo. Un
 * contatore a cui non si può arrivare non è un obiettivo, è un rimprovero.
 * I task atomici non hanno questo problema: /me li filtra già per dipendente.
 *
 * Restituisce coppie {riga, pendenti} già appaiate alla mappa locale giusta,
 * così il chiamante non deve più distinguere i due tipi.
 */
export const unitaCompilabili = (taskSettimana, dipendenteId, modifiche, modificheSottotask) =>
  (taskSettimana ?? []).flatMap((t) => {
    const pezzi = t.sottotask ?? []
    // La chiave `sottotask` arriva da /me SOLO sui task scomposti: la sua
    // presenza è il discriminante, come nel submit (`if (pezzi.length) continue`).
    if (pezzi.length === 0) {
      return [{ riga: t, pendenti: modifiche[t.task_id] }]
    }
    return pezzi
      .filter((p) => p.assegnatario_id === dipendenteId)
      .map((p) => ({ riga: p, pendenti: modificheSottotask[p.id] }))
  })
