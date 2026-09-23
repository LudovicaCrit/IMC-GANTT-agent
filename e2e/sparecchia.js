import fs from 'node:fs'
import { esegui, scenario, scenarioFasi } from './dati_prova.js'
import { CARTELLA_AUTH } from './utenti.js'

/** Dopo la verifica: via i task di prova e tutto ciò che ci è stato scritto
 *  sopra, e si ristampa l'impronta — dev'essere identica a quella di prima.
 *  Via anche le sessioni salvate: sono JWT veri, non restano in giro. */
export default async function sparecchia() {
  fs.rmSync(CARTELLA_AUTH, { recursive: true, force: true })
  console.log('\n── pulizia ──')
  esegui(['--pulisci'])
  scenario(['--cancella'])
  scenarioFasi(['--cancella'])
  console.log('── impronta DOPO ──')
  esegui(['--impronta'])
}
