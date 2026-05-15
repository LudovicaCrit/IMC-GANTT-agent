// ─────────────────────────────────────────────────────────────────────────
//  api.js — Client HTTP centralizzato per il backend GANTT Agent
//
//  Tutte le chiamate al backend passano da `apiFetch`, che gestisce:
//    • invio del cookie httpOnly (credentials: 'include')
//    • header Content-Type per richieste con body JSON
//    • redirect automatico al login su 401 (cookie scaduto/assente)
//    • lancio di ForbiddenError su 403 (loggato ma non autorizzato)
//    • messaggio dedicato su 429 (rate limit)
//    • parsing JSON di default (override con rawResponse per blob/PDF)
//
//  Le funzioni esportate mantengono la stessa firma di prima — questo file
//  è un refactoring infrastrutturale, non un cambio di API per le pagine.
// ─────────────────────────────────────────────────────────────────────────

const API_BASE = '/api';

// Errore custom per il 403 — la pagina che riceve questo errore può
// decidere di mostrare un messaggio in linea o renderizzare la 403 page.
export class ForbiddenError extends Error {
  constructor(message = 'Non sei autorizzato a questa operazione') {
    super(message);
    this.name = 'ForbiddenError';
  }
}

/**
 * Funzione interna: tutte le chiamate al backend passano da qui.
 *
 * @param {string} url - URL relativo o assoluto
 * @param {object} options - opzioni standard di fetch + estensioni:
 *   - body: se presente come oggetto, viene serializzato a JSON e l'header
 *     Content-Type viene impostato automaticamente
 *   - rawResponse: se true, restituisce la Response grezza senza parsare JSON
 *     (usato da exportGanttPdf per scaricare il blob)
 *   - skipAuthRedirect: se true, NON reindirizza al login su 401
 *     (riservato al solo getCurrentUser durante il bootstrap di AuthContext)
 */
export async function apiFetch(url, options = {}) {
  const { body, rawResponse = false, skipAuthRedirect = false, ...rest } = options;

  // Costruzione opzioni per fetch
  const fetchOptions = {
    credentials: 'include', // ← invia il cookie httpOnly
    ...rest,
    headers: { ...(rest.headers || {}) },
  };

  // Se c'è un body oggetto, lo serializziamo + Content-Type
  if (body !== undefined) {
    if (typeof body === 'string' || body instanceof FormData) {
      fetchOptions.body = body;
    } else {
      fetchOptions.body = JSON.stringify(body);
      fetchOptions.headers['Content-Type'] = 'application/json';
    }
  }

  let res;
  try {
    res = await fetch(url, fetchOptions);
  } catch (err) {
    // Errore di rete (server giù, DNS fallito, CORS bloccante)
    throw new Error(`Errore di rete: ${err.message}`);
  }

  // ── Gestione errori HTTP ─────────────────────────────────────────────
  if (res.status === 401) {
    if (!skipAuthRedirect) {
      // Cookie scaduto o assente → torna al login
      // Salvo l'URL corrente per redirect post-login (verrà letto da Login.jsx)
      const current = window.location.pathname + window.location.search;
      if (current !== '/login') {
        sessionStorage.setItem('postLoginRedirect', current);
      }
      window.location.href = '/login';
    }
    throw new Error('Non autenticato');
  }

  if (res.status === 403) {
    throw new ForbiddenError();
  }

  if (res.status === 429) {
    throw new Error('Troppi tentativi. Riprova tra un minuto.');
  }

  if (!res.ok) {
    // Altri errori: prova a estrarre un messaggio dal body
    let detail = `Errore ${res.status}`;
    try {
      const errBody = await res.json();
      if (errBody?.detail) detail = errBody.detail;
      else if (errBody?.message) detail = errBody.message;
    } catch {
      // body non era JSON, manteniamo messaggio generico
    }
    throw new Error(detail);
  }

  // ── Successo ────────────────────────────────────────────────────────
  if (rawResponse) return res;
  return res.json();
}

// ═════════════════════════════════════════════════════════════════════════
//  AUTH (nuove funzioni)
// ═════════════════════════════════════════════════════════════════════════

export async function login(email, password) {
  // Non vogliamo che apiFetch reindirizzi al login se /login stesso fallisce!
  return apiFetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    body: { email, password },
    skipAuthRedirect: true,
  });
}

export async function logout() {
  return apiFetch(`${API_BASE}/auth/logout`, { method: 'POST' });
}

/**
 * Chiamata al boot dell'app (da AuthContext) per capire se c'è già una sessione
 * attiva. Se 401, NON vogliamo redirect (siamo in fase di scoperta).
 */
export async function getCurrentUser() {
  return apiFetch(`${API_BASE}/auth/me`, { skipAuthRedirect: true });
}

