import React from 'react'
import { fmtData } from './formato'

/* ── Il promemoria della nota ereditata ────────────────────────────────
 * Nodo F-2 (b). Mostra il perché di un fermo scritto in una settimana
 * PRECEDENTE, così chi compila non deve ridigitare «aspetto le credenziali»
 * ogni lunedì.
 *
 * Estratto da ConsuntivazioneUser.jsx il 15/09/2026: lo usano la pagina a
 * cursore e la griglia a ore, e il comportamento deve restare lo stesso.
 *
 * SOLA LETTURA, E FUORI DAL CAMPO-NOTA. È la regola più importante di questo
 * componente, e non è una scelta di stile. Se il testo ereditato finisse
 * PRECOMPILATO nel campo della nota, al salvataggio partirebbe come nota
 * PROPRIA di questa settimana, e il backend non ha modo di distinguerla. Il
 * risultato sarebbe che il dipendente firma parole scritte da un collega — o
 * da sé stesso settimane fa — senza averle riscritte.
 * Quindi: un <p>, non un input. Nessun `value`, nessun `onChange`.
 *
 * QUANDO SI MOSTRA lo decide chi lo usa (`mostra`): l'unità è ferma e non ha
 * già una nota propria questa settimana.
 */
export default function PromemoriaNota({ testo, da, mostra }) {
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
