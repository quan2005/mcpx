import { useEffect, useState } from "react"
import { Link, Route, BrowserRouter as Router, Routes, useLocation } from "react-router-dom"
import type { Server } from "./api/client"
import { api } from "./api/client"
import { ToastProvider } from "./contexts/ToastContext"
import Dashboard from "./pages/Dashboard"
import Health from "./pages/Health"
import Resources from "./pages/Resources"
import Servers from "./pages/Servers"
import Settings from "./pages/Settings"
import Tools from "./pages/Tools"

function Sidebar() {
  const location = useLocation()
  const [servers, setServers] = useState<Server[]>([])

  useEffect(() => {
    api.listServers().then((data) => setServers(data.servers))
  }, [])

  const connectedCount = servers.filter((s) => s.connected).length

  const navItems = [
    { path: "/", label: "Dashboard", icon: "📊" },
    { path: "/servers", label: "Servers", icon: "🖥️", badge: `${connectedCount}/${servers.length}` },
    { path: "/tools", label: "Tools", icon: "🔧" },
    { path: "/resources", label: "Resources", icon: "📁" },
    { path: "/health", label: "Health", icon: "❤️" },
    { path: "/settings", label: "Settings", icon: "⚙️" },
  ]

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-700 flex flex-col">
      <div className="p-4 border-b border-slate-700">
        <h1 className="text-xl font-bold text-blue-400">MCPX Dashboard</h1>
        <p className="text-xs text-slate-400 mt-1">MCP Proxy Server</p>
      </div>

      <nav className="flex-1 p-4">
        <ul className="space-y-1">
          {navItems.map((item) => (
            <li key={item.path}>
              <Link
                to={item.path}
                className={`flex items-center justify-between px-3 py-2 rounded-lg transition-colors ${
                  location.pathname === item.path
                    ? "bg-blue-600 text-white"
                    : "text-slate-300 hover:bg-slate-800"
                }`}
              >
                <span className="flex items-center gap-3">
                  <span>{item.icon}</span>
                  <span>{item.label}</span>
                </span>
                {item.badge && (
                  <span className="text-xs bg-slate-700 px-2 py-0.5 rounded-full">
                    {item.badge}
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      <div className="p-4 border-t border-slate-700">
        <div className="text-xs text-slate-500">
          <p>v0.6.0</p>
          <a
            href="https://github.com/quan2005/mcpx"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-400 hover:underline"
          >
            GitHub
          </a>
        </div>
      </div>
    </aside>
  )
}

function App() {
  return (
    <Router>
      <ToastProvider>
        <div className="flex min-h-screen bg-slate-950">
          <Sidebar />
          <main className="flex-1 p-6 overflow-auto">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/servers" element={<Servers />} />
              <Route path="/tools" element={<Tools />} />
              <Route path="/resources" element={<Resources />} />
              <Route path="/health" element={<Health />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </main>
        </div>
      </ToastProvider>
    </Router>
  )
}

export default App
