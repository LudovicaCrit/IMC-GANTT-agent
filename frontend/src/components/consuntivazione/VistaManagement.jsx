/**
 * ═════════════════════════════════════════════════════════════════════════
 * VistaManagement — chi ha compilato, in tutta l'azienda
 * ═════════════════════════════════════════════════════════════════════════
 *
 * ESTRATTA da `pages/Consuntivazione.jsx` il 07/09/2026, quando quella pagina
 * è andata in pensione e la Consuntivazione è diventata una sola, role-aware.
 * Il componente era già autonomo — nessun prop, stato e fetch propri — quindi
 * lo spostamento è stato un taglia-e-incolla; le uniche modifiche sono le tre
 * correzioni qui sotto, che erano difetti noti e non si potevano trasportare.
 *
 * ── LA DOMANDA A CUI RISPONDE ────────────────────────────────────────
 * «Chi ha compilato?» — sintesi e KPI, col dettaglio a richiesta. È diversa
 * dalla domanda della VistaPM («cosa mi stanno dicendo?»), ed è la ragione per
 * cui sono due componenti: con 38 progetti nessuno può leggere ogni
 * segnalazione, e pretenderlo significherebbe non leggerne nessuna.
 *
 * Stesso endpoint della VistaPM: `/api/consuntivi/settimana` decide il
 * perimetro dal RUOLO di chi chiede. Qui arriva l'azienda intera perché a
 * chiamarla è un manager, non perché il componente lo chieda.
 *
 * ── TRE COSE CORRETTE NELLO SPOSTAMENTO ──────────────────────────────
 * 1. `fetch` grezzo → `fetchConsuntiviSettimana` (apiFetch). Il vecchio si
 *    fermava a `r.json()`, e il corpo di un 403 è JSON valido: la promise
 *    andava a buon fine, il `.catch` non vedeva niente, e la pagina crollava
 *    più tardi in render su `consuntivi.filter is not a function`.
 * 2. `.catch(() => {})` → l'errore si MOSTRA. Inghiottiva anche rete caduta e
 *    500, e il sintomo era sempre «nessun dato»: il modo più veloce per
 *    cercare un guasto nel posto sbagliato.
 * 3. Via il filtro `p.id !== 'P010'`. P010 era il contenitore delle attività
 *    interne, ma è stato riusato per un progetto CLIENTE: l'esclusione toglieva
 *    dal conto un progetto vero e lasciava dentro le interne — l'opposto di
 *    quel che voleva fare. Stesso hack stantio rimosso da Attività Interne.
 *
 * E via il banner «🔒 In produzione questa vista richiederà autenticazione»:
 * l'autenticazione c'è (dispatch sul ruolo nell'endpoint) e il toggle non si
 * mostra più a chi non deve. Era il promemoria di un lavoro ormai fatto.
 */

import React, { useState, useEffect } from 'react'
import { fetchConsuntiviSettimana } from '../../api'

