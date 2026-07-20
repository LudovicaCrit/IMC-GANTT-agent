import React, { useState, useEffect } from 'react'
import { fetchMarginiEconomia } from '../api'

/* ── Helpers ──────────────────────────────────────────────────────── */
const fmtEur = (n) =>
  `€${(n ?? 0).toLocaleString('it-IT', { maximumFractionDigits: 0 })}`

const fmtPct = (n) => `${(n ?? 0).toFixed(1)}%`

const fmtPp = (n) => `${n >= 0 ? '' : '+'}${Math.abs(n).toFixed(1)} pp`

/* ── Badge erosione ───────────────────────────────────────────────
   Erosione positiva = stiamo consumando più del previsto (male).
   Erosione negativa = stiamo consumando meno (bene, efficienza).
   ─────────────────────────────────────────────────────────────────── */
function ErosioneBadge({ eur, pp, size = 'md' }) {
  const negativa = eur < 0
  const grave = pp >= 15
  const media = pp >= 5
  const lieve = pp > 0

  let color = 'text-gray-400 bg-gray-800 border-gray-700'
  if (negativa) color = 'text-emerald-300 bg-emerald-900/20 border-emerald-800'
  else if (grave) color = 'text-red-300 bg-red-900/20 border-red-800'
  else if (media) color = 'text-amber-300 bg-amber-900/20 border-amber-800'
  else if (lieve) color = 'text-yellow-200/70 bg-yellow-900/10 border-yellow-900/50'

  const pad = size === 'lg' ? 'px-3 py-1.5 text-base' : 'px-2 py-1 text-xs'

  return (
    <span className={`inline-flex items-baseline gap-2 rounded-lg border ${color} ${pad}`}>
      <span className="font-bold">{negativa ? '−' : ''}{fmtEur(Math.abs(eur))}</span>
      <span className="opacity-70">{fmtPp(pp)}</span>
    </span>
  )
}

