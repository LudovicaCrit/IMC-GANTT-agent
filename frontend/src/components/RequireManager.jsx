// ─────────────────────────────────────────────────────────────────────────
//  RequireManager.jsx — Wrapper che richiede ruolo manager
//
//  Avvolge le pagine manager-only (GANTT, Pipeline, Economia, ecc.).
//
//  Comportamento:
//    • loading       → spinner full-screen
//    • non loggata   → redirect /login (come RequireAuth)
//    • loggata user  → pagina 403 (Forbidden)
//    • loggata mgr   → mostra contenuto
//
//  Difesa in profondità: anche se la sidebar a Step 5 nasconderà queste voci,
//  un user che digita /economia nell'URL viene bloccato qui.
// ─────────────────────────────────────────────────────────────────────────

import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import FullScreenLoader from './FullScreenLoader';
import Forbidden from '../pages/Forbidden';

export default function RequireManager({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <FullScreenLoader />;
  }

  if (!user) {
    const target = location.pathname + location.search;
    if (target !== '/login') {
      sessionStorage.setItem('postLoginRedirect', target);
    }
    return <Navigate to="/login" replace />;
  }

  if (user.ruolo_app !== 'manager') {
    return <Forbidden />;
  }

  return children;
}