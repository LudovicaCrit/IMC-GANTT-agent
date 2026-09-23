/**
 * ═════════════════════════════════════════════════════════════════════════
 * unitaLavoro.js — «Che cos'è un'unità di lavoro, e quando è dichiarata»
 * ═════════════════════════════════════════════════════════════════════════
 *
 * ESTRATTO da ConsuntivazioneUser.jsx il 04/09/2026, quando la Home ha avuto
 * bisogno dello stesso conteggio per «le mie cose». Da allora la pagina da cui
 * era stato estratto è stata cancellata (passo 5.2, 23/09/2026) e il chiamante
 * è rimasto uno solo: il contatore della Home. Il file resta qui e non torna
 * dentro la Home perché la domanda «questa unità è dichiarata?» è la stessa che
 * fa la griglia quando decide cosa mandare — se un giorno le due risposte
 * dovessero divergere, questo è il posto dove accorgersene.
 *
 * Entrambe le funzioni sono PURE: nessuna fetch, nessuno stato. Si testano
 * senza montare una pagina.
 */

/* ── «Questa unità è stata dichiarata?» ────────────────────────────────
 * Nodo F-1. La domanda è UNA e la risposta sta in UN posto, perché la fanno
 * in due: un TASK ATOMICO e un SOTTOTASK. Il payload di /me li rende
 * simmetrici apposta, quindi lo stesso criterio attraversa entrambi senza un
 * `if` sul tipo.
 *
 * LE ORE HANNO PRESO IL POSTO DELLA PERCENTUALE (passo 5.2). Fino al
 * 23/09/2026 la prima cosa che si guardava era `riga.percentuale`: era il
 * cursore, la dichiarazione principale del vecchio mondo. Nel mondo a blocchi
 * la dichiarazione principale sono le ORE, e `percentuale` è una colonna che
 * nessuno scrive più e che sparisce al passo 5.6 — continuare a leggerla
 * avrebbe reso il contatore sempre più cieco a mano a mano che i dati vecchi
 * invecchiavano, e poi rotto di colpo al drop.
 *
 * `blocchi` sono le ore MANUALI di questa settimana su questa unità, nella
 * stessa forma in cui la griglia le rimanda. `blocchi_storico` NON conta: sono
 * ore migrate dai consuntivi vecchi, in sola lettura, e non sono una
 * dichiarazione fatta questa settimana da questa persona.
 *
 * Gli altri tre termini restano quelli di prima, e sono il motivo per cui
 * «dichiarata» non vuol dire «ha delle ore»: un lavoro fermo si dichiara con
 * lo stato e la nota, senza ore (N6), e chi l'ha fatto ha compilato.
 */
export const unitaDichiarata = (riga) => {
  if ((riga.blocchi ?? []).length > 0) return true
  if (riga.stato_dichiarato != null) return true
  if ((riga.nota ?? '').trim() !== '') return true
  // «L'ho guardata, è ancora ferma» è una dichiarazione a tutti gli effetti.
  // NON si legge `nota_ereditata`: è il promemoria di una settimana
  // precedente, non una traccia di questa, e contarla direbbe «dichiarato» di
  // chi non ha aperto la pagina.
  if (riga.presa_visione === true) return true
  return false
}

/* ── «Scomposto» vuol dire CHE HA PEZZI VIVI ──────────────────────────
 * Gemella della costante omonima in ConsuntivazioneOre.jsx, e per la stessa
 * ragione: `Annullato` è lo stato con cui il PM toglie un pezzo dal PIANO, e
 * un task i cui pezzi sono stati annullati tutti torna a essere un'unità di
 * lavoro (M9). La lista dei pezzi che /me restituisce NON è vuota in quel caso
 * — ci restano dentro gli annullati su cui ci sono ore (N21) — quindi
 * `pezzi.length` non è la domanda giusta.
 *
 * È lo stesso identico confronto del backend (`tipo_unita_per_task` e
 * `task_scomposti`). Se di là cambia, questa è una delle due righe da cambiare.
 */
const PEZZO_ANNULLATO = 'Annullato'
const haPezziVivi = (pezzi) => pezzi.some((p) => p.stato !== PEZZO_ANNULLATO)

/* ── Le unità COMPILABILI della settimana ──────────────────────────────
 * Nodo F-1. L'unità di conteggio non è il task: è il pezzo di lavoro su cui
 * si dichiara. Un task scomposto NON conta per sé — «lo stato vive sui pezzi»
 * — contano i suoi sottotask, uno per uno. Un task con 3 pezzi vale 3.
 * Un task i cui pezzi sono tutti annullati torna a contare per uno: è M9, ed è
 * la stessa riga che la griglia disegna compilabile.
 *
 * COMPILABILI, non «mostrate». Un pezzo affidato a un collega compare in /me
 * ma è in sola lettura: contarlo renderebbe il denominatore IRRAGGIUNGIBILE —
 * 2/5 per sempre, con tre unità che chi guarda non può toccare in nessun modo.
 * Un contatore a cui non si può arrivare non è un obiettivo, è un rimprovero.
 * Per lo stesso motivo restano fuori i pezzi ANNULLATI: che abbiano ore o no,
 * nessuno ci può più scrivere.
 * I task atomici non hanno questo problema: /me li filtra già per dipendente.
 */
export const unitaCompilabili = (taskSettimana, dipendenteId) =>
  (taskSettimana ?? []).flatMap((t) => {
    const pezzi = t.sottotask ?? []
    if (!haPezziVivi(pezzi)) return [t]
    return pezzi.filter((p) =>
      p.stato !== PEZZO_ANNULLATO && p.assegnatario_id === dipendenteId)
  })
