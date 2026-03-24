import React from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Home from './pages/Home'
import Gantt from './pages/Gantt'
import Risorse from './pages/Risorse'
import Consuntivazione from './pages/Consuntivazione'
import AnalisiInterventi from './pages/AnalisiInterventi'
import Pipeline from './pages/Pipeline'
import Economia from './pages/Economia'

const navItems = [
  { to: '/', label: '📊 Home', end: true },
  { to: '/gantt', label: '📅 GANTT' },
  { to: '/analisi', label: '🔬 Analisi e Interventi' },
  { to: '/risorse', label: '👥 Risorse' },
  { to: '/consuntivazione', label: '⏱️ Consuntivazione' },
  { to: '/pipeline', label: '📋 Pipeline' },
  { to: '/economia', label: '💰 Economia' },
]

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-gray-950 text-gray-100">
        {/* Sidebar */}
        <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col flex-shrink-0">
          <div className="p-6">
            <h1 className="text-xl font-bold">📊 IMC-Group</h1>
            <p className="text-sm text-gray-400 mt-1">GANTT Agent v0.3</p>
          </div>
          <nav className="flex-1 px-3">
            {navItems.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `block px-4 py-2.5 rounded-lg mb-1 text-sm transition-colors ${
                    isActive
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="p-4 text-xs text-gray-500">
            Prototipo dimostrativo
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto p-8">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/gantt" element={<Gantt />} />
            <Route path="/analisi" element={<AnalisiInterventi />} />
            <Route path="/risorse" element={<Risorse />} />
            <Route path="/consuntivazione" element={<Consuntivazione />} />
            <Route path="/pipeline" element={<Pipeline />} />
            <Route path="/economia" element={<Economia />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
