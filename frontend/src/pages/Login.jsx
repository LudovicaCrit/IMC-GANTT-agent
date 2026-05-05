// ─────────────────────────────────────────────────────────────────────────
//  Login.jsx — Pagina di login
//
//  Form email + password. Su successo:
//    1. Aggiorna l'utente in AuthContext (gestito da useAuth().login)
//    2. Recupera eventuale URL salvato pre-redirect (postLoginRedirect)
//    3. Naviga lì, o a "/" se non c'è redirect salvato
//
//  Gestione errori:
//    • 401 → "Credenziali non valide"
//    • 429 → "Troppi tentativi, riprova tra un minuto"
//    • Errore di rete → "Errore di rete: ..."
//    • Altri → messaggio generico dal backend
// ─────────────────────────────────────────────────────────────────────────

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function Login() {
  const { login, user, loading } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // Se utente già loggato e atterra su /login, redirect a Home
  useEffect(() => {
    if (!loading && user) {
      navigate('/', { replace: true });
    }
  }, [loading, user, navigate]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting) return;

    setError(null);
    setSubmitting(true);

    const result = await login(email.trim(), password);

    if (result.success) {
      // Recupera redirect salvato da apiFetch su 401, altrimenti Home
      const redirect = sessionStorage.getItem('postLoginRedirect') || '/';
      sessionStorage.removeItem('postLoginRedirect');
      navigate(redirect, { replace: true });
    } else {
      setError(result.error || 'Errore durante il login');
      setSubmitting(false);
    }
  }

  // Durante il bootstrap (loading=true) non mostriamo niente per evitare
  // il flash della pagina di login se l'utente è già loggato
  if (loading) {
    return (
      <div
        className="flex h-screen items-center justify-center"
        style={{ backgroundColor: 'var(--color-surface-950)' }}
      >
        <div className="text-gray-400 text-sm">Caricamento…</div>
      </div>
    );
  }

  return (
    <div
      className="flex h-screen items-center justify-center"
      style={{ backgroundColor: 'var(--color-surface-950)', color: '#e2e8f0' }}
    >
      <div
        className="w-full max-w-sm p-8 rounded-2xl shadow-xl"
        style={{
          backgroundColor: 'var(--color-surface-900)',
          border: '1px solid var(--color-border-subtle)',
        }}
      >
        {/* Brand */}
        <div className="flex flex-col items-center mb-6">
          <img src="/logo.png" alt="IMC-Group" className="h-12 w-auto mb-3" />
          <p
            className="text-[10px] font-medium tracking-wider uppercase"
            style={{ color: '#60a5fa' }}
          >
            GANTT Agent
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label
              htmlFor="email"
              className="block text-xs uppercase tracking-wider text-gray-400 mb-1.5"
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={submitting}
              className="w-full px-3 py-2 text-sm rounded-lg outline-none transition-colors"
              style={{
                backgroundColor: 'var(--color-surface-800)',
                border: '1px solid var(--color-border-subtle)',
                color: '#e2e8f0',
              }}
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-xs uppercase tracking-wider text-gray-400 mb-1.5"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={submitting}
              className="w-full px-3 py-2 text-sm rounded-lg outline-none transition-colors"
              style={{
                backgroundColor: 'var(--color-surface-800)',
                border: '1px solid var(--color-border-subtle)',
                color: '#e2e8f0',
              }}
            />
          </div>

          {error && (
            <div
              role="alert"
              className="px-3 py-2 text-sm rounded-lg"
              style={{
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#fca5a5',
              }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || !email || !password}
            className="w-full px-4 py-2.5 text-sm font-semibold rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              backgroundColor: '#2563eb',
              color: '#ffffff',
            }}
          >
            {submitting ? 'Accesso in corso…' : 'Accedi'}
          </button>
        </form>

        {/* Footer */}
        <p className="text-[10px] text-center text-gray-500 mt-6">
          IMC-Group · Prototipo R1
        </p>
      </div>
    </div>
  );
}
