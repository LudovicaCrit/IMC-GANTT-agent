import React, { useState, useEffect } from 'react'

const API = '/api/config'

// ═══════════════════════════════════════════════════════════════
//  Hook generico per CRUD
// ═══════════════════════════════════════════════════════════════

function useCrud(endpoint) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  async function reload() {
    setLoading(true)
    try {
      const res = await fetch(`${API}/${endpoint}`)
      const data = await res.json()
      setItems(Array.isArray(data) ? data : [])
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  useEffect(() => { reload() }, [])

  async function create(body) {
    const res = await fetch(`${API}/${endpoint}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Errore'); }
    await reload()
    return res.json()
  }

  async function update(id, body) {
    const res = await fetch(`${API}/${endpoint}/${id}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Errore'); }
    await reload()
  }

  async function remove(id) {
    await fetch(`${API}/${endpoint}/${id}`, { method: 'DELETE' })
    await reload()
  }

  return { items, loading, reload, create, update, remove }
}


// ═══════════════════════════════════════════════════════════════
//  TAB: Ruoli
// ═══════════════════════════════════════════════════════════════

function TabRuoli() {
  const { items, loading, create, remove } = useCrud('ruoli')
  const [nome, setNome] = useState('')
  const [errore, setErrore] = useState('')

  async function aggiungi() {
    if (!nome.trim()) return
    setErrore('')
    try { await create({ nome: nome.trim() }); setNome('') }
    catch (e) { setErrore(e.message) }
  }

  if (loading) return <p className="text-gray-400 text-sm">Caricamento...</p>

  return (
    <div>
      <div className="flex gap-3 mb-4">
        <input value={nome} onChange={e => setNome(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && aggiungi()}
          placeholder="Nome del nuovo ruolo..."
          className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-sm focus:border-blue-500 focus:outline-none" />
        <button onClick={aggiungi}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors">
          + Aggiungi
        </button>
      </div>
      {errore && <p className="text-red-400 text-xs mb-3">{errore}</p>}
      <div className="space-y-1">
        {items.map(r => (
          <div key={r.id} className="flex items-center justify-between bg-gray-800/50 rounded-lg px-4 py-2.5">
            <span className="text-sm">{r.nome}</span>
            <button onClick={() => remove(r.id)}
              className="text-gray-500 hover:text-red-400 text-xs transition-colors">Rimuovi</button>
          </div>
        ))}
        {items.length === 0 && <p className="text-gray-500 text-sm">Nessun ruolo censito.</p>}
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════
//  TAB: Competenze
// ═══════════════════════════════════════════════════════════════

function TabCompetenze() {
  const { items, loading, create, remove } = useCrud('competenze')
  const [nome, setNome] = useState('')
  const [errore, setErrore] = useState('')

  async function aggiungi() {
    if (!nome.trim()) return
    setErrore('')
    try { await create({ nome: nome.trim() }); setNome('') }
    catch (e) { setErrore(e.message) }
  }

  if (loading) return <p className="text-gray-400 text-sm">Caricamento...</p>

  return (
    <div>
      <div className="flex gap-3 mb-4">
        <input value={nome} onChange={e => setNome(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && aggiungi()}
          placeholder="Nome della competenza (es. ARIS, GRC, Python...)"
          className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-sm focus:border-blue-500 focus:outline-none" />
        <button onClick={aggiungi}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors">
          + Aggiungi
        </button>
      </div>
      {errore && <p className="text-red-400 text-xs mb-3">{errore}</p>}
      <div className="flex flex-wrap gap-2">
        {items.map(c => (
          <span key={c.id} className="inline-flex items-center gap-2 bg-gray-800 rounded-lg px-3 py-1.5 text-sm border border-gray-700">
            {c.nome}
            <button onClick={() => remove(c.id)}
              className="text-gray-500 hover:text-red-400 text-xs transition-colors">✕</button>
          </span>
        ))}
        {items.length === 0 && <p className="text-gray-500 text-sm">Nessuna competenza censita.</p>}
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════
//  TAB: Fasi — Lista piatta di nomi fase disponibili
// ═══════════════════════════════════════════════════════════════

function TabFasi() {
  const { items, loading, create, remove } = useCrud('fasi-catalogo')
  const [nome, setNome] = useState('')
  const [errore, setErrore] = useState('')

  async function aggiungi() {
    if (!nome.trim()) return
    setErrore('')
    try { await create({ nome: nome.trim() }); setNome('') }
    catch (e) { setErrore(e.message) }
  }

  if (loading) return <p className="text-gray-400 text-sm">Caricamento...</p>

  return (
    <div>
      <p className="text-sm text-gray-400 mb-4">
        Le fasi qui censite saranno disponibili come opzioni quando crei un nuovo progetto in Pipeline.
      </p>
      <div className="flex gap-3 mb-4">
        <input value={nome} onChange={e => setNome(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && aggiungi()}
          placeholder="Nome della fase (es. Analisi, Design, Implementazione...)"
          className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-sm focus:border-blue-500 focus:outline-none" />
        <button onClick={aggiungi}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors">
          + Aggiungi
        </button>
      </div>
      {errore && <p className="text-red-400 text-xs mb-3">{errore}</p>}
      <div className="space-y-1">
        {items.map(f => (
          <div key={f.id} className="flex items-center justify-between bg-gray-800/50 rounded-lg px-4 py-2.5">
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500 w-6">{f.ordine || '—'}</span>
              <span className="text-sm">{f.nome || f.fase_nome}</span>
            </div>
            <button onClick={() => remove(f.id)}
              className="text-gray-500 hover:text-red-400 text-xs transition-colors">Rimuovi</button>
          </div>
        ))}
        {items.length === 0 && <p className="text-gray-500 text-sm">Nessuna fase censita. Aggiungi le fasi tipiche dei tuoi progetti.</p>}
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════
//  TAB: Dipendenti
// ═══════════════════════════════════════════════════════════════

function TabDipendenti() {
  const { items: dipendenti, loading, create, update, remove } = useCrud('dipendenti')
  const { items: ruoli } = useCrud('ruoli')
  const { items: competenze } = useCrud('competenze')

  const [editId, setEditId] = useState(null)
  const [form, setForm] = useState({ nome: '', profilo: '', ruolo_id: null, ore_sett: 40, costo_ora: null, email: '', competenze: [] })
  const [showNew, setShowNew] = useState(false)

  function startEdit(d) {
    setEditId(d.id)
    setForm({ nome: d.nome, profilo: d.profilo, ruolo_id: d.ruolo_id, ore_sett: d.ore_sett, costo_ora: d.costo_ora, email: d.email, competenze: d.competenze || [] })
  }

  function cancelEdit() {
    setEditId(null); setShowNew(false)
    setForm({ nome: '', profilo: '', ruolo_id: null, ore_sett: 40, costo_ora: null, email: '', competenze: [] })
  }

  async function salva() {
    try {
      if (showNew) { await create(form); setShowNew(false) }
      else { await update(editId, form); setEditId(null) }
      setForm({ nome: '', profilo: '', ruolo_id: null, ore_sett: 40, costo_ora: null, email: '', competenze: [] })
    } catch (e) { alert(e.message) }
  }

  function toggleComp(compNome) {
    setForm(prev => ({
      ...prev,
      competenze: prev.competenze.includes(compNome)
        ? prev.competenze.filter(c => c !== compNome)
        : [...prev.competenze, compNome]
    }))
  }

  if (loading) return <p className="text-gray-400 text-sm">Caricamento...</p>

  const isEditing = editId !== null || showNew

  return (
    <div>
      {!isEditing && (
        <button onClick={() => setShowNew(true)}
          className="mb-4 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors">
          + Nuovo dipendente
        </button>
      )}

      {isEditing && (
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-5 mb-4">
          <h4 className="text-sm font-medium mb-3">{showNew ? 'Nuovo dipendente' : `Modifica ${form.nome}`}</h4>
          <div className="grid grid-cols-3 gap-3 mb-3">
            <div>
              <label className="text-xs text-gray-400">Nome</label>
              <input value={form.nome} onChange={e => setForm({ ...form, nome: e.target.value })}
                className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm mt-1" />
            </div>
            <div>
              <label className="text-xs text-gray-400">Ruolo</label>
              <select value={form.ruolo_id || ''} onChange={e => {
                const rid = e.target.value ? parseInt(e.target.value) : null
                const ruolo = ruoli.find(r => r.id === rid)
                setForm({ ...form, ruolo_id: rid, profilo: ruolo ? ruolo.nome : form.profilo })
              }} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm mt-1">
                <option value="">— Seleziona —</option>
                {ruoli.map(r => <option key={r.id} value={r.id}>{r.nome}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-400">Email</label>
              <input value={form.email} onChange={e => setForm({ ...form, email: e.target.value })}
                className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm mt-1" />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 mb-3">
            <div>
              <label className="text-xs text-gray-400">Ore/settimana</label>
              <input type="number" value={form.ore_sett || ''} onChange={e => setForm({ ...form, ore_sett: e.target.value === '' ? null : parseInt(e.target.value) })}
                className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm mt-1" />
            </div>
            <div>
              <label className="text-xs text-gray-400">Costo orario (€)</label>
              <input type="number" step="0.01" value={form.costo_ora || ''} onChange={e => setForm({ ...form, costo_ora: e.target.value === '' ? null : parseFloat(e.target.value) })}
                className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm mt-1" />
            </div>
          </div>
          <div className="mb-4">
            <label className="text-xs text-gray-400 mb-2 block">Competenze</label>
            <div className="flex flex-wrap gap-2">
              {competenze.map(c => (
                <button key={c.id} onClick={() => toggleComp(c.nome)}
                  className={`px-3 py-1 rounded-lg text-xs border transition-colors ${
                    form.competenze.includes(c.nome)
                      ? 'bg-blue-600 border-blue-500 text-white'
                      : 'bg-gray-900 border-gray-700 text-gray-400 hover:border-gray-500'
                  }`}>
                  {c.nome}
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={salva} className="px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg text-sm font-medium transition-colors">Salva</button>
            <button onClick={cancelEdit} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors">Annulla</button>
          </div>
        </div>
      )}

      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-800 text-gray-400">
            <tr>
              <th className="text-left px-4 py-2">Nome</th>
              <th className="text-left px-4 py-2">Ruolo</th>
              <th className="text-right px-4 py-2">Ore/sett</th>
              <th className="text-right px-4 py-2">€/h</th>
              <th className="text-left px-4 py-2">Competenze</th>
              <th className="text-center px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {dipendenti.map(d => (
              <tr key={d.id} className="border-t border-gray-800 hover:bg-gray-800/30">
                <td className="px-4 py-2.5 font-medium">{d.nome}</td>
                <td className="px-4 py-2.5 text-gray-400">{d.profilo}</td>
                <td className="px-4 py-2.5 text-right">{d.ore_sett}h</td>
                <td className="px-4 py-2.5 text-right">{d.costo_ora ? `€${d.costo_ora.toFixed(2)}` : '—'}</td>
                <td className="px-4 py-2.5">
                  <div className="flex flex-wrap gap-1">
                    {(d.competenze || []).slice(0, 4).map((c, i) => (
                      <span key={i} className="text-[10px] bg-gray-800 rounded px-1.5 py-0.5 text-gray-400">{c}</span>
                    ))}
                    {(d.competenze || []).length > 4 && (
                      <span className="text-[10px] text-gray-500">+{d.competenze.length - 4}</span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-2.5 text-center">
                  <div className="flex gap-2 justify-center">
                    <button onClick={() => startEdit(d)} className="text-gray-500 hover:text-blue-400 text-xs transition-colors">Modifica</button>
                    <button onClick={() => { if (confirm(`Eliminare ${d.nome}?`)) remove(d.id) }}
                      className="text-gray-500 hover:text-red-400 text-xs transition-colors">Elimina</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════
//  PAGINA PRINCIPALE — CONFIGURAZIONE
// ═══════════════════════════════════════════════════════════════

export default function Configurazione() {
  const [tab, setTab] = useState('dipendenti')

  const tabs = [
    { id: 'dipendenti', label: 'Dipendenti', icon: '👥' },
    { id: 'ruoli', label: 'Ruoli', icon: '🏷️' },
    { id: 'competenze', label: 'Competenze', icon: '🎯' },
    { id: 'fasi', label: 'Fasi', icon: '📐' },
  ]

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">⚙️ Configurazione</h1>
      <p className="text-sm text-gray-400 mb-6">
        Gestisci anagrafica dipendenti, ruoli, competenze e fasi. I dati qui inseriti alimentano Pipeline, Tavolo di Lavoro e Consuntivazione.
      </p>

      <div className="flex gap-2 mb-6">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              tab === t.id ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
            }`}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {tab === 'dipendenti' && <TabDipendenti />}
      {tab === 'ruoli' && <TabRuoli />}
      {tab === 'competenze' && <TabCompetenze />}
      {tab === 'fasi' && <TabFasi />}
    </div>
  )
}