export default function VistaManagement() {
  const [consuntivi, setConsuntivi] = useState([])
  const [progetti, setProgetti] = useState([])
  const [segnalazioni, setSegnalazioni] = useState([])
  const [loading, setLoading] = useState(true)
  const [espanso, setEspanso] = useState({})
  const [errore, setErrore] = useState(null)

  useEffect(() => {
    Promise.all([
      fetchConsuntiviSettimana(),
      fetch('/api/progetti').then(r => r.json()),
      fetch('/api/segnalazioni').then(r => r.json()),
    ])
      .then(([c, p, s]) => { setConsuntivi(c || []); setProgetti(p); setSegnalazioni(s || []) })
      .catch((e) => setErrore(e.message || 'Non riesco a caricare i dati'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-gray-400 p-4">Caricamento dati management…</p>
  if (errore) return (
    <div className="text-sm bg-red-900/30 border border-red-800 text-red-200 rounded-lg px-4 py-3">
      {errore}
    </div>
  )

  const compilati = consuntivi.filter(c => c.compilato)
  const nonCompilati = consuntivi.filter(c => !c.compilato)
  const attivi = progetti.filter(p => p.stato === 'In esecuzione')

  const toggleEspanso = (id) => setEspanso(prev => ({ ...prev, [id]: !prev[id] }))

  return (
    <div className="space-y-6">
      {/* KPI rapidi */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <p className="text-xs text-gray-400 uppercase tracking-wider">Compilati</p>
          <p className="text-2xl font-bold mt-1 text-green-400">{compilati.length}<span className="text-sm text-gray-500 font-normal">/{consuntivi.length}</span></p>
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <p className="text-xs text-gray-400 uppercase tracking-wider">Mancanti</p>
          <p className={`text-2xl font-bold mt-1 ${nonCompilati.length > 0 ? 'text-red-400' : 'text-green-400'}`}>{nonCompilati.length}</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <p className="text-xs text-gray-400 uppercase tracking-wider">Progetti attivi</p>
          <p className="text-2xl font-bold mt-1">{attivi.length}</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <p className="text-xs text-gray-400 uppercase tracking-wider">Segnalazioni</p>
          <p className={`text-2xl font-bold mt-1 ${segnalazioni.length > 0 ? 'text-yellow-400' : 'text-green-400'}`}>{segnalazioni.length}</p>
        </div>
      </div>

      {/* ═══ Dettaglio consuntivi per persona ═══ */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <h3 className="font-semibold mb-1">📋 Consuntivi settimanali — dettaglio</h3>
        <p className="text-xs text-gray-500 mb-4">Clicca su un nome per vedere le ore per task.</p>

        {/* Compilati */}
        {compilati.length > 0 && (
          <div className="mb-4">
            <p className="text-xs text-green-400 uppercase tracking-wider font-medium mb-2">✅ Compilato ({compilati.length})</p>
            <div className="space-y-1.5">
              {compilati.map(c => (
                <div key={c.dipendente_id}>
                  <div onClick={() => toggleEspanso(c.dipendente_id)}
                    className="flex items-center justify-between p-3 rounded-lg bg-green-900/10 border border-green-900/20 text-sm cursor-pointer hover:bg-green-900/20 transition-colors">
                    <div className="flex items-center gap-3">
                      <span className="font-medium">{c.nome}</span>
                      <span className="text-xs text-gray-500">{c.profilo}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-mono text-green-400">{c.totale_ore}h/{c.ore_contrattuali}h</span>
                      <span className="text-xs text-gray-500">{espanso[c.dipendente_id] ? '▼' : '▶'}</span>
                    </div>
                  </div>
                  {espanso[c.dipendente_id] && (
                    <div className="ml-4 mt-1 mb-2 p-3 bg-gray-800/50 rounded-lg border-l-2 border-green-700">
                      {c.ore_per_task.map((t, i) => (
                        <div key={i} className="flex justify-between text-sm py-1">
                          <div>
                            <span className="text-gray-300">{t.task_nome}</span>
                            <span className="text-xs text-gray-600 ml-2">({t.progetto})</span>
                          </div>
                          <span className="font-mono text-green-300">{t.ore}h</span>
                        </div>
                      ))}
                      <div className="flex justify-between text-sm pt-2 mt-1 border-t border-gray-700 font-semibold">
                        <span>Totale</span>
                        <span className="font-mono">{c.totale_ore}h</span>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Non compilati */}
        {nonCompilati.length > 0 && (
          <div>
            <p className="text-xs text-red-400 uppercase tracking-wider font-medium mb-2">❌ Mancante ({nonCompilati.length})</p>
            <div className="space-y-1.5">
              {nonCompilati.map(c => (
                <div key={c.dipendente_id}
                  className="flex items-center justify-between p-3 rounded-lg bg-red-900/10 border border-red-900/20 text-sm">
                  <div className="flex items-center gap-3">
                    <span className="font-medium">{c.nome}</span>
                    <span className="text-xs text-gray-500">{c.profilo}</span>
                  </div>
                  <span className="text-xs text-red-400">non compilato</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {consuntivi.length === 0 && (
          <p className="text-sm text-gray-500 text-center py-4">Nessun consuntivo per questa settimana.</p>
        )}
      </div>

      {/* ═══ Budget ore consumato per progetto ═══
          Il titolo diceva «Avanzamento ore»: il numero è
          `ore_consuntivate / budget_ore`, cioè budget SPESO. Il sottotitolo e
          l'etichetta sotto la barra («% del budget consumato») lo dicevano già
          correttamente — mentiva solo l'intestazione, che è la riga che si
          legge per prima e quella che resta in mente. */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <h3 className="font-semibold mb-1">📊 Budget ore consumato per progetto</h3>
        <p className="text-xs text-gray-500 mb-4">Ore consuntivate rispetto al budget stimato.</p>
        <div className="space-y-3">
          {attivi.map(p => {
            const oreConsuntivate = Math.round(p.ore_consuntivate || 0)
            const budgetOre = p.budget_ore || 1
            const pctBudget = Math.round((oreConsuntivate / budgetOre) * 100)
            const barColor = pctBudget > 90 ? 'bg-red-500' : pctBudget > 70 ? 'bg-yellow-500' : 'bg-blue-500'
            return (
              <div key={p.id} className="p-3 rounded-lg bg-gray-800/30">
                <div className="flex justify-between items-center mb-2">
                  <div>
                    <span className="font-medium text-sm">{p.nome}</span>
                    <span className="text-xs text-gray-500 ml-2">{p.cliente}</span>
                  </div>
                  <span className="text-sm font-mono">{oreConsuntivate}h<span className="text-gray-500"> / {budgetOre}h</span></span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-2">
                  <div className={`${barColor} h-2 rounded-full transition-all`} style={{ width: `${Math.min(100, pctBudget)}%` }} />
                </div>
                <p className="text-[10px] text-gray-500 mt-1">{pctBudget}% del budget consumato</p>
              </div>
            )
          })}
        </div>
      </div>

      {/* ═══ Segnalazioni recenti ═══ */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <h3 className="font-semibold mb-1">🚨 Segnalazioni dal sistema</h3>
        <p className="text-xs text-gray-500 mb-4">Segnalazioni automatiche e dai dipendenti tramite consuntivazione.</p>
        {segnalazioni.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-4">Nessuna segnalazione aperta.</p>
        ) : (
          <div className="space-y-2">
            {segnalazioni.map((s, i) => (
              <div key={i} className="p-3 rounded-lg" style={{
                borderLeftWidth: '3px', borderLeftStyle: 'solid',
                borderLeftColor: s.priorita === 'alta' ? '#ef4444' : s.priorita === 'media' ? '#f59e0b' : '#6b7280',
                backgroundColor: s.priorita === 'alta' ? 'rgba(239,68,68,0.08)' : s.priorita === 'media' ? 'rgba(245,158,11,0.08)' : 'rgba(107,114,128,0.08)',
              }}>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${
                    s.priorita === 'alta' ? 'bg-red-700 text-red-100' :
                    s.priorita === 'media' ? 'bg-yellow-700 text-yellow-100' :
                    'bg-gray-600 text-gray-200'
                  }`}>{s.priorita}</span>
                  <span className="text-sm font-medium">{s.dipendente_nome || s.dipendente_id}</span>
                </div>
                <p className="text-sm text-gray-300">{s.dettaglio}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