/* ── Card azienda ─────────────────────────────────────────────────── */
function CardAzienda({ a }) {
  const efficiente = a.erosione_commerciale_eur < 0

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="font-semibold text-lg">{a.azienda_nome}</h3>
          <p className="text-xs text-gray-500">{a.n_progetti} progetti commerciali</p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-green-400">{fmtEur(a.margine_consumato)}</p>
          <p className="text-xs text-gray-500">margine reale · {fmtPct(a.margine_consumato_pct)}</p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 text-sm mb-4">
        <div>
          <p className="text-xs text-gray-500">Valore</p>
          <p className="font-medium">{fmtEur(a.valore_contratto)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Costo sostenuto</p>
          <p className="font-medium text-orange-400">{fmtEur(a.costo_consumato)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Margine sul venduto</p>
          <p className="font-medium text-gray-300">{fmtPct(a.margine_venduto_pct)}</p>
        </div>
      </div>

      <div className="pt-3 border-t border-gray-800">
        <p className="text-xs text-gray-500 mb-2">
          {efficiente ? 'Efficienza rispetto al venduto' : 'Erosione rispetto al venduto'}
        </p>
        <ErosioneBadge
          eur={a.erosione_commerciale_eur}
          pp={a.erosione_commerciale_pp}
          size="lg"
        />
      </div>
    </div>
  )
}

/* ── Pagina ───────────────────────────────────────────────────────── */
export default function Economia() {
  const [dati, setDati] = useState(null)
  const [loading, setLoading] = useState(true)
  const [errore, setErrore] = useState(null)
  const [aperto, setAperto] = useState(null)

  useEffect(() => {
    fetchMarginiEconomia()
      .then(setDati)
      .catch((e) => setErrore(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-gray-400">Caricamento…</p>
  if (errore) return <p className="text-red-400">Errore: {errore}</p>
  if (!dati) return null

  const progetti = dati.progetti ?? []
  const aziende = dati.totali_per_azienda ?? []

  // Totali di portafoglio (somma dei rami)
  const tot = aziende.reduce(
    (acc, a) => ({
      valore: acc.valore + a.valore_contratto,
      costo: acc.costo + a.costo_consumato,
      margine: acc.margine + a.margine_consumato,
      erosione: acc.erosione + a.erosione_commerciale_eur,
      progetti: acc.progetti + a.n_progetti,
    }),
    { valore: 0, costo: 0, margine: 0, erosione: 0, progetti: 0 }
  )

  const erosionePp = tot.valore > 0 ? (tot.erosione / tot.valore) * 100 : 0

  // Progetti ordinati per erosione decrescente: i più erosi in cima
  const ordinati = [...progetti].sort(
    (a, b) => b.erosione_commerciale_pp - a.erosione_commerciale_pp
  )

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">💰 Economia</h1>
      <p className="text-sm text-yellow-400 mb-6">🔒 Sezione riservata al management</p>

      {/* ═══ FASCIA 1 — Portafoglio ═══ */}
      <div className="grid grid-cols-5 gap-4 mb-8">
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Valore portafoglio</p>
          <p className="text-2xl font-bold mt-1">{fmtEur(tot.valore)}</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Costo sostenuto</p>
          <p className="text-2xl font-bold mt-1 text-orange-400">{fmtEur(tot.costo)}</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Margine reale</p>
          <p className="text-2xl font-bold mt-1 text-green-400">{fmtEur(tot.margine)}</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">
            {tot.erosione < 0 ? 'Efficienza netta' : 'Erosione netta'}
          </p>
          <p className={`text-2xl font-bold mt-1 ${tot.erosione < 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {tot.erosione < 0 ? '−' : ''}{fmtEur(Math.abs(tot.erosione))}
          </p>
          <p className="text-xs text-gray-500 mt-1 leading-snug">
            {aziende.map((a) => (
              <span key={a.azienda_id} className="block">
                {a.azienda_nome}{' '}
                <span className={a.erosione_commerciale_eur < 0 ? 'text-emerald-400' : 'text-red-400'}>
                  {a.erosione_commerciale_eur < 0 ? '−' : '+'}
                  {fmtEur(Math.abs(a.erosione_commerciale_eur))}
                </span>
              </span>
            ))}
          </p>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <p className="text-sm text-gray-400">Progetti commerciali</p>
          <p className="text-2xl font-bold mt-1">{tot.progetti}</p>
        </div>
      </div>

      {/* ═══ FASCIA 2 — I due rami ═══ */}
      <h2 className="text-lg font-semibold mb-3">Andamento per società</h2>
      <div className="grid grid-cols-2 gap-4 mb-3">
        {aziende.map((a) => (
          <CardAzienda key={a.azienda_id} a={a} />
        ))}
      </div>

      {/* Postilla sulle due erosioni */}
      <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-3 mb-8">
        <p className="text-xs text-gray-500 leading-relaxed">
          <span className="text-gray-400 font-medium">Due letture dell'erosione.</span>{' '}
          L'<strong className="text-gray-400">erosione commerciale</strong> confronta il margine
          sulle ore vendute con quello sulle ore realmente consumate: risponde a
          «è un buon affare?». L'<strong className="text-gray-400">erosione operativa</strong>{' '}
          confronta il margine sul piano corrente con quello reale: risponde a «lo stiamo
          gestendo bene?». Oggi i due valori coincidono perché le ore pianificate non sono
          ancora state riviste rispetto alle stime iniziali — divergeranno appena i PM
          aggiorneranno i piani in Cantiere.
        </p>
      </div>

      {/* ═══ FASCIA 3 — Progetti ═══ */}
      <h2 className="text-lg font-semibold mb-3">
        Progetti <span className="text-sm font-normal text-gray-500">— ordinati per erosione</span>
      </h2>
      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-800 text-gray-400">
            <tr>
              <th className="text-left px-4 py-3">Progetto</th>
              <th className="text-right px-4 py-3">Valore</th>
              <th className="text-right px-4 py-3">Ore cons.</th>
              <th className="text-right px-4 py-3">Margine reale</th>
              <th className="text-center px-4 py-3">Erosione commerciale</th>
              <th className="text-center px-4 py-3">Erosione operativa</th>
              <th className="text-center px-3 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {ordinati.map((p) => (
              <React.Fragment key={p.progetto_id}>
                <tr
                  className={`border-t border-gray-800 hover:bg-gray-800/50 transition-colors ${
                    p.erosione_commerciale_pp >= 15 ? 'bg-red-900/10' : ''
                  }`}
                >
                  <td className="px-4 py-3">
                    <p className="font-medium flex items-center gap-2">
                      {p.nome}
                      {p.costo_stimato && (
                        <span
                          title="Costo stimato: alcuni task non hanno assegnatario o ore pianificate. Pianificazione incompleta."
                          className="text-amber-400 text-xs cursor-help"
                        >
                          ⚠
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-gray-500">
                      {p.cliente} · {p.azienda_nome}
                    </p>
                  </td>
                  <td className="px-4 py-3 text-right font-medium">{fmtEur(p.valore_contratto)}</td>
                  <td className="px-4 py-3 text-right text-gray-400">{p.ore_consuntivate}h</td>
                  <td className="px-4 py-3 text-right font-bold text-green-400">
                    {fmtEur(p.margine_consumato)}
                    <br />
                    <span className="text-xs font-normal text-gray-500">
                      {fmtPct(p.margine_consumato_pct)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <ErosioneBadge
                      eur={p.erosione_commerciale_eur}
                      pp={p.erosione_commerciale_pp}
                    />
                  </td>
                  <td className="px-4 py-3 text-center">
                    <ErosioneBadge
                      eur={p.erosione_operativa_eur}
                      pp={p.erosione_operativa_pp}
                    />
                  </td>
                  <td className="px-3 py-3 text-center">
                    <button
                      onClick={() => setAperto(aperto === p.progetto_id ? null : p.progetto_id)}
                      className="text-gray-400 hover:text-white text-xs px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 transition-colors"
                    >
                      {aperto === p.progetto_id ? '▼' : '▶'}
                    </button>
                  </td>
                </tr>

                {/* Dettaglio: i tre margini + costi per persona */}
                {aperto === p.progetto_id && (
                  <tr>
                    <td colSpan={7} className="px-4 py-4 bg-gray-800/30">
                      {/* I tre margini */}
                      <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">
                        Le tre letture del margine
                      </p>
                      <div className="grid grid-cols-3 gap-3 mb-5">
                        <div className="bg-gray-800 rounded-lg px-4 py-3">
                          <p className="text-xs text-gray-500">Sul venduto (contratto)</p>
                          <p className="font-bold text-gray-200">{fmtEur(p.margine_venduto)}</p>
                          <p className="text-xs text-gray-500">
                            {fmtPct(p.margine_venduto_pct)} · costo {fmtEur(p.costo_venduto)}
                          </p>
                        </div>
                        <div className="bg-gray-800 rounded-lg px-4 py-3">
                          <p className="text-xs text-gray-500">Sul pianificato (piano PM)</p>
                          <p className="font-bold text-gray-200">{fmtEur(p.margine_pianificato)}</p>
                          <p className="text-xs text-gray-500">
                            {fmtPct(p.margine_pianificato_pct)} · costo {fmtEur(p.costo_pianificato)}
                          </p>
                        </div>
                        <div className="bg-gray-800 rounded-lg px-4 py-3 ring-1 ring-green-800/50">
                          <p className="text-xs text-gray-500">Sul consumato (reale)</p>
                          <p className="font-bold text-green-400">{fmtEur(p.margine_consumato)}</p>
                          <p className="text-xs text-gray-500">
                            {fmtPct(p.margine_consumato_pct)} · costo {fmtEur(p.costo_consumato)}
                          </p>
                        </div>
                      </div>

                      {/* Costi per persona */}
                      {p.dettaglio_persone?.length > 0 && (
                        <>
                          <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">
                            Costi per persona
                          </p>
                          <div className="grid grid-cols-2 gap-2">
                            {p.dettaglio_persone.map((dp, i) => (
                              <div
                                key={i}
                                className="flex items-center justify-between bg-gray-800 rounded-lg px-3 py-2 text-xs"
                              >
                                <div>
                                  <span className="font-medium">{dp.nome}</span>
                                  <span className="text-gray-500 ml-2">
                                    {dp.profilo} · €{dp.costo_ora}/h
                                  </span>
                                </div>
                                <div className="text-right">
                                  <span className="text-gray-300">{dp.ore.toFixed(0)}h</span>
                                  <span className="text-orange-400 ml-3 font-medium">
                                    {fmtEur(dp.costo)}
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </>
                      )}
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
