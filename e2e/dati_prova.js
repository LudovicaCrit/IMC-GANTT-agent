import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const QUI = path.dirname(fileURLToPath(import.meta.url))
const RADICE = path.resolve(QUI, '..')

/**
 * Chiama `dati_prova.py`, che è dove vivono davvero i dati di prova: le righe
 * si creano e si cancellano con i modelli del backend, non con SQL riscritto in
 * JavaScript. Qui c'è solo il ponte.
 */
export function esegui(argomenti) {
  return python('dati_prova.py', argomenti)
}

/** Lo scenario del mondo-scomposto (`scenario_sottotask.py`). */
export function scenario(argomenti) {
  return python('scenario_sottotask.py', argomenti)
}

function python(script, argomenti) {
  const out = execFileSync(
    path.join(RADICE, '.venv', 'bin', 'python'),
    [path.join(QUI, script), ...argomenti],
    { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
  process.stdout.write(out)
  return out
}
