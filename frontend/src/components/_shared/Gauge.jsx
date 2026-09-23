import React from 'react'

/**
 * ═════════════════════════════════════════════════════════════════════════
 * Gauge.jsx — un quadrante circolare per una percentuale
 * ═════════════════════════════════════════════════════════════════════════
 *
 * NATO PER RIPARARE UNA PAGINA BIANCA (23/09/2026). La scheda «Avanzamento»
 * dell'Economia usava `<Gauge …>` in tre punti, ma il componente non esisteva:
 * non era importato e non era definito da nessuna parte del frontend. La build
 * passava — Vite non risolve i nomi dei componenti a build time — e al click
 * sulla scheda partiva un `ReferenceError: Gauge is not defined` che smontava
 * l'intero albero React: schermata nera, non solo la scheda. Nessuno se n'era
 * accorto perché nessun test apriva quella scheda.
 *
 * LA PERCENTUALE PUÒ SUPERARE IL 100, e il quadrante lo deve dire.
 * L'arco si ferma al giro completo — un cerchio non sa disegnare il 322% — ma
 * IL NUMERO AL CENTRO RESTA QUELLO VERO. È il punto che conta: in questo
 * database ci sono progetti che hanno consumato il 322% del budget ore, e un
 * quadrante che li mostrasse «100%» come uno arrivato esattamente a fine
 * budget cancellerebbe proprio l'informazione per cui lo si guarda. Oltre il
 * giro l'anello prende un secondo bordo, così l'eccesso si vede anche senza
 * leggere la cifra.
 *
 * `colorThresholds` = {yellow, red}: sopra `red` è rosso, sopra `yellow` ambra,
 * sotto è blu-accento. Le soglie le decide CHI USA il quadrante, perché
 * dipendono da cosa misura: «80% del budget speso» e «80% del tempo passato»
 * non vogliono lo stesso colore, e cablarle qui dentro vorrebbe dire dare la
 * stessa risposta a due domande diverse.
 */
const R = 42                       // raggio del cerchio nel viewBox 100×100
const CIRC = 2 * Math.PI * R

export default function Gauge({ value, label, colorThresholds = {} }) {
  const v = Number(value) || 0
  const { yellow = 70, red = 90 } = colorThresholds

  // L'arco si ferma al giro; il numero no (vedi sopra).
  const quota = Math.max(0, Math.min(100, v))
  const oltre = v > 100

  const colore = v >= red ? '#f87171' : v >= yellow ? '#fbbf24' : '#3b82f6'

  return (
    <div className="flex flex-col items-center" data-gauge={label} data-valore={v.toFixed(1)}>
      <svg viewBox="0 0 100 100" className="w-24 h-24 -rotate-90" role="img"
           aria-label={`${label}: ${v.toFixed(0)}%`}>
        <circle cx="50" cy="50" r={R} fill="none" stroke="var(--color-surface-700)" strokeWidth="8" />
        {oltre && (
          // Anello esterno sottile: «ha fatto più di un giro».
          <circle cx="50" cy="50" r={R + 6} fill="none" stroke={colore} strokeWidth="2" opacity="0.5" />
        )}
        <circle
          cx="50" cy="50" r={R} fill="none" stroke={colore} strokeWidth="8" strokeLinecap="round"
          strokeDasharray={CIRC}
          strokeDashoffset={CIRC * (1 - quota / 100)}
          style={{ transition: 'stroke-dashoffset 0.5s ease-out' }}
        />
      </svg>
      <p className="text-xl font-bold -mt-16 mb-9" style={{ color: colore }}>
        {v.toFixed(0)}%
      </p>
      <p className="text-xs text-gray-400 text-center leading-tight">{label}</p>
    </div>
  )
}
