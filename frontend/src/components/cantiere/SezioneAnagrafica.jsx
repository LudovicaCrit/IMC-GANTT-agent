/**
 * ═════════════════════════════════════════════════════════════════════════
 * SezioneAnagrafica.jsx — Box anagrafica del progetto (tab Design Cantiere)
 * ═════════════════════════════════════════════════════════════════════════
 *
 * Estratto da CantiereDettaglio.jsx (Step 2.3-bis 4a, 18 mag 2026).
 *
 * Due modalità:
 *   - readonly=false (default in Cantiere): mostra anagrafica con bottoni
 *     "✏ Modifica" e (se progetto in Bozza) "🗑 Elimina bozza". Click su
 *     Modifica → form editabile inline con Salva/Annulla.
 *   - readonly=true (per GANTT accordion 4c, Archivio): mostra solo i
 *     valori senza bottoni. Niente form, niente edit.
 *
 * Props:
 *   - progetto: oggetto con id, tipologia, nome, cliente, data_inizio,
 *               data_fine, budget_ore, pm_id, stato
 *   - onSalva: callback async (dati) per salvare modifiche (solo non-readonly)
 *   - onEliminaBozza: callback async per il bottone elimina (solo non-readonly
 *                     e solo se progetto.stato === 'Bozza')
 *   - readonly: default false. Se true, nasconde tutti i bottoni e l'edit form.
 */

import React, { useState } from 'react'
import { FormRow, FormInput } from '../_shared/Form'

export default function SezioneAnagrafica({ progetto, onSalva, onEliminaBozza, readonly = false }) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({
    nome: progetto.nome || '',
    cliente: progetto.cliente || '',
    data_inizio: progetto.data_inizio || '',
    data_fine: progetto.data_fine || '',
    budget_ore: progetto.budget_ore || 0,
  })
  const [salvando, setSalvando] = useState(false)
  const [errore, setErrore] = useState(null)

  const handleSalva = async () => {
    setSalvando(true); setErrore(null)
    try {
      await onSalva({
        nome: form.nome,
        cliente: form.cliente,
        data_inizio: form.data_inizio || null,
        data_fine: form.data_fine || null,
        budget_ore: Number(form.budget_ore) || 0,
      })
      setEditing(false)
    } catch (e) {
      setErrore(e.message || 'Errore nel salvataggio')
    } finally { setSalvando(false) }
  }

  const handleAnnulla = () => {
    setForm({
      nome: progetto.nome || '',
      cliente: progetto.cliente || '',
      data_inizio: progetto.data_inizio || '',
      data_fine: progetto.data_fine || '',
      budget_ore: progetto.budget_ore || 0,
    })
    setEditing(false); setErrore(null)
  }

  return (
    <section className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">📋 Anagrafica</h2>
        {!readonly && (
          <div className="flex gap-2">
            {!editing && (
              <button onClick={() => setEditing(true)}
                className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-sm">
                ✏ Modifica
              </button>
            )}
            {progetto.stato === 'Bozza' && !editing && (
              <button onClick={onEliminaBozza}
                className="px-3 py-1.5 bg-red-900/60 hover:bg-red-900 rounded text-sm">
                🗑 Elimina bozza
              </button>
            )}
          </div>
        )}
      </div>

      {(!editing || readonly) ? (
        <div className="grid grid-cols-2 gap-x-8 gap-y-3 text-sm">
          <FormRow label="ID">{progetto.id}</FormRow>
          <FormRow label="Tipologia">{progetto.tipologia}</FormRow>
          <FormRow label="Nome">{progetto.nome}</FormRow>
          <FormRow label="Cliente">{progetto.cliente || <span className="text-gray-600 italic">—</span>}</FormRow>
          <FormRow label="Data inizio">{progetto.data_inizio || <span className="text-gray-600 italic">—</span>}</FormRow>
          <FormRow label="Data fine">{progetto.data_fine || <span className="text-gray-600 italic">—</span>}</FormRow>
          <FormRow label="Budget ore">{progetto.budget_ore || 0}h</FormRow>
          <FormRow label="PM">{progetto.pm_id || <span className="text-gray-600 italic">—</span>}</FormRow>
        </div>
      ) : (
        <div className="space-y-3">
          <FormInput label="Nome" value={form.nome} onChange={v => setForm({...form, nome: v})} required />
          <FormInput label="Cliente" value={form.cliente} onChange={v => setForm({...form, cliente: v})} />
          <div className="grid grid-cols-2 gap-4">
            <FormInput label="Data inizio" type="date" value={form.data_inizio} onChange={v => setForm({...form, data_inizio: v})} />
            <FormInput label="Data fine" type="date" value={form.data_fine} onChange={v => setForm({...form, data_fine: v})} />
          </div>
          <FormInput label="Budget ore" type="number" value={form.budget_ore} onChange={v => setForm({...form, budget_ore: v})} />
          {errore && <p className="text-sm text-red-400">{errore}</p>}
          <div className="flex gap-2 pt-2">
            <button onClick={handleSalva} disabled={salvando}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm font-semibold disabled:bg-gray-700">
              {salvando ? 'Salvataggio…' : '💾 Salva'}
            </button>
            <button onClick={handleAnnulla} disabled={salvando}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm">
              Annulla
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
