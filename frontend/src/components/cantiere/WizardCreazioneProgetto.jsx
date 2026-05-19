// ═════════════════════════════════════════════════════════════════════════
// WizardCreazioneProgetto.jsx — Wizard 3-step per creare un nuovo progetto
//
// Step 2.7 parte 2 (scheletro 19/05/2026 sera):
//   Step 1: Anagrafica (obbligatorio)
//     - nome, cliente, tipologia, PM, data_inizio, data_fine, budget_ore
//   Step 2: Fasi (obbligatorio, almeno 1 fase)
//     - tabella editabile: nome, ordine, data_inizio, data_fine, ore_vendute
//     - somma ore vendute fase deve quadrare col budget progetto
//   Step 3: Task iniziali (OPZIONALE)
//     - "I task sono dinamici, si aggiungono nel tempo. Se hai già task
//        definiti per qualche fase, puoi inserirli qui. Altrimenti salta."
//     - tabella editabile collegata a fase selezionata
//
// Submit:
//   - Salva come Bozza (sempre disponibile)
//   - Salva come Da iniziare (richiede formalizzazione stato — Step 2.7-pre domani)
//   - Salva come In esecuzione (richiede data_inizio <= oggi)
//
// Status implementazione (fine giornata 19/05):
//   [✓] Struttura 3-step navigabile
//   [✓] Step 1 Anagrafica con form completo
//   [✓] Step 2 Fasi tabella editabile
//   [✓] Step 3 Task iniziali opzionali
//   [ ] Submit collegato al backend (domani: API + stati Alembic)
//   [ ] Validazione cross-step (somma ore fasi = budget)
//   [ ] Autocomplete cliente da progetti esistenti
//
// ═════════════════════════════════════════════════════════════════════════

import React, { useState, useEffect } from 'react'
import { fetchDipendenti } from '../../api'
import { FormInput, FormSelect } from '../_shared/Form'


