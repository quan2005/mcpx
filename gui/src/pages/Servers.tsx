import { useEffect, useState } from "react"
import type { Server } from "../api/client"
import { api } from "../api/client"

export default function Servers() {
  const [servers, setServers] = useState<Server[]>([])
  const [loading, setLoading] = useState<string | null>(null)

  const loadServers = async () => {
    const data = await api.listServers()
    setServers(data.servers)
  }

  useEffect(() => {
    loadServers()
    const interval = setInterval(loadServers, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleToggle = async (name: string) => {
    setLoading(name)
    try {
      await api.toggleServer(name)
      await loadServers()
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">Servers</h2>
        <p className="text-slate-400">Manage your MCP servers</p>
      </div>

      <div className="space-y-4">
        {servers.length === 0 ? (
          <div className="card text-center py-12">
            <p className="text-slate-500">No servers configured</p>
            <p className="text-sm text-slate-600 mt-2">
              Add servers in Settings or edit your config.json
            </p>
          </div>
        ) : (
          servers.map((server) => (
            <div key={server.name} className="card">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h3 className="text-lg font-semibold text-white">{server.name}</h3>
                    <span
                      className={`px-2 py-0.5 rounded text-xs ${
                        server.connected
                          ? "bg-green-900 text-green-400"
                          : server.enabled
                          ? "bg-red-900 text-red-400"
                          : "bg-slate-700 text-slate-400"
                      }`}
                    >
                      {server.connected ? "Connected" : server.enabled ? "Disconnected" : "Disabled"}
                    </span>
                  </div>

                  <div className="mt-2 text-sm text-slate-400 space-y-1">
                    <p>Type: {server.type}</p>
                    {server.server_name && <p>Server: {server.server_name}</p>}
                    {server.version && <p>Version: {server.version}</p>}
                    {server.health && (
                      <p>
                        Health: {" "}
                        <span
                          className={
                            server.health.status === "healthy"
                              ? "text-green-400"
                              : server.health.status === "unhealthy"
                              ? "text-red-400"
                              : "text-slate-400"
                          }
                        >
                          {server.health.status}
                        </span>
                      </p>
                    )}
                  </div>

                  <div className="mt-3 flex gap-4 text-sm">
                    <span className="text-slate-500">
                      <span className="text-white">{server.tools_count || 0}</span> tools
                    </span>
                    <span className="text-slate-500">
                      <span className="text-white">{server.resources_count || 0}</span> resources
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <span className="text-sm text-slate-400">
                      {server.enabled ? "Enabled" : "Disabled"}
                    </span>
                    <input
                      type="checkbox"
                      className="toggle"
                      checked={server.enabled}
                      onChange={() => handleToggle(server.name)}
                      disabled={loading === server.name}
                    />
                  </label>
                </div>
              </div>

              {server.instructions && (
                <div className="mt-4 pt-4 border-t border-slate-700">
                  <p className="text-sm text-slate-400">{server.instructions}</p>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
