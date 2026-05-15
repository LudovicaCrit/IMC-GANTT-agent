// ─────────────────────────────────────────────────────────────────────────
//  NotFound.jsx — Pagina 404 mostrata quando l'URL non corrisponde a
//  nessuna route esistente.
//
//  Distinzione semantica da Forbidden (403): 404 = "questa pagina non
//  esiste"; 403 = "questa pagina esiste ma non hai i permessi".
//
//  Renderizzata dal catch-all `<Route path="*" />` in App.jsx.
// ─────────────────────────────────────────────────────────────────────────

import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="flex items-center justify-center" style={{ minHeight: '60vh' }}>
      <div
        className="max-w-md p-8 rounded-2xl text-center"
        style={{
          backgroundColor: 'var(--color-surface-900)',
          border: '1px solid var(--color-border-subtle)',
        }}
      >
        <div
          className="text-5xl mb-4"
          style={{ color: '#60a5fa', fontFamily: 'JetBrains Mono, ui-monospace, monospace' }}
        >
          404
        </div>
        <h1 className="text-lg font-semibold mb-2" style={{ color: '#e2e8f0' }}>
          Pagina non trovata
        </h1>
        <p className="text-sm text-gray-400 mb-6">
          La pagina che stai cercando non esiste o è stata spostata.
          Controlla l'URL o torna alla Home.
        </p>
        <Link
          to="/"
          className="inline-block px-4 py-2 text-sm font-semibold rounded-lg transition-colors"
          style={{
            backgroundColor: '#2563eb',
            color: '#ffffff',
          }}
        >
          ← Torna alla Home
        </Link>
      </div>
    </div>
  );
}