export default function WizardCreazioneProgetto({ onClose, onCreaProgetto }) {
  const [step, setStep] = useState(1)
  const [dipendenti, setDipendenti] = useState([])

  // Stato form complessivo
  const [anagrafica, setAnagrafica] = useState({
    nome: '',
    cliente: '',
    tipologia: 'ordinario',
    pm_id: '',
    data_inizio: '',
    data_fine: '',
    budget_ore: 0,
  })
  const [fasi, setFasi] = useState([
    { nome: '', ordine: 1, data_inizio: '', data_fine: '', ore_vendute: 0 }
  ])
  const [taskIniziali, setTaskIniziali] = useState([])

  useEffect(() => {
    fetchDipendenti().then(d => setDipendenti(d || []))
  }, [])

  // ── Validazione step 1 ────────────────────────────────────────────────
  const step1Valido = anagrafica.nome.trim() !== '' && anagrafica.budget_ore > 0

  // ── Validazione step 2 ────────────────────────────────────────────────
  const totaleOreFasi = fasi.reduce((s, f) => s + Number(f.ore_vendute || 0), 0)
  const step2Valido = fasi.length > 0
    && fasi.every(f => f.nome.trim() !== '' && f.ore_vendute > 0)
  const oreQuadrano = totaleOreFasi === Number(anagrafica.budget_ore)

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div className="bg-gray-900 rounded-xl border border-gray-700 max-w-4xl w-full max-h-[90vh] overflow-y-auto">

        {/* Header con progress 3 step */}
        <div className="border-b border-gray-800 p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xl font-semibold">＋ Nuovo progetto</h2>
            <button onClick={onClose} className="text-gray-500 hover:text-gray-200 text-xl">×</button>
          </div>
          <div className="flex items-center gap-2">
            <StepIndicator num={1} label="Anagrafica" attivo={step === 1} fatto={step > 1} />
            <span className="flex-1 h-px bg-gray-700" />
            <StepIndicator num={2} label="Fasi" attivo={step === 2} fatto={step > 2} />
            <span className="flex-1 h-px bg-gray-700" />
            <StepIndicator num={3} label="Task iniziali (opzionali)" attivo={step === 3} fatto={false} />
          </div>
        </div>

        {/* Contenuto step */}
        <div className="p-5">
          {step === 1 && (
            <StepAnagrafica
              dati={anagrafica}
              onChange={setAnagrafica}
              dipendenti={dipendenti}
            />
          )}
          {step === 2 && (
            <StepFasi
              fasi={fasi}
              onChange={setFasi}
              budgetProgetto={anagrafica.budget_ore}
              totaleOre={totaleOreFasi}
              oreQuadrano={oreQuadrano}
            />
          )}
          {step === 3 && (
            <StepTaskIniziali
              fasi={fasi}
              taskIniziali={taskIniziali}
              onChange={setTaskIniziali}
              dipendenti={dipendenti}
            />
          )}
        </div>

        {/* Footer navigazione */}
        <div className="border-t border-gray-800 p-4 flex items-center justify-between flex-wrap gap-3">
          <div className="flex gap-2">
            {step > 1 && (
              <button
                onClick={() => setStep(step - 1)}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm"
              >
                ← Indietro
              </button>
            )}
          </div>
          <div className="flex gap-2 items-center">
            {step === 3 && (
              <span className="text-xs text-gray-500 italic">Puoi saltare i task</span>
            )}
            {step < 3 && (
              <button
                onClick={() => setStep(step + 1)}
                disabled={(step === 1 && !step1Valido) || (step === 2 && !step2Valido)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg text-sm font-semibold"
              >
                Avanti →
              </button>
            )}
            {step === 3 && (
              <>
                <button
                  disabled
                  title="Submit attivo dopo Step 2.7-pre (formalizzazione stati domani)"
                  className="px-4 py-2 bg-amber-700/40 text-amber-300/60 rounded-lg text-sm font-semibold cursor-not-allowed opacity-60 border border-amber-700/50"
                >
                  Salva come Bozza
                </button>
                <button
                  disabled
                  title="Submit attivo dopo Step 2.7-pre"
                  className="px-4 py-2 bg-blue-700/40 text-blue-300/60 rounded-lg text-sm font-semibold cursor-not-allowed opacity-60 border border-blue-700/50"
                >
                  ▶ Crea progetto
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════════
// Step 1 — Anagrafica
// ═════════════════════════════════════════════════════════════════════════

function StepAnagrafica({ dati, onChange, dipendenti }) {
  const pmOptions = [
    { value: '', label: '— (da assegnare) —' },
    ...dipendenti.map(d => ({ value: d.id, label: `${d.nome} (${d.profilo || '—'})` }))
  ]

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold mb-1">Anagrafica progetto</h3>
        <p className="text-xs text-gray-500">Definisci nome, cliente e budget contrattuale.</p>
      </div>

      <FormInput
        label="Nome progetto *"
        value={dati.nome}
        onChange={v => onChange({ ...dati, nome: v })}
        required
      />

      <div className="grid grid-cols-2 gap-4">
        <FormInput
          label="Cliente"
          value={dati.cliente}
          onChange={v => onChange({ ...dati, cliente: v })}
          placeholder="Es. Sparkasse, Reale Mutua, BNP..."
        />
        <FormSelect
          label="Tipologia *"
          value={dati.tipologia}
          onChange={v => onChange({ ...dati, tipologia: v })}
          options={[
            { value: 'ordinario', label: 'Ordinario (cliente esterno)' },
            { value: 'interno', label: 'Interno (sviluppo IMC)' },
          ]}
        />
      </div>

      <FormSelect
        label="PM (Project Manager)"
        value={dati.pm_id}
        onChange={v => onChange({ ...dati, pm_id: v })}
        options={pmOptions}
      />

      <div className="grid grid-cols-2 gap-4">
        <FormInput
          label="Data inizio prevista"
          type="date"
          value={dati.data_inizio}
          onChange={v => onChange({ ...dati, data_inizio: v })}
        />
        <FormInput
          label="Data fine prevista"
          type="date"
          value={dati.data_fine}
          onChange={v => onChange({ ...dati, data_fine: v })}
        />
      </div>

      <FormInput
        label="Budget ore totale (vendute al cliente) *"
        type="number"
        value={dati.budget_ore}
        onChange={v => onChange({ ...dati, budget_ore: Number(v) || 0 })}
        placeholder="Somma delle ore vendute per fase"
      />

      <div className="bg-blue-900/20 border border-blue-800/50 rounded-lg p-3 text-xs text-blue-300/80">
        💡 Le ore si vendono per fase: nello Step 2 distribuirai questo budget tra le fasi del progetto.
        I task verranno aggiunti progressivamente nel tempo (Cantiere).
      </div>
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════════
// Step 2 — Fasi
// ═════════════════════════════════════════════════════════════════════════

function StepFasi({ fasi, onChange, budgetProgetto, totaleOre, oreQuadrano }) {

  function aggiungiFase() {
    onChange([
      ...fasi,
      { nome: '', ordine: fasi.length + 1, data_inizio: '', data_fine: '', ore_vendute: 0 }
    ])
  }

  function rimuoviFase(idx) {
    onChange(fasi.filter((_, i) => i !== idx).map((f, i) => ({ ...f, ordine: i + 1 })))
  }

  function aggiornaFase(idx, campo, valore) {
    const nuova = [...fasi]
    nuova[idx] = { ...nuova[idx], [campo]: valore }
    onChange(nuova)
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold mb-1">Fasi del progetto</h3>
        <p className="text-xs text-gray-500">
          Almeno una fase. Distribuisci il budget ({budgetProgetto}h) tra le fasi.
        </p>
      </div>

      <div className="bg-gray-800/40 border border-gray-700 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-800/60">
            <tr>
              <th className="text-left p-2 text-xs text-gray-400 font-medium uppercase tracking-wide w-12">#</th>
              <th className="text-left p-2 text-xs text-gray-400 font-medium uppercase tracking-wide">Nome fase</th>
              <th className="text-left p-2 text-xs text-gray-400 font-medium uppercase tracking-wide w-40">Data inizio</th>
              <th className="text-left p-2 text-xs text-gray-400 font-medium uppercase tracking-wide w-40">Data fine</th>
              <th className="text-left p-2 text-xs text-gray-400 font-medium uppercase tracking-wide w-32">Ore vendute</th>
              <th className="w-10"></th>
            </tr>
          </thead>
          <tbody>
            {fasi.map((f, idx) => (
              <tr key={idx} className="border-t border-gray-800">
                <td className="p-2 text-center text-gray-500">{f.ordine}</td>
                <td className="p-2">
                  <input
                    type="text"
                    value={f.nome}
                    onChange={e => aggiornaFase(idx, 'nome', e.target.value)}
                    placeholder="es. Analisi, Design, Sviluppo..."
                    className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm"
                  />
                </td>
                <td className="p-2">
                  <input
                    type="date"
                    value={f.data_inizio}
                    onChange={e => aggiornaFase(idx, 'data_inizio', e.target.value)}
                    className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm"
                  />
                </td>
                <td className="p-2">
                  <input
                    type="date"
                    value={f.data_fine}
                    onChange={e => aggiornaFase(idx, 'data_fine', e.target.value)}
                    className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm"
                  />
                </td>
                <td className="p-2">
                  <input
                    type="number"
                    value={f.ore_vendute}
                    onChange={e => aggiornaFase(idx, 'ore_vendute', Number(e.target.value) || 0)}
                    className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm"
                  />
                </td>
                <td className="p-2 text-center">
                  {fasi.length > 1 && (
                    <button
                      onClick={() => rimuoviFase(idx)}
                      className="text-red-400 hover:text-red-300 text-sm"
                      title="Rimuovi fase"
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
        onClick={aggiungiFase}
        className="text-sm text-blue-400 hover:text-blue-300"
      >
        + Aggiungi fase
      </button>

      {/* Box riepilogo ore */}
      <div className={`rounded-lg p-3 text-sm border ${
        oreQuadrano ? 'bg-green-900/20 border-green-800/50 text-green-300' :
        'bg-amber-900/20 border-amber-800/50 text-amber-300'
      }`}>
        <div className="flex justify-between items-center">
          <span>Totale ore fasi: <strong>{totaleOre}h</strong> / Budget progetto: <strong>{budgetProgetto}h</strong></span>
          {oreQuadrano ? (
            <span>✓ Le ore quadrano</span>
          ) : (
            <span>⚠ Differenza: {Math.abs(totaleOre - budgetProgetto)}h ({totaleOre > budgetProgetto ? 'eccesso' : 'mancanti'})</span>
          )}
        </div>
      </div>
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════════
// Step 3 — Task iniziali (opzionale)
// ═════════════════════════════════════════════════════════════════════════

function StepTaskIniziali({ fasi, taskIniziali, onChange, dipendenti }) {

  function aggiungiTask() {
    onChange([
      ...taskIniziali,
      { nome: '', fase_idx: 0, dipendente_id: '', ore_stimate: 0, data_inizio: '', data_fine: '' }
    ])
  }

  function rimuoviTask(idx) {
    onChange(taskIniziali.filter((_, i) => i !== idx))
  }

  function aggiornaTask(idx, campo, valore) {
    const nuovi = [...taskIniziali]
    nuovi[idx] = { ...nuovi[idx], [campo]: valore }
    onChange(nuovi)
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold mb-1">Task iniziali <span className="text-sm font-normal text-gray-500">(opzionali)</span></h3>
        <p className="text-xs text-gray-500">
          I task sono dinamici e si aggiungono nel tempo dal Cantiere. Se hai già task definiti, puoi inserirli qui adesso.
        </p>
      </div>

      <div className="bg-blue-900/20 border border-blue-800/50 rounded-lg p-3 text-xs text-blue-300/80">
        💡 <strong>Salta questo step se non hai ancora task definiti.</strong> Potrai sempre aggiungerli più tardi dal Cantiere.
      </div>

      {taskIniziali.length === 0 ? (
        <div className="bg-gray-900/40 border border-gray-800 border-dashed rounded-lg p-6 text-center">
          <p className="text-sm text-gray-500 italic mb-3">Nessun task iniziale.</p>
          <button
            onClick={aggiungiTask}
            className="text-sm text-blue-400 hover:text-blue-300"
          >
            + Aggiungi un primo task
          </button>
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
                  <th className="w-10"></th>
                </tr>
              </thead>
              <tbody>
                {taskIniziali.map((t, idx) => (
                  <tr key={idx} className="border-t border-gray-800">
                    <td className="p-2">
                      <input
                        type="text"
                        value={t.nome}
                        onChange={e => aggiornaTask(idx, 'nome', e.target.value)}
                        placeholder="Nome task"
                        className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm"
                      />
                    </td>
                    <td className="p-2">
                      <select
                        value={t.fase_idx}
                        onChange={e => aggiornaTask(idx, 'fase_idx', Number(e.target.value))}
                        className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm"
                      >
                        {fasi.map((f, i) => (
                          <option key={i} value={i}>
                            {f.nome || `Fase ${i + 1}`}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="p-2">
                      <select
                        value={t.dipendente_id}
                        onChange={e => aggiornaTask(idx, 'dipendente_id', e.target.value)}
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
                        onChange={e => aggiornaTask(idx, 'ore_stimate', Number(e.target.value) || 0)}
                        className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm"
                      />
                    </td>
                    <td className="p-2 text-center">
                      <button
                        onClick={() => rimuoviTask(idx)}
                        className="text-red-400 hover:text-red-300 text-sm"
                      >
                        🗑
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button
            onClick={aggiungiTask}
            className="text-sm text-blue-400 hover:text-blue-300"
          >
            + Aggiungi task
          </button>
        </>
      )}
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════════
// StepIndicator — visualizza progresso wizard in cima
// ═════════════════════════════════════════════════════════════════════════

function StepIndicator({ num, label, attivo, fatto }) {
  return (
    <div className="flex items-center gap-2 flex-shrink-0">
      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold ${
        fatto ? 'bg-green-600 text-white' :
        attivo ? 'bg-blue-600 text-white' :
        'bg-gray-700 text-gray-400'
      }`}>
        {fatto ? '✓' : num}
      </div>
      <span className={`text-xs ${attivo ? 'text-gray-200 font-medium' : 'text-gray-500'}`}>
        {label}
      </span>
    </div>
  )
}
