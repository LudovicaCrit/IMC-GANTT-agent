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
 * Allineate ai CHECK constraint del DB Postgres (i `ck_*_stato_ammessi` di
 * models.py).
 *
 * Se cambi qui, cambia anche in models.py e il CHECK nelle migration.
 *
 * Il prefisso "_" segnala "modulo interno di sezione cantiere": non importare
 * da altri ambiti (Risorse, Home, ecc.), che hanno costanti proprie.
 */

import {
  STATI_PROGETTO as STATI_PROGETTO_COLORI,
  STATI_FASE as STATI_FASE_COLORI,
  STATI_TASK as STATI_TASK_COLORI,
} from '../_shared/statiColori.js'

export const STATI_FASE = ['Da iniziare', 'In corso', 'Completata', 'Sospesa', 'Annullata']

// Step 2.7-pre (20/05/2026): aggiunti Sospeso e Annullato (formalizzati nel
// DB con CHECK constraint ck_task_stato_ammessi). La cascata Fase→Task li
// scriveva già a runtime, ora sono ammessi anche dal DB.
export const STATI_TASK = ['Da iniziare', 'In corso', 'Completato', 'Bloccato', 'Sospeso', 'Annullato']

// Stati di PIANIFICAZIONE del sottotask — quelli che il PM governa sulla
// DEFINIZIONE del pezzo dal Cantiere. CHECK a livello DB:
// ck_sottotask_stato_pianificazione.
//
// NON sono i tre dichiarabili (In corso / Completato / Bloccato): quelli sono
// l'asse del DIPENDENTE e vivono sulle sue dichiarazioni settimanali, non sulla
// definizione condivisa del pezzo. «In corso» su una definizione non
// significherebbe nulla: in corso per chi? Il backend rifiuta i dichiarabili con
// un 400 che rimanda alla Consuntivazione — il selettore del Cantiere offre solo
// questi tre, così quell'errore non si incontra.
export const STATI_PIANIFICAZIONE_SOTTOTASK = ['Da iniziare', 'Sospeso', 'Annullato']

// Colore ed etichetta dei badge di stato (StatoBadge), dalla stessa fonte delle
// barre del GANTT: condiviso/stati.json, letto da statiColori.js. Il badge
// riceve solo il nome dello stato e non il livello, quindi qui le tre mappe si
// fondono in una: si può fare perché uno stesso nome ha lo stesso colore in
// ogni livello («Sospeso» del progetto e del task sono entrambi ambra), e un
// test (frontend/test/statiColori.test.js) controlla che resti così.
// «Eliminato» non c'è: il soft-delete è fuori dal flusso e prende il colore
// degli stati ignoti.
export const COLORI_STATO = { ...STATI_PROGETTO_COLORI, ...STATI_FASE_COLORI, ...STATI_TASK_COLORI }
