import React, { useState, useEffect, useRef } from 'react'
import { fetchDipendenti, fetchDipendente, sendChatMessage, fetchAgentStatus } from '../api'

/* ── Chat message bubble ──────────────────────────────────────────── */
function ChatMessage({ role, content }) {
  const isAgent = role === 'assistant'
  return (
    <div className={`flex gap-3 mb-3 ${isAgent ? '' : 'flex-row-reverse'}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm flex-shrink-0 ${
        isAgent ? 'bg-blue-600' : 'bg-gray-600'
      }`}>
        {isAgent ? '🤖' : '👤'}
      </div>
      <div className={`max-w-[85%] rounded-xl px-4 py-3 text-sm leading-relaxed ${
        isAgent ? 'bg-gray-800 border border-gray-700' : 'bg-blue-900 border border-blue-700'
      }`}>
        {content}
      </div>
    </div>
  )
}

/* ── Typing indicator (3 dots animation) ─────────────────────────── */
function TypingIndicator() {
  return (
    <div className="flex gap-3 mb-3">
      <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm flex-shrink-0 bg-blue-600">
        🤖
      </div>
      <div className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 flex items-center gap-1.5">
        <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
        <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
        <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
        <span className="text-xs text-gray-400 ml-2">L'agente sta elaborando...</span>
      </div>
    </div>
  )
}

