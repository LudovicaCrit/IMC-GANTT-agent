/**
 * ═════════════════════════════════════════════════════════════════════════
 * Form.jsx — Componenti form riusabili (Step 2.3-bis 4a, 18 mag 2026)
 * ═════════════════════════════════════════════════════════════════════════
 *
 * Componenti di input condivisi da CantiereDettaglio, futuro Wizard di
 * Step 2.7, futuro Archivio di Step 2.6, e altri che li necessitassero.
 *
 * Esporta:
 *   - FormRow:        riga read-only con label + valore
 *   - FormInput:      input testuale/numerico/data
 *   - FormInputDate:  input data con vincoli min/max (Step 2.4-bis §14.2)
 *   - FormSelect:     select con opzioni stringa o {value,label}
 *
 * Convenzioni:
 *   - Tutti gli input mostrano '* ' rosso quando required={true}
 *   - L'estetica è dark-themed (bg-gray-800 border-gray-700)
 *   - Sono "controlled components": value + onChange obbligatori in input
 */

import React from 'react'

/** Riga read-only label + valore. */
export function FormRow({ label, children }) {
  return (
    <div>
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</div>
      <div className="text-gray-200">{children}</div>
    </div>
  )
}

/** Input controllato (text/number/date/email/...). */
export function FormInput({ label, value, onChange, type = 'text', required = false, placeholder = '' }) {
  return (
    <div>
      <label className="text-xs text-gray-500 uppercase tracking-wide block mb-1">
        {label}{required && <span className="text-red-400 ml-1">*</span>}
      </label>
      <input
        type={type}
        value={value ?? ''}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm focus:border-blue-500 outline-none"
      />
    </div>
  )
}

/**
 * Input date con vincoli min/max e tooltip esplicativo.
 * Visualizza bordo rosso e msg quando value è fuori dal range consentito
 * (utile per task vs fase, Step 2.4-bis §14.2).
 */
export function FormInputDate({ label, value, onChange, required = false, minDate = null, maxDate = null, hint = '' }) {
  const fuoriRange = value && ((minDate && value < minDate) || (maxDate && value > maxDate))
  return (
    <div>
      <label className="text-xs text-gray-500 uppercase tracking-wide block mb-1">
        {label}{required && <span className="text-red-400 ml-1">*</span>}
      </label>
      <input
        type="date"
        value={value ?? ''}
        onChange={e => onChange(e.target.value)}
        min={minDate || undefined}
        max={maxDate || undefined}
        className={`w-full border rounded px-3 py-2 text-sm focus:outline-none ${
          fuoriRange
            ? 'bg-red-950 border-red-700 focus:border-red-500'
            : 'bg-gray-800 border-gray-700 focus:border-blue-500'
        }`}
      />
      {hint && <div className="text-xs text-gray-500 mt-1">{hint}</div>}
      {fuoriRange && (
        <div className="text-xs text-red-400 mt-1">⚠ Data fuori dal range consentito</div>
      )}
    </div>
  )
}

/**
 * Select controllata. Le opzioni possono essere:
 *   - stringhe semplici → option value=label=stringa
 *   - oggetti {value, label} → option value=oggetto.value, testo=oggetto.label
 */
export function FormSelect({ label, value, onChange, options, required = false }) {
  return (
    <div>
      <label className="text-xs text-gray-500 uppercase tracking-wide block mb-1">
        {label}{required && <span className="text-red-400 ml-1">*</span>}
      </label>
      <select
        value={value ?? ''}
        onChange={e => onChange(e.target.value)}
        className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm focus:border-blue-500 outline-none"
      >
        {options.map(o => typeof o === 'string'
          ? <option key={o} value={o}>{o}</option>
          : <option key={o.value} value={o.value}>{o.label}</option>
        )}
      </select>
    </div>
  )
}
