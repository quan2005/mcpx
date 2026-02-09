import { useEffect, useState } from "react"
import type { HealthStatus } from "../api/client"
import { api } from "../api/client"

export default function Health() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [checking, setChecking] = useState<string | null>(null)

  const loadHealth = async () => {
    const data = await api.getHealth()
    setHealth(data)
  }

  useEffect(() => {
    loadHealth()
    const interval = setInterval(loadHealth, 10000)
    return () => clearInterval(interval)
  }, [])

  const handleCheck = async (server: string) => {
    setChecking(server)
    try {
      await api.checkServerHealth(server)
      await loadHealth()
    } finally {
      setChecking(null)
    }
  }

  if (!health) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">Health</h2>
        <p className="text-slate-400">Monitor server health status</p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card">
          <div className="text-sm text-slate-400">Total</div>
          <div className="text-2xl font-bold text-white">{health.summary.total}</div>
        </div>
        <div className="card">
          <div className="text-sm text-slate-400">Healthy</div>
          <div className="text-2xl font-bold text-green-400">{health.summary.healthy}</div>
        </div>
        <div className="card">
          <div className="text-sm text-slate-400">Unhealthy</div>
          <div className="text-2xl font-bold text-red-400">{health.summary.unhealthy}</div>
        </div>
        <div className="card">
          <div className="text-sm text-slate-400">Unknown</div>
          <div className="text-2xl font-bold text-slate-400">{health.summary.unknown}</div>
        </div>
      </div>

      {/* Server Health Details */}
      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4">Server Health</h3>
        {Object.keys(health.servers).length === 0 ? (
          <p className="text-slate-500">No servers configured</p>
        ) : (
          <div className="space-y-3">
            {Object.entries(health.servers).map(([name, server]) => (
              <div
                key={name}
                className="flex items-center justify-between p-4 bg-slate-900 rounded-lg"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        server.status === "healthy"
                          ? "bg-green-500"
                          : server.status === "unhealthy"
                          ? "bg-red-500"
                          : "bg-slate-500"
                      }`}
                    />
                    <span className="font-medium text-white">{name}</span>
                    <span
                      className={`px-2 py-0.5 rounded text-xs ${
                        server.status === "healthy"
                          ? "bg-green-900 text-green-400"
                          : server.status === "unhealthy"
                          ? "bg-red-900 text-red-400"
                          : "bg-slate-700 text-slate-400"
                      }`}
                    >
                      {server.status}
                    </span>
                  </div>

                  <div className="mt-2 text-sm text-slate-500 space-y-1">
                    {server.last_check && (
                      <p>Last check: {new Date(server.last_check).toLocaleString()}</p>
                    )}
                    {server.last_success && (
                      <p>Last success: {new Date(server.last_success).toLocaleString()}</p>
                    )}
                    {server.consecutive_failures > 0 && (
                      <p className="text-red-400">
                        Consecutive failures: {server.consecutive_failures}
                      </p>
                    )}
                    {server.last_error && (
                      <p className="text-red-400">Error: {server.last_error}</p>
                    )}
                  </div>
                </div>

                <button
                  onClick={() => handleCheck(name)}
                  disabled={checking === name}
                  className="btn btn-secondary"
                >
                  {checking === name ? "Checking..." : "Check Now"}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
