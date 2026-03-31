import React, { useState, useEffect, useMemo } from 'react'
import { fetchDipendenti, fetchProgetti, fetchTasks, fetchSegnalazioni, interpretaScenario, simulaScenario, confermaScenario } from '../api'
import { GanttChart } from './Gantt'

// ── Costanti ────────────────────────────────────────────────────────
const GRAVITA_STYLE = {
  alta:  'bg-red-900/30 border-red-700 text-red-300',
  media: 'bg-yellow-900/30 border-yellow-700 text-yellow-300',
  bassa: 'bg-gray-800/60 border-gray-700 text-gray-300',
}

const GRAVITA_BADGE = {
  alta:  'bg-red-600 text-white',
  media: 'bg-yellow-600 text-white',
  bassa: 'bg-gray-600 text-white',
}

const TIPO_ICON = {
  scadenza_bucata:      '🚨',
  task_slittato:        '📅',
  sovraccarico_persona: '👤',
}

// ═════════════════════════════════════════════════════════════════════
//  COMPONENTE: Input scenario con completion
// ═════════════════════════════════════════════════════════════════════

function ScenarioInput({ onSubmit, loading, progetti, dipendenti }) {
  const [testo, setTesto] = useState('')
  const [showSuggestions, setShowSuggestions] = useState(false)

  // Suggerimenti contestuali
  const suggerimenti = [
    'Il progetto [nome] anticipa di [N] giorni',
    '[Nome persona] si concentra al 100% su [progetto] per [N] settimane',
    '[Nome persona] aiuta su [progetto] ma continua i suoi task',
    'Il task [nome task] slitta di [N] giorni',
    'Servono [N] ore in più sullo sviluppo di [progetto]',
  ]

  function handleSubmit() {
    if (!testo.trim() || loading) return
    onSubmit(testo.trim())
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-lg">💬</span>
        <h3 className="font-semibold">Cosa sta cambiando?</h3>
      </div>
      <p className="text-sm text-gray-400 mb-3">
        Descrivi in linguaggio naturale cosa è successo o cosa deve cambiare. L'agente interpreterà e il sistema calcolerà l'impatto su tutti i GANTT.
      </p>
      <div className="flex gap-3">
        <div className="flex-1 relative">
          <textarea
            value={testo}
            onChange={e => setTesto(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => setShowSuggestions(true)}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
            placeholder="Es: 'Sparkasse ha anticipato la scadenza di 20 giorni' oppure 'Marco si concentra su Digital Health per 2 settimane'..."
            rows={2}
            disabled={loading}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-sm placeholder-gray-500 focus:border-blue-500 focus:outline-none resize-none disabled:opacity-50"
          />
          {/* Suggerimenti */}
          {showSuggestions && !testo && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-lg z-10 py-1">
              <p className="px-3 py-1 text-[10px] text-gray-500 uppercase tracking-wider">Esempi di input</p>
              {suggerimenti.map((s, i) => (
                <button key={i}
                  onMouseDown={() => { setTesto(s); setShowSuggestions(false) }}
                  className="w-full text-left px-3 py-2 text-sm text-gray-300 hover:bg-gray-700 transition-colors">
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
        <button
          onClick={handleSubmit}
          disabled={!testo.trim() || loading}
          className="self-end px-5 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg text-sm font-medium transition-colors whitespace-nowrap">
          {loading ? '⏳ Interpreto...' : '→ Analizza impatto'}
        </button>
      </div>
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════
//  COMPONENTE: Interpretazione IA (conferma/modifica prima di simulare)
// ═════════════════════════════════════════════════════════════════════

function InterpretazionePanel({ interpretazione, modifiche, domande, noteContesto, onConferma, onAnnulla, onRisposta, loading }) {
  const [risposta, setRisposta] = useState('')

  return (
    <div className="bg-blue-900/20 border border-blue-800 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-lg">🧠</span>
        <h3 className="font-semibold text-blue-200">Interpretazione dell'agente</h3>
      </div>

      {interpretazione && (
        <p className="text-sm text-gray-200 mb-4 leading-relaxed">{interpretazione}</p>
      )}

      {domande && (
        <div className="mb-4">
          <div className="bg-yellow-900/20 border border-yellow-800 rounded-lg p-3 mb-3">
            <p className="text-sm text-yellow-200">❓ {domande}</p>
          </div>
          {/* Campo risposta alla domanda */}
          <div className="flex gap-2">
            <input
              type="text"
              value={risposta}
              onChange={e => setRisposta(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && risposta.trim()) onRisposta(risposta.trim()) }}
              placeholder="Rispondi qui..."
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm placeholder-gray-500 focus:border-yellow-500 focus:outline-none"
            />
            <button
              onClick={() => { if (risposta.trim()) onRisposta(risposta.trim()) }}
              disabled={!risposta.trim() || loading}
              className="px-4 py-2 bg-yellow-600 hover:bg-yellow-500 disabled:bg-gray-700 rounded-lg text-sm font-medium transition-colors">
              {loading ? '⏳' : '→ Rispondi'}
            </button>
          </div>
        </div>
      )}

      {noteContesto && (
        <div className="bg-gray-800/50 rounded-lg p-3 mb-4">
          <p className="text-xs text-gray-400">📋 Contesto: {noteContesto}</p>
        </div>
      )}

      {modifiche && modifiche.length > 0 && (
        <div className="mb-4">
          <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">
            Modifiche che verranno simulate ({modifiche.length})
          </p>
          <div className="space-y-2">
            {modifiche.map((m, i) => (
              <div key={i} className="bg-gray-800 rounded-lg p-3 text-sm">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-xs font-medium uppercase px-2 py-0.5 rounded ${
                    m.tipo === 'sposta_task' ? 'bg-blue-700 text-blue-100' : 'bg-purple-700 text-purple-100'
                  }`}>
                    {m.tipo === 'sposta_task' ? 'Sposta date' : 'Cambia focus'}
                  </span>
                </div>
                {m.tipo === 'sposta_task' && (
                  <p className="text-gray-300">
                    Task <strong>{m.task_id}</strong>
                    {m.nuova_fine && <span> → nuova fine: {new Date(m.nuova_fine).toLocaleDateString('it-IT')}</span>}
                    {m.nuovo_inizio && <span> → nuovo inizio: {new Date(m.nuovo_inizio).toLocaleDateString('it-IT')}</span>}
                  </p>
                )}
                {m.tipo === 'cambia_focus' && (
                  <p className="text-gray-300">
                    <strong>{m.dipendente_id}</strong> → {m.percentuale}% su progetto <strong>{m.progetto_focus}</strong> per {m.durata_settimane} settimane
                  </p>
                )}
                {m.motivo && <p className="text-xs text-gray-500 mt-1">{m.motivo}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-2">
        {modifiche && modifiche.length > 0 && !domande && (
          <button onClick={onConferma} disabled={loading}
            className="flex-1 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 rounded-lg text-sm font-medium transition-colors">
            {loading ? '⏳ Calcolo cascata...' : '📊 Calcola impatto a cascata'}
          </button>
        )}
        <button onClick={onAnnulla}
          className="px-4 py-2.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors">
          Annulla
        </button>
      </div>
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════
//  COMPONENTE: Risultato simulazione (GANTT prima/dopo + conseguenze)
// ═════════════════════════════════════════════════════════════════════

function RisultatoSimulazione({ risultato, onConferma, onReset, confermaLoading, confermato }) {
  const [progettoAperto, setProgettoAperto] = useState(null)
  const [showSaturazioni, setShowSaturazioni] = useState(false)

  if (!risultato) return null

  const { gantt_prima, gantt_dopo, conseguenze, saturazioni, n_task_modificati, progetti_impattati, scadenze_bucate } = risultato

  // Prima apertura: mostra il primo progetto impattato
  const progettiIds = Object.keys(gantt_dopo || {})
  const progettoVisualizzato = progettoAperto || progettiIds[0]

  return (
    <div className="space-y-4">
      {/* Header riepilogo */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <span className="text-lg">📊</span>
            <h3 className="font-semibold">Risultato simulazione</h3>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-gray-400">{n_task_modificati} task impattati</span>
            <span className="text-gray-400">{progetti_impattati?.length || 0} progetti coinvolti</span>
          </div>
        </div>

        {/* Scadenze bucate — alert prominente */}
        {scadenze_bucate && scadenze_bucate.length > 0 && (
          <div className="mb-4 space-y-2">
            {scadenze_bucate.map((sb, i) => (
              <div key={i} className="p-3 bg-red-900/30 border border-red-700 rounded-lg flex items-center gap-3">
                <span className="text-xl">🚨</span>
                <div>
                  <p className="text-sm font-medium text-red-200">
                    {sb.progetto} ({sb.cliente}): sfora la scadenza di {sb.giorni_sforo} giorni
                  </p>
                  <p className="text-xs text-red-300/70">
                    Scadenza: {new Date(sb.scadenza).toLocaleDateString('it-IT')} → Ultimo task finisce: {new Date(sb.ultimo_task_fine).toLocaleDateString('it-IT')}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Tabs progetti */}
        {progettiIds.length > 1 && (
          <div className="flex gap-2 mb-4 flex-wrap">
            {progettiIds.map(pid => {
              const info = gantt_dopo[pid]
              const haScadenzaBucata = scadenze_bucate?.some(sb => sb.progetto_id === pid)
              return (
                <button key={pid}
                  onClick={() => setProgettoAperto(pid)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    progettoVisualizzato === pid
                      ? 'bg-blue-600 text-white'
                      : haScadenzaBucata
                        ? 'bg-red-900/30 text-red-300 border border-red-700 hover:bg-red-900/50'
                        : 'bg-gray-800 text-gray-400 hover:text-white'
                  }`}>
                  {haScadenzaBucata && '⚠️ '}{info?.progetto || pid}
                </button>
              )
            })}
          </div>
        )}

        {/* GANTT Prima / Dopo */}
        {progettoVisualizzato && gantt_prima[progettoVisualizzato] && (
          <div className="space-y-3">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 bg-gray-800 px-2 py-1 rounded">Prima</span>
                <span className="text-xs text-gray-500">{gantt_prima[progettoVisualizzato]?.progetto}</span>
              </div>
              <GanttChart tasks={gantt_prima[progettoVisualizzato]?.tasks || []} compact />
            </div>
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-amber-300 bg-amber-900/30 px-2 py-1 rounded">Dopo</span>
                <span className="text-xs text-gray-500">{gantt_dopo[progettoVisualizzato]?.progetto}</span>
              </div>
              <GanttChart tasks={gantt_dopo[progettoVisualizzato]?.tasks || []} compact />
            </div>
          </div>
        )}
      </div>

      {/* Conseguenze */}
      {conseguenze && conseguenze.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h3 className="font-semibold mb-3">📋 Conseguenze ({conseguenze.length})</h3>
          <div className="space-y-2 max-h-[400px] overflow-y-auto">
            {conseguenze.map((c, i) => (
              <div key={i} className={`p-3 rounded-lg border text-sm ${GRAVITA_STYLE[c.gravita]}`}>
                <div className="flex items-center gap-2 mb-1">
                  <span>{TIPO_ICON[c.tipo] || '📌'}</span>
                  <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${GRAVITA_BADGE[c.gravita]}`}>
                    {c.gravita}
                  </span>
                  <span className="text-[10px] text-gray-500">{c.tipo?.replace(/_/g, ' ')}</span>
                </div>
                <p className="text-gray-200 leading-relaxed">{c.testo}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Saturazioni settimanali */}
      {saturazioni && Object.keys(saturazioni).length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <button onClick={() => setShowSaturazioni(!showSaturazioni)}
            className="w-full flex items-center justify-between">
            <h3 className="font-semibold">👥 Dettaglio saturazioni per persona ({Object.keys(saturazioni).length})</h3>
            <span className="text-gray-400 text-sm">{showSaturazioni ? '▼' : '▶'}</span>
          </button>

          {showSaturazioni && (
            <div className="mt-4 space-y-4">
              {Object.entries(saturazioni).map(([did, data]) => (
                <div key={did} className="bg-gray-800/50 rounded-lg p-4">
                  <div className="flex items-center gap-3 mb-3">
                    <span className="font-medium">{data.nome}</span>
                    <span className="text-xs text-gray-400">{data.profilo} · {data.ore_sett}h/sett</span>
                  </div>
                  <div className="grid grid-cols-6 gap-1 text-[10px]">
                    {data.settimane?.slice(0, 6).map((s, i) => {
                      const lun = new Date(s.lunedi)
                      const overPrima = s.carico_prima > data.ore_sett
                      const overDopo = s.carico_dopo > data.ore_sett
                      const peggiorato = s.carico_dopo > s.carico_prima
                      return (
                        <div key={i} className={`p-2 rounded text-center ${
                          overDopo && peggiorato ? 'bg-red-900/40 border border-red-700' :
                          overDopo ? 'bg-yellow-900/30 border border-yellow-800' :
                          'bg-gray-700/30'
                        }`}>
                          <p className="text-gray-500 mb-1">
                            {lun.toLocaleDateString('it-IT', { day: 'numeric', month: 'short' })}
                          </p>
                          <p className="text-gray-400">{s.carico_prima}h</p>
                          <p className="text-gray-600">↓</p>
                          <p className={`font-bold ${overDopo ? 'text-red-400' : 'text-green-400'}`}>
                            {s.carico_dopo}h
                          </p>
                          {/* Dettaglio attività dopo */}
                          {s.dettaglio_dopo?.length > 0 && (
                            <div className="mt-1 pt-1 border-t border-gray-600/30">
                              {s.dettaglio_dopo.map((det, j) => (
                                <p key={j} className="text-gray-500 truncate" title={`${det.task} (${det.ore_sett}h)`}>
                                  {det.task?.substring(0, 12)}… {det.ore_sett}h
                                </p>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Azioni finali */}
      <div className="flex gap-3 justify-end">
        <button onClick={onReset}
          className="px-5 py-2.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors">
          🔄 Nuovo scenario
        </button>
        {!confermato && (
          <button onClick={onConferma} disabled={confermaLoading}
            className="px-5 py-2.5 bg-green-600 hover:bg-green-500 disabled:bg-green-800 rounded-lg text-sm font-medium transition-colors">
            {confermaLoading ? '⏳ Applico...' : '✅ Conferma e applica al GANTT'}
          </button>
        )}
        {confermato && (
          <div className="px-5 py-2.5 bg-green-900/30 border border-green-700 rounded-lg text-sm text-green-300 font-medium">
            ✅ Modifiche applicate! I GANTT sono aggiornati.
          </div>
        )}
      </div>
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════
//  COMPONENTE: Sidebar contesto (stato dell'arte)
// ═════════════════════════════════════════════════════════════════════

function SidebarContesto({ dipendenti, progetti, segnalazioni }) {
  // Persone con carico > 90%
  const sovraccarichi = dipendenti
    .filter(d => d.saturazione_pct > 90)
    .sort((a, b) => b.saturazione_pct - a.saturazione_pct)

  // Progetti in esecuzione
  const progettiAttivi = progetti.filter(p => p.stato === 'In esecuzione')

  return (
    <div className="space-y-4">
      {/* Persone */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">👥 Carico persone</h4>
        <div className="space-y-2">
          {dipendenti
            .sort((a, b) => b.saturazione_pct - a.saturazione_pct)
            .slice(0, 8)
            .map(d => (
              <div key={d.id} className="flex items-center justify-between text-sm">
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{d.nome}</p>
                  <p className="text-[10px] text-gray-500">{d.profilo} · {d.n_task_attivi ?? '?'} task · {d.progetti_attivi?.length ?? '?'} prog.</p>
                </div>
                <div className="flex items-center gap-2 ml-2">
                  <div className="w-16 bg-gray-700 rounded-full h-1.5">
                    <div className={`h-1.5 rounded-full ${
                      d.saturazione_pct > 100 ? 'bg-red-500' :
                      d.saturazione_pct > 85 ? 'bg-yellow-500' : 'bg-green-500'
                    }`} style={{ width: `${Math.min(100, d.saturazione_pct)}%` }} />
                  </div>
                  <span className={`text-xs font-mono w-10 text-right ${
                    d.saturazione_pct > 100 ? 'text-red-400' :
                    d.saturazione_pct > 85 ? 'text-yellow-400' : 'text-gray-400'
                  }`}>
                    {d.saturazione_pct}%
                  </span>
                </div>
              </div>
            ))}
        </div>
      </div>

      {/* Segnalazioni recenti */}
      {segnalazioni.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
            📥 Segnalazioni recenti ({segnalazioni.length})
          </h4>
          <div className="space-y-2 max-h-[200px] overflow-y-auto">
            {segnalazioni.slice(0, 5).map(s => (
              <div key={s.id} className="p-2 bg-gray-800/50 rounded-lg text-xs">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium ${GRAVITA_BADGE[s.priorita]}`}>
                    {s.priorita}
                  </span>
                  <span className="text-gray-400">{s.dipendente || ''}</span>
                </div>
                <p className="text-gray-300 line-clamp-2">{s.dettaglio}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Progetti attivi */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
          📁 Progetti attivi ({progettiAttivi.length})
        </h4>
        <div className="space-y-1.5">
          {progettiAttivi.map(p => (
            <div key={p.id} className="flex items-center justify-between text-xs">
              <span className="text-gray-300 truncate flex-1">{p.nome}</span>
              <span className="text-gray-500 ml-2">{p.cliente}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════
//  PAGINA PRINCIPALE — TAVOLO DI LAVORO
// ═════════════════════════════════════════════════════════════════════

export default function AnalisiInterventi() {
  // Dati di contesto
  const [dipendenti, setDipendenti] = useState([])
  const [progetti, setProgetti] = useState([])
  const [allTasks, setAllTasks] = useState([])
  const [segnalazioni, setSegnalazioni] = useState([])
  const [loadingData, setLoadingData] = useState(true)

  // Flusso scenario
  const [fase, setFase] = useState('input')
  // 'input'          → campo testo libero
  // 'interpretazione' → IA ha interpretato, management conferma
  // 'simulazione'     → cascata calcolata, GANTT prima/dopo visibili
  // 'confermato'      → modifiche applicate al db

  // Dati intermedi
  const [interpretazioneResult, setInterpretazioneResult] = useState(null)
  const [modificheConfermate, setModificheConfermate] = useState([])
  const [simulazioneResult, setSimulazioneResult] = useState(null)
  const [testoOriginale, setTestoOriginale] = useState('')  // salva il testo per follow-up

  // Loading states
  const [interpretaLoading, setInterpretaLoading] = useState(false)
  const [simulaLoading, setSimulaLoading] = useState(false)
  const [confermaLoading, setConfermaLoading] = useState(false)

  // Storico scenari nella sessione
  const [storico, setStorico] = useState([])

  // ── Caricamento dati ──
  useEffect(() => {
    Promise.all([fetchDipendenti(), fetchProgetti(), fetchTasks()])
      .then(([d, p, t]) => { setDipendenti(d); setProgetti(p); setAllTasks(t) })
      .finally(() => setLoadingData(false))
    fetchSegnalazioni()
      .then(s => { if (s && s.length > 0) setSegnalazioni(s) })
      .catch(() => {})
  }, [])

  if (loadingData) return <p className="text-gray-400 p-8">Caricamento...</p>

  // ── STEP 1: Interpreta input naturale ──
  async function handleInterpreta(testo, contesto_extra = '') {
    setInterpretaLoading(true)
    setInterpretazioneResult(null)
    if (!contesto_extra) setTestoOriginale(testo)  // salva solo il primo input
    try {
      const result = await interpretaScenario(testo, contesto_extra)
      setInterpretazioneResult(result)
      if (result.modifiche && result.modifiche.length > 0 && !result.domande) {
        setModificheConfermate(result.modifiche)
      }
      setFase('interpretazione')
    } catch (err) {
      alert('Errore nella comunicazione con l\'agente: ' + err.message)
    } finally {
      setInterpretaLoading(false)
    }
  }

  // ── STEP 1b: Risposta a domanda IA ──
  function handleRispostaIA(risposta) {
    // Reinvia il testo originale + la risposta come contesto aggiuntivo
    handleInterpreta(testoOriginale, risposta)
  }

  // ── STEP 2: Simula cascata ──
  async function handleSimula() {
    if (modificheConfermate.length === 0) return
    setSimulaLoading(true)
    try {
      const result = await simulaScenario(modificheConfermate)
      setSimulazioneResult(result)
      setFase('simulazione')
    } catch (err) {
      alert('Errore nella simulazione: ' + err.message)
    } finally {
      setSimulaLoading(false)
    }
  }

  // ── STEP 3: Conferma e applica ──
  async function handleConferma() {
    if (modificheConfermate.length === 0) return
    setConfermaLoading(true)
    try {
      const result = await confermaScenario(modificheConfermate)
      if (result.successo) {
        setFase('confermato')
        // Aggiorna storico
        setStorico(prev => [...prev, {
          timestamp: new Date().toLocaleString('it-IT'),
          n_modifiche: result.n_applicati,
          applicati: result.applicati,
        }])
        // Ricarica tutti i dati aggiornati
        Promise.all([fetchTasks(), fetchDipendenti(), fetchSegnalazioni()])
          .then(([t, d, s]) => {
            setAllTasks(t)
            setDipendenti(d)
            if (s && s.length > 0) setSegnalazioni(s)
          })
      } else {
        alert('Alcune modifiche non sono state applicate. Errori: ' + JSON.stringify(result.errori))
      }
    } catch (err) {
      alert('Errore nell\'applicazione: ' + err.message)
    } finally {
      setConfermaLoading(false)
    }
  }

  // ── Reset per nuovo scenario ──
  function handleReset() {
    setFase('input')
    setInterpretazioneResult(null)
    setModificheConfermate([])
    setSimulazioneResult(null)
    setTestoOriginale('')
  }

  // ═════════════════════════════════════════════════════════════════
  //  RENDER
  // ═════════════════════════════════════════════════════════════════

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">🔬 Tavolo di Lavoro</h1>
      <p className="text-sm text-gray-400 mb-6">
        Descrivi cosa sta cambiando → visualizza l'impatto su tutti i GANTT → conferma le modifiche.
      </p>

      <div className="flex gap-6">
        {/* ── Area principale ── */}
        <div className="flex-1 space-y-4">

          {/* Input sempre visibile (tranne dopo conferma) */}
          {fase !== 'confermato' && (
            <ScenarioInput
              onSubmit={handleInterpreta}
              loading={interpretaLoading}
              progetti={progetti}
              dipendenti={dipendenti}
            />
          )}

          {/* Interpretazione IA */}
          {fase === 'interpretazione' && interpretazioneResult && (
            <InterpretazionePanel
              interpretazione={interpretazioneResult.interpretazione}
              modifiche={interpretazioneResult.modifiche}
              domande={interpretazioneResult.domande}
              noteContesto={interpretazioneResult.note_contesto}
              onConferma={handleSimula}
              onAnnulla={handleReset}
              onRisposta={handleRispostaIA}
              loading={simulaLoading || interpretaLoading}
            />
          )}

          {/* Risultato simulazione */}
          {(fase === 'simulazione' || fase === 'confermato') && (
            <RisultatoSimulazione
              risultato={simulazioneResult}
              onConferma={handleConferma}
              onReset={handleReset}
              confermaLoading={confermaLoading}
              confermato={fase === 'confermato'}
            />
          )}

          {/* Storico sessione */}
          {storico.length > 0 && fase === 'input' && (
            <div className="bg-gray-900/50 rounded-xl border border-gray-800 p-4">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">
                📜 Scenari applicati in questa sessione
              </h4>
              <div className="space-y-1">
                {storico.map((s, i) => (
                  <div key={i} className="flex items-center justify-between text-xs text-gray-400">
                    <span>{s.timestamp}</span>
                    <span>{s.n_modifiche} modifiche applicate</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── Sidebar contesto ── */}
        <div className="w-72 flex-shrink-0">
          <SidebarContesto
            dipendenti={dipendenti}
            progetti={progetti}
            segnalazioni={segnalazioni}
          />
        </div>
      </div>
    </div>
  )
}
