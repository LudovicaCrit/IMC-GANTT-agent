/**
 * ═════════════════════════════════════════════════════════════════════════
 * _costanti.js — Costanti condivise dai componenti della scheda Cantiere
 * ═════════════════════════════════════════════════════════════════════════
 *
 * Estratte da CantiereDettaglio.jsx il 18 mag 2026 (Step 2.3-bis sotto-passo
 * 4a). Vivono qui perché sono usate da più componenti estratti
 * (SezioneFasiTask, FaseEditabile, BannerStato, ModaleConfermaCascata, ecc.)
 * e dal file principale.
 *
 * Allineate ai CHECK constraint del DB Postgres (vedi alembic migration
 * c3d4e5f6a7b8): se cambi qui, cambia anche in models.py e nella migration.
 *
 * Il prefisso "_" segnala "modulo interno di sezione cantiere": non importare
 * da altri ambiti (Risorse, Home, ecc.), che hanno costanti proprie.
 */

export const STATI_FASE = ['Da iniziare', 'In corso', 'Completata', 'Sospesa', 'Annullata']
export const STATI_TASK = ['Da iniziare', 'In corso', 'Completato', 'Bloccato']

export const COLORI_STATO = {
  // Fase
  'Da iniziare': 'bg-gray-700 text-gray-300',
  'In corso': 'bg-blue-700 text-blue-100',
  'Completata': 'bg-green-700 text-green-100',
  'Sospesa': 'bg-yellow-700 text-yellow-100',
  'Annullata': 'bg-red-900 text-red-200',
  // Task
  'Completato': 'bg-green-700 text-green-100',
  'Da fare': 'bg-gray-700 text-gray-300',
  'Bloccato': 'bg-red-700 text-red-100',
  'Eliminato': 'bg-red-950 text-red-300',
  // Progetto
  'Bozza': 'bg-amber-800 text-amber-100',
  'In esecuzione': 'bg-blue-700 text-blue-100',
  'Sospeso': 'bg-yellow-700 text-yellow-100',
  'Annullato': 'bg-red-900 text-red-200',
}
