/**
 * ═════════════════════════════════════════════════════════════════════════
 * VistaPM — il canale delle segnalazioni del proprio gruppo
 * ═════════════════════════════════════════════════════════════════════════
 *
 * Il PM legge cosa gli sta dicendo chi lavora sui progetti che DIRIGE. È il
 * primo consumatore di `ore_stimate_residue`, il campo costruito il 04/09 e
 * fin qui scritto da un form e letto da nessuno.
 *
 * ── PERCHÉ UN COMPONENTE A SÉ, E NON UN RAMO DI VistaManagement ──────
 * Le due viste rispondono a domande diverse:
 *
 *   management → «chi ha compilato?»   sintesi, KPI, dettaglio a richiesta.
 *                Con 38 progetti nessuno può leggere ogni segnalazione, e
 *                pretenderlo significherebbe non leggerne nessuna.
 *   PM         → «cosa mi stanno dicendo?»   il contenuto È il lavoro, e va
 *                messo davanti senza chiedere un click.
 *
 * Stesso endpoint e stesso payload — è il BACKEND a decidere il perimetro dal
 * ruolo (`progetti_diretti_da`, non `progetti_attivi_visibili`: quest'ultima
 * includerebbe i progetti dove il pm ha solo un task, portandolo da 8 a 14
 * dipendenti su 18). Qui non si filtra niente: arriva già il gruppo giusto.
 *
 * ── IL DEFAULT È DISTESO ─────────────────────────────────────────────
 * Le righe che portano una segnalazione si aprono da sole; quelle di sole ore
 * restano una riga sola, in coda. È la differenza fra un'inbox e un archivio:
 * in un archivio si cerca, in un'inbox si legge quello che è arrivato.
 *
 * ── NIENTE PastigliaSemaforo ─────────────────────────────────────────
 * Quella vuole `{colore, origine}` e questo payload non li ha. Fabbricarne uno
 * da `in_ritardo` metterebbe una pastiglia-semaforo accanto a qualcosa che
 * semaforo non è, e il suo tooltip parla un'altra lingua (grigio per i fermi,
 * origine dai figli). Qui i segni sono propri: badge rosso per il blocco,
 * ambra per lo scaduto e per la stima residua.
 */

import React, { useState, useEffect } from 'react'
import { fetchConsuntiviSettimana } from '../../api'

const fmtOre = (n) => `${(n ?? 0).toFixed(1).replace(/\.0$/, '')}h`

/**
 * Una riga porta una SEGNALAZIONE se dice qualcosa oltre alle ore.
 *
 * `!= null` sul residuo e non un test di verità: 0 significa «non manca più
 * niente», che è la dichiarazione più informativa che il campo possa portare —
 * un `if (r.ore_stimate_residue)` la scarterebbe proprio quando conta.
 */
export function haSegnale(r) {
  return Boolean(
    r.nota ||
    r.ore_stimate_residue != null ||
    r.stato_dichiarato === 'Bloccato' ||
    r.in_ritardo
  )
}

function RigaSegnalazione({ r }) {
  const bloccato = r.stato_dichiarato === 'Bloccato'
  return (
    <div className={`rounded-lg p-3 border-l-2 ${
      bloccato ? 'bg-red-950/20 border-red-700' : 'bg-amber-950/15 border-amber-700/70'
    }`}>
      <div className="flex items-baseline justify-between gap-3 flex-wrap">
        <span className="text-sm text-gray-200">
          {r.task_nome}
          <span className="text-xs text-gray-600 ml-2">{r.progetto}</span>
        </span>
        <span className="flex items-center gap-2 text-[11px] shrink-0">
          {bloccato && (
            <span className="px-1.5 py-0.5 rounded bg-red-900/50 text-red-200 font-medium">
              Bloccato
            </span>
          )}
          {r.in_ritardo && (
            <span className="px-1.5 py-0.5 rounded bg-amber-900/40 text-amber-200"
                  title={`Doveva finire il ${r.data_fine}`}>
              ⚠ scaduto {r.data_fine}
            </span>
          )}
          <span className="font-mono text-gray-300">{fmtOre(r.ore)}</span>
        </span>
      </div>

      {/* LA STIMA RESIDUA — la sua prima resa da quando esiste. Non è
          `ore_rimanenti` (piano meno consumato, aritmetica sul budget): è
          quanto LAVORO manca, secondo chi lo sta facendo. */}
      {r.ore_stimate_residue != null && (
        <p className="text-xs mt-1.5">
          <span className="text-gray-500">Stima per finire: </span>
          <span className="text-amber-300 font-medium">
            {r.ore_stimate_residue === 0
              ? 'non manca più niente'
              : `${fmtOre(r.ore_stimate_residue)} ancora`}
          </span>
          {r.ore_stimate_residue > 0 && (
            <span className="text-gray-600"> · dichiarate {fmtOre(r.ore)} questa settimana</span>
          )}
        </p>
      )}

      {/* Il COSA, accanto al QUANTO. */}
      {r.nota && <p className="text-xs text-gray-300 mt-1.5 italic">«{r.nota}»</p>}
    </div>
  )
}

