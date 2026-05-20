// ═════════════════════════════════════════════════════════════════════════
// Cantiere.jsx — Pagina di scrittura progetti (URL /cantiere)
//
// Scopo (Step 2.7, scheletro 19/05/2026 sera):
//   È IL POSTO dove si lavora attivamente sui progetti. Tre funzioni perenni:
//
//   1. CREARE nuovi progetti (bozza o "Da iniziare" / "In esecuzione" diretti)
//      → via Wizard guidato (Step 2.7 parte 2, domani)
//
//   2. COMPLETARE BOZZE esistenti → ripresa di progetti in stato "Bozza" che
//      avevano nome+cliente ma fasi/task incompleti
//
//   3. DETTAGLIARE PROGETTI ATTIVI/SOSPESI → principio cardine dinamismo:
//      i task si sviluppano nel corso dei mesi, le ore vendute al cliente
//      sono quelle delle FASI, i task vengono aggiunti progressivamente.
//      Da qui si seleziona un progetto attivo e si aggiungono task alla
//      fase appropriata.
//
// Routing:
//   /cantiere → questa pagina (lista + entry point Wizard)
//   /cantiere/:id → CantiereDettaglio (vecchia pagina di modifica, transitoria)
//
// Approfondimento solo-lettura → /elenco/{id} (ElencoDettaglio).
//
// Status implementazione (19/05/2026 fine giornata):
//   [✓] Scheletro pagina, sidebar voce, route
//   [ ] Lista bozze interattiva con "Riprendi" → Wizard
//   [ ] Lista progetti attivi/sospesi con "Aggiungi task" → mini-Wizard
//   [ ] Wizard creazione nuovo progetto (multi-step: anagrafica → fasi → task)
//   [ ] Wizard staffing progressivo (per progetti esistenti)
//
// ═════════════════════════════════════════════════════════════════════════

import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchGanttStrutturato, createProgettoCompleto, completaProgetto } from '../api'
import StatoBadge from '../components/_shared/StatoBadge'
import WizardCreazioneProgetto from '../components/cantiere/WizardCreazioneProgetto'
import AggiungiTaskModal from '../components/cantiere/AggiungiTaskModal'


// ── Trasformazione: progetto da /gantt/strutturato → bozzaIniziale Wizard ──
// Il Wizard vuole le date come stringa '' (non null, per gli <input date>) e
// i task "piatti" con fase_idx invece che annidati nelle fasi.
function progettoABozzaIniziale(p) {
  const fasi = (p.fasi || []).map(f => ({
    nome: f.nome || '',
    ordine: f.ordine || 1,
    data_inizio: f.data_inizio || '',
    data_fine: f.data_fine || '',
    ore_vendute: f.ore_vendute || 0,
  }))
  // Task: appiattiti, con fase_idx = posizione della fase di appartenenza.
  const task_iniziali = []
  ;(p.fasi || []).forEach((f, idx) => {
    ;(f.tasks || []).forEach(t => {
      task_iniziali.push({
        nome: t.nome || '',
        fase_idx: idx,
        dipendente_id: t.dipendente_id || '',
        ore_stimate: t.ore_stimate || 0,
        data_inizio: t.data_inizio || '',
        data_fine: t.data_fine || '',
      })
    })
  })
  return {
    id: p.id,
    nome: p.nome || '',
    cliente: p.cliente || '',
    tipologia: p.tipologia || 'ordinario',
    pm_id: p.pm_id || '',
    data_inizio: p.data_inizio || '',
    data_fine: p.data_fine || '',
    budget_ore: p.budget_ore || 0,
    fasi,
    task_iniziali,
  }
}


