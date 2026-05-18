/**
 * ═════════════════════════════════════════════════════════════════════════
 * BannerStato.jsx — Banner stato progetto in cima alla scheda Cantiere
 * ═════════════════════════════════════════════════════════════════════════
 *
 * Estratto da CantiereDettaglio.jsx (Step 2.3-bis 4a, 18 mag 2026).
 *
 * Due varianti:
 *   - Progetto in BOZZA: banner ambra con "Avvia progetto" (abilitato solo
 *     se almeno una fase esiste)
 *   - Progetto attivo (In esecuzione / Sospeso / Completato / Annullato):
 *     mostra stato corrente + badge + bottoni di cambio stato per attivi
 *
 * Props:
 *   - progetto: oggetto con stato, n_fasi, stato_derivato
 *   - onAvvia: callback per il bottone "▶ Avvia progetto" (solo in BOZZA)
 *   - onCambiaStato: callback (nuovoStato) per i bottoni di cambio
 *   - readonly: se true, nasconde tutti i bottoni interattivi. Mostra solo
 *     lo stato corrente e l'eventuale ⚠ derivato.
 *
 * Riuso futuro: accordion dinamica GANTT (4c, readonly=true), Archivio.
 */

import React from 'react'
import StatoBadge from '../_shared/StatoBadge'

export default function BannerStato({ progetto, onAvvia, onCambiaStato, readonly = false }) {
  if (progetto.stato === 'Bozza') {
    const puoAvviare = progetto.n_fasi > 0
    return (
      <div className="bg-amber-900/40 border border-amber-700 rounded-lg p-4 mb-6 flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="text-amber-200 font-semibold">📝 Progetto in BOZZA</div>
          <div className="text-sm text-amber-300/80 mt-1">
            {readonly
              ? 'Bozza non ancora avviata.'
              : puoAvviare
                ? 'Pronto per essere avviato. Verifica fasi e task, poi clicca "Avvia progetto".'
                : 'Per avviare il progetto, aggiungi almeno una fase nella sezione Design.'}
          </div>
        </div>
        {!readonly && (
          <button
            onClick={onAvvia}
            disabled={!puoAvviare}
            className={`px-5 py-2 rounded-lg font-semibold text-sm transition-colors ${
              puoAvviare
                ? 'bg-green-600 hover:bg-green-500 text-white'
                : 'bg-gray-700 text-gray-500 cursor-not-allowed'
            }`}
          >
            ▶ Avvia progetto
          </button>
        )}
      </div>
    )
  }

  const cambiabile = !readonly && ['In esecuzione', 'Sospeso'].includes(progetto.stato)
  const divergenza = progetto.stato !== progetto.stato_derivato

  return (
    <div className="bg-gray-800/60 border border-gray-700 rounded-lg p-4 mb-6">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm text-gray-400">Stato:</span>
        <StatoBadge stato={progetto.stato} />
        {divergenza && (
          <span className="text-xs text-yellow-400" title="Stato calcolato dalle fasi">
            ⚠ derivato: <strong>{progetto.stato_derivato}</strong>
          </span>
        )}
        {cambiabile && (
          <div className="ml-auto flex gap-2 items-center flex-wrap">
            <span className="text-xs text-gray-500">Cambia in:</span>
            {progetto.stato === 'In esecuzione' && (
              <button onClick={() => onCambiaStato('Sospeso')}
                className="px-3 py-1 text-xs bg-yellow-700/60 hover:bg-yellow-700 rounded">Sospeso</button>
            )}
            {progetto.stato === 'Sospeso' && (
              <button onClick={() => onCambiaStato('In esecuzione')}
                className="px-3 py-1 text-xs bg-blue-700/60 hover:bg-blue-700 rounded">In esecuzione</button>
            )}
            <button onClick={() => onCambiaStato('Completato')}
              className="px-3 py-1 text-xs bg-green-700/60 hover:bg-green-700 rounded">Completato</button>
            <button onClick={() => onCambiaStato('Annullato')}
              className="px-3 py-1 text-xs bg-red-800/60 hover:bg-red-800 rounded">Annullato</button>
          </div>
        )}
      </div>
    </div>
  )
}
