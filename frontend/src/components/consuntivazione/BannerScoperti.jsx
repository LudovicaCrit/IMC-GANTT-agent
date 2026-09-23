import React from 'react'

/**
 * BannerScoperti.jsx — «di queste non hai detto niente».
 *
 * Consuntivazione a ore, passo 4 sotto-passo 6. L'ultima cosa che manca alla
 * griglia: un promemoria sulle attività rimaste SENZA ORE E SENZA STATO.
 *
 * PERCHÉ ESISTE. Una settimana può essere compilata benissimo e lasciare
 * indietro tre task su cui non si è lavorato. Non è un errore — ci sono
 * settimane così — ma chi legge la Consuntivazione dall'altra parte (il PM, la
 * vista-settimana) vede una riga vuota e non sa distinguere «non ci ho
 * lavorato perché aspetto il cliente» da «mi sono dimenticato di compilare».
 * Sono due cose molto diverse e costa una tendina dirlo. Il banner chiede
 * quella tendina, e basta.
 *
 * INVITA, NON OBBLIGA. Non è un errore, non colora di rosso, non ferma il
 * Salva. Il salvataggio con attività ancora mute passa: a volte non c'è
 * davvero niente da dire, e un promemoria che diventa un muro insegna solo a
 * scrivere «ok» per farlo tacere.
 *
 * NON È LA COPERTURA. I giorni sotto-monte li segnala già la sintesi in cima
 * (sotto-passo 4, «giorni coperti»), e quella guarda le ORE del giorno. Questo
 * guarda le ATTIVITÀ senza spiegazione: si può avere la settimana coperta al
 * 100% e tre task muti, e viceversa. Due domande diverse, due posti diversi.
 *
 * `scoperti`: [{chiave, nome}] — le righe da nominare, già decise dalla pagina.
 * `onVai(chiave)`: portami lì. Qui non si cerca nel DOM e non si decide nulla.
 */
export default function BannerScoperti({ scoperti, onVai }) {
  if (!scoperti?.length) return null
  const uno = scoperti.length === 1

  return (
    <div className="mt-3 rounded-xl border border-amber-900/60 bg-amber-950/20 px-4 py-3"
         data-banner-scoperti={scoperti.length}>
      <p className="text-sm text-amber-100/90">
        {uno
          ? 'Un’attività non ha né ore né stato. Vuoi dire come sta?'
          : `${scoperti.length} attività non hanno né ore né stato. Vuoi dire come stanno?`}
      </p>
      <p className="text-[11px] text-amber-200/50 mt-0.5">
        Basta lo stato — e la nota, se è bloccata. Le ore non servono: un lavoro fermo si
        dichiara così. Puoi anche salvare senza dire niente.
      </p>
      <div className="flex flex-wrap gap-1.5 mt-2">
        {scoperti.map((s) => (
          <button
            key={s.chiave}
            type="button"
            onClick={() => onVai(s.chiave)}
            data-vai-riga={s.chiave}
            className="px-2 py-1 rounded-md text-xs border border-amber-900/70 bg-amber-950/40
                       text-amber-100/90 hover:bg-amber-900/40 hover:text-white
                       focus:outline-none focus:ring-2 focus:ring-amber-600"
          >
            {s.nome} →
          </button>
        ))}
      </div>
    </div>
  )
}
