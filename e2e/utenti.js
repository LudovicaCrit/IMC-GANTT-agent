import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const QUI = path.dirname(fileURLToPath(import.meta.url))

/** Le sessioni già aperte, su file: le scrive apparecchia.js, le legge lo spec. */
export const CARTELLA_AUTH = path.join(QUI, '.auth')
export const statoAuth = (u) => path.join(CARTELLA_AUTH, `${u.chiave}.json`)

/** Gli utenti che servono alla verifica: quelli del seed e quelli di prova. */
export const UTENTI = {
  helena: {
    chiave: 'helena', email: 'helena@imcgroup.it', password: 'user123',
    dipendente: 'D004',   // ruolo `user`: /api/tasks gli dà già solo i suoi
  },
  ludovica: {
    chiave: 'ludovica', email: 'ludovica@imcgroup.it', password: 'user123',
    dipendente: 'D011',   // ruolo `manager`: /api/tasks gli dà l'azienda intera
  },
  // Gli utenti di prova, non del seed: li crea dati_prova.py, e indirizzo e
  // password stanno solo in utenti_prova.json.
  ...utentiDiProva(),
}

function utentiDiProva() {
  const file = JSON.parse(fs.readFileSync(path.join(QUI, 'utenti_prova.json'), 'utf8'))
  return Object.fromEntries(Object.entries(file.utenti).map(([chiave, u]) =>
    [chiave, { chiave, email: u.email, password: u.password }]))
}
