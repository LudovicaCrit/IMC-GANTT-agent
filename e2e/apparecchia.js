import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { request } from '@playwright/test'
import { esegui, scenario } from './dati_prova.js'
import { UTENTI, statoAuth, CARTELLA_AUTH } from './utenti.js'

const QUI = path.dirname(fileURLToPath(import.meta.url))

/**
 * Prima della verifica: via i residui di un giro precedente, poi i due task di
 * prova, poi l'impronta dello storico da confrontare alla fine.
 *
 * E il LOGIN, una volta per utente, salvato su file. Non è un'ottimizzazione:
 * `/api/auth/login` ha un rate limit di 5 al minuto per IP (auth_routes.py), e
 * una verifica che accede a ogni test lo sfonda appena cresce — il quinto test
 * resta sulla pagina di login e fallisce per un motivo che non c'entra niente
 * con quello che stava provando. Qui si accede due volte e basta.
 */
export default async function apparecchia() {
  console.log('\n── dati di prova ──')
  esegui(['--pulisci', '--crea'])
  console.log('── scenario sottotask ──')
  scenario(['--cancella', '--crea'])

  fs.mkdirSync(CARTELLA_AUTH, { recursive: true })
  for (const u of Object.values(UTENTI)) {
    const ctx = await request.newContext({ baseURL: 'http://localhost:3000' })
    const r = await ctx.post('/api/auth/login', { data: { email: u.email, password: u.password } })
    if (!r.ok()) throw new Error(`login ${u.email}: ${r.status()} ${await r.text()}`)
    await ctx.storageState({ path: statoAuth(u) })
    await ctx.dispose()
    console.log(`  sessione di ${u.email} salvata`)
  }

  console.log('── impronta PRIMA ──')
  esegui(['--impronta'])
}
