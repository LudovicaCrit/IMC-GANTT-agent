/**
 * Test della fonte unica dei colori (condiviso/stati.json) lato frontend.
 * Test runner integrato di Node: `npm run test:disegno`.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {
  STATI_PROGETTO, STATI_FASE, STATI_TASK, COLORE_IGNOTO, coloreStato,
} from '../src/components/_shared/statiColori.js'

const FILE = new URL('../../condiviso/stati.json', import.meta.url)
const SUL_DISCO = JSON.parse(fs.readFileSync(FILE, 'utf-8'))

test('statiColori espone esattamente il contenuto di condiviso/stati.json', () => {
  assert.deepEqual(STATI_PROGETTO, SUL_DISCO.progetto)
  assert.deepEqual(STATI_FASE, SUL_DISCO.fase)
  assert.deepEqual(STATI_TASK, SUL_DISCO.task)
  assert.equal(COLORE_IGNOTO, SUL_DISCO.ignoto.colore)
  assert.equal(coloreStato('task', 'Bloccato'), SUL_DISCO.task.Bloccato.colore)
  assert.equal(coloreStato('task', 'Inventato'), COLORE_IGNOTO)
})

test('ogni voce ha un colore esadecimale e un\'etichetta', () => {
  for (const mappa of [STATI_PROGETTO, STATI_FASE, STATI_TASK]) {
    for (const [stato, voce] of Object.entries(mappa)) {
      assert.match(voce.colore, /^#[0-9a-f]{6}$/i, stato)
      assert.ok(voce.etichetta, stato)
    }
  }
})

// I badge (cantiere/_costanti.js, COLORI_STATO) ricevono solo il nome dello
// stato e fondono le tre mappe: regge solo se un nome ha lo stesso colore e la
// stessa etichetta in ogni livello.
test('uno stesso nome di stato ha la stessa voce in ogni livello', () => {
  const visti = {}
  for (const mappa of [STATI_PROGETTO, STATI_FASE, STATI_TASK]) {
    for (const [stato, voce] of Object.entries(mappa)) {
      if (stato in visti) assert.deepEqual(voce, visti[stato], stato)
      visti[stato] = voce
    }
  }
})
