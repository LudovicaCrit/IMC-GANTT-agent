/**
 * ═════════════════════════════════════════════════════════════════════════
 * KpiSintetici.jsx — 4 KPI card in cima al tab Design del Cantiere
 * ═════════════════════════════════════════════════════════════════════════
 *
 * Estratto da CantiereDettaglio.jsx (Step 2.3-bis 4a, 18 mag 2026).
 *
 * Mostra: Budget ore | Ore consumate/vendute | Avanzamento % | Task completati.
 * Lo sforamento ore_consumate > ore_vendute_totali è evidenziato in rosso.
 *
 * Props:
 *   - progetto: oggetto con budget_ore, ore_consumate_totali,
 *               ore_vendute_totali, fasi[].tasks[].stato
 *   - readonly: prop accettata per simmetria con altri componenti estratti,
 *               ma KpiSintetici è già read-only per natura (non ha bottoni
 *               né interazioni). Il prop viene ignorato.
 *
 * Riuso futuro: GANTT accordion dinamica (4c), pagina Archivio (Step 2.6).
 */

import React from 'react'

export default function KpiSintetici({ progetto, readonly = false }) {
  const budgetOre = progetto.budget_ore || 0
  const oreCons = progetto.ore_consumate_totali || 0
  const oreVen = progetto.ore_vendute_totali || 0
  const pct = oreVen > 0 ? Math.round((oreCons / oreVen) * 100) : 0
  const sforamento = oreVen > 0 && oreCons > oreVen

  // Conteggio task per stato (completamento percentuale)
  let taskTot = 0
  let taskComp = 0
  progetto.fasi?.forEach(f => {
    f.tasks.forEach(t => {
      taskTot++
      if (t.stato === 'Completato') taskComp++
    })
  })
  const pctTask = taskTot > 0 ? Math.round((taskComp / taskTot) * 100) : 0

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      <KpiCard label="Budget ore" valore={`${budgetOre}h`} />
      <KpiCard
        label="Ore consumate"
        valore={`${oreCons}h / ${oreVen}h`}
        rosso={sforamento}
      />
      <KpiCard label="Avanzamento" valore={`${pct}%`} />
      <KpiCard label="Task completati" valore={`${taskComp} / ${taskTot} (${pctTask}%)`} />
    </div>
  )
}

function KpiCard({ label, valore, rosso = false }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</div>
      <div className={`text-xl font-semibold ${rosso ? 'text-red-400' : 'text-gray-100'}`}>
        {valore}
      </div>
    </div>
  )
}
