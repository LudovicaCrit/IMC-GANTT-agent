import React, { useState, useEffect } from 'react'
import { fetchDipendenti, fetchGantt, richiediAnalisiGantt } from '../api'

const PRIORITA_COLORS = {
  alta:  'bg-red-900/30 border-red-700 text-red-300',
  media: 'bg-yellow-900/30 border-yellow-700 text-yellow-300',
  bassa: 'bg-gray-800 border-gray-700 text-gray-300',
}

const FATTIBILITA_BADGE = {
  alta:  'bg-green-600 text-white',
  media: 'bg-yellow-600 text-white',
  bassa: 'bg-red-600 text-white',
}

/* ── Mini GANTT for preview ───────────────────────────────────────── */
function MiniGantt({ tasks }) {
  if (!tasks || tasks.length === 0) return null
  const starts = tasks.map(t => new Date(t.start || t.data_inizio).getTime())
  const ends = tasks.map(t => new Date(t.end || t.data_fine).getTime())
  const min = Math.min(...starts)
  const max = Math.max(...ends)
  const range = max - min || 1

  const STATUS_COLORS = { 'Completato': '#22c55e', 'In corso': '#3b82f6', 'Da iniziare': '#6b7280', 'Sospeso': '#4b5563' }

  return (
    <div className="bg-gray-800 rounded-lg p-3 space-y-1">
      {tasks.slice(0, 15).map((t, i) => {
        const s = ((new Date(t.start || t.data_inizio).getTime() - min) / range) * 100
        const e = ((new Date(t.end || t.data_fine).getTime() - min) / range) * 100
        const w = Math.max(1, e - s)
        return (
          <div key={i} className="flex items-center h-5">
            <span className="text-[10px] text-gray-400 w-32 truncate flex-shrink-0">{t.name || t.nome}</span>
            <div className="flex-1 relative h-3">
              <div className="absolute h-3 rounded-sm" style={{
                left: `${s}%`, width: `${w}%`,
                backgroundColor: STATUS_COLORS[t.status || t.stato] || '#6b7280',
                opacity: 0.8, minWidth: '3px'
              }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

/* ── Main page ────────────────────────────────────────────────────── */
export default function CentroSegnalazioni() {
  const [dipendenti, setDipendenti] = useState([])
  const [loading, setLoading] = useState(false)
  const [analisiResult, setAnalisiResult] = useState(null)
  const [ganttPreview, setGanttPreview] = useState([])

  // Segnalazione manuale (in produzione arriverebbe dal chatbot)
  const [segnTipo, setSegnTipo] = useState('sovraccarico')
  const [segnDip, setSegnDip] = useState('')
  const [segnDettaglio, setSegnDettaglio] = useState('')
  const [segnPriorita, setSegnPriorita] = useState('alta')

  // Segnalazioni simulate (in produzione arriverebbero dal backend)
  const [segnalazioni] = useState([
    {
      id: 'S001', tipo: 'sovraccarico', priorita: 'alta',
      dipendente_id: 'D005', dipendente: 'Alessandro Conte',
      dettaglio: 'Saturazione al 133%, 5 progetti attivi. Non riesce a lavorare sulla proposta tecnica Allerta.',
      timestamp: '2026-03-09 10:30',
    },
    {
      id: 'S002', tipo: 'richiesta_supporto', priorita: 'alta',
      dipendente_id: 'D001', dipendente: 'Marco Bianchi',
      dettaglio: 'Richiede supporto tecnico junior per Design architettura HL7 FHIR.',
      timestamp: '2026-03-09 11:15',
    },
    {
      id: 'S003', tipo: 'sovraccarico', priorita: 'media',
      dipendente_id: 'D007', dipendente: 'Roberto Esposito',
      dettaglio: 'Saturazione al 106%, gestisce 3 backend contemporaneamente.',
      timestamp: '2026-03-08 16:45',
    },
  ])

  const [selectedSegn, setSelectedSegn] = useState(null)

  useEffect(() => {
    fetchDipendenti().then(setDipendenti)
  }, [])

  const handleAnalizza = async (segn) => {
    setSelectedSegn(segn)
    setLoading(true)
    setAnalisiResult(null)

    try {
      const result = await richiediAnalisiGantt({
        segnalazione_tipo: segn.tipo,
        segnalazione_dettaglio: segn.dettaglio,
        dipendente_id: segn.dipendente_id,
        priorita: segn.priorita,
      })
      setAnalisiResult(result)

      // Fetch GANTT per preview
      const gantt = await fetchGantt()
      setGanttPreview(gantt)
    } catch (err) {
      setAnalisiResult({ error: err.message })
    } finally {
      setLoading(false)
    }
  }

  const handleAnalizzaManuale = async () => {
    if (!segnDip || !segnDettaglio) return
    const dip = dipendenti.find(d => d.id === segnDip)
    await handleAnalizza({
      id: 'manual',
      tipo: segnTipo,
      priorita: segnPriorita,
      dipendente_id: segnDip,
      dipendente: dip?.nome || '',
      dettaglio: segnDettaglio,
      timestamp: 'Ora',
    })
  }

  const proposte = analisiResult?.proposte

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">🧠 Centro Segnalazioni</h1>
      <p className="text-sm text-yellow-400 mb-6">🔒 Riservato al management — L'agente analizza e propone, tu decidi.</p>

      <div className="grid grid-cols-5 gap-6">
        {/* ── Colonna sinistra: segnalazioni ── */}
        <div className="col-span-2">
          <h2 className="text-lg font-semibold mb-3">📥 Segnalazioni in arrivo</h2>

          <div className="space-y-2 mb-6">
            {segnalazioni.map(s => (
              <div key={s.id}
                onClick={() => handleAnalizza(s)}
                className={`p-4 rounded-xl border cursor-pointer transition-all ${
                  selectedSegn?.id === s.id ? 'ring-2 ring-blue-500' : ''
                } ${PRIORITA_COLORS[s.priorita]}`}
              >
                <div className="flex justify-between items-start mb-1">
                  <span className="text-xs font-medium uppercase">{s.tipo.replace('_', ' ')}</span>
                  <span className="text-xs opacity-70">{s.timestamp}</span>
                </div>
                <p className="font-medium text-sm">{s.dipendente}</p>
                <p className="text-xs mt-1 opacity-80">{s.dettaglio}</p>
              </div>
            ))}
          </div>

          {/* Segnalazione manuale */}
          <details className="mb-4">
            <summary className="cursor-pointer text-sm text-gray-400 hover:text-white">➕ Inserisci segnalazione manuale</summary>
            <div className="mt-3 bg-gray-900 rounded-xl border border-gray-800 p-4 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <select value={segnTipo} onChange={e => setSegnTipo(e.target.value)}
                  className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm">
                  <option value="sovraccarico">Sovraccarico</option>
                  <option value="richiesta_supporto">Richiesta supporto</option>
                  <option value="blocco_task">Task bloccato</option>
                </select>
                <select value={segnPriorita} onChange={e => setSegnPriorita(e.target.value)}
                  className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm">
                  <option value="alta">Priorità alta</option>
                  <option value="media">Priorità media</option>
                  <option value="bassa">Priorità bassa</option>
                </select>
              </div>
              <select value={segnDip} onChange={e => setSegnDip(e.target.value)}
                className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm">
                <option value="">Seleziona dipendente...</option>
                {dipendenti.map(d => <option key={d.id} value={d.id}>{d.nome} ({d.saturazione_pct}%)</option>)}
              </select>
              <textarea value={segnDettaglio} onChange={e => setSegnDettaglio(e.target.value)}
                placeholder="Descrivi la segnalazione..."
                className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm h-20 placeholder-gray-500" />
              <button onClick={handleAnalizzaManuale}
                disabled={!segnDip || !segnDettaglio}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 rounded-lg text-sm font-medium">
                🧠 Analizza
              </button>
            </div>
          </details>
        </div>

        {/* ── Colonna destra: analisi agente ── */}
        <div className="col-span-3">
          {!selectedSegn && !loading && (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-12 text-center text-gray-400">
              <p className="text-lg mb-2">Seleziona una segnalazione</p>
              <p className="text-sm">L'agente analizzerà la situazione e proporrà opzioni di redistribuzione.</p>
            </div>
          )}

          {loading && (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-12 text-center">
              <p className="text-lg text-blue-400 animate-pulse">🧠 L'agente sta analizzando...</p>
              <p className="text-sm text-gray-400 mt-2">Valuto carichi, disponibilità e dipendenze.</p>
            </div>
          )}

          {analisiResult && !loading && (
            <div className="space-y-4">
              {/* Errore */}
              {analisiResult.error && (
                <div className="bg-red-900/20 border border-red-800 rounded-xl p-4 text-red-300">
                  ⚠️ {analisiResult.error}
                </div>
              )}

              {/* Parse error — mostra raw */}
              {proposte?.parse_error && (
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
                  <p className="text-yellow-400 text-sm mb-2">⚠️ Risposta non strutturata dall'agente:</p>
                  <pre className="text-xs text-gray-300 whitespace-pre-wrap">{proposte.raw_response}</pre>
                </div>
              )}

              {/* Analisi strutturata */}
              {proposte && !proposte.parse_error && !analisiResult.error && (
                <>
                  {/* Analisi */}
                  <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
                    <h3 className="font-semibold mb-2">📊 Analisi della situazione</h3>
                    <p className="text-sm text-gray-300">{proposte.analisi}</p>
                    {proposte.urgenza && (
                      <span className={`inline-block mt-2 px-3 py-1 rounded-full text-xs font-medium ${
                        proposte.urgenza === 'alta' ? 'bg-red-600' : proposte.urgenza === 'media' ? 'bg-yellow-600' : 'bg-gray-600'
                      } text-white`}>
                        Urgenza: {proposte.urgenza}
                      </span>
                    )}
                  </div>

                  {/* Proposte */}
                  {proposte.proposte?.map((p, i) => (
                    <div key={i} className="bg-gray-900 rounded-xl border border-gray-800 p-5">
                      <div className="flex justify-between items-start mb-3">
                        <h3 className="font-semibold">
                          Opzione {p.id}: {p.titolo}
                        </h3>
                        {p.impatto?.fattibilita && (
                          <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                            FATTIBILITA_BADGE[p.impatto.fattibilita] || 'bg-gray-600 text-white'
                          }`}>
                            Fattibilità: {p.impatto.fattibilita}
                          </span>
                        )}
                      </div>

                      {/* Azioni */}
                      <div className="space-y-2 mb-3">
                        {p.azioni?.map((a, j) => (
                          <div key={j} className="bg-gray-800 rounded-lg p-3 text-sm">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-xs font-medium uppercase text-blue-400">{a.tipo?.replace('_', ' ')}</span>
                              <span className="font-medium">{a.task_nome}</span>
                            </div>
                            {a.da_dipendente && <p className="text-gray-400">Da: {a.da_dipendente} → A: {a.a_dipendente}</p>}
                            {a.nuova_data_inizio && <p className="text-gray-400">Nuove date: {a.nuova_data_inizio} → {a.nuova_data_fine}</p>}
                            {a.motivazione && <p className="text-gray-500 text-xs mt-1">{a.motivazione}</p>}
                          </div>
                        ))}
                      </div>

                      {/* Impatto */}
                      {p.impatto && (
                        <div className="grid grid-cols-2 gap-3 text-xs">
                          <div>
                            <p className="text-green-400 font-medium mb-1">✅ Benefici</p>
                            {p.impatto.benefici?.map((b, k) => <p key={k} className="text-gray-300">• {b}</p>)}
                          </div>
                          <div>
                            <p className="text-red-400 font-medium mb-1">⚠️ Rischi</p>
                            {p.impatto.rischi?.map((r, k) => <p key={k} className="text-gray-300">• {r}</p>)}
                          </div>
                        </div>
                      )}

                      {/* Bottone applica */}
                      <button className="mt-4 px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg text-sm font-medium transition-colors"
                        onClick={() => alert(`In produzione: applica Opzione ${p.id} e ridisegna il GANTT.`)}>
                        ✅ Applica questa opzione
                      </button>
                    </div>
                  ))}

                  {/* Conflitti */}
                  {proposte.conflitti && (
                    <div className="bg-red-900/20 border border-red-800 rounded-xl p-4">
                      <p className="text-red-300 font-semibold">⚠️ Conflitti irrisolvibili</p>
                      <p className="text-sm text-red-200 mt-1">{proposte.conflitti}</p>
                    </div>
                  )}

                  {/* GANTT preview */}
                  {ganttPreview.length > 0 && (
                    <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
                      <h3 className="font-semibold mb-3">📅 GANTT attuale (riferimento)</h3>
                      <MiniGantt tasks={ganttPreview} />
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
