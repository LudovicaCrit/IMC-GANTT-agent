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
 * Allineate ai CHECK constraint del DB Postgres. Storico migration:
 *   - c3d4e5f6a7b8 (13 mag 2026): CHECK fasi.stato e progetti.stato (5 stati)
 *   - d4e5f6a7b8c9 (20 mag 2026): CHECK task.stato + "Da iniziare" su progetti
 *
 * Se cambi qui, cambia anche in models.py e nella migration corrispondente.
 *
 * Il prefisso "_" segnala "modulo interno di sezione cantiere": non importare
 * da altri ambiti (Risorse, Home, ecc.), che hanno costanti proprie.
 */

export const STATI_FASE = ['Da iniziare', 'In corso', 'Completata', 'Sospesa', 'Annullata']

// Step 2.7-pre (20/05/2026): aggiunti Sospeso e Annullato (formalizzati nel
// DB con CHECK constraint ck_task_stato_ammessi). La cascata Fase→Task li
// scriveva già a runtime, ora sono ammessi anche dal DB.
export const STATI_TASK = ['Da iniziare', 'In corso', 'Completato', 'Bloccato', 'Sospeso', 'Annullato']

// Step 2.7-pre (20/05/2026): aggiunto "Da iniziare" — progetto approvato dal
// cliente con fasi pianificate ma non ancora partito (data_inizio futura).
// Transizione "Da iniziare → In esecuzione" è MANUALE (decisione PM, vedi
// handoff §3.5 "controllo non automazione").
export const STATI_PROGETTO = ['Bozza', 'Da iniziare', 'In esecuzione', 'Sospeso', 'Completato', 'Annullato']

// Sottoinsieme "attivi": progetti visibili in GANTT (In esecuzione + Sospeso).
// "Da iniziare" NON è qui — il progetto Da iniziare è in attesa di partire,
// la sua visualizzazione in GANTT sarà gestita con un alert in Home quando
// data_inizio <= oggi (Blocco 3).
export const STATI_PROGETTO_ATTIVI = ['In esecuzione', 'Sospeso']

export const COLORI_STATO = {
  // ── Fase ──────────────────────────────────────────────────────────
  'Da iniziare': 'bg-gray-700 text-gray-300',
  'In corso': 'bg-blue-700 text-blue-100',
  'Completata': 'bg-green-700 text-green-100',
  'Sospesa': 'bg-yellow-700 text-yellow-100',
  'Annullata': 'bg-red-900 text-red-200',

  // ── Task (alcuni stati coincidono con Fase, vedi 'Da iniziare') ──
  'Completato': 'bg-green-700 text-green-100',
  'Bloccato': 'bg-red-700 text-red-100',
  // Soft-delete task: lo lascio come colore "fantasma" per retrocompatibilità
  // ma NON è nella whitelist STATI_TASK (è un soft delete fuori dal flusso).
  'Eliminato': 'bg-red-950 text-red-300',

  // ── Progetto ──────────────────────────────────────────────────────
  'Bozza': 'bg-amber-800 text-amber-100',
  'In esecuzione': 'bg-blue-700 text-blue-100',
  'Sospeso': 'bg-yellow-700 text-yellow-100',  // condiviso anche con Task.Sospeso
  'Annullato': 'bg-red-900 text-red-200',      // condiviso anche con Task.Annullato
  // Nota: "Da iniziare" Progetto eredita lo stesso colore di "Da iniziare" Fase/Task
  // (è gray-700/gray-300, vedi prima entry). Questo è voluto: la semantica
  // "non ancora partito" è la stessa.
}
