// ─────────────────────────────────────────────────────────────────────────
//  Forbidden.jsx — Pagina 403 mostrata quando un user (non manager)
//  prova ad accedere a una pagina manager-only.
//
//  Renderizzata da <RequireManager> quando user.ruolo_app !== 'manager'.
// ─────────────────────────────────────────────────────────────────────────

import { Link } from 'react-router-dom';

export default function Forbidden() {
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
          403
        </div>
        <h1 className="text-lg font-semibold mb-2" style={{ color: '#e2e8f0' }}>
          Accesso non autorizzato
        </h1>
        <p className="text-sm text-gray-400 mb-6">
          Non hai i permessi per visualizzare questa pagina.
          Se ritieni sia un errore, contatta un manager.
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
