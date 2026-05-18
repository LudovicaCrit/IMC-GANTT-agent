/**
 * ═════════════════════════════════════════════════════════════════════════
 * SezionePersone.jsx — Persone coinvolte nei task del progetto
 * ═════════════════════════════════════════════════════════════════════════
 *
 * Estratto da CantiereDettaglio.jsx (Step 2.3-bis 4a, 18 mag 2026).
 *
 * Deriva la lista persone uniche dai task della gerarchia progetto→fasi→task.
 * Già read-only di sua natura: mostra solo tag con nome + profilo. Non ha
 * bottoni di edit, quindi il prop `readonly` è accettato per coerenza ma
 * di fatto non cambia il comportamento.
 *
 * Props:
 *   - progetto: oggetto con .fasi[].tasks[].dipendente_id
 *   - dipendenti: lista [{ id, nome, profilo }]
 *   - readonly: accettato per simmetria, ignorato (è già read-only).
 */

import React, { useMemo } from 'react'

export default function SezionePersone({ progetto, dipendenti, readonly = false }) {
  const personeIds = useMemo(() => {
    const s = new Set()
    progetto.fasi?.forEach(f => f.tasks.forEach(t => { if (t.dipendente_id) s.add(t.dipendente_id) }))
    return [...s]
  }, [progetto])

  if (personeIds.length === 0) {
    return (
      <section className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <h2 className="text-xl font-semibold mb-2">👥 Persone coinvolte</h2>
        <p className="text-sm text-gray-500 italic">Nessuna persona assegnata ai task di questo progetto.</p>
      </section>
    )
  }

  const persone = personeIds.map(id => dipendenti.find(d => d.id === id)).filter(Boolean)

  return (
    <section className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
      <h2 className="text-xl font-semibold mb-3">👥 Persone coinvolte ({persone.length})</h2>
      <div className="flex flex-wrap gap-2">
        {persone.map(d => (
          <div key={d.id} className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm">
            <div className="font-medium">{d.nome}</div>
            <div className="text-xs text-gray-500">{d.profilo || ''}</div>
          </div>
        ))}
      </div>
    </section>
  )
}
