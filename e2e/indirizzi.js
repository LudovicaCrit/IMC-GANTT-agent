import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

/**
 * Gli indirizzi del backend e del frontend per la verifica, ricavati dalle
 * stesse variabili che leggono il backend e Vite (GANTT_PORTA_BACKEND,
 * GANTT_PORTA_FRONTEND in backend/.env). Nessun numero è scritto qui: se le
 * variabili mancano la verifica si ferma, invece di cercare i server su porte
 * diverse da quelle su cui partono.
 *
 * Una variabile già presente nell'ambiente vince sul file (process.loadEnvFile
 * non sovrascrive), come per il backend e per Vite.
 */
export const RADICE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const ENV_BACKEND = path.join(RADICE, 'backend', '.env')

if (fs.existsSync(ENV_BACKEND)) process.loadEnvFile(ENV_BACKEND)

function porta(nome) {
  const valore = process.env[nome]
  if (!valore) {
    throw new Error(`${nome} non impostata: aggiungila in backend/.env (vedi backend/.env.example).`)
  }
  return valore
}

export const PORTA_BACKEND = porta('GANTT_PORTA_BACKEND')
export const PORTA_FRONTEND = porta('GANTT_PORTA_FRONTEND')
export const URL_BACKEND = `http://localhost:${PORTA_BACKEND}`
export const URL_FRONTEND = `http://localhost:${PORTA_FRONTEND}`
