import React from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Home from './pages/Home'
import Gantt from './pages/Gantt'
import Risorse from './pages/Risorse'
import Consuntivazione from './pages/Consuntivazione'
import AnalisiInterventi from './pages/AnalisiInterventi'
import Pipeline from './pages/Pipeline'
import Economia from './pages/Economia'
import AttivitaInterne from './pages/AttivitaInterne'

const navItems = [
  { to: '/', label: 'Home', icon: '📊', end: true },
  { to: '/gantt', label: 'GANTT', icon: '📅' },
  { to: '/analisi', label: 'Tavolo di Lavoro', icon: '🔬' },
  { to: '/risorse', label: 'Risorse', icon: '👥' },
  { to: '/consuntivazione', label: 'Consuntivazione', icon: '⏱️' },
  { to: '/pipeline', label: 'Pipeline', icon: '📋' },
  { to: '/economia', label: 'Economia', icon: '💰' },
  { to: '/attivita-interne', label: 'Attività Interne', icon: '🏢' },
]

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen" style={{ backgroundColor: 'var(--color-surface-950)', color: '#e2e8f0' }}>
        {/* Sidebar */}
        <aside className="w-64 flex flex-col flex-shrink-0 border-r"
          style={{ backgroundColor: 'var(--color-surface-900)', borderColor: 'var(--color-border-subtle)' }}>
          
          {/* Brand */}
          <div className="p-5 pb-4">
            <div className="flex items-center gap-3">
              <img src="/logo.png" alt="IMC-Group" className="h-10 w-auto" />
            </div>
            <p className="text-[10px] font-medium tracking-wider uppercase mt-2 ml-1" style={{ color: '#60a5fa' }}>
              GANTT Agent
            </p>
          </div>

          {/* Divider */}
          <div className="mx-4 mb-2" style={{ height: 1, backgroundColor: 'var(--color-border-subtle)' }} />

          {/* Navigation */}
          <nav className="flex-1 px-3 py-1">
            {navItems.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg mb-0.5 text-sm transition-all ${
                    isActive
                      ? 'nav-active font-semibold'
                      : 'text-gray-400 hover:text-gray-200 hover:bg-white/[0.03]'
                  }`
                }
              >
                <span className="text-base w-5 text-center">{item.icon}</span>
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>

          {/* Footer */}
          <div className="p-4 mx-3 mb-3 rounded-lg" style={{ backgroundColor: 'var(--color-surface-800)' }}>
            <p className="text-[10px] uppercase tracking-wider font-medium" style={{ color: '#60a5fa' }}>
              Prototipo v0.6
            </p>
            <p className="text-[10px] text-gray-500 mt-0.5">Build 1 aprile 2026</p>
          </div>
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
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
