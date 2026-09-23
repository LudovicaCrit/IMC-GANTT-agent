/**
 * formato.js — formattazione condivisa dalle due pagine di Consuntivazione.
 *
 * Estratto il 15/09/2026, quando è nata la griglia a ore accanto alla pagina a
 * cursore: le date si scrivono uguali in tutte e due, e due copie di `fmtData`
 * avrebbero finito per divergere.
 */

/** «7 set» da una data ISO. Stringa vuota se manca. */
export const fmtData = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('it-IT', { day: 'numeric', month: 'short' })
}

/**
 * «lun 7 set» da una data ISO 'YYYY-MM-DD' — la forma in cui l'utente legge un
 * giorno. Mai la data ISO in faccia a chi compila. Letta a mezzogiorno locale:
 * a mezzanotte un fuso la sposterebbe al giorno prima.
 */
export const fmtGiorno = (iso) => {
  if (!iso) return ''
  const d = new Date(`${String(iso).slice(0, 10)}T12:00:00`)
  if (Number.isNaN(d.getTime())) return String(iso)
  return d.toLocaleDateString('it-IT', { weekday: 'short', day: 'numeric', month: 'short' })
}

/**
 * Ore a DUE decimali, all'italiana: 16,75 · 8 · 2,5.
 *
 * Due e non uno: le ore da blocchi sono NUMERIC(5,2) e il backend le espone a
 * 2 decimali (quarti d'ora compresi). Arrotondare qui rifarebbe in pagina
 * l'errore corretto in /me (16,75 mostrato 16,8). Gli zeri finali si tolgono:
 * «8» si legge meglio di «8,00» in una matrice di numeri.
 */
export const fmtOre = (n) =>
  (Number(n) || 0).toLocaleString('it-IT', { maximumFractionDigits: 2 })
