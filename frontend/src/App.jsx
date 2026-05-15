import React, { useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import Home from './pages/Home'
import Gantt from './pages/Gantt'
import Risorse from './pages/Risorse'
import Consuntivazione from './pages/Consuntivazione'
import AnalisiInterventi from './pages/AnalisiInterventi'
import Pipeline from './pages/Pipeline'
import Economia from './pages/Economia'
import AttivitaInterne from './pages/AttivitaInterne'
import Configurazione from './pages/Configurazione'
import CantiereDettaglio from './pages/CantiereDettaglio'
import Login from './pages/Login'
import Forbidden from './pages/Forbidden'
import NotFound from './pages/NotFound'
import RequireAuth from './components/RequireAuth'
import RequireManager from './components/RequireManager'
import { useAuth } from './contexts/AuthContext'

// requiresManager: true = voce visibile solo ai manager (Scenario B)
// 📌 TODO Tappa A: aggiungere voci user "I miei task" + "Profilo"
// 📌 TODO Tappa A: valutare layout topbar alternativo per Helena
//                  (sul pattern del sito imc-group.eu)
const navItems = [
  { to: '/', label: 'Home', icon: '📊', end: true, requiresManager: false },
  { to: '/gantt', label: 'GANTT', icon: '📅', requiresManager: true },
  { to: '/analisi', label: 'Tavolo di Lavoro', icon: '🔬', requiresManager: true },
  { to: '/risorse', label: 'Risorse', icon: '👥', requiresManager: true },
  { to: '/consuntivazione', label: 'Consuntivazione', icon: '⏱️', requiresManager: false },
  { to: '/pipeline', label: 'Pipeline', icon: '📋', requiresManager: true },
  { to: '/economia', label: 'Economia', icon: '💰', requiresManager: true },
  { to: '/attivita-interne', label: 'Attività Interne', icon: '🏢', requiresManager: true },
  { to: '/configurazione', label: 'Configurazione', icon: '⚙️', requiresManager: true },
]

/**
 * Layout principale dell'app autenticata: sidebar + main.
 * Sidebar filtrata per ruolo, footer utente con Logout.
 */
function MainLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const { user, logout } = useAuth()

  // Sidebar filtrata: user vede solo voci non-manager, manager vede tutto
  const isManager = user?.ruolo_app === 'manager'
  const visibleNavItems = navItems.filter(item => isManager || !item.requiresManager)

  return (
    <div className="flex h-screen" style={{ backgroundColor: 'var(--color-surface-950)', color: '#e2e8f0' }}>
      {/* Sidebar */}
      <aside className={`flex flex-col flex-shrink-0 border-r transition-all duration-300 ${collapsed ? 'w-16' : 'w-64'}`}
        style={{ backgroundColor: 'var(--color-surface-900)', borderColor: 'var(--color-border-subtle)' }}>
        
        {/* Brand */}
        <div className={`p-5 pb-4 ${collapsed ? 'px-2 py-4 flex justify-center' : ''}`}>
          {collapsed ? (
            <img src="/logo.png" alt="IMC" className="h-8 w-auto" />
          ) : (
            <>
              <div className="flex items-center gap-3">
                <img src="/logo.png" alt="IMC-Group" className="h-10 w-auto" />
              </div>
              <p className="text-[10px] font-medium tracking-wider uppercase mt-2 ml-1" style={{ color: '#60a5fa' }}>
                GANTT Agent
              </p>
            </>
          )}
        </div>

        {/* Divider */}
        <div className="mx-2 mb-2" style={{ height: 1, backgroundColor: 'var(--color-border-subtle)' }} />

        {/* Navigation */}
        <nav className="flex-1 px-2 py-1">
          {visibleNavItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              title={collapsed ? item.label : ''}
              className={({ isActive }) =>
                `flex items-center ${collapsed ? 'justify-center' : ''} gap-3 px-3 py-2.5 rounded-lg mb-0.5 text-sm transition-all ${
                  isActive
                    ? 'nav-active font-semibold'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-white/[0.03]'
                }`
              }
            >
              <span className="text-base w-5 text-center">{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Collapse toggle */}
        <button onClick={() => setCollapsed(!collapsed)}
          className="mx-2 mb-2 px-3 py-2 rounded-lg text-xs text-gray-500 hover:text-gray-300 hover:bg-white/[0.03] transition-colors flex items-center justify-center gap-2">
          <span>{collapsed ? '→' : '←'}</span>
          {!collapsed && <span>Comprimi</span>}
        </button>

        {/* Footer utente loggato */}
        {!collapsed ? (
          <div className="mx-3 mb-3 rounded-lg overflow-hidden" style={{ backgroundColor: 'var(--color-surface-800)' }}>
            {/* Info utente */}
            <div className="p-3 pb-2">
              <div className="flex items-center gap-2">
                <span
                  className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{ backgroundColor: '#22c55e' }}
                  aria-label="Online"
                />
                <p className="text-xs font-medium truncate" style={{ color: '#e2e8f0' }} title={user?.email}>
                  {user?.nome || user?.email}
                </p>
              </div>
              <p className="text-[10px] uppercase tracking-wider text-gray-500 mt-1 ml-3.5">
                {user?.ruolo_app === 'manager' ? 'Manager' : 'User'}
              </p>
            </div>

            {/* Divider */}
            <div className="mx-3" style={{ height: 1, backgroundColor: 'var(--color-border-subtle)' }} />

            {/* Logout */}
            <button
              onClick={logout}
              className="w-full px-3 py-2 text-xs text-gray-400 hover:text-gray-200 hover:bg-white/[0.03] transition-colors flex items-center gap-2 text-left"
            >
              <span className="text-sm">↪</span>
              <span>Logout</span>
            </button>
          </div>
        ) : (
          // Versione compatta quando collapsed: solo bottone logout con icona
          <button
            onClick={logout}
            title={`Logout (${user?.nome || user?.email})`}
            className="mx-2 mb-3 p-2 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-white/[0.03] transition-colors flex items-center justify-center"
          >
            <span className="text-base">↪</span>
          </button>
        )}
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto p-8"
        style={{ backgroundColor: 'var(--color-surface-950)' }}>
        <Routes>
          {/* Pagine accessibili a TUTTI gli utenti loggati (user + manager) */}
          <Route path="/" element={<Home />} />
          <Route path="/consuntivazione" element={<Consuntivazione />} />

          {/* Pagine manager-only — wrapped in <RequireManager> */}
          <Route path="/gantt" element={
            <RequireManager><Gantt /></RequireManager>
          } />
          <Route path="/analisi" element={
            <RequireManager><AnalisiInterventi /></RequireManager>
          } />
          <Route path="/risorse" element={
            <RequireManager><Risorse /></RequireManager>
          } />
          <Route path="/pipeline" element={
            <RequireManager><Pipeline /></RequireManager>
          } />
          <Route path="/economia" element={
            <RequireManager><Economia /></RequireManager>
          } />
          <Route path="/attivita-interne" element={
            <RequireManager><AttivitaInterne /></RequireManager>
          } />
          <Route path="/configurazione" element={
            <RequireManager><Configurazione /></RequireManager>
          } />
          <Route path="/cantiere/:progettoId" element={
            <RequireManager><CantiereDettaglio /></RequireManager>
          } />

          {/* Fallback per URL ignoti */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </div>
  )
}

/**
 * Router root: distingue /login (no sidebar, no auth required)
 * dal resto (con sidebar, auth required).
 */
function AppRoutes() {
  const location = useLocation()
  const isLoginPage = location.pathname === '/login'

  if (isLoginPage) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
      </Routes>
    )
  }

  return (
    <RequireAuth>
      <MainLayout />
    </RequireAuth>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