export default function VistaPM() {
  const [dati, setDati] = useState([])
  const [loading, setLoading] = useState(true)
  const [errore, setErrore] = useState(null)

  useEffect(() => {
    fetchConsuntiviSettimana()
      .then((d) => setDati(d || []))
      .catch((e) => setErrore(e.message || 'Non riesco a caricare le dichiarazioni'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-gray-400">Carico le dichiarazioni del gruppo…</p>
  if (errore) return (
    <div className="text-sm bg-red-900/30 border border-red-800 text-red-200 rounded-lg px-4 py-3">
      {errore}
    </div>
  )

  const compilati = dati.filter(d => d.compilato)
  const mancanti = dati.filter(d => !d.compilato)
  const totSegnali = compilati.reduce(
    (s, d) => s + d.ore_per_task.filter(haSegnale).length, 0)

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-gray-100">Le dichiarazioni dei tuoi</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          Settimana corrente, sui progetti che dirigi.{' '}
          {totSegnali > 0
            ? `${totSegnali} ${totSegnali === 1 ? 'segnalazione' : 'segnalazioni'} da leggere.`
            : 'Nessuna segnalazione.'}
        </p>
      </div>

      {compilati.length === 0 && mancanti.length === 0 && (
        <p className="text-sm text-gray-500 italic">
          Nessuno del gruppo ha task attivi questa settimana.
        </p>
      )}

      {/* ── CHI HA RISPOSTO ─────────────────────────────────────────── */}
      {compilati.map((d) => {
        const conSegnale = d.ore_per_task.filter(haSegnale)
        const soleOre = d.ore_per_task.filter(r => !haSegnale(r))
        return (
          <div key={d.dipendente_id} className="bg-gray-900 rounded-xl border border-gray-800 p-4">
            <div className="flex items-baseline justify-between gap-3 flex-wrap mb-3">
              <span className="text-sm">
                <span className="font-medium text-gray-100">{d.nome}</span>
                <span className="text-xs text-gray-500 ml-2">{d.profilo}</span>
              </span>
              <span className="text-xs font-mono text-gray-400">
                {fmtOre(d.totale_ore)}<span className="text-gray-600">/{d.ore_contrattuali}h</span>
              </span>
            </div>

            {conSegnale.length > 0 && (
              <div className="space-y-2">
                {conSegnale.map((r) => <RigaSegnalazione key={r.task_id} r={r} />)}
              </div>
            )}

            {/* Le righe di SOLE ORE non spariscono — sarebbero un buco nel
                totale — ma non occupano spazio come quelle che parlano. */}
            {soleOre.length > 0 && (
              <div className={conSegnale.length > 0 ? 'mt-3 pt-2 border-t border-gray-800' : ''}>
                {soleOre.map((r) => (
                  <div key={r.task_id} className="flex justify-between text-xs py-1">
                    <span className="text-gray-500 truncate">
                      {r.task_nome}
                      <span className="text-gray-700 ml-2">{r.progetto}</span>
                    </span>
                    <span className="font-mono text-gray-500 shrink-0 ml-3">{fmtOre(r.ore)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}

      {/* ── CHI NON HA ANCORA RISPOSTO ──────────────────────────────
          In fondo e non in cima: sono un promemoria, non il contenuto. E
          «non ha risposto» ora significa davvero questo — dal 07/09 chi
          dichiara zero ore con una nota conta come compilante. */}
      {mancanti.length > 0 && (
        <div className="bg-gray-900/60 rounded-xl border border-gray-800 p-4">
          <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">
            Non hanno ancora risposto ({mancanti.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {mancanti.map((d) => (
              <span key={d.dipendente_id}
                    className="text-xs px-2 py-1 rounded-md bg-gray-800 text-gray-400"
                    title={d.profilo}>
                {d.nome}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
