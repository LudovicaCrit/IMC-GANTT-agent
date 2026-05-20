// ═════════════════════════════════════════════════════════════════════════
// AggiungiTaskModal.jsx — Mini-Wizard "Aggiungi task" (staffing progressivo)
//
// Step 2.7 parte 3 (20/05/2026):
//   Apre dalla CTA "Aggiungi task" in Cantiere, per i progetti attivi/sospesi.
//   Permette di aggiungere PIÙ task a fasi ESISTENTI del progetto, in
//   un'unica transazione (principio del dinamismo, handoff §0.3: i task si
//   sviluppano nel tempo, le ore vendute restano quelle delle fasi).
//
// Differenza dallo Step 3 del Wizard di creazione: lì le fasi non esistono
// ancora (si referenziano per indice); qui le fasi sono reali e si
// referenziano per fase_id.
//
// Submit: POST /api/progetti/{id}/task-multipli (endpoint transazionale).
// ═════════════════════════════════════════════════════════════════════════

import React, { useState, useEffect } from 'react'
import { fetchDipendenti, aggiungiTaskMultipli } from '../../api'


export default function AggiungiTaskModal({ progetto, onClose, onTaskAggiunti }) {
  // progetto: oggetto da /gantt/strutturato — ha id, nome, fasi[] (con id reali).
  const [dipendenti, setDipendenti] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [errore, setErrore] = useState(null)

  const fasi = progetto.fasi || []
  console.log('DEBUG modale — progetto:', progetto, '| fasi.length:', fasi.length)

  // Riga task: la fase si sceglie per fase_id reale. Default = prima fase.
  const faseIdDefault = fasi.length > 0 ? fasi[0].id : null
  const [task, setTask] = useState([
    { nome: '', fase_id: faseIdDefault, dipendente_id: '', ore_stimate: 0,
      data_inizio: '', data_fine: '' },
  ])

  useEffect(() => {
    fetchDipendenti().then(d => setDipendenti(d || []))
  }, [])

  function aggiungiRiga() {
    setTask([
      ...task,
      { nome: '', fase_id: faseIdDefault, dipendente_id: '', ore_stimate: 0,
        data_inizio: '', data_fine: '' },
    ])
  }

  function rimuoviRiga(idx) {
    setTask(task.filter((_, i) => i !== idx))
  }

  function aggiornaRiga(idx, campo, valore) {
    const nuovi = [...task]
    nuovi[idx] = { ...nuovi[idx], [campo]: valore }
    setTask(nuovi)
  }

  // Valido: ogni task ha nome non vuoto e una fase selezionata.
  const tuttiValidi = task.length > 0
    && task.every(t => t.nome.trim() !== '' && t.fase_id != null)

  async function handleSubmit() {
    setErrore(null)
    setSubmitting(true)
    try {
      const payload = {
        task: task.map(t => ({
          nome: t.nome.trim(),
          fase_id: t.fase_id,
          dipendente_id: t.dipendente_id || null,
          ore_stimate: Number(t.ore_stimate) || 0,
          data_inizio: t.data_inizio || null,
          data_fine: t.data_fine || null,
          predecessore: null,
        })),
      }
      await aggiungiTaskMultipli(progetto.id, payload)
      await onTaskAggiunti()  // ricarica la lista Cantiere
      onClose()
    } catch (e) {
      setErrore(e.message || "Errore durante l'aggiunta dei task")
      setSubmitting(false)
    }
  }

  // Caso limite: progetto senza fasi → non si possono aggiungere task.
  const senzaFasi = fasi.length === 0

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div className="bg-gray-900 rounded-xl border border-gray-700 max-w-4xl w-full max-h-[90vh] overflow-y-auto">

        {/* Header */}
        <div className="border-b border-gray-800 p-5 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold">
              🔧 Aggiungi task · {progetto.nome}
            </h2>
            <p className="text-xs text-gray-500 mt-1">
              I task si agganciano alle fasi esistenti del progetto. Le ore
              vendute restano quelle delle fasi.
            </p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-200 text-xl">×</button>
        </div>

        {/* Contenuto */}
        <div className="p-5">
          {senzaFasi ? (
            <div className="bg-amber-900/20 border border-amber-800/50 rounded-lg p-4 text-sm text-amber-300">
              Questo progetto non ha fasi. Aggiungi prima almeno una fase
              prima di poter aggiungere task.
            </div>
          ) : (
            <>
              <div className="bg-gray-800/40 border border-gray-700 rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-800/60">
                    <tr>
                      <th className="text-left p-2 text-xs text-gray-400 font-medium uppercase tracking-wide">Nome task</th>
                      <th className="text-left p-2 text-xs text-gray-400 font-medium uppercase tracking-wide w-44">Fase</th>
                      <th className="text-left p-2 text-xs text-gray-400 font-medium uppercase tracking-wide w-44">Dipendente</th>
                      <th className="text-left p-2 text-xs text-gray-400 font-medium uppercase tracking-wide w-24">Ore</th>
                      <th className="text-left p-2 text-xs text-gray-400 font-medium uppercase tracking-wide w-36">Inizio</th>
                      <th className="text-left p-2 text-xs text-gray-400 font-medium uppercase tracking-wide w-36">Fine</th>
                      <th className="w-10"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {task.map((t, idx) => (
                      <tr key={idx} className="border-t border-gray-800">
                        <td className="p-2">
                          <input
                            type="text"
                            value={t.nome}
                            onChange={e => aggiornaRiga(idx, 'nome', e.target.value)}
                            placeholder="Nome task"
                            className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm"
                          />
                        </td>
                        <td className="p-2">
                          <select
                            value={t.fase_id ?? ''}
                            onChange={e => aggiornaRiga(idx, 'fase_id', Number(e.target.value))}
                            className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm"
                          >
                            {fasi.map(f => (
                              <option key={f.id} value={f.id}>
                                {f.nome || `Fase ${f.id}`}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="p-2">
                          <select
                            value={t.dipendente_id}
                            onChange={e => aggiornaRiga(idx, 'dipendente_id', e.target.value)}
                            className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm"
                          >
                            <option value="">—</option>
                            {dipendenti.map(d => (
                              <option key={d.id} value={d.id}>{d.nome}</option>
                            ))}
                          </select>
                        </td>
                        <td className="p-2">
                          <input
                            type="number"
                            value={t.ore_stimate}
                            onChange={e => aggiornaRiga(idx, 'ore_stimate', Number(e.target.value) || 0)}
                            className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm"
                          />
                        </td>
                        <td className="p-2">
                          <input
                            type="date"
                            value={t.data_inizio}
                            onChange={e => aggiornaRiga(idx, 'data_inizio', e.target.value)}
                            className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm"
                          />
                        </td>
                        <td className="p-2">
                          <input
                            type="date"
                            value={t.data_fine}
                            onChange={e => aggiornaRiga(idx, 'data_fine', e.target.value)}
                            className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm"
                          />
                        </td>
                        <td className="p-2 text-center">
                          {task.length > 1 && (
                            <button
                              onClick={() => rimuoviRiga(idx)}
                              className="text-red-400 hover:text-red-300 text-sm"
                              title="Rimuovi questo task"
                            >
                              🗑
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button
                onClick={aggiungiRiga}
                className="mt-3 text-sm text-blue-400 hover:text-blue-300"
              >
                + Aggiungi un altro task
              </button>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-800 p-4">
          {errore && (
            <div className="mb-3 bg-red-900/30 border border-red-700 rounded-lg px-3 py-2 text-sm text-red-300">
              {errore}
            </div>
          )}
          <div className="flex items-center justify-end gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm"
            >
              Annulla
            </button>
            <button
              onClick={handleSubmit}
              disabled={submitting || senzaFasi || !tuttiValidi}
              title={
                tuttiValidi
                  ? 'Aggiungi i task al progetto'
                  : 'Ogni task deve avere un nome e una fase'
              }
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed text-white rounded-lg text-sm font-semibold"
            >
              {submitting ? 'Salvataggio…' : `Aggiungi ${task.length} task`}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