export default function CantierePage() {
  const navigate = useNavigate()
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [errore, setErrore] = useState(null)
  const [wizardAperto, setWizardAperto] = useState(false)
  // bozzaSelezionata: se valorizzata, il Wizard si apre in modalità
  // "completa bozza" precaricato; se null, modalità "crea da zero".
  const [bozzaSelezionata, setBozzaSelezionata] = useState(null)
  // progettoStaffing: se valorizzato, è aperto il modale "Aggiungi task"
  // su quel progetto.
  const [progettoStaffing, setProgettoStaffing] = useState(null)

  const caricaCantiere = useCallback(() => {
    setLoading(true)
    setErrore(null)
    return fetchGanttStrutturato({ stato: 'all' })
      .then(d => setData(d || []))
      .catch(e => setErrore(e.message || 'Errore di caricamento'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    caricaCantiere()
  }, [caricaCantiere])

  // Categorizzazione per sezione
  const bozze = useMemo(() => data.filter(p => p.stato === 'Bozza'), [data])
  const attiviSospesi = useMemo(
    () => data.filter(p => p.stato === 'In esecuzione' || p.stato === 'Sospeso'),
    [data]
  )

  return (
    <div className="max-w-6xl">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <span>🔨</span> Cantiere
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Crea progetti, completa bozze, dettaglia progressivamente i progetti attivi.
          </p>
        </div>
        <button
          onClick={() => { setBozzaSelezionata(null); setWizardAperto(true) }}
          title="Apri Wizard creazione nuovo progetto"
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-semibold transition-colors"
        >
          ＋ Nuovo progetto
        </button>
      </div>

      {/* Wizard creazione / completamento bozza (modale) */}
      {wizardAperto && (
        <WizardCreazioneProgetto
          bozzaIniziale={bozzaSelezionata}
          onClose={() => { setWizardAperto(false); setBozzaSelezionata(null) }}
          onCreaProgetto={async (payload, modalitaBozza) => {
            // Step 2.7 (20/05/2026): submit reale via endpoint transazionale.
            // L'errore NON viene inghiottito qui: viene rilanciato così il
            // Wizard può mostrarlo e restare aperto (l'utente corregge e
            // riprova). Il Wizard si chiude solo a operazione riuscita.
            if (modalitaBozza) {
              // Completamento bozza: PUT /progetti/{id}/completo
              await completaProgetto(payload.progetto.id, payload)
            } else {
              // Creazione nuovo progetto: POST /progetti/completo
              await createProgettoCompleto(payload)
            }
            setWizardAperto(false)
            setBozzaSelezionata(null)
            await caricaCantiere()  // il progetto compare/aggiornato subito
          }}
        />
      )}

      {/* Modale "Aggiungi task" (staffing progressivo) */}
      {progettoStaffing && (
        <AggiungiTaskModal
          progetto={progettoStaffing}
          onClose={() => setProgettoStaffing(null)}
          onTaskAggiunti={async () => {
            await caricaCantiere()  // i task aggiunti compaiono subito
          }}
        />
      )}

      {/* Contenuto */}
      {loading ? (
        <p className="text-gray-400 py-8">Caricamento Cantiere…</p>
      ) : errore ? (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4">
          <p className="text-red-300">Errore: {errore}</p>
        </div>
      ) : (
        <>
          {/* Sezione 1 — Bozze da completare */}
          <SezioneCantiere
            titolo="📝 Bozze da completare"
            descrizione="Progetti iniziati ma non ancora avviati. Riprendi per finire la pianificazione."
            progetti={bozze}
            ctaLabel="Riprendi"
            ctaDisabled={false}
            ctaTooltip="Apri il Wizard precaricato per completare questa bozza"
            onCta={(progetto) => {
              setBozzaSelezionata(progettoABozzaIniziale(progetto))
              setWizardAperto(true)
            }}
            emptyMessage="Nessuna bozza in sospeso."
            navigate={navigate}
            colorAccent="#f59e0b"
          />

          {/* Sezione 2 — Progetti attivi/sospesi (per staffing progressivo) */}
          <SezioneCantiere
            titolo="🔧 Progetti attivi e sospesi"
            descrizione="Progetti in corso a cui aggiungere task progressivamente — i task si sviluppano nel tempo, le ore vendute restano quelle delle fasi."
            progetti={attiviSospesi}
            ctaLabel="Aggiungi task"
            ctaDisabled={false}
            ctaTooltip="Aggiungi uno o più task a una fase di questo progetto"
            onCta={(progetto) => setProgettoStaffing(progetto)}
            emptyMessage="Nessun progetto attivo o sospeso al momento."
            navigate={navigate}
            colorAccent="#3b82f6"
          />

          {/* Nota piano */}
          <div className="mt-8 bg-gray-900/60 border border-gray-800 rounded-lg p-4 text-xs text-gray-500">
            <div className="font-medium text-gray-400 mb-1">Status scheletro Cantiere</div>
            <p>
              Questa pagina è uno scheletro funzionale. Step 2.7 implementerà
              il Wizard di creazione progetto (multi-step) e i flussi di
              ripresa bozza + staffing progressivo. Vedi handoff v18.
            </p>
          </div>
        </>
      )}
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════════
// SezioneCantiere — blocco lista di progetti con CTA contestuale.
// Riusabile per le tre sezioni della pagina (bozze, attivi, eventualmente
// "completati" o altro in futuro).
// ═════════════════════════════════════════════════════════════════════════

function SezioneCantiere({ titolo, descrizione, progetti, ctaLabel, ctaDisabled, ctaTooltip, onCta, emptyMessage, navigate, colorAccent }) {
  return (
    <section className="mb-8">
      <div className="mb-3">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          {titolo}
          <span className="text-xs text-gray-500 font-normal">({progetti.length})</span>
        </h2>
        <p className="text-xs text-gray-500 mt-1">{descrizione}</p>
      </div>

      {progetti.length === 0 ? (
        <div className="bg-gray-900/40 border border-gray-800 border-dashed rounded-lg p-6 text-center">
          <p className="text-sm text-gray-500 italic">{emptyMessage}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {progetti.map(p => (
            <CardCantiere
              key={p.id}
              progetto={p}
              ctaLabel={ctaLabel}
              ctaDisabled={ctaDisabled}
              ctaTooltip={ctaTooltip}
              onCta={onCta}
              navigate={navigate}
              colorAccent={colorAccent}
            />
          ))}
        </div>
      )}
    </section>
  )
}


function CardCantiere({ progetto, ctaLabel, ctaDisabled, ctaTooltip, onCta, navigate, colorAccent }) {
  const nTaskTot = (progetto.fasi || []).reduce((s, f) => s + (f.tasks?.length || 0), 0)
  const sforamento = progetto.ore_vendute_totali > 0 && progetto.ore_consumate_totali > progetto.ore_vendute_totali

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 hover:border-gray-700 transition-colors overflow-hidden">
      <div className="flex">
        {/* Bandina laterale colorata */}
        <div style={{ width: 4, backgroundColor: colorAccent }} />

        <div className="flex-1 px-4 py-3 flex items-center justify-between flex-wrap gap-3">
          {/* Info progetto: nome + meta */}
          <div className="flex items-center gap-3 min-w-0 flex-1">
            <button
              onClick={() => navigate(`/elenco/${progetto.id}`)}
              className="text-lg font-semibold text-gray-200 hover:text-blue-300 hover:underline truncate"
              title="Apri approfondimento (lettura)"
            >
              {progetto.nome}
            </button>
            <span className="text-xs text-gray-500 font-mono flex-shrink-0">{progetto.id}</span>
            <StatoBadge stato={progetto.stato} />
          </div>

          {/* Meta extra */}
          <div className="text-xs text-gray-400 flex items-center gap-3 flex-wrap">
            <span>Cliente: <span className="text-gray-200">{progetto.cliente || '—'}</span></span>
            <span className="text-gray-700">|</span>
            <span>{progetto.n_fasi} {progetto.n_fasi === 1 ? 'fase' : 'fasi'} · {nTaskTot} task</span>
            {progetto.ore_vendute_totali > 0 && (
              <>
                <span className="text-gray-700">|</span>
                <span>Ore: <span className={sforamento ? 'text-red-400 font-medium' : 'text-gray-200'}>
                  {progetto.ore_consumate_totali}h
                </span>
                <span className="text-gray-600"> / {progetto.ore_vendute_totali}h</span></span>
              </>
            )}
          </div>

          {/* CTA contestuale */}
          <button
            disabled={ctaDisabled}
            onClick={() => { if (!ctaDisabled && onCta) onCta(progetto) }}
            title={ctaTooltip}
            className={`px-3 py-1.5 rounded text-sm font-medium flex-shrink-0 ${
              ctaDisabled
                ? 'bg-gray-700 text-gray-500 cursor-not-allowed opacity-60'
                : 'bg-blue-600 hover:bg-blue-500 text-white'
            }`}
          >
            {ctaLabel} →
          </button>
        </div>
      </div>
    </div>
  )
}