/* ── Main page ────────────────────────────────────────────────────── */
export default function Consuntivazione() {
  const [dipendenti, setDipendenti] = useState([])
  const [selectedDip, setSelectedDip] = useState('')
  const [dipDetail, setDipDetail] = useState(null)
  const [ore, setOre] = useState({})
  const [stati, setStati] = useState({})
  const [agentAvailable, setAgentAvailable] = useState(false)
  const [chatHistory, setChatHistory] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const chatEndRef = useRef(null)
  const chatContainerRef = useRef(null)

  // Assenze
  const [hasAssenza, setHasAssenza] = useState(false)
  const [tipoAssenza, setTipoAssenza] = useState('Permesso retribuito')
  const [oreAssenza, setOreAssenza] = useState(0)
  const [notaAssenza, setNotaAssenza] = useState('')

  // Smart working
  const [giorniSede, setGiorniSede] = useState(3)
  const [giorniRemoto, setGiorniRemoto] = useState(2)

  // Spese
  const [hasSpese, setHasSpese] = useState(false)
  const [spese, setSpese] = useState([{ descrizione: '', importo: 0, categoria: 'Trasporti' }])

  // Vista
  const [vista, setVista] = useState('dipendente')

  useEffect(() => {
    fetchDipendenti().then(setDipendenti)
    fetchAgentStatus().then(s => setAgentAvailable(s.available))
  }, [])

  useEffect(() => {
    if (selectedDip) {
      fetchDipendente(selectedDip).then(d => {
        setDipDetail(d)
        const oreInit = {}
        const statiInit = {}
        d.tasks.forEach(t => { oreInit[t.id] = 0; statiInit[t.id] = 'In corso' })
        setOre(oreInit)
        setStati(statiInit)
        setChatHistory([])
        setSubmitted(false)
        setHasAssenza(false)
        setHasSpese(false)
        setOreAssenza(0)
        setGiorniSede(3)
        setGiorniRemoto(2)
        setSpese([{ descrizione: '', importo: 0, categoria: 'Trasporti' }])
      })
    }
  }, [selectedDip])

  // Auto-scroll chat con smooth behavior
  useEffect(() => {
    if (chatContainerRef.current) {
      const container = chatContainerRef.current
      // Scroll graduale verso il fondo
      setTimeout(() => {
        container.scrollTo({
          top: container.scrollHeight,
          behavior: 'smooth'
        })
      }, 100)
    }
  }, [chatHistory, chatLoading])

  const totaleOre = Object.values(ore).reduce((s, v) => s + v, 0)
  const totaleRendicontato = totaleOre + (hasAssenza ? oreAssenza : 0)
  const oreContrattuali = dipDetail?.ore_sett || 40
  const delta = totaleRendicontato - oreContrattuali
  const taskZero = dipDetail?.tasks.filter(t => ore[t.id] === 0) || []
  const taskBloccati = dipDetail?.tasks.filter(t => stati[t.id] === 'Bloccato') || []

  // Calcolo buoni pasto stimati (giorni sede con >4h lavorate)
  const buoniPastoStimati = giorniSede // semplificato: si assume >4h nei giorni in sede

  const handleChat = async () => {
    if (!chatInput.trim() || chatLoading) return
    const userMsg = chatInput.trim()
    setChatInput('')
    setChatHistory(prev => [...prev, { role: 'user', content: userMsg }])
    setChatLoading(true)

    try {
      const res = await sendChatMessage({
        dipendente_id: selectedDip,
        messaggio: userMsg,
        ore_compilate: ore,
        stati_compilati: stati,
        ore_assenza: hasAssenza ? oreAssenza : 0,
        tipo_assenza: hasAssenza ? tipoAssenza : '',
        nota_assenza: hasAssenza ? notaAssenza : '',
        spese: hasSpese ? spese.filter(s => s.importo > 0) : [],
      })
      setChatHistory(prev => [...prev, { role: 'assistant', content: res.risposta }])
      if (res.segnalazione) {
        setChatHistory(prev => [...prev, {
          role: 'system',
          content: '📋 Segnalazione inoltrata — Il management la troverà in Analisi e Interventi.'
        }])
      }
    } catch (err) {
      setChatHistory(prev => [...prev, { role: 'assistant', content: `⚠️ Errore di comunicazione con l'agente. Riprova tra qualche secondo.` }])
    } finally {
      setChatLoading(false)
    }
  }

  const addSpesa = () => setSpese(prev => [...prev, { descrizione: '', importo: 0, categoria: 'Trasporti' }])
  const updateSpesa = (i, field, val) => {
    const updated = [...spese]
    updated[i] = { ...updated[i], [field]: val }
    setSpese(updated)
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">⏱️ Consuntivazione</h1>

      {/* Vista toggle */}
      <div className="flex gap-2 mb-6">
        <button onClick={() => setVista('dipendente')}
          className={`px-4 py-2 rounded-lg text-sm ${vista === 'dipendente' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400'}`}>
          👤 Vista Dipendente
        </button>
        <button onClick={() => setVista('management')}
          className={`px-4 py-2 rounded-lg text-sm ${vista === 'management' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400'}`}>
          📊 Vista Management
        </button>
      </div>

      {/* ═══════════════════════════════════════════════════════════ */}
      {/* VISTA DIPENDENTE                                          */}
      {/* ═══════════════════════════════════════════════════════════ */}
      {vista === 'dipendente' && (
        <>
          <div className="mb-6">
            <label className="text-sm text-gray-400 block mb-2">Accedi come:</label>
            <select value={selectedDip} onChange={e => setSelectedDip(e.target.value)}
              className="bg-gray-800 border border-gray-600 rounded-lg px-4 py-2.5 w-full max-w-md focus:border-blue-500 focus:outline-none">
              <option value="">Seleziona dipendente...</option>
              {dipendenti.map(d => <option key={d.id} value={d.id}>{d.nome} — {d.profilo}</option>)}
            </select>
          </div>

          {dipDetail && (
            <div className="grid grid-cols-3 gap-6">
              {/* ── Colonna sinistra: form ── */}
              <div className="col-span-2 space-y-6">
                {/* Saluto + ore task */}
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                  <h2 className="text-lg font-semibold mb-1">Ciao {dipDetail.nome.split(' ')[0]}! 👋</h2>
                  <p className="text-sm text-gray-400 mb-4">Settimana corrente — {dipDetail.tasks.length} task attivi</p>

                  <h3 className="font-medium text-sm text-gray-300 mb-3">📝 Ore lavorate per task</h3>
                  {dipDetail.tasks.map(task => (
                    <div key={task.id} className="flex items-center gap-4 py-3 border-b border-gray-800">
                      <div className="flex-1">
                        <p className="font-medium">{task.nome}</p>
                        <p className="text-xs text-gray-400">{task.progetto} — {task.fase}</p>
                      </div>
                      <input type="number" placeholder="Ore" min="0" max="60" step="0.5"
                        value={ore[task.id] || ''}
                        onChange={e => setOre(prev => ({ ...prev, [task.id]: parseFloat(e.target.value) || 0 }))}
                        className="w-24 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm placeholder-gray-500 focus:border-blue-500 focus:outline-none" />
                      <select value={stati[task.id] || 'In corso'}
                        onChange={e => setStati(prev => ({ ...prev, [task.id]: e.target.value }))}
                        className="w-36 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm focus:border-blue-500 focus:outline-none">
                        <option>In corso</option>
                        <option>Completato</option>
                        <option>Bloccato</option>
                      </select>
                    </div>
                  ))}
                </div>

                {/* Modalità lavoro + Assenze */}
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                  <h3 className="font-medium text-sm text-gray-300 mb-3">📅 Modalità e presenze</h3>

                  {/* Smart working */}
                  <div className="mb-4">
                    <p className="text-xs text-gray-500 mb-2">Modalità lavoro questa settimana</p>
                    <div className="flex gap-4 items-center">
                      <div className="flex items-center gap-2">
                        <label className="text-sm text-gray-400">🏢 In sede</label>
                        <input type="number" min="0" max="5" value={giorniSede}
                          onChange={e => {
                            const v = parseInt(e.target.value) || 0
                            setGiorniSede(v)
                            setGiorniRemoto(Math.max(0, 5 - v - (hasAssenza ? Math.ceil(oreAssenza / 8) : 0)))
                          }}
                          className="w-16 bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-sm text-center focus:border-blue-500 focus:outline-none" />
                        <span className="text-xs text-gray-500">gg</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <label className="text-sm text-gray-400">🏠 Da remoto</label>
                        <input type="number" min="0" max="5" value={giorniRemoto}
                          onChange={e => {
                            const v = parseInt(e.target.value) || 0
                            setGiorniRemoto(v)
                            setGiorniSede(Math.max(0, 5 - v - (hasAssenza ? Math.ceil(oreAssenza / 8) : 0)))
                          }}
                          className="w-16 bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-sm text-center focus:border-blue-500 focus:outline-none" />
                        <span className="text-xs text-gray-500">gg</span>
                      </div>
                      <span className="text-xs text-gray-500 ml-2">
                        ~{buoniPastoStimati} buoni pasto
                      </span>
                    </div>
                  </div>

                  {/* Assenze */}
                  <div className="border-t border-gray-800 pt-4">
                    <label className="flex items-center gap-2 text-sm cursor-pointer">
                      <input type="checkbox" checked={hasAssenza} onChange={e => setHasAssenza(e.target.checked)} className="rounded" />
                      Ho avuto assenze o permessi questa settimana
                    </label>
                    {hasAssenza && (
                      <div className="grid grid-cols-3 gap-4 mt-3">
                        <select value={tipoAssenza} onChange={e => setTipoAssenza(e.target.value)}
                          className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm">
                          <option>Permesso retribuito</option>
                          <option>Ferie</option>
                          <option>Malattia</option>
                          <option>Permesso non retribuito</option>
                          <option>Altro</option>
                        </select>
                        <input type="number" placeholder="Ore assenza" min="0" max="40" step="0.5"
                          value={oreAssenza || ''}
                          onChange={e => setOreAssenza(parseFloat(e.target.value) || 0)}
                          className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm placeholder-gray-500 focus:border-blue-500 focus:outline-none" />
                        <input type="text" placeholder="Nota (es: visita medica)"
                          value={notaAssenza}
                          onChange={e => setNotaAssenza(e.target.value)}
                          className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm placeholder-gray-500 focus:border-blue-500 focus:outline-none" />
                      </div>
                    )}
                  </div>
                </div>

                {/* Spese */}
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                  <h3 className="font-medium text-sm text-gray-300 mb-3">💳 Note spese</h3>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={hasSpese} onChange={e => setHasSpese(e.target.checked)} className="rounded" />
                    Sì, ho spese da rendicontare
                  </label>
                  {hasSpese && (
                    <div className="mt-3 space-y-2">
                      {spese.map((s, i) => (
                        <div key={i} className="flex gap-3">
                          <input type="text" placeholder="Descrizione" value={s.descrizione}
                            onChange={e => updateSpesa(i, 'descrizione', e.target.value)}
                            className="flex-1 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm placeholder-gray-500" />
                          <input type="number" placeholder="€" min="0" step="0.5"
                            value={s.importo || ''}
                            onChange={e => updateSpesa(i, 'importo', parseFloat(e.target.value) || 0)}
                            className="w-28 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm placeholder-gray-500" />
                          <select value={s.categoria} onChange={e => updateSpesa(i, 'categoria', e.target.value)}
                            className="w-40 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm">
                            <option>Trasporti</option>
                            <option>Vitto</option>
                            <option>Alloggio</option>
                            <option>Materiali</option>
                            <option>Software/Licenze</option>
                            <option>Altro</option>
                          </select>
                        </div>
                      ))}
                      <button onClick={addSpesa} className="text-sm text-blue-400 hover:text-blue-300">+ Aggiungi voce</button>
                    </div>
                  )}
                </div>

                {/* Riepilogo KPI */}
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                  <h3 className="font-medium text-sm text-gray-300 mb-3">📊 Riepilogo settimana</h3>
                  <div className="grid grid-cols-4 gap-4">
                    <div className="bg-gray-800 rounded-lg p-3">
                      <p className="text-xs text-gray-400">Ore lavorate</p>
                      <p className="text-2xl font-bold">{totaleOre.toFixed(1)}h</p>
                    </div>
                    <div className="bg-gray-800 rounded-lg p-3">
                      <p className="text-xs text-gray-400">Ore assenza</p>
                      <p className="text-2xl font-bold">{(hasAssenza ? oreAssenza : 0).toFixed(1)}h</p>
                    </div>
                    <div className="bg-gray-800 rounded-lg p-3">
                      <p className="text-xs text-gray-400">Totale rendicontato</p>
                      <p className="text-2xl font-bold">{totaleRendicontato.toFixed(1)}h</p>
                    </div>
                    <div className="bg-gray-800 rounded-lg p-3">
                      <p className="text-xs text-gray-400">vs contrattuali ({oreContrattuali}h)</p>
                      <p className={`text-2xl font-bold ${delta > 0 ? 'text-yellow-400' : delta < -4 ? 'text-red-400' : 'text-green-400'}`}>
                        {delta > 0 ? '+' : ''}{delta.toFixed(1)}h
                      </p>
                    </div>
                  </div>

                  {/* Avvisi intelligenti */}
                  {totaleRendicontato > 0 && totaleRendicontato < oreContrattuali - 4 && (
                    <div className="mt-3 p-3 bg-yellow-900/20 border border-yellow-800 rounded-lg text-sm text-yellow-300">
                      ⚠️ Hai rendicontato {totaleRendicontato.toFixed(1)}h su {oreContrattuali}h contrattuali. Mancano {(oreContrattuali - totaleRendicontato).toFixed(1)}h.
                    </div>
                  )}
                  {taskBloccati.length > 0 && (
                    <div className="mt-3 p-3 bg-red-900/20 border border-red-800 rounded-lg text-sm text-red-300">
                      🔴 {taskBloccati.length} task bloccati: {taskBloccati.map(t => t.nome).join(', ')}. Il PM verrà notificato.
                    </div>
                  )}
                  {taskZero.length > 0 && (
                    <div className="mt-3 p-3 bg-yellow-900/20 border border-yellow-800 rounded-lg text-sm text-yellow-300">
                      ⚠️ Task senza avanzamento: {taskZero.map(t => t.nome).join(', ')}
                    </div>
                  )}
                </div>

                {/* Submit */}
                <div className="flex gap-3">
                  <button onClick={() => {
                    if (totaleOre === 0 && (!hasAssenza || oreAssenza === 0)) {
                      alert('Compila almeno le ore lavorate o indica un\'assenza.')
                      return
                    }
                    setSubmitted(true)
                  }}
                    disabled={submitted}
                    className="px-6 py-2.5 bg-green-600 hover:bg-green-500 disabled:bg-gray-600 rounded-lg font-medium transition-colors">
                    {submitted ? '✅ Consuntivo inviato!' : '✅ Invia consuntivo'}
                  </button>
                  <button className="px-6 py-2.5 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">
                    ⏰ Ricordamelo dopo
                  </button>
                </div>
              </div>

              {/* ── Colonna destra: chat ── */}
              <div className="col-span-1">
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 sticky top-8 flex flex-col" style={{ maxHeight: 'calc(100vh - 8rem)' }}>
                  <div className="flex items-center gap-2 mb-3">
                    <h3 className="font-semibold">💬 Assistente</h3>
                    <span className={`w-2 h-2 rounded-full ${agentAvailable ? 'bg-green-500' : 'bg-yellow-500'}`} />
                    <span className="text-xs text-gray-500">{agentAvailable ? 'AI attivo' : 'Non connesso'}</span>
                  </div>

                  {/* Riepilogo compilazione */}
                  {(totaleOre > 0 || taskZero.length > 0) && (
                    <details className="mb-3 text-xs">
                      <summary className="cursor-pointer text-gray-400 hover:text-white">📋 Cosa ha recepito l'agente</summary>
                      <div className="mt-1 p-2 bg-gray-800 rounded space-y-1">
                        {dipDetail.tasks.map(t => (
                          <p key={t.id} className={ore[t.id] === 0 ? 'text-yellow-400' : 'text-gray-300'}>
                            {ore[t.id] === 0 ? '⚠️' : '•'} {ore[t.id] || 0}h su {t.nome}
                            {ore[t.id] === 0 && ' — nessun avanzamento'}
                          </p>
                        ))}
                        {hasAssenza && oreAssenza > 0 && (
                          <p className="text-gray-300">• {oreAssenza}h assenza ({tipoAssenza})</p>
                        )}
                        <p className="text-gray-300">• 🏢 {giorniSede}gg sede · 🏠 {giorniRemoto}gg remoto</p>
                      </div>
                    </details>
                  )}

                  {/* Chat */}
                  <div ref={chatContainerRef} className="flex-1 overflow-y-auto mb-3 space-y-1 min-h-[250px]">
                    <ChatMessage role="assistant"
                      content="Compila le ore qui a fianco. Se hai bisogno di segnalare qualcosa — un blocco, una richiesta di supporto, o qualsiasi altra cosa — scrivimi qui." />
                    {chatHistory.map((msg, i) => (
                      msg.role === 'system' ? (
                        <div key={i} className="text-center py-2">
                          <span className="text-xs text-green-400 bg-green-900/20 px-3 py-1 rounded-full">
                            {msg.content}
                          </span>
                        </div>
                      ) : (
                        <ChatMessage key={i} role={msg.role} content={msg.content} />
                      )
                    ))}
                    {chatLoading && <TypingIndicator />}
                    <div ref={chatEndRef} />
                  </div>

                  {/* Input */}
                  <div className="flex gap-2 items-end">
                    <textarea value={chatInput}
                      onChange={e => {
                        setChatInput(e.target.value)
                        // Auto-resize
                        e.target.style.height = 'auto'
                        e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
                      }}
                      onKeyDown={e => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault()
                          handleChat()
                        }
                      }}
                      placeholder={chatLoading ? "Attendi la risposta..." : "Scrivi qui... (Shift+Invio per andare a capo)"}
                      disabled={chatLoading}
                      rows={1}
                      className="flex-1 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm placeholder-gray-500 focus:border-blue-500 focus:outline-none disabled:opacity-50 resize-none overflow-y-auto"
                      style={{ minHeight: '38px', maxHeight: '120px' }} />
                    <button onClick={handleChat} disabled={chatLoading || !chatInput.trim()}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 rounded-lg text-sm transition-colors flex-shrink-0">
                      Invia
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* ═══════════════════════════════════════════════════════════ */}
      {/* VISTA MANAGEMENT                                          */}
      {/* ═══════════════════════════════════════════════════════════ */}
      {vista === 'management' && (
        <div>
          <p className="text-sm text-yellow-400 mb-6">🔒 In produzione, questa vista richiederà autenticazione con ruolo management.</p>
          <p className="text-gray-400">Vista management — da implementare con i dati aggregati dei consuntivi. Vedi la pagina Economia per i dati finanziari.</p>
        </div>
      )}
    </div>
  )
}
