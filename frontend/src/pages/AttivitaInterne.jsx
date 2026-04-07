import React, { useState, useEffect } from 'react'
import { fetchDipendenti, fetchTasks } from '../api'

const CATEGORIE = [
  'Formazione',
  'Amministrazione',
  'Coordinamento',
  'HR e recruiting',
  'Strategia e relazioni',
  'Vendita e networking',
  'Altro',
]

export default function AttivitaInterne() {
  const [dipendenti, setDipendenti] = useState([])
  const [attivita, setAttivita] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState(null)

  // Form fields
  const [formDip, setFormDip] = useState([])
  const [formNome, setFormNome] = useState('')
  const [formCategoria, setFormCategoria] = useState('Formazione')
  const [formOreSett, setFormOreSett] = useState(4)
  const [formInizio, setFormInizio] = useState('')
  const [formFine, setFormFine] = useState('')
  const [formNote, setFormNote] = useState('')

  const caricaDati = () => {
    setLoading(true)
    Promise.all([fetchDipendenti(), fetchTasks('P010')])
      .then(([d, t]) => {
        setDipendenti(d)
        setAttivita(t)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { caricaDati() }, [])

  const resetForm = () => {
    setFormDip([])
    setFormNome('')
    setFormCategoria('Formazione')
    setFormOreSett(4)
    setFormInizio('')
    setFormFine('')
    setFormNote('')
    setShowForm(false)
  }

  const handleSalva = async () => {
    if (formDip.length === 0 || !formNome || !formInizio || !formFine) {
      setFeedback({ tipo: 'errore', msg: 'Compila tutti i campi obbligatori (almeno una persona).' })
      return
    }

    const inizio = new Date(formInizio)
    const fine = new Date(formFine)
    if (fine <= inizio) {
      setFeedback({ tipo: 'errore', msg: 'La data di fine deve essere dopo la data di inizio.' })
      return
    }

    const settimane = Math.max(1, Math.round((fine - inizio) / (7 * 86400000)))
    const oreTotali = formOreSett * settimane

    setSaving(true)
    try {
      // Chiamate sequenziali per evitare conflitti ID nel backend
      for (const dipId of formDip) {
        const res = await fetch('/api/attivita-interne', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            dipendente_id: dipId,
            nome: formNome,
            categoria: formCategoria,
            ore_settimanali: formOreSett,
            ore_stimate: oreTotali,
            data_inizio: formInizio,
            data_fine: formFine,
            note: formNote,
          }),
        })
        if (!res.ok) throw new Error(`Errore per ${dipId}`)
      }
      const nomi = formDip.map(id => dipendenti.find(d => d.id === id)?.nome || id)
      setFeedback({ tipo: 'ok', msg: `Attività "${formNome}" aggiunta per ${nomi.join(', ')}.` })
      resetForm()
      caricaDati()
    } catch (err) {
      setFeedback({ tipo: 'errore', msg: 'Errore nel salvataggio: ' + err.message })
    } finally {
      setSaving(false)
    }
  }

  const handleElimina = async (taskId, taskNome) => {
    if (!confirm(`Eliminare "${taskNome}"?`)) return
    try {
      const res = await fetch(`/api/attivita-interne/${taskId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Errore')
      setFeedback({ tipo: 'ok', msg: `"${taskNome}" eliminata.` })
      caricaDati()
    } catch (err) {
      setFeedback({ tipo: 'errore', msg: 'Errore nell\'eliminazione.' })
    }
  }

  if (loading) return <p className="text-gray-400">Caricamento...</p>

  // Raggruppa attività per persona
  const perPersona = {}
  attivita.forEach(a => {
    if (!perPersona[a.dipendente_id]) perPersona[a.dipendente_id] = []
    perPersona[a.dipendente_id].push(a)
  })

  // Calcola ore settimanali stimate per ogni attività
  const calcolaOreSett = (a) => {
    const inizio = new Date(a.data_inizio)
    const fine = new Date(a.data_fine)
    const settimane = Math.max(1, Math.round((fine - inizio) / (7 * 86400000)))
    return (a.ore_stimate / settimane).toFixed(1)
  }

  return (
    <div>
      <div className="flex justify-between items-start mb-6">
        <div>
          <h1 className="text-2xl font-bold">🏢 Attività Interne</h1>
          <p className="text-gray-400 mt-1">Attività non a progetto: formazione, amministrazione, coordinamento, HR.</p>
          <p className="text-xs text-gray-500 mt-1">Queste attività completano il quadro settimanale di ogni persona e sono registrabili tramite consuntivazione.</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors"
        >
          {showForm ? '✕ Chiudi' : '+ Nuova attività'}
        </button>
      </div>

      {/* Feedback */}
      {feedback && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${feedback.tipo === 'ok' ? 'bg-green-900/20 border border-green-700 text-green-300' : 'bg-red-900/20 border border-red-700 text-red-300'}`}>
          {feedback.msg}
          <button onClick={() => setFeedback(null)} className="ml-3 text-xs underline">chiudi</button>
        </div>
      )}

      {/* Form nuova attività */}
      {showForm && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5 mb-6">
          <h3 className="font-semibold mb-4">Nuova attività interna</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs text-gray-400 mb-2">Persone * <span className="text-gray-600">(seleziona una o più)</span></label>
              <div className="grid grid-cols-3 gap-1.5 max-h-48 overflow-y-auto bg-gray-800 border border-gray-700 rounded-lg p-3">
                <button type="button" onClick={() => {
                  if (formDip.length === dipendenti.length) setFormDip([])
                  else setFormDip(dipendenti.map(d => d.id))
                }} className="col-span-3 text-xs text-blue-400 hover:text-blue-300 text-left mb-1">
                  {formDip.length === dipendenti.length ? '☐ Deseleziona tutti' : '☑ Seleziona tutti'}
                </button>
                {dipendenti.map(d => {
                  const checked = formDip.includes(d.id)
                  return (
                    <label key={d.id} className={`flex items-center gap-2 p-1.5 rounded cursor-pointer text-sm transition-colors ${checked ? 'bg-blue-900/30' : 'hover:bg-gray-700/50'}`}>
                      <input type="checkbox" checked={checked}
                        onChange={() => {
                          if (checked) setFormDip(formDip.filter(id => id !== d.id))
                          else setFormDip([...formDip, d.id])
                        }}
                        className="rounded border-gray-600" />
                      <span className={checked ? 'text-white' : 'text-gray-400'}>{d.nome}</span>
                      <span className="text-[10px] text-gray-600">{d.profilo}</span>
                    </label>
                  )
                })}
              </div>
              {formDip.length > 0 && <p className="text-xs text-blue-400 mt-1">{formDip.length} persone selezionate</p>}
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Nome attività *</label>
              <input type="text" value={formNome} onChange={e => setFormNome(e.target.value)}
                placeholder="es. Corso inglese B2, Gestione presenze..."
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Categoria</label>
              <select value={formCategoria} onChange={e => setFormCategoria(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm">
                {CATEGORIE.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Ore settimanali stimate</label>
              <input type="number" min="1" max="40" value={formOreSett} onChange={e => setFormOreSett(parseInt(e.target.value) || 1)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Data inizio *</label>
              <input type="date" value={formInizio} onChange={e => setFormInizio(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Data fine *</label>
              <input type="date" value={formFine} onChange={e => setFormFine(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-400 mb-1">Note (opzionale)</label>
              <input type="text" value={formNote} onChange={e => setFormNote(e.target.value)}
                placeholder="es. Certificazione obbligatoria, provider XYZ..."
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm" />
            </div>
          </div>
          <div className="flex gap-3 mt-4">
            <button onClick={handleSalva} disabled={saving}
              className="px-5 py-2 bg-green-600 hover:bg-green-500 disabled:bg-gray-600 rounded-lg text-sm font-medium transition-colors">
              {saving ? 'Salvataggio...' : '✅ Salva attività'}
            </button>
            <button onClick={resetForm}
              className="px-5 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors">
              Annulla
            </button>
          </div>
          {formDip.length > 0 && formOreSett && formInizio && formFine && (
            <p className="text-xs text-gray-500 mt-3">
              Ore totali stimate: {formOreSett * Math.max(1, Math.round((new Date(formFine) - new Date(formInizio)) / (7 * 86400000)))}h
              su {Math.max(1, Math.round((new Date(formFine) - new Date(formInizio)) / (7 * 86400000)))} settimane
            </p>
          )}
        </div>
      )}

      {/* Tabella attività raggruppate per persona */}
      <div className="space-y-4">
        {dipendenti
          .filter(d => perPersona[d.id] && perPersona[d.id].length > 0)
          .sort((a, b) => a.nome.localeCompare(b.nome))
          .map(d => {
            const tasks = perPersona[d.id]
            const totOreSett = tasks.reduce((s, a) => s + parseFloat(calcolaOreSett(a)), 0)
            return (
              <div key={d.id} className="bg-gray-900 rounded-xl border border-gray-800 p-4">
                <div className="flex justify-between items-center mb-3">
                  <div>
                    <span className="font-semibold">{d.nome}</span>
                    <span className="text-xs text-gray-500 ml-2">{d.profilo} · {d.ore_sett}h/sett</span>
                  </div>
                  <span className="text-sm font-mono text-blue-400">~{totOreSett.toFixed(0)}h/sett interne</span>
                </div>
                <div className="space-y-1.5">
                  {tasks.map(a => (
                    <div key={a.id} className="flex items-center justify-between p-2.5 rounded-lg bg-gray-800/50 text-sm">
                      <div className="flex-1 min-w-0">
                        <span className="font-medium">{a.nome}</span>
                        <span className="text-xs text-gray-500 ml-2">{a.fase}</span>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="text-xs text-gray-400">
                          {new Date(a.data_inizio).toLocaleDateString('it-IT', { month: 'short', year: '2-digit' })} → {new Date(a.data_fine).toLocaleDateString('it-IT', { month: 'short', year: '2-digit' })}
                        </span>
                        <span className="text-xs font-mono w-16 text-right text-blue-300">~{calcolaOreSett(a)}h/sett</span>
                        <button onClick={() => handleElimina(a.id, a.nome)}
                          className="text-xs text-red-500 hover:text-red-400 transition-colors px-2">✕</button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
      </div>

      {/* Persone senza attività interne */}
      {dipendenti.filter(d => !perPersona[d.id] || perPersona[d.id].length === 0).length > 0 && (
        <div className="mt-6 bg-gray-900 rounded-xl border border-gray-800 p-4">
          <h3 className="font-semibold mb-3 text-sm">Senza attività interne assegnate</h3>
          <div className="flex flex-wrap gap-2">
            {dipendenti
              .filter(d => !perPersona[d.id] || perPersona[d.id].length === 0)
              .map(d => (
                <button key={d.id} onClick={() => { setFormDip([d.id]); setShowForm(true) }}
                  className="text-xs px-3 py-1.5 rounded-lg border border-yellow-700 bg-yellow-900/20 text-yellow-300 hover:bg-yellow-900/40 transition-colors cursor-pointer">
                  + {d.nome}
                </button>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}
