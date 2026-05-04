import React, { useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Home from './pages/Home'
import Gantt from './pages/Gantt'
import Risorse from './pages/Risorse'
import Consuntivazione from './pages/Consuntivazione'
import AnalisiInterventi from './pages/AnalisiInterventi'
import Pipeline from './pages/Pipeline'
import Economia from './pages/Economia'
import AttivitaInterne from './pages/AttivitaInterne'
import Configurazione from './pages/Configurazione'

const navItems = [
  { to: '/', label: 'Home', icon: '📊', end: true },
  { to: '/gantt', label: 'GANTT', icon: '📅' },
  { to: '/analisi', label: 'Tavolo di Lavoro', icon: '🔬' },
  { to: '/risorse', label: 'Risorse', icon: '👥' },
  { to: '/consuntivazione', label: 'Consuntivazione', icon: '⏱️' },
  { to: '/pipeline', label: 'Pipeline', icon: '📋' },
  { to: '/economia', label: 'Economia', icon: '💰' },
  { to: '/attivita-interne', label: 'Attività Interne', icon: '🏢' },
  { to: '/configurazione', label: 'Configurazione', icon: '⚙️'},
]

export default function App() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <BrowserRouter>
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
            {navItems.map(item => (
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

          {/* Footer */}
          {!collapsed && (
            <div className="p-4 mx-3 mb-3 rounded-lg" style={{ backgroundColor: 'var(--color-surface-800)' }}>
              <p className="text-[10px] uppercase tracking-wider font-medium" style={{ color: '#60a5fa' }}>
                Prototipo v0.7
              </p>
              <p className="text-[10px] text-gray-500 mt-0.5">Build {new Date().toLocaleDateString('it-IT')}</p>
            </div>
          )}
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto p-8"
          style={{ backgroundColor: 'var(--color-surface-950)' }}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/gantt" element={<Gantt />} />
            <Route path="/analisi" element={<AnalisiInterventi />} />
            <Route path="/risorse" element={<Risorse />} />
            <Route path="/consuntivazione" element={<Consuntivazione />} />
            <Route path="/pipeline" element={<Pipeline />} />
            <Route path="/economia" element={<Economia />} />
            <Route path="/attivita-interne" element={<AttivitaInterne />} />
            <Route path="/configurazione" element={<Configurazione />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}