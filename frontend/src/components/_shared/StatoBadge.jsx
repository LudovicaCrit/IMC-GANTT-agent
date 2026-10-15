/**
 * ═════════════════════════════════════════════════════════════════════════
 * StatoBadge.jsx — Badge colorato per stati Fase/Task/Progetto
 * ═════════════════════════════════════════════════════════════════════════
 *
 * Estratto da CantiereDettaglio.jsx (Step 2.3-bis 4a, 18 mag 2026).
 * Mostra uno stato con colore ed etichetta presi dalla mappa COLORI_STATO
 * di components/cantiere/_costanti.js, che li legge da condiviso/stati.json:
 * gli stessi colori delle barre del GANTT. Il colore è un esadecimale e va in
 * `style`: una classe Tailwind costruita a runtime non verrebbe generata.
 * Il fondo è il colore pieno e il testo è scuro, leggibile su tutti i colori
 * della mappa.
 *
 * Usato in: CantiereDettaglio, FaseEditabile, eventualmente Risorse,
 * pagina Archivio futura.
 */

import React from 'react'
import { COLORI_STATO } from '../cantiere/_costanti'
import { COLORE_IGNOTO } from './statiColori'

export default function StatoBadge({ stato }) {
  const voce = COLORI_STATO[stato]
  return (
    <span className="text-xs px-2 py-0.5 rounded text-gray-900"
      style={{ backgroundColor: voce?.colore ?? COLORE_IGNOTO }}>
      {voce?.etichetta ?? stato}
    </span>
  )
}
