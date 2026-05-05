// ─────────────────────────────────────────────────────────────────────────
//  AuthContext.jsx — Context React per stato autenticazione
//
//  Espone:
//    • <AuthProvider>     — avvolge l'app, deve stare in main.jsx
//    • useAuth()          — hook per leggere/usare l'auth da qualsiasi pagina
//
//  Stato esposto:
//    • user        : oggetto utente loggato, o null se non loggato
//    • loading     : true durante il bootstrap (chiamata iniziale a /me),
//                    false quando sappiamo se l'utente è loggato o no
//    • login()     : (email, password) => Promise<{success, error?}>
//    • logout()    : () => Promise<void>, redirect automatico a /login
//
//  Convenzione: dopo il bootstrap, `loading` resta sempre false. Login/logout
//  aggiornano solo `user`, non riportano `loading` a true (sarebbe confuso
//  per la UI). Login.jsx gestirà il proprio loading locale.
// ─────────────────────────────────────────────────────────────────────────

import { createContext, useContext, useEffect, useState } from 'react';
import {
  login as apiLogin,
  logout as apiLogout,
  getCurrentUser,
} from '../api';

// Context vuoto (sarà popolato dal Provider)
const AuthContext = createContext(null);

/**
 * Hook per consumare AuthContext. Da usare in qualsiasi componente
 * che ha bisogno di sapere chi è loggato o di fare login/logout.
 *
 * Esempio d'uso:
 *   const { user, login, logout, loading } = useAuth();
 */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error('useAuth() deve essere usato dentro <AuthProvider>');
  }
  return ctx;
}

/**
 * Provider che avvolge l'app. Al mount fa una chiamata GET /api/auth/me
 * per scoprire se c'è una sessione attiva (cookie ancora valido).
 *
 * Va messo in main.jsx attorno a <App />.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Bootstrap: al primo mount, chiediamo al backend chi siamo.
  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const me = await getCurrentUser();
        if (!cancelled) setUser(me);
      } catch (err) {
        // 401 atteso se non loggati, lo ignoriamo
        // Altri errori (es. backend giù) li loggiamo ma non blocchiamo
        if (!cancelled && err.message !== 'Non autenticato') {
          console.warn('Bootstrap auth fallito:', err.message);
        }
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    bootstrap();

    // Cleanup: se il componente smonta prima che la chiamata torni,
    // non aggiorniamo stato su un componente smontato (warning React)
    return () => {
      cancelled = true;
    };
  }, []);

  // ── Azioni esposte ─────────────────────────────────────────────────

  /**
   * Tenta il login. Restituisce { success: true, user } o { success: false, error }.
   * Login.jsx userà il return per decidere se mostrare un errore o redirigere.
   */
  async function login(email, password) {
    try {
      const result = await apiLogin(email, password);
      // Il backend risponde con i dati dell'utente loggato
      setUser(result);
      return { success: true, user: result };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }

  /**
   * Effettua il logout: chiama il backend per rimuovere il cookie,
   * pulisce lo stato locale, redirige a /login.
   */
  async function logout() {
    try {
      await apiLogout();
    } catch (err) {
      // Anche se il backend fallisce, sloggiamo localmente
      console.warn('Logout backend fallito (sloggo comunque):', err.message);
    }
    setUser(null);
    window.location.href = '/login';
  }

  // ── Valore esposto al Context ──────────────────────────────────────
  const value = {
    user,
    loading,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
