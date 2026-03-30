const API_BASE = '/api';

export async function fetchDipendenti() {
  const res = await fetch(`${API_BASE}/dipendenti`);
  return res.json();
}

export async function fetchDipendente(id) {
  const res = await fetch(`${API_BASE}/dipendenti/${id}`);
  return res.json();
}

export async function fetchProgetti() {
  const res = await fetch(`${API_BASE}/progetti`);
  return res.json();
}

export async function fetchTasks(progettoId = null, profilo = null) {
  const params = new URLSearchParams();
  if (progettoId) params.set('progetto_id', progettoId);
  if (profilo) params.set('profilo', profilo);
  const res = await fetch(`${API_BASE}/tasks?${params}`);
  return res.json();
}

export async function fetchGantt(progettoId = null) {
  const params = progettoId ? `?progetto_id=${progettoId}` : '';
  const res = await fetch(`${API_BASE}/gantt${params}`);
  return res.json();
}

export async function fetchCaricoRisorse(settimane = 12) {
  const res = await fetch(`${API_BASE}/risorse/carico?settimane=${settimane}`);
  return res.json();
}

export async function fetchAgentStatus() {
  const res = await fetch(`${API_BASE}/agent/status`);
  return res.json();
}

export async function sendChatMessage(data) {
  const res = await fetch(`${API_BASE}/agent/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function simulaRitardo(taskId, giorniRitardo) {
  const res = await fetch(`${API_BASE}/simulazione/ritardo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_id: taskId, giorni_ritardo: giorniRitardo }),
  });
  return res.json();
}

export async function simulaRitardoMultiplo(ritardi) {
  const res = await fetch(`${API_BASE}/simulazione/ritardo-multiplo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ritardi }),
  });
  return res.json();
}

export async function richiediAnalisiGantt(data) {
  const res = await fetch(`${API_BASE}/agent/analisi-gantt`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function fetchSegnalazioni() {
  const res = await fetch(`${API_BASE}/segnalazioni`);
  return res.json();
}

// ── Anteprima impatto e applicazione modifiche ──

export async function anteprimaImpatto(data) {
  const res = await fetch(`${API_BASE}/task/anteprima-impatto`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function applicaModifiche(data) {
  const res = await fetch(`${API_BASE}/task/applica`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

// ── Bozze pianificazione ──

export async function salvaBozza(progettoId, datiJson) {
  const res = await fetch(`${API_BASE}/pianificazione/salva-bozza`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ progetto_id: progettoId, dati_json: datiJson }),
  });
  return res.json();
}

export async function caricaBozza(progettoId) {
  const res = await fetch(`${API_BASE}/pianificazione/bozza/${progettoId}`);
  return res.json();
}

// ── Salva consuntivo ──

export async function salvaConsuntivo(data) {

  const res = await fetch(`${API_BASE}/consuntivi/salva`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

// ── Export GANTT PDF ──

export async function exportGanttPdf(progettoId = null) {
  const params = progettoId ? `?progetto_id=${progettoId}` : '';
  const res = await fetch(`${API_BASE}/gantt/export-pdf${params}`);
  if (!res.ok) throw new Error('Errore nella generazione PDF');
  const blob = await res.blob();
  // Scarica il file
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `gantt_${progettoId || 'tutti'}_${new Date().toISOString().slice(0,10)}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── IA verifica pianificazione ──

export async function verificaPianificazione(data) {
  const res = await fetch(`${API_BASE}/agent/verifica-pianificazione`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

// ── IA suggerisci task ──

export async function suggerisciTask(data) {
  const res = await fetch(`${API_BASE}/agent/suggerisci-task`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}