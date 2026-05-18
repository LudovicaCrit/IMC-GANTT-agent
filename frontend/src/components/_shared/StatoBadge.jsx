/**
 * ═════════════════════════════════════════════════════════════════════════
 * StatoBadge.jsx — Badge colorato per stati Fase/Task/Progetto
 * ═════════════════════════════════════════════════════════════════════════
 *
 * Estratto da CantiereDettaglio.jsx (Step 2.3-bis 4a, 18 mag 2026).
 * Mostra uno stato con colore appropriato (verde Completato, rosso
 * Annullato, ecc.) usando la mappa COLORI_STATO definita in
 * components/cantiere/_costanti.js.
 *
 * Usato in: CantiereDettaglio, FaseEditabile, eventualmente Risorse,
 * pagina Archivio futura.
 */

import React from 'react'
import { COLORI_STATO } from '../cantiere/_costanti'

export default function StatoBadge({ stato }) {
  const cls = COLORI_STATO[stato] || 'bg-gray-700 text-gray-300'
  return <span className={`text-xs px-2 py-0.5 rounded ${cls}`}>{stato}</span>
}
