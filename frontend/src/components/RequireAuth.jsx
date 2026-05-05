// ─────────────────────────────────────────────────────────────────────────
//  RequireAuth.jsx — Wrapper che richiede solo autenticazione
//
//  Avvolge le pagine accessibili a TUTTI gli utenti loggati (user + manager).
//  Se l'utente non è loggato, redirect a /login (preservando l'URL
//  cercato, così dopo il login lo si rispedisce lì).
//
//  Durante il bootstrap di AuthContext (loading=true), mostra uno spinner
//  full-screen invece di lampeggiare contenuto-poi-redirect.
// ─────────────────────────────────────────────────────────────────────────

import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import FullScreenLoader from './FullScreenLoader';

export default function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  // Mentre verifichiamo se c'è una sessione, mostra spinner
  if (loading) {
    return <FullScreenLoader />;
  }

  // Non loggato: salva URL corrente per redirect post-login + manda a /login
  if (!user) {
    const target = location.pathname + location.search;
    if (target !== '/login') {
      sessionStorage.setItem('postLoginRedirect', target);
    }
    return <Navigate to="/login" replace />;
  }

  // Loggato: mostra il contenuto
  return children;
}