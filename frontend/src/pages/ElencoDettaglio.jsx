// ═════════════════════════════════════════════════════════════════════════
// ElencoDettaglio.jsx — Approfondimento read-only del progetto (URL /elenco/{id})
//
// Scopo (decisione di prodotto 19/05/2026 pom):
//   È la "lente di lettura" totale del progetto: anagrafica, KPI, persone,
//   fasi/task — TUTTO quello che esiste nel sistema, in modalità readonly.
//   Risponde alla domanda "quali progetti ci sono in azienda e com'è messo
//   questo?". Si arriva qui cliccando il nome del progetto dall'Elenco di
//   /gantt o cliccando una barra task in Timeline.
//
//   Per modificare il progetto, l'utente clicca "✏ Modifica in Cantiere"
//   e va alla pagina /cantiere (Step 2.7 da costruire) dove può creare,
//   completare, dettagliare progressivamente.
//
// Differenze rispetto a CantiereDettaglio.jsx (che adesso vive come
// "appendice storica" finché non viene rimosso al completamento di Step 2.7):
//   - Tutti i componenti chiamati con readonly={true}
//   - Nessuna callback di modifica (salva, aggiungi, elimina, cambiaStato)
//   - Nessun caricamento di dipendenti per modifica modali — solo per
//     visualizzazione in SezioneFasiTask readonly
//   - Bottone "✏ Modifica in Cantiere" in cima
//   - Tab Scenari mantenuto: è già read-only di natura (snapshot deterministico)
//
// Backend consumati (sola lettura):
//   GET /api/gantt/strutturato?progetto_id={id}  → gerarchia + aggregati
//   GET /api/dipendenti                          → per nominativi nelle tab
//
// Componenti riusati grazie all'estrazione 4a (18 mag):
//   KpiSintetici, BannerStato, SezioneAnagrafica, SezionePersone,
//   SezioneFasiTask — tutti accettano già il prop `readonly`.
//
// ═════════════════════════════════════════════════════════════════════════

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  fetchGanttStrutturato,
  fetchDipendenti,
} from '../api'

import BannerStato from '../components/cantiere/BannerStato'
import KpiSintetici from '../components/cantiere/KpiSintetici'
import SezioneAnagrafica from '../components/cantiere/SezioneAnagrafica'
import SezionePersone from '../components/cantiere/SezionePersone'
import SezioneFasiTask from '../components/cantiere/SezioneFasiTask'


// ─── Tab Scenari: snapshot deterministico (cloned from CantiereDettaglio) ──
// È read-only di natura: mostra criticità calcolate dai dati attuali.
// Lo stesso codice vive in CantiereDettaglio.jsx. Per ora duplicato:
// quando si rimuove CantiereDettaglio (Step 2.7 completo), questa è la
// "casa" naturale di TabScenari.

function calcolaCriticita(progetto) {
  const out = []
  const oggi = new Date()

  // Criticità progetto
  if (progetto.ore_vendute_totali > 0 && progetto.ore_consumate_totali > progetto.ore_vendute_totali) {
    const eccesso = progetto.ore_consumate_totali - progetto.ore_vendute_totali
    const pct = Math.round((eccesso / progetto.ore_vendute_totali) * 100)
    out.push({
      livello: pct > 50 ? 'alto' : 'medio',
      tipo: 'progetto',
      messaggio: `Sforamento ore: +${eccesso}h (+${pct}% sul venduto)`,
    })
  }

  if (progetto.data_fine) {
    const dFine = new Date(progetto.data_fine)
    if (dFine < oggi && progetto.stato !== 'Completato' && progetto.stato !== 'Annullato') {
      const gg = Math.floor((oggi - dFine) / (1000 * 60 * 60 * 24))
      out.push({
        livello: gg > 30 ? 'alto' : 'medio',
        tipo: 'progetto',
        messaggio: `Data fine progetto superata di ${gg} ${gg === 1 ? 'giorno' : 'giorni'}`,
      })
    }
  }

  // Criticità per fase
  progetto.fasi?.forEach(f => {
    if (f.ore_vendute > 0 && f.ore_consumate > f.ore_vendute) {
      const eccesso = f.ore_consumate - f.ore_vendute
      out.push({
        livello: eccesso > f.ore_vendute * 0.5 ? 'alto' : 'medio',
        tipo: 'fase',
        messaggio: `Fase "${f.nome}": sforamento ${eccesso}h`,
      })
    }

    if (f.data_fine) {
      const dFine = new Date(f.data_fine)
      if (dFine < oggi && f.stato !== 'Completata' && f.stato !== 'Annullata') {
        const gg = Math.floor((oggi - dFine) / (1000 * 60 * 60 * 24))
        out.push({
          livello: gg > 14 ? 'alto' : 'medio',
          tipo: 'fase',
          messaggio: `Fase "${f.nome}": data fine superata di ${gg} ${gg === 1 ? 'giorno' : 'giorni'}`,
        })
      }
    }

    const tuttiComp = f.tasks.every(t => t.stato === 'Completato')
    const almenoUnoCorso = f.tasks.some(t => t.stato === 'In corso')
    if (tuttiComp && f.tasks.length > 0 && f.stato !== 'Completata') {
      out.push({
        livello: 'basso',
        tipo: 'fase',
        messaggio: `Fase "${f.nome}": tutti i task completati ma fase ancora "${f.stato}"`,
      })
    }
    if (almenoUnoCorso && f.stato === 'Da iniziare') {
      out.push({
        livello: 'medio',
        tipo: 'fase',
        messaggio: `Fase "${f.nome}": task in corso ma fase ancora "Da iniziare"`,
      })
    }
  })

  return out
}