// ═════════════════════════════════════════════════════════════════════════
//  DIPENDENTI / PROGETTI / TASKS / GANTT
// ═════════════════════════════════════════════════════════════════════════

export async function fetchDipendenti() {
  return apiFetch(`${API_BASE}/dipendenti`);
}

export async function fetchDipendente(id) {
  return apiFetch(`${API_BASE}/dipendenti/${id}`);
}

export async function fetchProgetti(stato = null) {
  // stato opzionale: "attivi" (default backend), "bozza", "all", "in esecuzione", ecc.
  const params = new URLSearchParams();
  if (stato) params.set('stato', stato);
  const qs = params.toString();
  return apiFetch(`${API_BASE}/progetti${qs ? `?${qs}` : ''}`);
}

export async function createProgetto(data) {
  // Crea progetto (bozza di default). Body: {nome, cliente?, stato?, ...}.
  return apiFetch(`${API_BASE}/progetti`, { method: 'POST', body: data });
}

export async function updateProgetto(progettoId, data) {
  // Aggiorna campi di un progetto. Body: campi parziali.
  return apiFetch(`${API_BASE}/progetti/${progettoId}`, { method: 'PATCH', body: data });
}

export async function deleteProgetto(progettoId) {
  // Elimina progetto (SOLO se stato='Bozza').
  return apiFetch(`${API_BASE}/progetti/${progettoId}`, { method: 'DELETE' });
}

export async function fetchBilanciamento() {
  return apiFetch(`${API_BASE}/risorse/suggerisci-bilanciamento`);
}

export async function fetchTasks(progettoId = null, profilo = null) {
  const params = new URLSearchParams();
  if (progettoId) params.set('progetto_id', progettoId);
  if (profilo) params.set('profilo', profilo);
  return apiFetch(`${API_BASE}/tasks?${params}`);
}

export async function fetchGantt(progettoId = null) {
  const params = progettoId ? `?progetto_id=${progettoId}` : '';
  return apiFetch(`${API_BASE}/gantt${params}`);
}

export async function fetchGanttStrutturato({ stato = null, progettoId = null } = {}) {
  // Endpoint gerarchico Progetto → Fase → Task per drill-down (Step 2.2).
  // stato: "attivi" (default backend), "all", "bozza", "in esecuzione", "sospeso", ecc.
  // progettoId: drill su un singolo progetto.
  const params = new URLSearchParams();
  if (stato) params.set('stato', stato);
  if (progettoId) params.set('progetto_id', progettoId);
  const qs = params.toString();
  return apiFetch(`${API_BASE}/gantt/strutturato${qs ? `?${qs}` : ''}`);
}

// ═════════════════════════════════════════════════════════════════════════
//  FASI — CRUD (Step 2.4 + D2 cancellazione bloccante se task figli)
// ═════════════════════════════════════════════════════════════════════════

export async function createFase(data) {
  // Body: { progetto_id, nome, ordine, data_inizio?, data_fine?, ore_vendute?, ore_pianificate?, note? }
  return apiFetch(`${API_BASE}/fasi`, { method: 'POST', body: data });
}

export async function updateFase(faseId, data) {
  // Body: campi parziali. Stato validato server-side contro STATI_FASE.
  return apiFetch(`${API_BASE}/fasi/${faseId}`, { method: 'PATCH', body: data });
}

export async function deleteFase(faseId) {
  // HTTP 204 success; 409 se la fase ha task agganciati.
  return apiFetch(`${API_BASE}/fasi/${faseId}`, { method: 'DELETE' });
}

// ═════════════════════════════════════════════════════════════════════════
//  TASK — CRUD singolo (Step 2.4 Cantiere)
// ═════════════════════════════════════════════════════════════════════════

export async function createTask(data) {
  // Body: { progetto_id, nome, fase_id?, fase?, ore_stimate?, data_inizio?, data_fine?,
  //         profilo_richiesto?, dipendente_id?, predecessore?, stato? }
  return apiFetch(`${API_BASE}/tasks`, { method: 'POST', body: data });
}

export async function updateTask(taskId, data) {
  // Body: campi parziali. Le date come stringhe ISO.
  return apiFetch(`${API_BASE}/tasks/${taskId}`, { method: 'PATCH', body: data });
}

export async function deleteTask(taskId) {
  // Soft delete: stato → "Eliminato" (endpoint legacy /elimina).
  return apiFetch(`${API_BASE}/tasks/${taskId}/elimina`, { method: 'PATCH' });
}

export async function fetchCaricoRisorse(settimane = 12) {
  return apiFetch(`${API_BASE}/risorse/carico?settimane=${settimane}`);
}

// ═════════════════════════════════════════════════════════════════════════
//  AGENT / IA
// ═════════════════════════════════════════════════════════════════════════

