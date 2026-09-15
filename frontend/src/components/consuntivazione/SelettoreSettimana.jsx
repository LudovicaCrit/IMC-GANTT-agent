import React from 'react'

/* ── Il selettore della settimana + l'avviso di sola lettura ──────────────
 * Estratto da ConsuntivazioneUser.jsx il 15/09/2026: la pagina a cursore e la
 * griglia a ore aprono le stesse settimane con le stesse regole, che arrivano
 * GIÀ DECISE da /me (`settimane_disponibili`: la corrente e la precedente, con
 * `compilabile`). Qui non si ricalcola nulla, si mostra.
 *
 * `onScegli(lunedi)` — la conferma «hai modifiche non salvate» resta a chi usa
 * il componente: solo la pagina sa se ha modifiche pendenti.
 */
export default function SelettoreSettimana({ settimane, attiva, soloLettura, onScegli }) {
  return (
    <>
      <div className="flex items-center gap-2 mb-6">
        {settimane?.map((s) => {
          const selezionata = s.lunedi === attiva
          return (
            <button
              key={s.lunedi}
              onClick={() => onScegli(s.lunedi)}
              className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                selezionata
                  ? 'bg-gray-700 text-white border-gray-600'
                  : 'bg-gray-900 text-gray-400 border-gray-800 hover:text-gray-200'
              }`}
            >
              {s.etichetta}
              {!s.compilabile && <span className="ml-2 text-[10px] text-gray-500">già chiusa</span>}
            </button>
          )
        })}
      </div>

      {soloLettura && (
        <div className="bg-gray-800/60 border border-gray-700 rounded-lg px-4 py-3 mb-6">
          <p className="text-sm text-gray-300">
            Questa settimana è già stata compilata: puoi consultarla, ma non modificarla.
          </p>
        </div>
      )}
    </>
  )
}
