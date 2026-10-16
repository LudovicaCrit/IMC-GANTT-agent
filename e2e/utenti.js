import path from 'node:path'
import { fileURLToPath } from 'node:url'

const QUI = path.dirname(fileURLToPath(import.meta.url))

/** Le sessioni già aperte, su file: le scrive apparecchia.js, le legge lo spec. */
export const CARTELLA_AUTH = path.join(QUI, '.auth')
export const statoAuth = (u) => path.join(CARTELLA_AUTH, `${u.chiave}.json`)

/** Gli utenti che servono alla verifica: quelli del seed e uno di prova. */
export const UTENTI = {
  helena: {
    chiave: 'helena', email: 'helena@imcgroup.it', password: 'user123',
    dipendente: 'D004',   // ruolo `user`: /api/tasks gli dà già solo i suoi
  },
  ludovica: {
    chiave: 'ludovica', email: 'ludovica@imcgroup.it', password: 'user123',
    dipendente: 'D011',   // ruolo `manager`: /api/tasks gli dà l'azienda intera
  },
  // Utente di prova, non del seed: lo crea dati_prova.py (UTENTE_INTONSA, stessi
  // indirizzo e password) per un dipendente senza dichiarazioni nella settimana.
  intonsa: {
    chiave: 'intonsa', email: 'e2e-settimana-intonsa@prova.invalid', password: 'prova-e2e-intonsa',
  },
}