export async function fetchAgentStatus() {
  return apiFetch(`${API_BASE}/agent/status`);
}

export async function sendChatMessage(data) {
  return apiFetch(`${API_BASE}/agent/chat`, { method: 'POST', body: data });
}

export async function richiediAnalisiGantt(data) {
  return apiFetch(`${API_BASE}/agent/analisi-gantt`, { method: 'POST', body: data });
}

export async function verificaPianificazione(data) {
  return apiFetch(`${API_BASE}/agent/verifica-pianificazione`, { method: 'POST', body: data });
}

export async function suggerisciTask(data) {
  return apiFetch(`${API_BASE}/agent/suggerisci-task`, { method: 'POST', body: data });
}

// ═════════════════════════════════════════════════════════════════════════
//  SIMULAZIONE RITARDI (LEGACY — usato dal vecchio GANTT)
// ═════════════════════════════════════════════════════════════════════════

export async function simulaRitardo(taskId, giorniRitardo) {
  return apiFetch(`${API_BASE}/simulazione/ritardo`, {
    method: 'POST',
    body: { task_id: taskId, giorni_ritardo: giorniRitardo },
  });
}

export async function simulaRitardoMultiplo(ritardi) {
  return apiFetch(`${API_BASE}/simulazione/ritardo-multiplo`, {
    method: 'POST',
    body: { ritardi },
  });
}

// ═════════════════════════════════════════════════════════════════════════
//  SEGNALAZIONI / ANTEPRIMA IMPATTO / APPLICA MODIFICHE
// ═════════════════════════════════════════════════════════════════════════

export async function fetchSegnalazioni() {
  return apiFetch(`${API_BASE}/segnalazioni`);
}

export async function anteprimaImpatto(data) {
  return apiFetch(`${API_BASE}/tasks/anteprima-impatto`, { method: 'POST', body: data });
}

export async function applicaModifiche(data) {
  return apiFetch(`${API_BASE}/tasks/applica`, { method: 'POST', body: data });
}

// ═════════════════════════════════════════════════════════════════════════
//  BOZZE PIANIFICAZIONE — DEPRECATE (Step 2.0, 13 mag 2026)
//
//  Le bozze sono ora progetti con stato='Bozza' (vedi createProgetto sopra).
//  Pipeline.jsx e AnalisiInterventi.jsx mantengono il pulsante "Salva bozza"
//  disabilitato fino a quando non verranno cancellate (Step 2.7).
// ═════════════════════════════════════════════════════════════════════════

export async function salvaBozza(_progettoId, _datiJson) {
  throw new Error(
    "salvaBozza deprecata dal 13 mag 2026 (Step 2.0). " +
    "Le bozze ora sono progetti con stato='Bozza'. " +
    "Usa createProgetto({ stato: 'Bozza', ... })."
  );
}

export async function caricaBozza(_progettoId) {
  throw new Error(
    "caricaBozza deprecata dal 13 mag 2026 (Step 2.0). " +
    "Le bozze ora sono progetti con stato='Bozza'. " +
    "Usa fetchProgetti('bozza') o fetchProgetto(id)."
  );
}

// ═════════════════════════════════════════════════════════════════════════
//  CONSUNTIVI
// ═════════════════════════════════════════════════════════════════════════

export async function salvaConsuntivo(data) {
  return apiFetch(`${API_BASE}/consuntivi/salva`, { method: 'POST', body: data });
}

// ═════════════════════════════════════════════════════════════════════════
//  EXPORT (PDF — caso speciale: blob, non JSON)
// ═════════════════════════════════════════════════════════════════════════

export async function exportGanttPdf(progettoId = null) {
  const params = progettoId ? `?progetto_id=${progettoId}` : '';
  const res = await apiFetch(`${API_BASE}/gantt/export-pdf${params}`, {
    rawResponse: true,
  });
  const blob = await res.blob();
  // Scarica il file
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `gantt_${progettoId || 'tutti'}_${new Date().toISOString().slice(0, 10)}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ═════════════════════════════════════════════════════════════════════════
//  SCENARIO: Tavolo di Lavoro
// ═════════════════════════════════════════════════════════════════════════

export async function interpretaScenario(testo, contesto_extra = '') {
  return apiFetch(`${API_BASE}/agent/interpreta-scenario`, {
    method: 'POST',
    body: { testo, contesto_extra },
  });
}

export async function simulaScenario(modifiche) {
  return apiFetch(`${API_BASE}/scenario/simula`, {
    method: 'POST',
    body: { modifiche },
  });
}

export async function confermaScenario(modifiche) {
  return apiFetch(`${API_BASE}/scenario/conferma`, {
    method: 'POST',
    body: { modifiche },
  });
}