function TabScenari({ progetto }) {
  const criticita = useMemo(() => calcolaCriticita(progetto), [progetto])
  const livelliOrdine = { alto: 0, medio: 1, basso: 2 }
  const sorted = [...criticita].sort((a, b) => livelliOrdine[a.livello] - livelliOrdine[b.livello])

  return (
    <div>
      <div className="mb-4 bg-blue-900/30 border border-blue-700 rounded-lg p-4">
        <div className="text-blue-200 font-medium mb-1">📸 Snapshot criticità</div>
        <div className="text-sm text-blue-300/80">
          Calcolate dai dati attuali del progetto. In R2 questa tab ospiterà
          una IA propositiva ("what-if") in chat.
        </div>
      </div>

      {sorted.length === 0 ? (
        <div className="bg-green-900/30 border border-green-700 rounded-lg p-6 text-center">
          <div className="text-2xl mb-2">✅</div>
          <div className="text-green-200 font-medium">Nessuna criticità rilevata</div>
          <div className="text-sm text-green-300/80 mt-1">Il progetto procede entro i parametri.</div>
        </div>
      ) : (
        <div className="space-y-2">
          {sorted.map((c, i) => {
            const colore = c.livello === 'alto' ? 'red' : c.livello === 'medio' ? 'amber' : 'gray'
            return (
              <div key={i} className={`bg-${colore}-900/30 border border-${colore}-700 rounded-lg p-3 flex items-start gap-3`}>
                <div className={`text-${colore}-400 mt-0.5`}>
                  {c.livello === 'alto' ? '🔴' : c.livello === 'medio' ? '🟡' : '⚪'}
                </div>
                <div className="flex-1">
                  <div className="text-xs uppercase tracking-wide text-gray-500">
                    {c.tipo} · {c.livello}
                  </div>
                  <div className="text-sm">{c.messaggio}</div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}


// ─── Pagina principale ───────────────────────────────────────────────────

export default function ElencoDettaglioPage() {
  const { progettoId } = useParams()
  const navigate = useNavigate()
  const [progetto, setProgetto] = useState(null)
  const [dipendenti, setDipendenti] = useState([])
  const [loading, setLoading] = useState(true)
  const [errore, setErrore] = useState(null)
  const [tab, setTab] = useState('design')

  const ricarica = useCallback(async () => {
    try {
      const [data, dips] = await Promise.all([
        fetchGanttStrutturato({ progettoId }),
        fetchDipendenti(),
      ])
      if (!data || data.length === 0) {
        setErrore('Progetto non trovato')
        setProgetto(null)
      } else {
        setProgetto(data[0])
        setDipendenti(dips || [])
        setErrore(null)
      }
    } catch (e) {
      setErrore(e.message || 'Errore di caricamento')
    } finally {
      setLoading(false)
    }
  }, [progettoId])

  useEffect(() => {
    setLoading(true)
    ricarica()
  }, [ricarica])

  // ── Render ────────────────────────────────────────────────────────────

  if (loading) return <p className="text-gray-400">Caricamento scheda progetto…</p>
  if (errore) {
    return (
      <div className="max-w-2xl">
        <Link to="/gantt" className="text-sm text-blue-400 hover:text-blue-300">← Torna a GANTT</Link>
        <div className="mt-4 bg-red-900/30 border border-red-700 rounded-lg p-6">
          <h2 className="text-xl font-semibold text-red-200 mb-2">Errore</h2>
          <p className="text-red-300">{errore}</p>
        </div>
      </div>
    )
  }
  if (!progetto) return null

  return (
    <div className="max-w-5xl">
      {/* Breadcrumb */}
      <div className="mb-4">
        <Link to="/gantt" className="text-sm text-blue-400 hover:text-blue-300">← Torna a GANTT</Link>
      </div>

      {/* Header con bottone "Modifica in Cantiere" */}
      <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold mb-1">{progetto.nome}</h1>
          <div className="text-sm text-gray-500">
            <span className="font-mono">{progetto.id}</span>
            {progetto.cliente && <span> · {progetto.cliente}</span>}
          </div>
        </div>
        <button
          onClick={() => navigate('/cantiere')}
          title="Apri il Cantiere per modificare progetti o aggiungere task"
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-semibold transition-colors"
        >
          ✏ Modifica in Cantiere
        </button>
      </div>

      {/* Banner stato — readonly */}
      <BannerStato progetto={progetto} readonly={true} />

      {/* Tab switcher */}
      <div className="border-b border-gray-800 mb-6">
        <div className="flex gap-1">
          <TabButton attivo={tab === 'design'} onClick={() => setTab('design')}>
            ⚙ Design
          </TabButton>
          <TabButton attivo={tab === 'scenari'} onClick={() => setTab('scenari')}>
            🔍 Scenari
          </TabButton>
        </div>
      </div>

      {/* Contenuto tab — tutti i componenti in readonly */}
      {tab === 'design' && (
        <>
          <KpiSintetici progetto={progetto} readonly={true} />
          <SezioneAnagrafica progetto={progetto} readonly={true} />
          <SezionePersone progetto={progetto} dipendenti={dipendenti} readonly={true} />
          <SezioneFasiTask
            progetto={progetto}
            dipendenti={dipendenti}
            readonly={true}
          />
        </>
      )}

      {tab === 'scenari' && <TabScenari progetto={progetto} />}
    </div>
  )
}

function TabButton({ attivo, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`px-5 py-2.5 text-sm font-medium border-b-2 transition-colors ${
        attivo
          ? 'border-blue-500 text-blue-300'
          : 'border-transparent text-gray-500 hover:text-gray-300'
      }`}
    >
      {children}
    </button>
  )
}
