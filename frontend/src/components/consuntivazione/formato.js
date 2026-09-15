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
 * Ore a DUE decimali, all'italiana: 16,75 · 8 · 2,5.
 *
 * Due e non uno: le ore da blocchi sono NUMERIC(5,2) e il backend le espone a
 * 2 decimali (quarti d'ora compresi). Arrotondare qui rifarebbe in pagina
 * l'errore corretto in /me (16,75 mostrato 16,8). Gli zeri finali si tolgono:
 * «8» si legge meglio di «8,00» in una matrice di numeri.
 */
export const fmtOre = (n) =>
  (Number(n) || 0).toLocaleString('it-IT', { maximumFractionDigits: 2 })
