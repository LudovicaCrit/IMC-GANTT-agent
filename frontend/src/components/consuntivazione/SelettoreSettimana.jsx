import React from 'react'

/* ── Il selettore della settimana ─────────────────────────────────────────
 * Le settimane arrivano GIÀ DECISE da /me (`settimane_disponibili`: la corrente
 * e la precedente). Qui non si ricalcola nulla, si mostra.
 *
 * NON C'È PIÙ UNA SETTIMANA IN SOLA LETTURA, e questo componente lo dice con
 * quello che non ha. Fino al fix N17 la precedente si chiudeva al
 * raggiungimento del monte ore e si mostrava con un «già chiusa» accanto e un
 * banner «puoi consultarla, ma non modificarla»; da quando la finestra è
 * temporale, tutt'e due le settimane sono compilabili e quelle fuori finestra
 * non si aprono affatto — /me risponde 400 e la pagina mostra l'errore, non una
 * griglia da guardare. Badge e banner sono usciti col passo 5.2.
 *
 * `onScegli(lunedi)` — la conferma «hai modifiche non salvate» resta a chi usa
 * il componente: solo la pagina sa se ha modifiche pendenti.
 */
export default function SelettoreSettimana({ settimane, attiva, onScegli }) {
  return (
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
          </button>
        )
      })}
    </div>
  )
}
