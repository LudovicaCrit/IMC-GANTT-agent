/**
 * soglie.js — le soglie della griglia a ore, in UN posto solo.
 *
 * Sono TARATURA, non regole: stanno qui, e non sparse nei componenti, perché
 * quando esisterà la Configurazione si sposteranno lì senza cercarle in giro.
 *
 * COSA MISURANO — il NUMERO, non la persona. Un giorno «oltre il monte» dice
 * che quel giorno ha più ore del contratto, e basta: nessun giudizio su chi le
 * ha lavorate. Nessuna di queste soglie blocca il salvataggio; l'unico muro è
 * quello del backend a 24 ore in un giorno (N14), che la griglia anticipa per
 * evitare il 400.
 *
 * IL MONTE della persona arriva da /me (`ore_contrattuali`): 40 per quasi
 * tutti, 20 per un part-time. Il monte GIORNALIERO non esiste nel modello: si
 * approssima come settimanale / GIORNI_LAVORATIVI. È solo un segnale, e per chi
 * lavora meno giorni ma più lunghi può essere impreciso.
 */

export const GIORNI_LAVORATIVI = 5

export const SOGLIE = {
  // Un giorno oltre queste ore ASSOLUTE ha un segnale più marcato («è tanto»).
  giornoAltoOre: 10,
  // Una settimana oltre questa FRAZIONE del monte ha un segnale più marcato
  // (1,25 = 125%: 50h su 40).
  settimanaAltaQuota: 1.25,
  // Un giorno è «coperto» quando le sue ore arrivano a questa frazione del
  // monte giornaliero: un margine sotto va bene (7,5h su 8 conta).
  giornoCopertoQuota: 0.9,
  // Il muro del backend (N14). Qui è solo per avvisare prima del 400.
  giornoTettoOre: 24,
}

export const monteGiornaliero = (monteSettimana) =>
  (Number(monteSettimana) || 0) / GIORNI_LAVORATIVI

/** 'normale' | 'oltre' | 'alto' | 'tetto' — il livello delle ore di un giorno. */
export const livelloGiorno = (ore, monteGiorno) => {
  if (ore > SOGLIE.giornoTettoOre) return 'tetto'
  if (ore > SOGLIE.giornoAltoOre) return 'alto'
  if (monteGiorno > 0 && ore > monteGiorno) return 'oltre'
  return 'normale'
}

/** 'normale' | 'oltre' | 'alto' — il livello delle ore della settimana. */
export const livelloSettimana = (ore, monteSettimana) => {
  if (monteSettimana > 0 && ore > monteSettimana * SOGLIE.settimanaAltaQuota) return 'alto'
  if (monteSettimana > 0 && ore > monteSettimana) return 'oltre'
  return 'normale'
}

export const giornoCoperto = (ore, monteGiorno) =>
  monteGiorno > 0 && ore >= monteGiorno * SOGLIE.giornoCopertoQuota
