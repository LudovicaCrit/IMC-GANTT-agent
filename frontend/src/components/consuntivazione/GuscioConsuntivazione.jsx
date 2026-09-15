import React, { useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import VistaPM from './VistaPM'
import VistaManagement from './VistaManagement'

/* ── Il guscio della Consuntivazione: titolo, vista personale o di gruppo ──
 * Estratto da ConsuntivazioneUser.jsx il 15/09/2026, quando è nata la griglia
 * a ore accanto alla pagina a cursore. Le due pagine hanno la stessa testata e
 * la stessa vista di gruppo; cambia solo la settimana personale, che è
 * `children`.
 *
 * `vistaGruppo` è 'manager' | 'pm' | null, e governa INSIEME il bottone e la
 * resa. Una variabile sola per le due decisioni: tenendole separate, prima o
 * poi il bottone porta a una vista che non c'è, o la vista resta raggiungibile
 * senza bottone.
 * `null` per il ruolo 'user': non è un permesso negato da spiegare, è una
 * domanda che per lui non esiste. Il backend risponde comunque 403 — quella è
 * la rete; qui si toglie l'invito.
 *
 * L'INTESTAZIONE SOPRAVVIVE A TUTTO. La vista personale può fallire (errore su
 * /me) senza portarsi via titolo e navigazione, e la vista di gruppo non passa
 * dalle guardie di /me: un manager non deve restare fuori perché è fallita una
 * chiamata che non gli serviva.
 */
export default function GuscioConsuntivazione({ children }) {
  const { user } = useAuth()
  const vistaGruppo = (user?.ruolo_app === 'manager' || user?.ruolo_app === 'pm')
    ? user.ruolo_app
    : null
  // 'dipendente' | 'gruppo'. Default 'dipendente' per TUTTI, manager compresi:
  // anche chi supervisiona ha una propria settimana da compilare.
  const [vista, setVista] = useState('dipendente')

  return (
    <div className="max-w-6xl pb-6">
      <h1 className="text-3xl font-bold mb-1">⏱️ Consuntivazione</h1>
      {vistaGruppo && (
        <div className="flex gap-2 mb-6 mt-3">
          <button onClick={() => setVista('dipendente')}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              vista === 'dipendente' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-gray-200'
            }`}>
            👤 La mia settimana
          </button>
          <button onClick={() => setVista('gruppo')}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              vista === 'gruppo' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-gray-200'
            }`}>
            {vistaGruppo === 'pm' ? '📥 I miei progetti' : '📊 Tutta l\'azienda'}
          </button>
        </div>
      )}

      {vista === 'gruppo' && vistaGruppo
        ? (vistaGruppo === 'pm' ? <VistaPM /> : <VistaManagement />)
        : children}
    </div>
  )
}
