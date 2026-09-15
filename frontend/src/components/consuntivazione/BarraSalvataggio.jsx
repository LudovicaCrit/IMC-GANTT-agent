import React from 'react'

/* ── La barra di salvataggio in fondo alla pagina ─────────────────────────
 * Estratta da ConsuntivazioneUser.jsx il 15/09/2026: la usano la pagina a
 * cursore e la griglia a ore.
 *
 * STICKY, non FIXED — e la differenza è il logout di Helena.
 * `fixed bottom-0 left-0` ancora al VIEWPORT: `left-0` è il bordo sinistro
 * dello schermo, non l'inizio del contenuto, quindi la barra passava sotto la
 * sidebar per tutta la sua larghezza e copriva il bottone Logout.
 * `sticky bottom-0` si ancora al fondo dell'area visibile del suo contenitore di
 * scroll — il `<main>` — che comincia DOPO la sidebar: non può uscirne per
 * costruzione, e sopravvive al toggle «Comprimi» senza sapere quanto è larga.
 *
 * `stato`: null | 'invio' | 'ok' | messaggio d'errore (stringa).
 * `errori`: FACOLTATIVO, lista di messaggi. Se c'è, l'errore si mostra come
 *   elenco — un 400 del salvataggio a blocchi porta TUTTE le violazioni, e in
 *   una riga sola sarebbero illeggibili. Senza, il comportamento è quello di
 *   sempre (la stringa in rosso).
 * `avvisi`: FACOLTATIVO, segnalazioni non bloccanti dopo un salvataggio riuscito.
 */
export default function BarraSalvataggio({ stato, haPendenti, nModifiche, onSalva, errori, avvisi }) {
  const inErrore = stato && !['ok', 'invio'].includes(stato)
  return (
    <div className="sticky bottom-0 z-20 -mx-2 mt-4 rounded-t-xl border-t backdrop-blur"
         style={{ backgroundColor: 'rgba(17,24,39,0.92)', borderColor: 'var(--color-border-subtle, #1f2937)' }}>
      <div className="px-6 py-3 flex items-center justify-between gap-4">
        <div className="text-sm min-w-0" role="status" aria-live="polite">
          {stato === 'ok' && <span className="text-green-400">✓ Salvato</span>}
          {stato === 'ok' && avvisi?.length > 0 && (
            <ul className="text-amber-300 text-xs mt-1 list-disc pl-4">
              {avvisi.map((a, i) => <li key={i}>{a}</li>)}
            </ul>
          )}
          {stato === 'invio' && <span className="text-gray-400">Salvataggio…</span>}
          {inErrore && (errori?.length > 1 ? (
            <div className="text-red-400">
              <p>Non salvato — da correggere:</p>
              <ul className="list-disc pl-4 text-xs mt-1 space-y-0.5">
                {errori.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </div>
          ) : (
            <span className="text-red-400">{errori?.[0] ?? stato}</span>
          ))}
          {!stato && haPendenti && (
            <span className="text-amber-300">
              {nModifiche} {nModifiche === 1 ? 'modifica' : 'modifiche'} da salvare
            </span>
          )}
          {!stato && !haPendenti && (
            <span className="text-gray-600">Nessuna modifica</span>
          )}
        </div>

        <button
          onClick={onSalva}
          disabled={!haPendenti || stato === 'invio'}
          className="px-5 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white shrink-0
                     hover:bg-blue-500 disabled:bg-gray-800 disabled:text-gray-600
                     disabled:cursor-not-allowed transition-colors"
        >
          Salva
        </button>
      </div>
    </div>
  )
}
